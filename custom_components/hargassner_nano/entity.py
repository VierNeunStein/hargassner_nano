"""Base class of all entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HargassnerCoordinator


class HargassnerEntity(CoordinatorEntity[HargassnerCoordinator]):
    """An entity that shows a value of the boiler."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HargassnerCoordinator, key: str) -> None:
        """Initialize the entity. ``key`` is the stable part of the unique id."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=coordinator.layout.title,
        )
