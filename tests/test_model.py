"""Tests for the entity model and the texts."""

from __future__ import annotations

import unittest

from custom_components.hargassner_nano.layout import builtin_layouts, parse_daqprj
from custom_components.hargassner_nano.model import (
    BINARY_SENSORS,
    BOILER_STATES,
    SENSORS,
    binary_value,
    enabled_by_default,
    entity_keys,
    error_code,
    raw_analog_channels,
    raw_digital_channels,
    resolve_binary_sensors,
    resolve_sensors,
    sensor_value,
)
from custom_components.hargassner_nano.texts import ERROR_TEXTS, error_text, preview_lines, state_text

from .telegrams import NANO2_LINES

# Entity keys of version 1.1.0. They are part of the unique ids and must never change.
V1_SENSORS = {
    "state", "error_number", "output", "o2", "draft_fan", "boiler_temp", "boiler_setpoint", "return_temp",
    "flue_temp", "combustion_temp", "outdoor_temp", "outdoor_temp_avg", "flow_temp", "flow_setpoint",
    "buffer_temp_top", "buffer_temp_mid", "buffer_temp_bot", "buffer_fill", "buffer_setpoint", "dhw_temp",
    "pellet_silo", "pellet_consumption_total",
}  # fmt: skip
V1_BINARY_SENSORS = {"error_status", "hk1_pump", "buffer_pump"}


def nano2():
    return builtin_layouts()["nano2_124"]


def telegram(line: str = NANO2_LINES[0], **changes: str):
    layout = nano2()
    values = list(line.split()[1:])
    for name, text in changes.items():
        values[layout.find_analog(name.replace("__", " ")).index] = text
    return layout.decode(values)


class SpecTest(unittest.TestCase):
    def test_keys_are_unique(self) -> None:
        keys = [spec.key for spec in SENSORS] + [spec.key for spec in BINARY_SENSORS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_keys_of_version_1_are_kept(self) -> None:
        self.assertLessEqual(V1_SENSORS, {item.spec.key for item in resolve_sensors(nano2())})
        self.assertLessEqual(V1_BINARY_SENSORS, {item.spec.key for item in resolve_binary_sensors(nano2())})

    def test_every_layout_yields_the_main_entities(self) -> None:
        main = {"state", "boiler_temp", "flue_temp", "outdoor_temp", "flow_temp", "dhw_temp"}
        main.add("pellet_consumption_total")
        for key, layout in builtin_layouts().items():
            with self.subTest(layout=key):
                self.assertLessEqual(main, {item.spec.key for item in resolve_sensors(layout)})
                binary = {item.spec.key for item in resolve_binary_sensors(layout)}
                self.assertLessEqual({"error_status", "hk1_pump"}, binary)

    def test_no_channel_is_used_twice(self) -> None:
        for key, layout in builtin_layouts().items():
            with self.subTest(layout=key):
                channels = [item.channel.key for item in resolve_sensors(layout)]
                self.assertEqual(len(channels), len(set(channels)))
                bits = [item.channel.key for item in resolve_binary_sensors(layout) if item.channel]
                self.assertEqual(len(bits), len(set(bits)))


class ValueTest(unittest.TestCase):
    def read(self, **changes: str) -> dict[str, object]:
        data = telegram(**changes)
        return {item.spec.key: sensor_value(item.spec, item.channel, data) for item in resolve_sensors(nano2())}

    def test_values_of_the_recorded_line(self) -> None:
        values = self.read()
        expected = {
            "state": "off", "error_number": 0, "output": 0, "o2": 21, "draft_fan": 25, "boiler_temp": 63.9,
            "boiler_setpoint": 0, "return_temp": 61.8, "flue_temp": 67.4, "combustion_temp": 102.6,
            "outdoor_temp": 7.6, "outdoor_temp_avg": 5.5, "flow_temp": 44.0, "flow_setpoint": 44,
            "buffer_temp_top": 70.3, "buffer_temp_mid": None, "buffer_temp_bot": 48.2, "buffer_fill": 85,
            "buffer_setpoint": 44, "dhw_temp": 70.6, "pellet_silo": 5393, "pellet_consumption_total": 19884,
            "hc1_room_temp": 20.0, "hc2_flow_temp": None, "hca_flow_temp": None, "hcb_flow_temp": None,
        }  # fmt: skip
        for key, value in expected.items():
            self.assertEqual(values[key], value, key)
        self.assertIsInstance(values["pellet_silo"], int)

    def test_states(self) -> None:
        for number, state in BOILER_STATES.items():
            self.assertEqual(self.read(ZK=str(number))["state"], state)
        self.assertIsNone(self.read(ZK="0")["state"])
        self.assertIsNone(self.read(ZK="11")["state"])
        self.assertIsNone(self.read(ZK="x")["state"])

    def test_outside_temperature_of_minus_20_is_a_real_value(self) -> None:
        self.assertEqual(self.read(Taus="-20.0")["outdoor_temp"], -20.0)

    def test_binary_sensors(self) -> None:
        layout = nano2()
        data = telegram()
        states = {item.spec.key: binary_value(item, layout, data) for item in resolve_binary_sensors(layout)}
        self.assertEqual(states["error_status"], False)
        self.assertEqual(states["hk1_pump"], True)
        self.assertEqual(states["buffer_pump"], False)
        self.assertEqual(states["dhw_pump"], False)
        self.assertEqual(states["hc2_pump"], False)
        # The status word has a bit for circuit 3, but this boiler has no values for it.
        self.assertIsNotNone(layout.find_digital("HKP3"))
        self.assertNotIn("hc3_pump", states)

    def test_fault_number_counts_as_problem_without_fault_bit(self) -> None:
        layout = nano2()
        data = telegram(Störungs__Nr="6")
        problem = next(item for item in resolve_binary_sensors(layout) if item.spec.key == "error_status")
        self.assertEqual(error_code(layout, data), 6)
        self.assertIs(binary_value(problem, layout, data), True)

    def test_fault_sensor_without_fault_bit(self) -> None:
        text = "<DAQPRJ><ANALOG><CHANNEL id='0' name='Störungs Nr'/></ANALOG></DAQPRJ>"
        layout = parse_daqprj(text, key="x", title="x")
        (problem,) = resolve_binary_sensors(layout)
        self.assertIsNone(problem.channel)
        self.assertIs(binary_value(problem, layout, layout.decode(("0",))), False)
        self.assertIs(binary_value(problem, layout, layout.decode(("5",))), True)
        self.assertIsNone(binary_value(problem, layout, layout.decode(("?",))))

    def test_enabled_by_default_follows_installed_probes(self) -> None:
        layout = nano2()
        data = telegram()
        enabled = {item.spec.key: enabled_by_default(item.spec, layout, data) for item in resolve_sensors(layout)}
        enabled.update(
            {item.spec.key: enabled_by_default(item.spec, layout, data) for item in resolve_binary_sensors(layout)}
        )
        for key in ("state", "boiler_temp", "flow_temp", "flow_setpoint", "buffer_temp_top", "dhw_temp", "hk1_pump"):
            self.assertTrue(enabled[key], key)
        for key in ("buffer_temp_mid", "hc2_flow_temp", "hc2_flow_setpoint", "hc2_pump", "hca_pump", "draft_fan",
                    "hc1_room_temp", "outdoor_temp_avg"):  # fmt: skip
            self.assertFalse(enabled[key], key)

    def test_entity_keys(self) -> None:
        layout = nano2()
        plain = entity_keys(layout, raw_channels=False)
        self.assertLessEqual(V1_SENSORS | V1_BINARY_SENSORS | {"pellet_energy_total", "dhw_pump"}, plain)
        self.assertFalse(any(key.startswith("raw_") for key in plain))
        everything = entity_keys(layout, raw_channels=True)
        self.assertLess(plain, everything)
        self.assertIn("raw_tplat", everything)
        self.assertIn("raw_es_run", everything)

    def test_raw_channels_exclude_used_and_placeholder_channels(self) -> None:
        layout = nano2()
        analog = {channel.name for channel in raw_analog_channels(layout)}
        self.assertIn("Tplat", analog)
        self.assertNotIn("TK", analog)
        self.assertNotIn("dummy1", analog)
        digital = {channel.name for channel in raw_digital_channels(layout)}
        self.assertIn("ES Run", digital)
        self.assertNotIn("HKP1", digital)


class TextTest(unittest.TestCase):
    def test_error_text(self) -> None:
        self.assertIsNone(error_text(None, "de"))
        self.assertEqual(error_text(0, "de"), "Keine Störung")
        self.assertEqual(error_text(0, "en-GB"), "No fault")
        self.assertEqual(error_text(6, "de-AT"), "Aschelade zu voll")
        self.assertEqual(error_text(6, "fr"), "Ash drawer too full")
        self.assertEqual(error_text(9999, "de"), "Störung Nr. 9999")
        self.assertEqual(error_text(9999, None), "Fault no. 9999")
        self.assertTrue(all(len(texts) == 2 and all(texts) for texts in ERROR_TEXTS.values()))

    def test_every_state_has_a_name(self) -> None:
        for state in BOILER_STATES.values():
            self.assertTrue(state_text(state, "de"))
            self.assertTrue(state_text(state, "en"))

    def test_preview(self) -> None:
        lines = preview_lines(nano2(), telegram(), "de")
        self.assertIn("Betriebszustand: Aus", lines)
        self.assertIn("Kesseltemperatur: 63.9 °C", lines)
        self.assertIn("Pelletlagerstand: 5393 kg", lines)
        english = preview_lines(nano2(), telegram(ZK="99", TB1="-20.0"), "en")
        self.assertIn("Boiler state: unknown (99)", english)
        self.assertIn("Hot water tank: not installed", english)


if __name__ == "__main__":
    unittest.main()
