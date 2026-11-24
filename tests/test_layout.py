"""Tests for layout parsing and detection."""

from __future__ import annotations

import unittest

from custom_components.hargassner_nano.layout import (
    LayoutError,
    builtin_layouts,
    channel_key,
    detect_layout,
    extract_daqprj,
    matching_layouts,
    parse_custom_daqprj,
    parse_daqprj,
)
from custom_components.hargassner_nano.layout_data import BUILTIN_LAYOUTS

from .telegrams import NANO2_LINES

SMALL = """
<DAQPRJ><ANALOG>
<CHANNEL id='0' name='ZK' dop='0'/>
<CHANNEL id='1' name='TK' unit='°C'/>
<CHANNEL id='2' name='Heiz U Lambda' unit='V' dop='2'/>
</ANALOG><DIGITAL>
<CHANNEL id='0' bit='0' name='Störung'/>
<CHANNEL id='1' bit='3' name='HKP1'/>
</DIGITAL></DAQPRJ>
"""

# Value counts (without the leading "pm") the layouts must keep forever: config entries
# refer to layouts by key, so a changed count would break existing installations.
VALUE_COUNTS = {
    "nano2_124": 124,
    "nano2_v14_1_q1": 120,
    "nano_pk_plus_v14_1_q": 121,
    "pk_v14_1_q1_tra_first": 121,
    "nano2_v14_1_q1_solar": 140,
    "nano2_v14_1_q_zuspuf_aup": 155,
    "nano_pk_v14_0_q": 120,
    "nano_pk_v14_0_o3": 113,
    "nano_pk_v14_0_n2": 135,
    "nano_pk_v14_0_n": 112,
    "nano_pk_v14_0_m": 154,
    "nano_pk_v14_0_l": 149,
    "nano_pk_v14_0_k": 190,
    "hsv_classic_v14_0_d": 171,
    "nano_v40_0_az15": 157,
}


def values(line: str) -> tuple[str, ...]:
    return tuple(line.split()[1:])


class ChannelKeyTest(unittest.TestCase):
    def test_spelling_variants_share_a_key(self) -> None:
        self.assertEqual(channel_key("Störungs Nr"), "storungs_nr")
        self.assertEqual(channel_key("Storungs Nr"), "storungs_nr")
        self.assertEqual(channel_key("Stoerungs Nr"), "storungs_nr")
        self.assertEqual(channel_key("Puff Füllgrad"), channel_key("Puff Fuellgrad"))
        self.assertEqual(channel_key("Verbrauchszähler"), channel_key("Verbrauchszaehler"))

    def test_keys_are_plain_identifiers(self) -> None:
        self.assertEqual(channel_key("TA Gem."), "ta_gem")
        self.assertEqual(channel_key("RLP/PuffP"), "rlp_puffp")
        self.assertEqual(channel_key("  max.Leist.TRG "), "max_leist_trg")
        self.assertEqual(channel_key("°"), "")


class ParseTest(unittest.TestCase):
    def test_parses_channels(self) -> None:
        layout = parse_daqprj(SMALL, key="small", title="Small")
        self.assertEqual([c.name for c in layout.analog], ["ZK", "TK", "Heiz U Lambda"])
        self.assertEqual(layout.analog[1].unit, "°C")
        self.assertIsNone(layout.analog[0].unit)
        self.assertEqual([c.decimals for c in layout.analog], [0, None, 2])
        self.assertEqual(layout.digital_words, 2)
        self.assertEqual(layout.value_count, 5)
        self.assertEqual(layout.find_digital("HKP1").bit, 3)

    def test_decode(self) -> None:
        layout = parse_daqprj(SMALL, key="small", title="Small")
        telegram = layout.decode(("7", "63.9", "13.31", "1", "8"))
        self.assertEqual(telegram.analog, {"zk": 7, "tk": 63.9, "heiz_u_lambda": 13.31})
        self.assertIsInstance(telegram.analog["zk"], int)
        self.assertEqual(telegram.digital, {"storung": True, "hkp1": True})
        self.assertEqual(layout.decode(("7", "x", "13.31", "0", "zz")).analog["tk"], None)
        self.assertEqual(layout.decode(("7", "1", "13.31", "0", "zz")).digital, {"storung": False, "hkp1": None})
        with self.assertRaises(LayoutError):
            layout.decode(("7", "63.9"))

    def test_check_reports_format_violations(self) -> None:
        layout = parse_daqprj(SMALL, key="small", title="Small")
        self.assertEqual(layout.check(("7", "63.9", "13.31", "1", "8")), [])
        self.assertEqual(len(layout.check(("7.0", "63.9", "13.31", "1", "8"))), 1)  # dop=0 with decimals
        self.assertEqual(len(layout.check(("7", "63.9", "13.3", "1", "8"))), 1)  # dop=2 with one decimal
        self.assertEqual(len(layout.check(("7", "63.9", "13.31", "1", "8.5"))), 1)  # status word not hex
        self.assertEqual(len(layout.check(("7", "63.9", "13.31", "1"))), 1)  # wrong length

    def test_order_follows_ids_not_position(self) -> None:
        swapped = "<DAQPRJ><ANALOG><CHANNEL id='1' name='B'/><CHANNEL id='0' name='A'/></ANALOG></DAQPRJ>"
        layout = parse_daqprj(swapped, key="x", title="x")
        self.assertEqual([c.name for c in layout.analog], ["A", "B"])
        self.assertEqual(layout.digital_words, 0)

    def test_duplicate_names_get_distinct_keys(self) -> None:
        text = "<DAQPRJ><ANALOG><CHANNEL id='0' name='DUMMY'/><CHANNEL id='1' name='DUMMY'/></ANALOG></DAQPRJ>"
        layout = parse_daqprj(text, key="x", title="x")
        self.assertEqual([c.key for c in layout.analog], ["dummy", "dummy_2"])
        self.assertTrue(all(c.is_placeholder for c in layout.analog))

    def test_invalid_definitions(self) -> None:
        cases = {
            "no_analog_section": "hello",
            "no_analog_channels": "<DAQPRJ><ANALOG></ANALOG></DAQPRJ>",
            "channel_gap": "<ANALOG><CHANNEL id='0' name='A'/><CHANNEL id='2' name='C'/></ANALOG>",
            "duplicate_channel": "<ANALOG><CHANNEL id='0' name='A'/><CHANNEL id='0' name='B'/></ANALOG>",
            "bad_channel": "<ANALOG><CHANNEL name='A'/></ANALOG>",
            "too_long": "<ANALOG>" + " " * 200_001 + "</ANALOG>",
        }
        for reason, text in cases.items():
            with self.subTest(reason=reason), self.assertRaises(LayoutError) as caught:
                parse_daqprj(text, key="x", title="x")
            self.assertEqual(caught.exception.reason, reason)

    def test_xml_entities_and_double_quotes(self) -> None:
        text = '<DAQPRJ><ANALOG><CHANNEL id="0" name="A &amp; B" unit="&#176;C"/></ANALOG></DAQPRJ>'
        channel = parse_daqprj(text, key="x", title="x").analog[0]
        self.assertEqual((channel.name, channel.unit), ("A & B", "°C"))

    def test_damaged_umlauts_are_still_found(self) -> None:
        text = "<DAQPRJ><ANALOG><CHANNEL id='0' name='St�rungs Nr'/><CHANNEL id='1' name='StÃ¶rung'/></ANALOG></DAQPRJ>"
        layout = parse_daqprj(text, key="x", title="x")
        self.assertEqual(layout.find_analog("Störungs Nr").index, 0)
        self.assertEqual(layout.find_analog("Störung").index, 1)

    def test_extract_daqprj(self) -> None:
        self.assertEqual(extract_daqprj("junk <daqprj>x</DAQPRJ> more"), "<daqprj>x</DAQPRJ>")
        self.assertEqual(extract_daqprj("  no block  "), "no block")


class CustomLayoutTest(unittest.TestCase):
    LINE = ("7", "63.9", "13.31", "1", "8")

    def test_exact_fit(self) -> None:
        self.assertEqual(parse_custom_daqprj(SMALL, self.LINE).digital_words, 2)

    def test_unnamed_status_words_are_accepted(self) -> None:
        self.assertEqual(parse_custom_daqprj(SMALL, (*self.LINE, "0")).digital_words, 3)
        self.assertEqual(parse_custom_daqprj(SMALL, (*self.LINE, "0", "2007")).value_count, 7)

    def test_wrong_length_is_rejected(self) -> None:
        for line in (self.LINE[:4], (*self.LINE, "0", "0", "0"), ("1",) * 120):
            with self.subTest(count=len(line)), self.assertRaises(LayoutError) as caught:
                parse_custom_daqprj(SMALL, line)
            self.assertEqual(caught.exception.reason, "count_mismatch")

    def test_surplus_is_only_accepted_if_the_line_follows_the_definition(self) -> None:
        # One value more, but the line is shifted against the definition: the channel
        # declared with two decimals does not have them.
        with self.assertRaises(LayoutError) as caught:
            parse_custom_daqprj(SMALL, ("7", "63.9", "20.5", "13.31", "1", "8"))
        self.assertEqual(caught.exception.reason, "count_mismatch")


class BuiltinLayoutTest(unittest.TestCase):
    def test_all_layouts_parse_with_stable_value_counts(self) -> None:
        layouts = builtin_layouts()
        self.assertEqual({key: layout.value_count for key, layout in layouts.items()}, VALUE_COUNTS)
        for key, layout in layouts.items():
            with self.subTest(layout=key):
                self.assertEqual(layout.key, key)
                self.assertIn(f"({layout.value_count} values)", layout.title)
                self.assertEqual(len({c.key for c in layout.analog}), len(layout.analog))
                self.assertEqual(len({c.key for c in layout.digital}), len(layout.digital))
                self.assertTrue(all(c.key for c in layout.analog + layout.digital))

    def test_every_layout_has_the_essential_channels(self) -> None:
        without_fault_number = set()
        for key, layout in builtin_layouts().items():
            with self.subTest(layout=key):
                for name in ("ZK", "TK", "TRG", "Taus", "Verbrauchszähler", "TVL_1", "TB1"):
                    self.assertIsNotNone(layout.find_analog(name), name)
                self.assertIsNotNone(layout.find_digital("Störung"))
                self.assertIsNotNone(layout.find_digital("HKP1"))
            if layout.find_analog("Störungs Nr") is None:
                without_fault_number.add(key)
        # This old layout only has the fault bit.
        self.assertEqual(without_fault_number, {"hsv_classic_v14_0_d"})

    def test_definitions_are_written_one_channel_per_line(self) -> None:
        for key, (_title, definition) in BUILTIN_LAYOUTS.items():
            with self.subTest(layout=key):
                self.assertEqual(definition.count("<CHANNEL "), definition.count("/>\n"))

    def test_nano2_positions(self) -> None:
        layout = builtin_layouts()["nano2_124"]
        # Position in the line (1 = first value after "pm") as verified on the boiler.
        positions = {
            "ZK": 1, "O2": 2, "TK": 4, "TKsoll": 5, "TRL": 6, "TRG": 9, "SZist": 10, "TPo": 12, "TPm": 13,
            "TPu": 14, "Puff Füllgrad": 15, "Puffer_soll oben": 16, "Leistung": 21, "Störungs Nr": 31,
            "Lagerstand": 44, "Verbrauchszähler": 45, "BRT": 52, "Taus": 57, "TA Gem.": 58, "TVL_1": 69,
            "TVLs_1": 70, "TB1": 92,
        }  # fmt: skip
        for name, position in positions.items():
            self.assertEqual(layout.find_analog(name).index + 1, position, name)
        self.assertEqual(len(layout.analog), 116)
        self.assertEqual((layout.find_digital("Störung").word, layout.find_digital("Störung").bit), (0, 0))
        self.assertEqual((layout.find_digital("HKP1").word, layout.find_digital("HKP1").bit), (2, 3))
        self.assertEqual((layout.find_digital("RLP/PuffP").word, layout.find_digital("RLP/PuffP").bit), (0, 3))


class DetectionTest(unittest.TestCase):
    def test_recorded_lines_are_detected_as_nano2(self) -> None:
        for line in NANO2_LINES:
            layout = detect_layout(values(line))
            self.assertIsNotNone(layout)
            self.assertEqual(layout.key, "nano2_124")
            self.assertEqual(layout.check(values(line)), [])

    def test_unknown_length_is_not_detected(self) -> None:
        self.assertIsNone(detect_layout(("1", "2", "3")))
        self.assertEqual(matching_layouts(("1", "2", "3")), [])

    def test_layouts_with_equal_length_are_told_apart_by_format(self) -> None:
        # Both layouts have 120 values. A line of the factory Nano.2 layout must not be
        # accepted as the V14.0HAR.q layout, whose channels are shifted.
        layouts = builtin_layouts()
        nano2, other = layouts["nano2_v14_1_q1"], layouts["nano_pk_v14_0_q"]
        self.assertEqual(nano2.value_count, other.value_count)
        line = []
        for channel in nano2.analog:
            line.append({0: "12", 2: "1.25"}.get(channel.decimals, "20.5"))
        line += ["406", "1", "8", "0", "2007", "0", "0", "0"]
        self.assertEqual(nano2.check(line), [])
        self.assertNotEqual(other.check(line), [])
        self.assertEqual(detect_layout(line).key, "nano2_v14_1_q1")
        matches = matching_layouts(line)
        self.assertEqual([layout.key for layout, _ in matches], ["nano2_v14_1_q1", "nano_pk_v14_0_q"])


if __name__ == "__main__":
    unittest.main()
