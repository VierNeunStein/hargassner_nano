"""Binary sensors of the Hargassner integration (fault, pumps)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .const import CONF_RAW_CHANNELS
from .entity import HargassnerEntity
from .model import (
    RAW_PREFIX,
    BinaryKind,
    ResolvedBinary,
    binary_value,
    enabled_by_default,
    error_code,
    raw_digital_channels,
    resolve_binary_sensors,
)
from .texts import error_text

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import HargassnerConfigEntry, HargassnerCoordinator
    from .layout import DigitalChannel

# The coordinator reads the boiler; the entities only pick their value.
PARALLEL_UPDATES = 0

ATTR_CODE = "code"
ATTR_DESCRIPTION = "description"

_DEVICE_CLASSES = {
    BinaryKind.PROBLEM: BinarySensorDeviceClass.PROBLEM,
    BinaryKind.RUNNING: BinarySensorDeviceClass.RUNNING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HargassnerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the binary sensors the boiler's layout provides."""
    coordinator = entry.runtime_data
    layout = coordinator.layout

    entities: list[BinarySensorEntity] = [
        HargassnerBinarySensor(coordinator, item) for item in resolve_binary_sensors(layout)
    ]
    if entry.options.get(CONF_RAW_CHANNELS, False):
        entities.extend(HargassnerRawBinarySensor(coordinator, channel) for channel in raw_digital_channels(layout))
    async_add_entities(entities)


class HargassnerBinarySensor(HargassnerEntity, BinarySensorEntity):
    """A named on/off state of the boiler, e.g. a pump."""

    def __init__(self, coordinator: HargassnerCoordinator, item: ResolvedBinary) -> None:
        """Initialize the binary sensor."""
        spec = item.spec
        super().__init__(coordinator, spec.key)
        self._item = item
        self._attr_translation_key = spec.name_key
        if spec.circuit is not None:
            self._attr_translation_placeholders = {"circuit": spec.circuit}
        self._attr_device_class = _DEVICE_CLASSES[spec.kind]
        self._attr_entity_registry_enabled_default = enabled_by_default(spec, coordinator.layout, coordinator.data)

    @property
    def is_on(self) -> bool | None:
        """Return the current state."""
        return binary_value(self._item, self.coordinator.layout, self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return fault number and text along with the fault state."""
        if self._item.spec.kind is not BinaryKind.PROBLEM:
            return None
        code = error_code(self.coordinator.layout, self.coordinator.data)
        if code is None:
            return None
        return {ATTR_CODE: code, ATTR_DESCRIPTION: error_text(code, self.hass.config.language)}


class HargassnerRawBinarySensor(HargassnerEntity, BinarySensorEntity):
    """Any other status bit, named as the boiler names it."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HargassnerCoordinator, channel: DigitalChannel) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, RAW_PREFIX + channel.key)
        self._channel = channel
        self._attr_name = channel.name

    @property
    def is_on(self) -> bool | None:
        """Return the current state."""
        return self.coordinator.data.digital.get(self._channel.key)
