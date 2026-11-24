"""Constants for the Hargassner integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hargassner_nano"
MANUFACTURER: Final = "Hargassner"

# Config entry data
CONF_LAYOUT: Final = "layout"
CONF_CUSTOM_DAQPRJ: Final = "custom_daqprj"
CONF_DIGITAL_WORDS: Final = "digital_words"

# Config entry options
CONF_RAW_CHANNELS: Final = "raw_channels"
CONF_PELLET_ENERGY: Final = "pellet_energy"

# Special values of CONF_LAYOUT
LAYOUT_AUTO: Final = "auto"
LAYOUT_CUSTOM: Final = "custom"
CUSTOM_LAYOUT_TITLE: Final = "Custom DAQPRJ definition"

DEFAULT_NAME: Final = "Hargassner"
DEFAULT_PORT: Final = 23
DEFAULT_SCAN_INTERVAL: Final = 60  # seconds
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 3600
DEFAULT_PELLET_ENERGY: Final = 4.8  # kWh per kg of wood pellets
