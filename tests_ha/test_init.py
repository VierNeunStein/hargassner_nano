"""Tests of setting up and unloading entries, migration, repairs and diagnostics."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hargassner_nano.client import CannotConnect
from custom_components.hargassner_nano.const import CONF_CUSTOM_DAQPRJ, CONF_LAYOUT, DOMAIN, LAYOUT_CUSTOM
from custom_components.hargassner_nano.coordinator import layout_issue_id
from custom_components.hargassner_nano.diagnostics import async_get_config_entry_diagnostics
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .conftest import HOST, NANO2_VALUES, PORT, FakeBoiler, setup_entry


def _entity_id(entity_registry: er.EntityRegistry, entry: MockConfigEntry, platform: str, key: str) -> str | None:
    return entity_registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


async def test_setup_and_unload(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """The entry loads, creates its entities and unloads again."""
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert boiler.reads == [(HOST, PORT, 124)]
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 44

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_boiler_unreachable(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry
) -> None:
    """A boiler that is switched off delays the setup instead of failing it."""
    boiler.error = CannotConnect("no answer")
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_for_unknown_layout(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """An entry that names a layout that does not exist asks to be reconfigured."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_LAYOUT: "gone"})
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert boiler.reads == []


async def test_setup_fails_for_broken_custom_definition(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """A stored custom definition that cannot be parsed asks to be reconfigured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_LAYOUT: LAYOUT_CUSTOM, CONF_CUSTOM_DAQPRJ: "<DAQPRJ/>"},
    )
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_migration_from_version_1(
    hass: HomeAssistant, boiler: FakeBoiler, entity_registry: er.EntityRegistry
) -> None:
    """Entries of version 1.x get their layout detected and keep entities and interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Hargassner Nano ({HOST})",
        unique_id=f"{HOST}:{PORT}",
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_SCAN_INTERVAL: 30},
    )
    entry.add_to_hass(hass)
    old = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_boiler_temp",
        config_entry=entry,
        suggested_object_id="hargassner_nano_kesseltemperatur",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_LAYOUT] == "nano2_124"
    assert entry.runtime_data.update_interval.total_seconds() == 30
    assert _entity_id(entity_registry, entry, "sensor", "boiler_temp") == old.entity_id
    assert hass.states.get(old.entity_id).state == "63.9"


async def test_migration_with_unknown_length(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """A 1.x entry whose boiler sends an unknown format must be reconfigured."""
    boiler.values = ("1", "2", "3")
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT})
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert CONF_LAYOUT not in entry.data


async def test_migration_retries_when_boiler_unreachable(hass: HomeAssistant, boiler: FakeBoiler) -> None:
    """The layout of a 1.x entry is detected as soon as the boiler answers."""
    boiler.error = CannotConnect("no answer")
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT})
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_stale_entities_are_removed(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Entities the layout and options no longer provide are removed on setup."""
    entry.add_to_hass(hass)
    stale = entity_registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_raw_tplat", config_entry=entry)
    kept = entity_registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_boiler_temp", config_entry=entry)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(stale.entity_id) is None
    assert entity_registry.async_get(kept.entity_id) is not None


async def test_changed_format_raises_repair_issue(
    hass: HomeAssistant,
    boiler: FakeBoiler,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """After a firmware update the entities become unavailable and a repair issue appears."""
    await setup_entry(hass, entry)
    coordinator = entry.runtime_data
    boiler_temp = _entity_id(entity_registry, entry, "sensor", "boiler_temp")
    issue_id = layout_issue_id(entry.entry_id)

    boiler.values = (*NANO2_VALUES, "0")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(boiler_temp).state == STATE_UNAVAILABLE
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "layout_mismatch"
    assert issue.translation_placeholders == {"name": "Hargassner", "expected": "124", "received": "125"}

    boiler.values = NANO2_VALUES
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(boiler_temp).state == "63.9"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_unload_removes_repair_issue(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry, issue_registry: ir.IssueRegistry
) -> None:
    """The repair issue of an entry does not outlive it."""
    await setup_entry(hass, entry)
    boiler.values = (*NANO2_VALUES, "0")
    await entry.runtime_data.async_refresh()
    assert issue_registry.async_get_issue(DOMAIN, layout_issue_id(entry.entry_id)) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, layout_issue_id(entry.entry_id)) is None


async def test_connection_loss_makes_entities_unavailable(
    hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """A boiler that stops answering shows its entities as unavailable, without a repair issue."""
    await setup_entry(hass, entry)
    boiler.error = CannotConnect("no answer")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(_entity_id(entity_registry, entry, "sensor", "boiler_temp")).state == STATE_UNAVAILABLE
    assert ir.async_get(hass).async_get_issue(DOMAIN, layout_issue_id(entry.entry_id)) is None


async def test_diagnostics(hass: HomeAssistant, boiler: FakeBoiler, entry: MockConfigEntry) -> None:
    """Diagnostics contain the line and the decoded values, but not the address."""
    await setup_entry(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"] == {CONF_HOST: "**REDACTED**", CONF_PORT: PORT, CONF_LAYOUT: "nano2_124"}
    assert HOST not in repr(diagnostics)
    assert diagnostics["layout"]["key"] == "nano2_124"
    assert diagnostics["layout"]["value_count"] == 124
    assert diagnostics["last_update_success"] is True
    telegram = diagnostics["telegram"]
    assert telegram["line"] == "pm " + " ".join(NANO2_VALUES)
    assert telegram["format_problems"] == []
    assert telegram["analog"]["004 TK"] == 63.9
