"""Fixtures for the Home Assistant tests.

The boiler is replaced by ``FakeBoiler``: it stands in for ``async_read_telegram`` and
behaves like the real reader (including the length check of the coordinator). The
reader itself is tested against a TCP server in ``tests/test_client.py``.
"""

from __future__ import annotations

from collections.abc import Generator
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hargassner_nano.client import UnexpectedLength
from custom_components.hargassner_nano.const import CONF_LAYOUT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

PACKAGE = "custom_components.hargassner_nano"
HOST = "192.0.2.10"  # documentation address, never reached
PORT = 23
TITLE = "Hargassner"


def _recorded_lines() -> tuple[str, ...]:
    # Loaded by path: importing the ``tests`` package would register a stub of the
    # integration that hides its real ``__init__`` from Home Assistant.
    path = Path(__file__).resolve().parents[1] / "tests" / "telegrams.py"
    spec = importlib.util.spec_from_file_location("_recorded_telegrams", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NANO2_LINES


NANO2_VALUES: tuple[str, ...] = tuple(_recorded_lines()[0].split()[1:])


class FakeBoiler:
    """Answers like a boiler that sends ``values`` (or fails with ``error``)."""

    def __init__(self, values: tuple[str, ...]) -> None:
        self.values = values
        self.error: Exception | None = None
        self.reads: list[tuple[str, int, int | None]] = []

    async def read(self, host: str, port: int = 23, *, expected: int | None = None, **_: object) -> tuple[str, ...]:
        self.reads.append((host, port, expected))
        if self.error is not None:
            raise self.error
        if expected is not None and len(self.values) != expected:
            raise UnexpectedLength(expected, [len(self.values)])
        return tuple(self.values)

    def set_value(self, index: int, value: str) -> None:
        values = list(self.values)
        values[index] = value
        self.values = tuple(values)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def boiler() -> Generator[FakeBoiler]:
    """Replace the network reader everywhere it is used."""
    fake = FakeBoiler(NANO2_VALUES)
    with (
        patch(f"{PACKAGE}.async_read_telegram", fake.read),
        patch(f"{PACKAGE}.config_flow.async_read_telegram", fake.read),
        patch(f"{PACKAGE}.coordinator.async_read_telegram", fake.read),
    ):
        yield fake


@pytest.fixture
def entry() -> MockConfigEntry:
    """A config entry as the config flow creates it for the recorded Nano.2."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=f"{HOST}:{PORT}",
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_LAYOUT: "nano2_124"},
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add and set up a config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
