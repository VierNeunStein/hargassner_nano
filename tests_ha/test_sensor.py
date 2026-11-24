"""Tests of the sensor and binary sensor entities."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache_with_extra_data

from custom_components.hargassner_nano.const import CONF_PELLET_ENERGY, CONF_RAW_CHANNELS, DOMAIN
from custom_components.hargassner_nano.layout import builtin_layouts
from custom_components.hargassner_nano.model import CONSUMPTION_CHANNELS, ERROR_CHANNELS
from homeassistant.components.sensor import ATTR_OPTIONS, ATTR_STATE_CLASS, SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import FakeBoiler, setup_entry

LAYOUT = builtin_layouts()["nano2_124"]
ERROR_INDEX = LAYOUT.find_analog(*ERROR_CHANNELS).index
COUNTER_INDEX = LAYOUT.find_analog(*CONSUMPTION_CHANNELS).index
STATE_INDEX = LAYOUT.find_analog("ZK").index


def _state(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id is not None, key
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} has no state (disabled?)"
    return state


async def _refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_values_of_the_recorded_line(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """The entities show the values of the boiler's line."""
    await setup_entry(hass, entry)

    boiler_temp = _state(hass, entry, "sensor", "boiler_temp")
    assert boiler_temp.state == "63.9"
    assert boiler_temp.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert boiler_temp.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert boiler_temp.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert boiler_temp.name == "Hargassner Boiler temperature"

    assert _state(hass, entry, "sensor", "outdoor_temp").state == "7.6"
    assert _state(hass, entry, "sensor", "flow_temp").state == "44.0"
    assert _state(hass, entry, "sensor", "pellet_silo").state == "5393"
    assert _state(hass, entry, "sensor", "pellet_consumption_total").state == "19884"
    assert _state(hass, entry, "binary_sensor", "hk1_pump").state == STATE_ON
    assert _state(hass, entry, "binary_sensor", "buffer_pump").state == STATE_OFF


async def test_boiler_state(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """The state is an enum with translated options and the number as attribute."""
    await setup_entry(hass, entry)
    state = _state(hass, entry, "sensor", "state")
    assert state.state == "off"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert "full_firing" in state.attributes[ATTR_OPTIONS]
    assert state.attributes["code"] == 1

    boiler.set_value(STATE_INDEX, "7")
    await _refresh(hass, entry)
    assert _state(hass, entry, "sensor", "state").state == "full_firing"

    # A state number the integration does not know is shown as unknown, with its number.
    boiler.set_value(STATE_INDEX, "42")
    await _refresh(hass, entry)
    state = _state(hass, entry, "sensor", "state")
    assert state.state == STATE_UNKNOWN
    assert state.attributes["code"] == 42


async def test_fault(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """A fault number turns the problem sensor on and is shown as text."""
    await setup_entry(hass, entry)
    assert _state(hass, entry, "sensor", "error_number").state == "No fault"
    problem = _state(hass, entry, "binary_sensor", "error_status")
    assert problem.state == STATE_OFF
    assert problem.attributes["code"] == 0
    assert problem.attributes["description"] == "No fault"

    boiler.set_value(ERROR_INDEX, "5")
    await _refresh(hass, entry)
    message = _state(hass, entry, "sensor", "error_number")
    assert message.state == "Empty the ash drawer"
    assert message.attributes["code"] == 5
    problem = _state(hass, entry, "binary_sensor", "error_status")
    assert problem.state == STATE_ON
    assert problem.attributes["code"] == 5
    assert problem.attributes["description"] == "Empty the ash drawer"

    boiler.set_value(ERROR_INDEX, "777")
    await _refresh(hass, entry)
    assert _state(hass, entry, "sensor", "error_number").state == "Fault no. 777"


async def test_fault_text_follows_server_language(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry
) -> None:
    """Fault texts are produced in Python and follow the language of the server."""
    hass.config.language = "de"
    boiler.set_value(ERROR_INDEX, "5")
    await setup_entry(hass, entry)
    assert _state(hass, entry, "sensor", "error_number").state == "Aschelade entleeren"


async def test_probe_not_installed(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """A probe that reports -20 °C, 120 °C or 140 °C is not installed and shown as unknown."""
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_buffer_temp_mid", config_entry=entry, disabled_by=None
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, entry, "sensor", "buffer_temp_mid").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("platform", "key", "enabled"),
    [
        ("sensor", "boiler_temp", True),
        ("sensor", "dhw_temp", True),
        ("binary_sensor", "dhw_pump", True),
        # Disabled by default
        ("sensor", "draft_fan", False),
        ("sensor", "outdoor_temp_avg", False),
        ("sensor", "hc1_room_temp", False),
        # Parts that are not installed on the recorded boiler
        ("sensor", "buffer_temp_mid", False),
        ("sensor", "hc2_flow_temp", False),
        ("binary_sensor", "hc2_pump", False),
    ],
)
async def test_enabled_by_default(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry, platform: str, key: str, enabled: bool
) -> None:
    """Entities of parts that are not installed are created disabled."""
    await setup_entry(hass, entry)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id is not None
    assert (registry.async_get(entity_id).disabled_by is None) is enabled


async def test_pellet_energy(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """The energy sensor starts with the boiler's counter and adds what is burnt."""
    await setup_entry(hass, entry)
    energy = _state(hass, entry, "sensor", "pellet_energy_total")
    assert energy.state == "95443.2"  # 19884 kg * 4.8 kWh/kg
    assert energy.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR
    assert energy.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert energy.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING
    assert energy.attributes["pellet_counter"] == 19884

    boiler.set_value(COUNTER_INDEX, "19886")
    await _refresh(hass, entry)
    assert _state(hass, entry, "sensor", "pellet_energy_total").state == "95452.8"

    # A counter reset on the boiler does not make the total go down.
    boiler.set_value(COUNTER_INDEX, "3")
    await _refresh(hass, entry)
    assert _state(hass, entry, "sensor", "pellet_energy_total").state == "95452.8"
    boiler.set_value(COUNTER_INDEX, "5")
    await _refresh(hass, entry)
    assert _state(hass, entry, "sensor", "pellet_energy_total").state == "95462.4"


async def test_pellet_energy_is_restored(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """After a restart the total continues with the pellets burnt in the meantime."""
    entry.add_to_hass(hass)
    entity_id = (
        er.async_get(hass)
        .async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_pellet_energy_total", config_entry=entry)
        .entity_id
    )
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, "1000.0", {"pellet_counter": 19880}),
                {"native_value": 1000.0, "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR},
            )
        ],
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "1019.2"  # 1000 kWh + 4 kg * 4.8 kWh/kg
    assert state.attributes["pellet_counter"] == 19884


async def test_pellet_energy_content_option(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """The energy content of the option is used for the pellets burnt."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Hargassner",
        data={"host": "192.0.2.10", "port": 23, "layout": "nano2_124"},
        options={CONF_PELLET_ENERGY: 5.0},
    )
    await setup_entry(hass, entry)
    energy = _state(hass, entry, "sensor", "pellet_energy_total")
    assert energy.state == "99420.0"
    assert energy.attributes["energy_per_kg"] == 5.0


async def test_raw_channels(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """With the option, every other channel becomes a disabled diagnostic entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Hargassner",
        data={"host": "192.0.2.10", "port": 23, "layout": "nano2_124"},
        options={CONF_RAW_CHANNELS: True},
    )
    await setup_entry(hass, entry)
    registry = er.async_get(hass)
    raw = [
        reg_entry
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id)
        if reg_entry.unique_id.startswith(f"{entry.entry_id}_raw_")
    ]
    assert len(raw) == 78 + 109
    assert all(reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION for reg_entry in raw)
    assert all(reg_entry.entity_category == "diagnostic" for reg_entry in raw)
