"""Diagnostics: everything needed to check or add a layout, without the address."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import HargassnerConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: HargassnerConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    layout = coordinator.layout
    telegram = coordinator.data

    diagnostics: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "layout": {
            "key": layout.key,
            "title": layout.title,
            "analog_channels": len(layout.analog),
            "digital_words": layout.digital_words,
            "value_count": layout.value_count,
        },
        "last_update_success": coordinator.last_update_success,
        "telegram": None,
    }
    if telegram is not None:
        diagnostics["telegram"] = {
            "line": "pm " + " ".join(telegram.values),
            "format_problems": layout.check(telegram.values),
            "analog": {
                f"{channel.index + 1:03} {channel.name}": telegram.analog.get(channel.key)
                for channel in layout.analog
            },
            "digital": {
                f"{channel.word}.{channel.bit:02} {channel.name}": telegram.digital.get(channel.key)
                for channel in layout.digital
            },
        }
    return diagnostics
