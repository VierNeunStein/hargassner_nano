"""Sensors of the Hargassner integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import callback

from .const import CONF_PELLET_ENERGY, CONF_RAW_CHANNELS, DEFAULT_PELLET_ENERGY
from .entity import HargassnerEntity
from .model import (
    BOILER_STATES,
    CONSUMPTION_CHANNELS,
    PELLET_ENERGY_KEY,
    RAW_PREFIX,
    Kind,
    ResolvedSensor,
    enabled_by_default,
    raw_analog_channels,
    resolve_sensors,
    sensor_value,
)
from .texts import error_text

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import HargassnerConfigEntry, HargassnerCoordinator
    from .layout import AnalogChannel

# The coordinator reads the boiler; the entities only pick their value.
PARALLEL_UPDATES = 0

ATTR_CODE = "code"
ATTR_PELLET_COUNTER = "pellet_counter"
ATTR_ENERGY_PER_KG = "energy_per_kg"

# Unit of a channel in the boiler's own description -> (device class, unit, state class)
_MEASUREMENT = SensorStateClass.MEASUREMENT
_RAW_UNITS: dict[str, tuple[SensorDeviceClass | None, str, SensorStateClass]] = {
    "°C": (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, _MEASUREMENT),
    "%": (None, PERCENTAGE, _MEASUREMENT),
    "mA": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.MILLIAMPERE, _MEASUREMENT),
    "V": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, _MEASUREMENT),
    "mV": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.MILLIVOLT, _MEASUREMENT),
    "W": (SensorDeviceClass.POWER, UnitOfPower.WATT, _MEASUREMENT),
    "kW": (SensorDeviceClass.POWER, UnitOfPower.KILO_WATT, _MEASUREMENT),
    "KW": (SensorDeviceClass.POWER, UnitOfPower.KILO_WATT, _MEASUREMENT),
    "kWh": (SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, SensorStateClass.TOTAL_INCREASING),
    "kg": (SensorDeviceClass.WEIGHT, UnitOfMass.KILOGRAMS, _MEASUREMENT),
    "Min": (SensorDeviceClass.DURATION, UnitOfTime.MINUTES, _MEASUREMENT),
    "h": (SensorDeviceClass.DURATION, UnitOfTime.HOURS, _MEASUREMENT),
    "bar": (SensorDeviceClass.PRESSURE, UnitOfPressure.BAR, _MEASUREMENT),
    "mm": (SensorDeviceClass.DISTANCE, UnitOfLength.MILLIMETERS, _MEASUREMENT),
    "rpm": (None, REVOLUTIONS_PER_MINUTE, _MEASUREMENT),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HargassnerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensors the boiler's layout provides."""
    coordinator = entry.runtime_data
    layout = coordinator.layout

    entities: list[SensorEntity] = [HargassnerSensor(coordinator, item) for item in resolve_sensors(layout)]
    if (counter := layout.find_analog(*CONSUMPTION_CHANNELS)) is not None:
        energy_per_kg = float(entry.options.get(CONF_PELLET_ENERGY, DEFAULT_PELLET_ENERGY))
        entities.append(HargassnerPelletEnergySensor(coordinator, counter, energy_per_kg))
    if entry.options.get(CONF_RAW_CHANNELS, False):
        entities.extend(HargassnerRawSensor(coordinator, channel) for channel in raw_analog_channels(layout))
    async_add_entities(entities)


class HargassnerSensor(HargassnerEntity, SensorEntity):
    """A named value of the boiler, e.g. the boiler temperature."""

    def __init__(self, coordinator: HargassnerCoordinator, item: ResolvedSensor) -> None:
        """Initialize the sensor."""
        spec = item.spec
        super().__init__(coordinator, spec.key)
        self._spec = spec
        self._channel = item.channel

        self._attr_translation_key = spec.name_key
        if spec.circuit is not None:
            self._attr_translation_placeholders = {"circuit": spec.circuit}
        self._attr_entity_registry_enabled_default = enabled_by_default(spec, coordinator.layout, coordinator.data)
        if spec.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        if spec.kind is Kind.STATE:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(BOILER_STATES.values())
        elif spec.kind is Kind.TEMPERATURE:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
        elif spec.kind is Kind.PERCENT:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif spec.kind is Kind.WEIGHT:
            self._attr_device_class = SensorDeviceClass.WEIGHT
            self._attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 0
        elif spec.kind is Kind.WEIGHT_TOTAL:
            self._attr_device_class = SensorDeviceClass.WEIGHT
            self._attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value."""
        value = sensor_value(self._spec, self._channel, self.coordinator.data)
        if self._spec.kind is Kind.ERROR:
            # The fault text is free text, so it follows the language of the server.
            return error_text(value if isinstance(value, int) else None, self.hass.config.language)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the number behind the state and fault texts."""
        if self._spec.kind not in (Kind.STATE, Kind.ERROR):
            return None
        return {ATTR_CODE: self.coordinator.data.analog.get(self._channel.key)}


class HargassnerPelletEnergySensor(HargassnerEntity, RestoreSensor):
    """Energy content of the pellets burnt, for the energy dashboard.

    The boiler counts kilograms. The sensor adds up the increase of that counter times
    the energy content of pellets. Because it accumulates, changing the energy content
    later only affects pellets burnt from then on and does not distort the statistics.
    """

    _attr_translation_key = PELLET_ENERGY_KEY
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: HargassnerCoordinator, channel: AnalogChannel, energy_per_kg: float) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, PELLET_ENERGY_KEY)
        self._channel = channel
        self._energy_per_kg = energy_per_kg
        self._energy: float | None = None
        self._counter: int | None = None

    async def async_added_to_hass(self) -> None:
        """Continue with the total and counter reading from before the restart."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        last_state = await self.async_get_last_state()
        if last_data is not None and last_data.native_value is not None:
            try:
                self._energy = float(last_data.native_value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                self._energy = None
        if self._energy is not None and last_state is not None:
            counter = last_state.attributes.get(ATTR_PELLET_COUNTER)
            if isinstance(counter, (int, float)):
                self._counter = int(counter)
        self._accumulate()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Add the pellets burnt since the previous reading."""
        self._accumulate()
        super()._handle_coordinator_update()

    def _accumulate(self) -> None:
        value = self.coordinator.data.analog.get(self._channel.key)
        if value is None:
            return
        counter = int(value)
        if self._energy is None:
            # First start: begin with the energy of everything the boiler has burnt so far.
            self._energy = counter * self._energy_per_kg
        elif self._counter is not None and counter > self._counter:
            self._energy += (counter - self._counter) * self._energy_per_kg
        # A counter that went backwards was reset on the boiler; just continue from there.
        self._counter = counter

    @property
    def native_value(self) -> float | None:
        """Return the accumulated energy."""
        return None if self._energy is None else round(self._energy, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the counter reading the total is based on."""
        return {ATTR_PELLET_COUNTER: self._counter, ATTR_ENERGY_PER_KG: self._energy_per_kg}


class HargassnerRawSensor(HargassnerEntity, SensorEntity):
    """Any other analog channel, named as the boiler names it."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HargassnerCoordinator, channel: AnalogChannel) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, RAW_PREFIX + channel.key)
        self._channel = channel
        self._attr_name = channel.name
        if channel.unit in _RAW_UNITS:
            device_class, unit, state_class = _RAW_UNITS[channel.unit]
            self._attr_device_class = device_class
            self._attr_native_unit_of_measurement = unit
            self._attr_state_class = state_class
        elif channel.unit:
            self._attr_native_unit_of_measurement = channel.unit
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if channel.decimals is not None:
            self._attr_suggested_display_precision = channel.decimals

    @property
    def native_value(self) -> float | int | None:
        """Return the current value."""
        return self.coordinator.data.analog.get(self._channel.key)
