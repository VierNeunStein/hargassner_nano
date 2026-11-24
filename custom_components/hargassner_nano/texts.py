"""Texts that are produced in Python: fault descriptions and the setup preview.

This module does not depend on Home Assistant. Entity names and states are translated
in ``translations/``; the texts here end up inside a state or a description, where
Home Assistant offers no translation, so they follow the language of the server.
"""

from __future__ import annotations

from .layout import Layout, Telegram
from .model import Kind, resolve_sensors, sensor_value

GERMAN = "de"
ENGLISH = "en"

# Fault number -> (German, English). The numbers and German texts follow the fault list
# of the boiler's display as collected by the projects nano_pk and
# IP-HargassnerIntegration. Unknown numbers are shown as "Störung Nr. X".
ERROR_TEXTS: dict[int, tuple[str, str]] = {
    1: ("Übertemperatur, STB gefallen", "Overtemperature, safety limiter tripped"),
    2: ("Überstrom Einschubschnecke", "Overcurrent feed screw"),
    3: ("Überstrom Raumaustragungsschnecke 1", "Overcurrent storage room screw 1"),
    4: ("Thermoschutz Raumaustragungsschnecke 1", "Thermal protection storage room screw 1"),
    5: ("Aschelade entleeren", "Empty the ash drawer"),
    6: ("Aschelade zu voll", "Ash drawer too full"),
    7: ("Schieberost öffnet nicht", "Grate does not open"),
    8: ("Schieberost schließt nicht", "Grate does not close"),
    9: ("Überstrom Putzeinrichtung", "Overcurrent cleaning device"),
    10: ("Rauchgasfühler falsch angeschlossen", "Flue gas sensor connected incorrectly"),
    11: ("Rauchgasfühler Unterbrechung", "Flue gas sensor open circuit"),
    12: ("Kesselfühler Kurzschluss", "Boiler sensor short circuit"),
    13: ("Kesselfühler Unterbrechung", "Boiler sensor open circuit"),
    14: ("Boilerfühler 1 Kurzschluss", "Hot water sensor 1 short circuit"),
    15: ("Boilerfühler 1 Unterbrechung", "Hot water sensor 1 open circuit"),
    16: ("Außenfühler Kurzschluss", "Outside sensor short circuit"),
    17: ("Außenfühler Unterbrechung", "Outside sensor open circuit"),
    18: ("Vorlauffühler HK1 Kurzschluss", "Flow sensor heating circuit 1 short circuit"),
    19: ("Vorlauffühler HK1 Unterbrechung", "Flow sensor heating circuit 1 open circuit"),
    20: ("Vorlauffühler HK2 Kurzschluss", "Flow sensor heating circuit 2 short circuit"),
    21: ("Vorlauffühler HK2 Unterbrechung", "Flow sensor heating circuit 2 open circuit"),
    22: ("Raumfühler HK1 Kurzschluss", "Room sensor heating circuit 1 short circuit"),
    23: ("Raumfühler HK1 Unterbrechung", "Room sensor heating circuit 1 open circuit"),
    24: ("Raumfühler HK2 Kurzschluss", "Room sensor heating circuit 2 short circuit"),
    25: ("Raumfühler HK2 Unterbrechung", "Room sensor heating circuit 2 open circuit"),
    26: ("Zündzeit überschritten", "Ignition time exceeded"),
    27: ("Rauchgastemperatur unterschritten", "Flue gas temperature too low"),
    28: ("Anlage zu lange auf O2-Stopp", "O2 stop for too long"),
    29: ("Verbrennungsstörung", "Combustion fault"),
    30: ("Batterie leer", "Battery empty"),
    31: ("Blockade Einschubmotor", "Feed motor blocked"),
    32: ("Füllzeit überschritten", "Filling time exceeded"),
    33: ("Putzeinrichtung nicht in Ruhelage", "Cleaning device not in rest position"),
    34: ("Pufferfühler oben Kurzschluss", "Buffer sensor top short circuit"),
    35: ("Pufferfühler oben Unterbrechung", "Buffer sensor top open circuit"),
    36: ("Pufferfühler unten Kurzschluss", "Buffer sensor bottom short circuit"),
    37: ("Pufferfühler unten Unterbrechung", "Buffer sensor bottom open circuit"),
    38: ("Überstrom Schieberost", "Overcurrent grate"),
    39: ("Boilerfühler 2 Kurzschluss", "Hot water sensor 2 short circuit"),
    40: ("Boilerfühler 2 Unterbrechung", "Hot water sensor 2 open circuit"),
    41: ("Aschebox fast voll", "Ash box almost full"),
    42: ("Überstrom Ascheschnecke", "Overcurrent ash screw"),
    43: ("Ascheaustragung nicht angeschlossen", "Ash discharge not connected"),
    45: ("Rücklaufanhebung: Temperatur nicht erreicht", "Return temperature not reached"),
    46: ("Rücklauffühler Kurzschluss", "Return sensor short circuit"),
    47: ("Rücklauffühler Unterbrechung", "Return sensor open circuit"),
    49: ("Saugzuggebläse Störung", "Induced draft fan fault"),
    50: ("Zeitüberschreitung Füllvorgang", "Filling timed out"),
    52: ("Fremdwärmefühler Kurzschluss", "External heat sensor short circuit"),
    53: ("Fremdwärmefühler Unterbrechung", "External heat sensor open circuit"),
    54: ("Pufferfühler Mitte Kurzschluss", "Buffer sensor middle short circuit"),
    55: ("Pufferfühler Mitte Unterbrechung", "Buffer sensor middle open circuit"),
    70: ("Pelletslagerstand niedrig", "Pellet stock low"),
    89: ("Schieberost schwergängig", "Grate hard to move"),
    90: ("Kessel-IO nicht angeschlossen", "Boiler IO board not connected"),
    91: ("Max. Platinentemperatur überschritten", "Board temperature too high"),
    92: ("Lambdasonde nicht angeschlossen oder defekt", "Lambda probe not connected or defective"),
    93: ("Aschelade offen", "Ash drawer open"),
    94: ("Betriebsart Aus, Frostschutz nicht gewährleistet", "Mode Off, no frost protection"),
    96: ("Spannung Netzteil kontrollieren", "Check the power supply voltage"),
    99: ("Kessel Übertemperatur", "Boiler overtemperature"),
    155: ("Spülung defekt", "Flushing defective"),
    190: ("Verbrennung überprüfen, O2-Sollwert nicht erreicht", "Check combustion, O2 target not reached"),
    196: ("Ausbrand mehrmals nicht vollständig ausgeführt", "Burn-out repeatedly incomplete"),
    227: ("Lagerraumschalter aus", "Storage room switch off"),
    228: ("Pelletsbehälter fast leer", "Pellet hopper almost empty"),
    229: ("Füllstandsmelder kontrollieren", "Check the fill level sensor"),
    314: ("Ascheschnecke blockiert", "Ash screw blocked"),
    332: ("Lagerraumschalter betätigt", "Storage room switch actuated"),
    371: ("Brennraum prüfen", "Check the combustion chamber"),
    380: ("Wartung fällig", "Service due"),
    381: ("Laufzeit Saugturbine: Schleifkohlen tauschen", "Suction turbine runtime: replace carbon brushes"),
}

_NO_ERROR = ("Keine Störung", "No fault")
_UNKNOWN_ERROR = ("Störung Nr. {}", "Fault no. {}")

_STATE_NAMES: dict[str, tuple[str, str]] = {
    "off": ("Aus", "Off"),
    "start_preparation": ("Startvorbereitung", "Preparing start"),
    "boiler_start": ("Kessel Start", "Boiler start"),
    "ignition_monitoring": ("Zündüberwachung", "Monitoring ignition"),
    "ignition": ("Zündung", "Ignition"),
    "transition_full_firing": ("Übergang Leistungsbrand", "Transition to full firing"),
    "full_firing": ("Leistungsbrand", "Full firing"),
    "ember_preservation": ("Gluterhaltung", "Ember preservation"),
    "waiting_ash_removal": ("Warten auf Entaschung", "Waiting for ash removal"),
    "ash_removal": ("Entaschung", "Ash removal"),
    "cleaning": ("Putzen", "Cleaning"),
}

# Sensors shown when the user is asked whether the values look right: key -> (German, English).
_PREVIEW: dict[str, tuple[str, str]] = {
    "state": ("Betriebszustand", "Boiler state"),
    "boiler_temp": ("Kesseltemperatur", "Boiler temperature"),
    "flue_temp": ("Abgastemperatur", "Flue gas temperature"),
    "outdoor_temp": ("Außentemperatur", "Outside temperature"),
    "flow_temp": ("Vorlauf Heizkreis 1", "Flow heating circuit 1"),
    "buffer_temp_top": ("Puffer oben", "Buffer top"),
    "dhw_temp": ("Boiler (Warmwasser)", "Hot water tank"),
    "pellet_silo": ("Pelletlagerstand", "Pellet stock"),
    "pellet_consumption_total": ("Pelletverbrauch gesamt", "Pellet consumption, total"),
}
_PREVIEW_UNITS = {
    Kind.TEMPERATURE: "°C",
    Kind.PERCENT: "%",
    Kind.WEIGHT: "kg",
    Kind.WEIGHT_TOTAL: "kg",
}
_NOT_INSTALLED = ("nicht angeschlossen", "not installed")
_UNKNOWN_STATE = ("unbekannt ({})", "unknown ({})")


def _index(language: str | None) -> int:
    return 0 if (language or "").lower().startswith(GERMAN) else 1


def error_text(code: int | None, language: str | None) -> str | None:
    """Return the description of a fault number in German or English."""
    if code is None:
        return None
    index = _index(language)
    if code == 0:
        return _NO_ERROR[index]
    if code in ERROR_TEXTS:
        return ERROR_TEXTS[code][index]
    return _UNKNOWN_ERROR[index].format(code)


def state_text(state: str, language: str | None) -> str:
    """Return the name of a boiler state in German or English."""
    return _STATE_NAMES[state][_index(language)]


def preview_lines(layout: Layout, telegram: Telegram, language: str | None) -> list[str]:
    """Return a few decoded values as 'label: value' lines for the setup dialog."""
    index = _index(language)
    lines: list[str] = []
    for item in resolve_sensors(layout):
        label = _PREVIEW.get(item.spec.key)
        if label is None:
            continue
        value = sensor_value(item.spec, item.channel, telegram)
        if item.spec.kind is Kind.STATE:
            raw = telegram.analog.get(item.channel.key)
            text = state_text(value, language) if isinstance(value, str) else _UNKNOWN_STATE[index].format(raw)
        elif value is None:
            text = _NOT_INSTALLED[index]
        else:
            text = f"{value} {_PREVIEW_UNITS[item.spec.kind]}"
        lines.append(f"{label[index]}: {text}")
    return lines
