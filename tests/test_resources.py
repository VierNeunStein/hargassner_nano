"""Consistency checks for translations, icons and the manifest."""

from __future__ import annotations

import json
import re
import unittest

from custom_components.hargassner_nano.model import BINARY_SENSORS, BOILER_STATES, PELLET_ENERGY_KEY, SENSORS

from . import COMPONENT_DIR, ROOT

PLACEHOLDER = re.compile(r"\{(\w+)\}")
# hassfest rejects translation strings that look like HTML.
HTML = re.compile(r"<[a-z].*?>", re.IGNORECASE)


def load(name: str) -> dict:
    return json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))


def flatten(node: object, prefix: str = "") -> dict[str, str]:
    if isinstance(node, dict):
        result: dict[str, str] = {}
        for key, value in node.items():
            result.update(flatten(value, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: node}


class TranslationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.en = flatten(load("translations/en.json"))
        cls.de = flatten(load("translations/de.json"))

    def test_languages_have_the_same_keys(self) -> None:
        self.assertEqual(sorted(self.en), sorted(self.de))

    def test_placeholders_match(self) -> None:
        for key, text in self.en.items():
            self.assertEqual(
                sorted(PLACEHOLDER.findall(text)), sorted(PLACEHOLDER.findall(self.de[key])), key
            )

    def test_strings_are_plain_text(self) -> None:
        for language in (self.en, self.de):
            for key, text in language.items():
                self.assertIsInstance(text, str, key)
                self.assertTrue(text.strip(), key)
                self.assertIsNone(HTML.search(text), key)
                self.assertNotIn("'{", text, key)  # hassfest: no single-quoted placeholders

    def test_every_entity_has_a_name(self) -> None:
        for platform, specs in (("sensor", SENSORS), ("binary_sensor", BINARY_SENSORS)):
            for spec in specs:
                key = f"entity.{platform}.{spec.name_key}.name"
                self.assertIn(key, self.en, spec.key)
                has_placeholder = "{circuit}" in self.en[key]
                self.assertEqual(has_placeholder, spec.circuit is not None, spec.key)
        self.assertIn(f"entity.sensor.{PELLET_ENERGY_KEY}.name", self.en)

    def test_no_unused_entity_names(self) -> None:
        used = {f"sensor.{spec.name_key}" for spec in SENSORS}
        used |= {f"binary_sensor.{spec.name_key}" for spec in BINARY_SENSORS}
        used.add(f"sensor.{PELLET_ENERGY_KEY}")
        translated = {".".join(key.split(".")[1:3]) for key in self.en if key.startswith("entity.")}
        self.assertEqual(translated, used)

    def test_every_boiler_state_is_translated(self) -> None:
        states = {key.rsplit(".", 1)[1] for key in self.en if key.startswith("entity.sensor.state.state.")}
        self.assertEqual(states, set(BOILER_STATES.values()))

    def test_config_flow_texts_exist(self) -> None:
        source = (COMPONENT_DIR / "config_flow.py").read_text(encoding="utf-8")
        for step in re.findall(r'step_id="(\w+)"', source):
            section = "options" if step == "init" else "config"
            self.assertIn(f"{section}.step.{step}.title", self.en, step)
        for step in ("user", "reconfigure", "layout", "custom", "confirm"):
            self.assertIn(f"config.step.{step}.description", self.en)
        for option in ("finish", "layout", "custom"):
            self.assertIn(f"config.step.confirm.menu_options.{option}", self.en)
            self.assertIn(f"async def async_step_{option}(", source)
        for error in re.findall(r'"(cannot_connect|no_telegram|invalid_daqprj|count_mismatch)"', source):
            self.assertIn(f"config.error.{error}", self.en)
        for reason in ("already_configured", "reconfigure_successful"):
            self.assertIn(f"config.abort.{reason}", self.en)
        for option in ("scan_interval", "pellet_energy", "raw_channels"):
            self.assertIn(f"options.step.init.data.{option}", self.en)

    def test_issue_texts_exist(self) -> None:
        source = (COMPONENT_DIR / "coordinator.py").read_text(encoding="utf-8")
        (key,) = set(re.findall(r'translation_key="(\w+)"', source))
        self.assertIn(f"issues.{key}.title", self.en)
        placeholders = set(PLACEHOLDER.findall(self.en[f"issues.{key}.title"] + self.en[f"issues.{key}.description"]))
        self.assertEqual(placeholders, {"name", "expected", "received"})


class IconTest(unittest.TestCase):
    def test_icons_belong_to_translated_entities(self) -> None:
        icons = flatten(load("icons.json"))
        names = flatten(load("translations/en.json"))
        for key, icon in icons.items():
            self.assertRegex(icon, r"^mdi:[a-z0-9-]+$", key)
            platform, entity = key.split(".")[1:3]
            self.assertIn(f"entity.{platform}.{entity}.name", names, key)


class ManifestTest(unittest.TestCase):
    def test_manifest(self) -> None:
        manifest = load("manifest.json")
        self.assertEqual(manifest["domain"], "hargassner_nano")
        self.assertEqual(COMPONENT_DIR.name, manifest["domain"])
        # hassfest: domain and name first, the rest in alphabetical order
        keys = list(manifest)
        self.assertEqual(keys[:2], ["domain", "name"])
        self.assertEqual(keys[2:], sorted(keys[2:]))
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["requirements"], [])

    def test_changelog_mentions_the_version(self) -> None:
        version = load("manifest.json")["version"]
        self.assertIn(f"## {version}", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
