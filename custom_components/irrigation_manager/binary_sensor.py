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

from .const import DOMAIN, INTEGRATION_NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IrrigationCoordinator
from .runtime import IrrigationConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create installation-level safety entities."""
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
            WinterLockBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
            MaintenanceModeBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
        ]
    )
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE):
        zone_id = subentry.unique_id or subentry.subentry_id
        async_add_entities(
            [
                ZoneSafetyLockBinarySensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
                ZoneAutomationNeededBinarySensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class EmergencyStopBinarySensor(CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity):
    """Expose the persistent installation safety lock."""

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
        """Initialize the installation safety-lock entity."""
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
        """Return true while the persistent safety lock is active."""
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
        """Expose the lock reason when present."""
        reason = self.coordinator.data.installation_safety_lock
        return {"reason": reason} if reason is not None else {}


class WinterLockBinarySensor(CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity):
    """Expose the persistent non-overridable winter lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "winter_lock"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the winter-lock entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_winter_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true while all irrigation is winter-locked."""
        return self.coordinator.data.winter_lock


class MaintenanceModeBinarySensor(CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity):
    """Expose the single active supervised maintenance slot."""

    _attr_has_entity_name = True
    _attr_translation_key = "maintenance_mode"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the maintenance-mode entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_maintenance_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true only while one supervised test is active."""
        return self.coordinator.data.maintenance_active

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose deadlines and stable test identifiers for supervision UIs."""
        snapshot = self.coordinator.data
        return {
            key: value
            for key, value in {
                "test_id": snapshot.maintenance_test_id,
                "kind": snapshot.maintenance_kind,
                "expires_at": snapshot.maintenance_expires_at,
                "confirmation_deadline": snapshot.maintenance_confirmation_deadline,
            }.items()
            if value is not None
        }


class ZoneSafetyLockBinarySensor(CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity):
    """Expose a persistent safety lock for one irrigation zone."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone_safety_lock"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
    ) -> None:
        """Initialize the zone safety-lock entity."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{zone_id}_safety_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=zone_name,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation zone",
            via_device=(DOMAIN, installation_id),
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true while this zone is safety-locked."""
        return self._zone_id in self.coordinator.data.zone_safety_locks

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the lock reason when present."""
        reason = self.coordinator.data.zone_safety_locks.get(self._zone_id)
        return {"reason": reason} if reason is not None else {}


class ZoneAutomationNeededBinarySensor(
    CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity
):
    """Expose whether current deficit/rhythm policy calls for automatic water."""

    _attr_has_entity_name = True
    _attr_translation_key = "automation_needed"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
    ) -> None:
        """Initialize one zone demand indicator."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{zone_id}_automation_needed"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=zone_name,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation zone",
            via_device=(DOMAIN, installation_id),
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true while automatic irrigation is needed."""
        return self.coordinator.data.zone_automation_needed.get(self._zone_id, False)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the current scheduler explanation."""
        return {
            "reason": self.coordinator.data.zone_planning_reason.get(
                self._zone_id, "automation_disabled"
            )
        }
