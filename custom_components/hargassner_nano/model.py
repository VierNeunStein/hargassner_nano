"""Which entities exist for a layout and how their values are derived.

This module does not depend on Home Assistant. The sensor platforms only translate the
specifications below into entities.

Entity keys are part of the unique ids. Never rename a key.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .layout import AnalogChannel, DigitalChannel, Layout, Telegram

# Values the boiler reports for a temperature probe that is not installed.
NOT_CONNECTED = (-20.0, 120.0, 140.0)

# Value of the channel "ZK" -> state of the boiler.
BOILER_STATES: dict[int, str] = {
    1: "off",
    2: "start_preparation",
    3: "boiler_start",
    4: "ignition_monitoring",
    5: "ignition",
    6: "transition_full_firing",
    7: "full_firing",
    8: "ember_preservation",
    9: "waiting_ash_removal",
    10: "ash_removal",
    12: "cleaning",
}

ERROR_CHANNELS = ("Störungs Nr",)
CONSUMPTION_CHANNELS = ("Verbrauchszähler",)
PELLET_ENERGY_KEY = "pellet_energy_total"
RAW_PREFIX = "raw_"

# Heating circuits as the boiler numbers them.
CIRCUITS = ("A", "1", "2", "3", "4", "5", "6", "B")


class Kind(StrEnum):
    """What a sensor measures."""

    STATE = "state"
    ERROR = "error"
    TEMPERATURE = "temperature"
    PERCENT = "percent"
    WEIGHT = "weight"
    WEIGHT_TOTAL = "weight_total"


class BinaryKind(StrEnum):
    """What a binary sensor signals."""

    PROBLEM = "problem"
    RUNNING = "running"


@dataclass(frozen=True, slots=True)
class SensorSpec:
    """A sensor that is created if one of its channels exists in the layout."""

    key: str
    kind: Kind
    channels: tuple[str, ...]
    translation_key: str = ""
    enabled: bool = True
    # Report the "probe not installed" values as unknown.
    check_connected: bool = False
    # Probes that must be installed for the entity to be enabled by default.
    presence: tuple[str, ...] = ()
    circuit: str | None = None
    diagnostic: bool = False

    @property
    def name_key(self) -> str:
        """Key of the entity name in the translation files."""
        return self.translation_key or self.key


@dataclass(frozen=True, slots=True)
class BinarySpec:
    """A binary sensor that is created if one of its channels exists in the layout."""

    key: str
    kind: BinaryKind
    channels: tuple[str, ...]
    translation_key: str = ""
    enabled: bool = True
    presence: tuple[str, ...] = ()
    circuit: str | None = None

    @property
    def name_key(self) -> str:
        """Key of the entity name in the translation files."""
        return self.translation_key or self.key


def _circuit_sensors(circuit: str) -> tuple[SensorSpec, ...]:
    # Circuit 1 keeps the keys it had before other circuits were supported.
    prefix = f"hc{circuit.lower()}"
    flow = f"TVL_{circuit}"
    return (
        SensorSpec(
            "flow_temp" if circuit == "1" else f"{prefix}_flow_temp",
            Kind.TEMPERATURE,
            (flow,),
            translation_key="hc_flow_temp",
            check_connected=True,
            presence=(flow,),
            circuit=circuit,
        ),
        SensorSpec(
            "flow_setpoint" if circuit == "1" else f"{prefix}_flow_setpoint",
            Kind.TEMPERATURE,
            (f"TVLs_{circuit}",),
            translation_key="hc_flow_setpoint",
            presence=(flow,),
            circuit=circuit,
        ),
        # Without a room unit the boiler reports a constant 20 °C.
        SensorSpec(
            f"{prefix}_room_temp",
            Kind.TEMPERATURE,
            (f"TRA_{circuit}", f"TR{circuit}"),
            translation_key="hc_room_temp",
            enabled=False,
            circuit=circuit,
        ),
        SensorSpec(
            f"{prefix}_room_setpoint",
            Kind.TEMPERATURE,
            (f"TRs_{circuit}",),
            translation_key="hc_room_setpoint",
            enabled=False,
            circuit=circuit,
        ),
    )


SENSORS: tuple[SensorSpec, ...] = (
    # Boiler
    SensorSpec("state", Kind.STATE, ("ZK",)),
    SensorSpec("error_number", Kind.ERROR, ERROR_CHANNELS, translation_key="error", diagnostic=True),
    SensorSpec("output", Kind.PERCENT, ("Leistung",)),
    SensorSpec("o2", Kind.PERCENT, ("O2",)),
    SensorSpec("draft_fan", Kind.PERCENT, ("SZist", "SZ"), enabled=False),
    SensorSpec("boiler_temp", Kind.TEMPERATURE, ("TK",)),
    SensorSpec("boiler_setpoint", Kind.TEMPERATURE, ("TKsoll",)),
    SensorSpec("return_temp", Kind.TEMPERATURE, ("TRL",)),
    SensorSpec("flue_temp", Kind.TEMPERATURE, ("TRG",)),
    SensorSpec("combustion_temp", Kind.TEMPERATURE, ("BRT",)),
    # Outside
    SensorSpec("outdoor_temp", Kind.TEMPERATURE, ("Taus",)),
    SensorSpec("outdoor_temp_avg", Kind.TEMPERATURE, ("TA Gem.",), enabled=False),
    # Buffer
    SensorSpec("buffer_temp_top", Kind.TEMPERATURE, ("TPo",), check_connected=True, presence=("TPo",)),
    SensorSpec("buffer_temp_mid", Kind.TEMPERATURE, ("TPm",), check_connected=True, presence=("TPm",)),
    SensorSpec("buffer_temp_bot", Kind.TEMPERATURE, ("TPu",), check_connected=True, presence=("TPu",)),
    SensorSpec("buffer_fill", Kind.PERCENT, ("Puff Füllgrad",), presence=("TPo",)),
    SensorSpec("buffer_setpoint", Kind.TEMPERATURE, ("Puffer_soll oben", "Puffer_soll"), enabled=False),
    # Domestic hot water
    SensorSpec("dhw_temp", Kind.TEMPERATURE, ("TB1",), check_connected=True, presence=("TB1",)),
    # Pellets
    SensorSpec("pellet_silo", Kind.WEIGHT, ("Lagerstand",)),
    SensorSpec("pellet_consumption_total", Kind.WEIGHT_TOTAL, CONSUMPTION_CHANNELS),
    # Heating circuits
    *(spec for circuit in CIRCUITS for spec in _circuit_sensors(circuit)),
)

BINARY_SENSORS: tuple[BinarySpec, ...] = (
    BinarySpec("error_status", BinaryKind.PROBLEM, ("Störung",)),
    BinarySpec("buffer_pump", BinaryKind.RUNNING, ("RLP/PuffP",)),
    BinarySpec("dhw_pump", BinaryKind.RUNNING, ("BP1",), presence=("TB1",)),
    *(
        BinarySpec(
            "hk1_pump" if circuit == "1" else f"hc{circuit.lower()}_pump",
            BinaryKind.RUNNING,
            (f"HKP{circuit}",),
            translation_key="hc_pump",
            # Circuit 1 exists on practically every boiler, also without a flow probe.
            presence=() if circuit == "1" else (f"TVL_{circuit}",),
            circuit=circuit,
        )
        for circuit in CIRCUITS
    ),
)


@dataclass(frozen=True, slots=True)
class ResolvedSensor:
    """A sensor specification bound to the channel of a layout."""

    spec: SensorSpec
    channel: AnalogChannel


@dataclass(frozen=True, slots=True)
class ResolvedBinary:
    """A binary sensor specification bound to the bit of a layout.

    ``channel`` is None for the fault sensor of a layout without a fault bit; it is then
    derived from the fault number alone.
    """

    spec: BinarySpec
    channel: DigitalChannel | None


def resolve_sensors(layout: Layout) -> list[ResolvedSensor]:
    """Return the sensors that can be read from a layout."""
    resolved: list[ResolvedSensor] = []
    for spec in SENSORS:
        if (channel := layout.find_analog(*spec.channels)) is not None:
            resolved.append(ResolvedSensor(spec, channel))
    return resolved


def resolve_binary_sensors(layout: Layout) -> list[ResolvedBinary]:
    """Return the binary sensors that can be read from a layout."""
    has_error_number = layout.find_analog(*ERROR_CHANNELS) is not None
    resolved: list[ResolvedBinary] = []
    for spec in BINARY_SENSORS:
        # The status words have bits for more heating circuits than a boiler supports.
        # A pump is only offered if the layout also has the values of its circuit.
        if any(layout.find_analog(name) is None for name in spec.presence):
            continue
        channel = layout.find_digital(*spec.channels)
        if channel is not None or (spec.kind is BinaryKind.PROBLEM and has_error_number):
            resolved.append(ResolvedBinary(spec, channel))
    return resolved


def raw_analog_channels(layout: Layout) -> list[AnalogChannel]:
    """Return the analog channels that no sensor above uses."""
    used = {item.channel.key for item in resolve_sensors(layout)}
    return [channel for channel in layout.analog if channel.key not in used and not channel.is_placeholder]


def raw_digital_channels(layout: Layout) -> list[DigitalChannel]:
    """Return the status bits that no binary sensor above uses."""
    used = {item.channel.key for item in resolve_binary_sensors(layout) if item.channel is not None}
    return [channel for channel in layout.digital if channel.key not in used and not channel.is_placeholder]


def has_pellet_energy(layout: Layout) -> bool:
    """Return True if the layout has the pellet counter the energy sensor is based on."""
    return layout.find_analog(*CONSUMPTION_CHANNELS) is not None


def entity_keys(layout: Layout, *, raw_channels: bool) -> set[str]:
    """Return the keys of all entities the integration creates for a layout."""
    keys = {item.spec.key for item in resolve_sensors(layout)}
    keys.update(item.spec.key for item in resolve_binary_sensors(layout))
    if has_pellet_energy(layout):
        keys.add(PELLET_ENERGY_KEY)
    if raw_channels:
        keys.update(RAW_PREFIX + channel.key for channel in raw_analog_channels(layout))
        keys.update(RAW_PREFIX + channel.key for channel in raw_digital_channels(layout))
    return keys


def is_connected(value: float | None) -> bool:
    """Return False if a temperature value means 'probe not installed'."""
    return value is not None and float(value) not in NOT_CONNECTED


def sensor_value(spec: SensorSpec, channel: AnalogChannel, telegram: Telegram) -> float | int | str | None:
    """Return the state of a sensor.

    For ``Kind.ERROR`` this is the fault number; the text belongs to the platform.
    """
    value = telegram.analog.get(channel.key)
    if value is None:
        return None
    if spec.kind is Kind.STATE:
        return BOILER_STATES.get(int(value))
    if spec.kind in (Kind.ERROR, Kind.WEIGHT, Kind.WEIGHT_TOTAL):
        return int(value)
    if spec.check_connected and not is_connected(value):
        return None
    return value


def error_code(layout: Layout, telegram: Telegram) -> int | None:
    """Return the current fault number (0 = no fault), or None if it is not available."""
    channel = layout.find_analog(*ERROR_CHANNELS)
    if channel is None:
        return None
    value = telegram.analog.get(channel.key)
    return None if value is None else int(value)


def binary_value(item: ResolvedBinary, layout: Layout, telegram: Telegram) -> bool | None:
    """Return the state of a binary sensor."""
    state = telegram.digital.get(item.channel.key) if item.channel is not None else None
    if item.spec.kind is BinaryKind.PROBLEM:
        # A fault number counts as a problem even if the fault bit is not set.
        code = error_code(layout, telegram)
        if code:
            return True
        if state is None and code is not None:
            return False
    return state


def enabled_by_default(spec: SensorSpec | BinarySpec, layout: Layout, telegram: Telegram | None) -> bool:
    """Return True if an entity should be enabled when it is first created.

    Entities of parts that are not installed (second heating circuit, buffer, hot water
    tank) are created disabled, judged by the probe values of the first telegram.
    """
    if not spec.enabled:
        return False
    if telegram is None:
        return not spec.presence
    for name in spec.presence:
        channel = layout.find_analog(name)
        if channel is None or not is_connected(telegram.analog.get(channel.key)):
            return False
    return True
