"""Hargassner boilers with touch control, read through their telnet port."""

from __future__ import annotations

from functools import partial
import logging

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .client import HargassnerError, async_read_telegram
from .const import (
    CONF_CUSTOM_DAQPRJ,
    CONF_DIGITAL_WORDS,
    CONF_LAYOUT,
    CONF_RAW_CHANNELS,
    CUSTOM_LAYOUT_TITLE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LAYOUT_AUTO,
    LAYOUT_CUSTOM,
)
from .coordinator import HargassnerConfigEntry, HargassnerCoordinator, layout_issue_id
from .layout import Layout, LayoutError, builtin_layouts, detect_layout, parse_daqprj
from .model import entity_keys

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HargassnerConfigEntry) -> bool:
    """Set up a boiler."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data.get(CONF_PORT, DEFAULT_PORT)
    layout = await _async_get_layout(hass, entry, host, port)
    # Entries created by version 1.x keep the interval in their data.
    scan_interval: int = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = HargassnerCoordinator(hass, entry, layout, host, port, scan_interval)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _async_remove_stale_entities(hass, entry, layout)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # No update listener: the options flow and the reconfigure flow reload the entry
    # themselves. Home Assistant does not allow both.
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HargassnerConfigEntry) -> bool:
    """Unload a boiler."""
    ir.async_delete_issue(hass, DOMAIN, layout_issue_id(entry.entry_id))
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_get_layout(hass: HomeAssistant, entry: HargassnerConfigEntry, host: str, port: int) -> Layout:
    """Return the layout the entry is configured for."""
    key: str = entry.data.get(CONF_LAYOUT, LAYOUT_AUTO)

    if key == LAYOUT_CUSTOM:
        try:
            return await hass.async_add_executor_job(
                partial(
                    parse_daqprj,
                    entry.data[CONF_CUSTOM_DAQPRJ],
                    key=LAYOUT_CUSTOM,
                    title=CUSTOM_LAYOUT_TITLE,
                    digital_words=entry.data.get(CONF_DIGITAL_WORDS),
                )
            )
        except (KeyError, LayoutError) as err:
            raise ConfigEntryError(
                f"The stored DAQPRJ definition is not usable ({err}). Reconfigure the integration."
            ) from err

    layouts = await hass.async_add_executor_job(builtin_layouts)
    if key != LAYOUT_AUTO:
        if key not in layouts:
            raise ConfigEntryError(f"Unknown layout '{key}'. Reconfigure the integration.")
        return layouts[key]

    # Entry created by version 1.x, which knew a single layout: find out which layout
    # the boiler uses and remember it.
    try:
        values = await async_read_telegram(host, port)
    except HargassnerError as err:
        raise ConfigEntryNotReady(str(err)) from err
    layout = detect_layout(values)
    if layout is None:
        raise ConfigEntryError(
            f"The boiler sends {len(values)} values per line, which does not identify a known layout. "
            "Reconfigure the integration to select the layout."
        )
    _LOGGER.info("Detected layout '%s' for %s", layout.title, entry.title)
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_LAYOUT: layout.key})
    return layout


@callback
def _async_remove_stale_entities(hass: HomeAssistant, entry: HargassnerConfigEntry, layout: Layout) -> None:
    """Remove entities that the current layout and options no longer provide."""
    valid = {
        f"{entry.entry_id}_{key}"
        for key in entity_keys(layout, raw_channels=entry.options.get(CONF_RAW_CHANNELS, False))
    }
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id not in valid:
            _LOGGER.info("Removing entity %s, which is no longer provided", reg_entry.entity_id)
            registry.async_remove(reg_entry.entity_id)
