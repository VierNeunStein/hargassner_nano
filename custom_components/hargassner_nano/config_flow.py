"""Config flow of the Hargassner integration.

Setup: address -> the integration reads a telegram and looks for the layout that fits
-> the user compares a few decoded values with the boiler's display -> done.

If no built-in layout fits, the user pastes the <DAQPRJ> definition from a log file
the boiler writes to its SD card.
"""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .client import CannotConnect, HargassnerError, async_read_telegram
from .const import (
    CONF_CUSTOM_DAQPRJ,
    CONF_DIGITAL_WORDS,
    CONF_LAYOUT,
    CONF_PELLET_ENERGY,
    CONF_RAW_CHANNELS,
    CUSTOM_LAYOUT_TITLE,
    DEFAULT_NAME,
    DEFAULT_PELLET_ENERGY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LAYOUT_CUSTOM,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import HargassnerConfigEntry
from .layout import (
    Layout,
    LayoutError,
    builtin_layouts,
    extract_daqprj,
    matching_layouts,
    parse_custom_daqprj,
)
from .texts import preview_lines

_LOGGER = logging.getLogger(__name__)

# Appended to layouts whose number format does not match the received line.
DOUBTFUL_MARK = " (?)"
# Shown in the instructions for a custom definition. They are passed as placeholders
# because translation files must not contain anything that looks like HTML.
DAQPRJ_PLACEHOLDERS = {"tag_open": "<DAQPRJ>", "tag_close": "</DAQPRJ>", "file": "DAQ00000.DAQ"}

_PORT = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): _PORT,
    }
)
RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): _PORT,
    }
)
CUSTOM_SCHEMA = vol.Schema({vol.Required(CONF_CUSTOM_DAQPRJ): TextSelector(TextSelectorConfig(multiline=True))})
OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
        vol.Required(CONF_PELLET_ENERGY, default=DEFAULT_PELLET_ENERGY): vol.All(
            vol.Coerce(float), vol.Range(min=3.0, max=6.0)
        ),
        vol.Required(CONF_RAW_CHANNELS, default=False): bool,
    }
)


class HargassnerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up or reconfigure a boiler."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._name = DEFAULT_NAME
        self._host = ""
        self._port = DEFAULT_PORT
        # Values of the telegram read from the boiler
        self._values: tuple[str, ...] = ()
        # Built-in layouts with the right number of values, best first: (layout, fits)
        self._matches: list[tuple[Layout, bool]] = []
        self._layout: Layout | None = None
        self._custom_daqprj: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: HargassnerConfigEntry) -> HargassnerOptionsFlow:
        """Return the options flow."""
        return HargassnerOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the address of the boiler."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._name = user_input[CONF_NAME].strip() or DEFAULT_NAME
            self._host = user_input[CONF_HOST].strip()
            self._port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{self._host}:{self._port}")
            self._abort_if_unique_id_configured()
            if (error := await self._async_read()) is None:
                return await self._async_step_after_read()
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the address or, e.g. after a firmware update, the layout."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            self._port = user_input[CONF_PORT]
            unique_id = f"{self._host}:{self._port}"
            if any(
                other.unique_id == unique_id and other.entry_id != entry.entry_id
                for other in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")
            if (error := await self._async_read()) is None:
                return await self._async_step_after_read()
            errors["base"] = error

        suggested = user_input or {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(RECONFIGURE_SCHEMA, suggested),
            errors=errors,
        )

    async def _async_read(self) -> str | None:
        """Read a telegram from the boiler. Return an error key on failure."""
        try:
            self._values = await async_read_telegram(self._host, self._port)
        except CannotConnect as err:
            _LOGGER.debug("Cannot connect to %s:%s: %s", self._host, self._port, err)
            return "cannot_connect"
        except HargassnerError as err:
            _LOGGER.debug("No telegram from %s:%s: %s", self._host, self._port, err)
            return "no_telegram"
        return None

    async def _async_step_after_read(self) -> ConfigFlowResult:
        """Pick the layout that fits the telegram, or ask the user."""
        matches = await self.hass.async_add_executor_job(matching_layouts, self._values)
        self._matches = [(layout, not problems) for layout, problems in matches]
        fitting = [layout for layout, fits in self._matches if fits]
        _LOGGER.debug(
            "%s:%s sends %d values; layouts with that length: %s",
            self._host,
            self._port,
            len(self._values),
            [(layout.key, fits) for layout, fits in self._matches],
        )
        if len(fitting) == 1:
            self._layout = fitting[0]
            self._custom_daqprj = None
            return await self.async_step_confirm()
        if self._matches:
            return await self.async_step_layout()
        return await self.async_step_custom()

    async def async_step_layout(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user choose between the built-in layouts of the right length."""
        if user_input is not None:
            self._layout = builtin_layouts()[user_input[CONF_LAYOUT]]
            self._custom_daqprj = None
            return await self.async_step_confirm()

        choices = {layout.key: layout.title + ("" if fits else DOUBTFUL_MARK) for layout, fits in self._matches}
        return self.async_show_form(
            step_id="layout",
            data_schema=vol.Schema({vol.Required(CONF_LAYOUT, default=next(iter(choices))): vol.In(choices)}),
            description_placeholders={"count": str(len(self._values))},
        )

    async def async_step_custom(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Take the boiler's own description of its telegram (DAQPRJ)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # A pasted text can be a whole DAQ file; scan it outside the event loop.
            definition = await self.hass.async_add_executor_job(extract_daqprj, user_input[CONF_CUSTOM_DAQPRJ])
            try:
                layout = await self.hass.async_add_executor_job(
                    partial(parse_custom_daqprj, definition, self._values, title=CUSTOM_LAYOUT_TITLE)
                )
            except LayoutError as err:
                _LOGGER.debug("DAQPRJ definition rejected: %s", err)
                errors["base"] = "count_mismatch" if err.reason == "count_mismatch" else "invalid_daqprj"
            else:
                self._layout = layout
                self._custom_daqprj = definition
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="custom",
            data_schema=self.add_suggested_values_to_schema(CUSTOM_SCHEMA, user_input or {}),
            errors=errors,
            description_placeholders={"count": str(len(self._values)), **DAQPRJ_PLACEHOLDERS},
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show some decoded values so the user can compare them with the display."""
        assert self._layout is not None
        telegram = self._layout.decode(self._values)
        lines = preview_lines(self._layout, telegram, self.hass.config.language)
        menu_options = ["finish"]
        if self._matches:
            menu_options.append("layout")
        menu_options.append("custom")
        return self.async_show_menu(
            step_id="confirm",
            menu_options=menu_options,
            description_placeholders={
                "layout": self._layout.title,
                "count": str(len(self._values)),
                "preview": "\n".join(f"- {line}" for line in lines),
            },
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create or update the config entry."""
        assert self._layout is not None
        data: dict[str, Any] = {CONF_HOST: self._host, CONF_PORT: self._port, CONF_LAYOUT: self._layout.key}
        if self._custom_daqprj is not None:
            data[CONF_LAYOUT] = LAYOUT_CUSTOM
            data[CONF_CUSTOM_DAQPRJ] = self._custom_daqprj
            data[CONF_DIGITAL_WORDS] = self._layout.digital_words

        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            new_data = {
                key: value
                for key, value in entry.data.items()
                if key not in (CONF_CUSTOM_DAQPRJ, CONF_DIGITAL_WORDS)
            }
            new_data.update(data)
            changes: dict[str, Any] = {"unique_id": f"{self._host}:{self._port}", "data": new_data}
            # Entries of version 1.x carry the address in their name.
            old_host = entry.data[CONF_HOST]
            if old_host != self._host and old_host in entry.title:
                changes["title"] = entry.title.replace(old_host, self._host)
            return self.async_update_reload_and_abort(entry, **changes)
        return self.async_create_entry(title=self._name, data=data)


class HargassnerOptionsFlow(OptionsFlowWithReload):
    """Change the settings that do not concern the connection.

    Home Assistant reloads the entry when the options were changed.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        current = {
            # Entries created by version 1.x keep the interval in their data.
            CONF_SCAN_INTERVAL: entry.options.get(
                CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            CONF_PELLET_ENERGY: entry.options.get(CONF_PELLET_ENERGY, DEFAULT_PELLET_ENERGY),
            CONF_RAW_CHANNELS: entry.options.get(CONF_RAW_CHANNELS, False),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, current),
        )
