"""Binary sensor platform for Irrigation Manager."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_NAME
from .coordinator import IrrigationCoordinator
from .runtime import IrrigationConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the installation-wide emergency and safety entities."""
    installation_id = entry.unique_id or entry.entry_id
    async_add_entities(
        [
            EmergencyStopBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
            InstallationSafetyLockBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
        ]
    )


class EmergencyStopBinarySensor(CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity):
    """Expose whether an emergency stop is active."""

    _attr_has_entity_name = True
    _attr_translation_key = "emergency_stop"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the emergency-stop entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_emergency_stop"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true while the emergency stop is active."""
        return self.coordinator.data.emergency_stop


class InstallationSafetyLockBinarySensor(
    CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity
):
    """Expose the persistent installation safety lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "installation_safety_lock"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the installation safety-lock entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_safety_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true while the installation is safety-locked."""
        return self.coordinator.data.installation_safety_lock is not None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the persistent lock reason and occurrence time when present."""
        reason = self.coordinator.data.installation_safety_lock
        occurred_at = self.coordinator.data.installation_safety_lock_at
        return {
            key: value
            for key, value in {"reason": reason, "occurred_at": occurred_at}.items()
            if value is not None
        }
