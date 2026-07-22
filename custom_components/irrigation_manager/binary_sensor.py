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
            FrostSafetyBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
            RainStopBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
            ExternalSafetyBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
            InstallationAutomationReleaseBinarySensor(
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
                ZoneExternalSafetyBinarySensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
                ZoneWindInterlockBinarySensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
                ZoneAutomationReleaseBinarySensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
                ZoneArchivedBinarySensor(
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


class InstallationAutomationReleaseBinarySensor(
    CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity
):
    """Expose effective installation automatic release including timed suspension."""

    _attr_has_entity_name = True
    _attr_translation_key = "automation_release"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the effective installation automation release."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_automation_release"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def is_on(self) -> bool:
        snapshot = self.coordinator.data
        return snapshot.automation_enabled and snapshot.automatic_suspended_until is None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        until = self.coordinator.data.automatic_suspended_until
        return {"suspended_until": until} if until is not None else {}


class _WeatherSafetyBinarySensor(CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity):
    """Base for installation weather safety indicators."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        return {"weather_safety_status": self.coordinator.data.weather_safety_status}


class FrostSafetyBinarySensor(_WeatherSafetyBinarySensor):
    """Expose the non-overridable frost interlock."""

    _attr_translation_key = "frost_safety"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the frost safety indicator."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            installation_id=installation_id,
            suffix="frost_safety",
        )

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.data.frost_blocked


class RainStopBinarySensor(_WeatherSafetyBinarySensor):
    """Expose the automatic rain-stop interlock."""

    _attr_translation_key = "rain_stop"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the automatic rain-stop indicator."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            installation_id=installation_id,
            suffix="rain_stop",
        )

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.data.rain_stop_active


class ExternalSafetyBinarySensor(_WeatherSafetyBinarySensor):
    """Expose installation-level external permit/block state."""

    _attr_translation_key = "external_safety"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the installation external-safety indicator."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            installation_id=installation_id,
            suffix="external_safety",
        )

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.data.external_safety_blocked


class _ZoneSafetyIndicator(CoordinatorEntity[IrrigationCoordinator], BinarySensorEntity):
    """Base for one zone-scoped safety indicator."""

    _attr_has_entity_name = True
    _attr_device_class: BinarySensorDeviceClass | None = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
        suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{zone_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=zone_name,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation zone",
            via_device=(DOMAIN, installation_id),
        )


class ZoneExternalSafetyBinarySensor(_ZoneSafetyIndicator):
    """Expose zonal external permit/block state."""

    _attr_translation_key = "external_safety"

    def __init__(self, **kwargs: object) -> None:
        """Initialize one zone external-safety indicator."""
        super().__init__(**kwargs, suffix="external_safety")  # type: ignore[arg-type]

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.data.zone_external_safety_blocked.get(self._zone_id, False)


class ZoneWindInterlockBinarySensor(_ZoneSafetyIndicator):
    """Expose automatic strong-wind blocking for one zone."""

    _attr_translation_key = "wind_interlock"

    def __init__(self, **kwargs: object) -> None:
        """Initialize one zone wind-interlock indicator."""
        super().__init__(**kwargs, suffix="wind_interlock")  # type: ignore[arg-type]

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.data.zone_wind_blocked.get(self._zone_id, False)


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


class ZoneAutomationReleaseBinarySensor(_ZoneSafetyIndicator):
    """Expose effective zone release without conflating manual availability."""

    _attr_translation_key = "automation_release"
    _attr_device_class = None

    def __init__(self, **kwargs: object) -> None:
        """Initialize one effective zone automation release."""
        super().__init__(**kwargs, suffix="automation_release")  # type: ignore[arg-type]

    @property
    @override
    def is_on(self) -> bool:
        snapshot = self.coordinator.data
        return (
            snapshot.automation_enabled
            and snapshot.zone_automation_enabled.get(self._zone_id, False)
            and self._zone_id not in snapshot.archived_zones
            and self._zone_id not in snapshot.zone_automatic_suspended_until
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        until = self.coordinator.data.zone_automatic_suspended_until.get(self._zone_id)
        return {"suspended_until": until} if until is not None else {}


class ZoneArchivedBinarySensor(_ZoneSafetyIndicator):
    """Expose the durable archive lifecycle while retaining the zone device."""

    _attr_translation_key = "archived"
    _attr_device_class = None

    def __init__(self, **kwargs: object) -> None:
        """Initialize one zone archive indicator."""
        super().__init__(**kwargs, suffix="archived")  # type: ignore[arg-type]

    @property
    @override
    def is_on(self) -> bool:
        return self._zone_id in self.coordinator.data.archived_zones

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        archived_at = self.coordinator.data.archived_zones.get(self._zone_id)
        return {"archived_at": archived_at} if archived_at is not None else {}
