"""Polls the boiler and hands the decoded values to the entities."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HargassnerError, UnexpectedLength, async_read_telegram
from .const import DOMAIN
from .layout import Layout, LayoutError, Telegram

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type HargassnerConfigEntry = ConfigEntry[HargassnerCoordinator]


def layout_issue_id(entry_id: str) -> str:
    """Return the id of the repair issue raised when the boiler changes its format."""
    return f"layout_mismatch_{entry_id}"


class HargassnerCoordinator(DataUpdateCoordinator[Telegram]):
    """Reads one telegram per update interval.

    The connection is opened for each reading and closed again, so the boiler's telnet
    port stays free for other tools most of the time.
    """

    config_entry: HargassnerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HargassnerConfigEntry,
        layout: Layout,
        host: str,
        port: int,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {host}",
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.layout = layout
        self.host = host
        self.port = port

    async def _async_update_data(self) -> Telegram:
        """Read and decode one telegram."""
        issue_id = layout_issue_id(self.config_entry.entry_id)
        try:
            values = await async_read_telegram(self.host, self.port, expected=self.layout.value_count)
            telegram = self.layout.decode(values)
        except UnexpectedLength as err:
            # Typically a firmware update: the values no longer are where the layout expects them.
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="layout_mismatch",
                translation_placeholders={
                    "name": self.config_entry.title,
                    "expected": str(err.expected),
                    "received": ", ".join(str(count) for count in err.received),
                },
            )
            raise UpdateFailed(
                f"The boiler sends {err.received} values per line, the configured layout "
                f"'{self.layout.title}' has {err.expected}. Reconfigure the integration to select the new layout."
            ) from err
        except (HargassnerError, LayoutError) as err:
            raise UpdateFailed(str(err)) from err

        ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return telegram
