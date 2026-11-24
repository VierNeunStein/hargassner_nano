"""Tests of the config flow, the reconfigure flow and the options flow."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hargassner_nano.client import CannotConnect, NoTelegram
from custom_components.hargassner_nano.const import (
    CONF_CUSTOM_DAQPRJ,
    CONF_DIGITAL_WORDS,
    CONF_LAYOUT,
    CONF_PELLET_ENERGY,
    CONF_RAW_CHANNELS,
    DOMAIN,
    LAYOUT_CUSTOM,
)
from custom_components.hargassner_nano.layout import builtin_layouts, matching_layouts
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .conftest import HOST, NANO2_VALUES, PORT, FakeBoiler, setup_entry

USER_INPUT = {CONF_NAME: "Heizung", CONF_HOST: HOST, CONF_PORT: PORT}

# A boiler with an unknown firmware: five analog values and one status word.
CUSTOM_VALUES = ("7", "65", "1", "2", "3", "0")
CUSTOM_DAQPRJ = (
    "<DAQPRJ><ANALOG>"
    '<CHANNEL id="0" name="ZK" dop="0"/>'
    '<CHANNEL id="1" name="TK" dop="0"/>'
    '<CHANNEL id="2" name="X2" dop="0"/>'
    '<CHANNEL id="3" name="X3" dop="0"/>'
    '<CHANNEL id="4" name="X4" dop="0"/>'
    "</ANALOG><DIGITAL>"
    '<CHANNEL id="0" bit="0" name="Störung"/>'
    "</DIGITAL></DAQPRJ>"
)


async def _start(hass: HomeAssistant, user_input: dict = USER_INPUT) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_user_flow(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """The layout is detected, the values are shown and the entry is created."""
    result = await _start(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "confirm"
    assert result["menu_options"] == ["finish", "layout", "custom"]
    placeholders = result["description_placeholders"]
    assert placeholders["layout"] == "Nano.2 (124 values)"
    assert placeholders["count"] == "124"
    assert "- Boiler temperature: 63.9 °C" in placeholders["preview"]
    assert "- Boiler state: Off" in placeholders["preview"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Heizung"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT, CONF_LAYOUT: "nano2_124"}
    assert result["result"].unique_id == f"{HOST}:{PORT}"
    await hass.async_block_till_done()
    assert result["result"].state is ConfigEntryState.LOADED


async def test_user_flow_strips_input(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """Spaces around the address are removed and an empty name gets the default."""
    result = await _start(hass, {CONF_NAME: "  ", CONF_HOST: f" {HOST} ", CONF_PORT: PORT})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hargassner"
    assert result["data"][CONF_HOST] == HOST


@pytest.mark.parametrize(
    ("error", "reason"),
    [(CannotConnect("refused"), "cannot_connect"), (NoTelegram("no pm line"), "no_telegram")],
)
async def test_user_flow_errors(hass: HomeAssistant, boiler: FakeBoiler, error: Exception, reason: str) -> None:
    """Connection problems are shown in the form, and the user can try again."""
    boiler.error = error
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    boiler.error = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """The same address and port cannot be set up twice."""
    entry.add_to_hass(hass)
    result = await _start(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert boiler.reads == []


async def test_user_flow_choose_layout(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """If several layouts have the length of the line, the user chooses one."""
    layouts = builtin_layouts()
    first, second = layouts["nano2_v14_1_q1"], layouts["nano_pk_v14_0_q"]
    assert first.value_count == second.value_count
    # Zeros fit neither layout exactly (both have channels with two decimals).
    boiler.values = ("0",) * first.value_count
    assert all(problems for _, problems in matching_layouts(boiler.values))

    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "layout"
    assert result["description_placeholders"] == {"count": str(first.value_count)}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LAYOUT: second.key})
    assert result["type"] is FlowResultType.MENU
    assert result["description_placeholders"]["layout"] == second.title

    # Back to the selection and choose the other one
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "layout"})
    assert result["step_id"] == "layout"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LAYOUT: first.key})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LAYOUT] == first.key


async def test_user_flow_custom_definition(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """An unknown length leads to the DAQPRJ step, which checks the pasted block."""
    boiler.values = CUSTOM_VALUES
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom"
    assert result["description_placeholders"]["count"] == "6"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CUSTOM_DAQPRJ: "not a block"})
    assert result["errors"] == {"base": "invalid_daqprj"}

    # A block of another firmware that describes more values than the boiler sends
    too_long = CUSTOM_DAQPRJ.replace("</ANALOG>", '<CHANNEL id="5" name="X5" dop="0"/></ANALOG>')
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CUSTOM_DAQPRJ: too_long})
    assert result["errors"] == {"base": "count_mismatch"}

    # A whole DAQ file may be pasted; the block is cut out of it.
    pasted = f"header line\n{CUSTOM_DAQPRJ}\n1;2;3;4\n"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CUSTOM_DAQPRJ: pasted})
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["finish", "custom"]
    assert "- Boiler temperature: 65 °C" in result["description_placeholders"]["preview"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_LAYOUT: LAYOUT_CUSTOM,
        CONF_CUSTOM_DAQPRJ: CUSTOM_DAQPRJ,
        CONF_DIGITAL_WORDS: 1,
    }
    await hass.async_block_till_done()
    assert result["result"].state is ConfigEntryState.LOADED


async def test_reconfigure(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """A new address is stored, the layout detected again and the entry reloaded."""
    await setup_entry(hass, entry)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.11", CONF_PORT: 2323}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.data == {CONF_HOST: "192.0.2.11", CONF_PORT: 2323, CONF_LAYOUT: "nano2_124"}
    assert entry.unique_id == "192.0.2.11:2323"
    assert entry.title == "Hargassner"
    assert entry.state is ConfigEntryState.LOADED
    assert boiler.reads[-1] == ("192.0.2.11", 2323, 124)


async def test_reconfigure_to_custom_and_back(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """A stored custom definition is dropped when a built-in layout is chosen again."""
    await setup_entry(hass, entry)
    boiler.values = CUSTOM_VALUES
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["step_id"] == "custom"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CUSTOM_DAQPRJ: CUSTOM_DAQPRJ})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.data[CONF_LAYOUT] == LAYOUT_CUSTOM
    assert entry.state is ConfigEntryState.LOADED

    boiler.values = NANO2_VALUES
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.data == {CONF_HOST: HOST, CONF_PORT: PORT, CONF_LAYOUT: "nano2_124"}


async def test_reconfigure_updates_address_in_old_title(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """Entries of version 1.x carry the address in their title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Hargassner Nano ({HOST})",
        unique_id=f"{HOST}:{PORT}",
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_LAYOUT: "nano2_124"},
    )
    await setup_entry(hass, entry)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.11", CONF_PORT: PORT}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Hargassner Nano (192.0.2.11)"


async def test_reconfigure_to_address_of_other_entry(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry
) -> None:
    """Two entries cannot point to the same boiler."""
    await setup_entry(hass, entry)
    MockConfigEntry(domain=DOMAIN, unique_id="192.0.2.11:23", data={CONF_HOST: "192.0.2.11"}).add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "192.0.2.11", CONF_PORT: 23})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


async def test_reconfigure_cannot_connect(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """The form is shown again with an error and the entry is not changed."""
    await setup_entry(hass, entry)
    boiler.error = CannotConnect("refused")
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.11", CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_HOST] == HOST


async def test_options_flow(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """Changed options are stored and take effect after the reload."""
    await setup_entry(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30, CONF_PELLET_ENERGY: 5.0, CONF_RAW_CHANNELS: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_SCAN_INTERVAL: 30, CONF_PELLET_ENERGY: 5.0, CONF_RAW_CHANNELS: True}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval.total_seconds() == 30


async def test_options_flow_rejects_out_of_range(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry
) -> None:
    """The update interval must be between 10 and 3600 seconds."""
    await setup_entry(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 5, CONF_PELLET_ENERGY: 4.8, CONF_RAW_CHANNELS: False}
        )
