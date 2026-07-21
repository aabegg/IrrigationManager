"""Sensor platform for Irrigation Manager."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IrrigationCoordinator
from .models import InstallationSnapshot
from .runtime import IrrigationConfigEntry


@dataclass(frozen=True, kw_only=True)
class IrrigationSensorDescription(SensorEntityDescription):
    """Describe one coordinator-backed irrigation sensor."""

    value_fn: Callable[[InstallationSnapshot], float]


WATER_TOTAL_DESCRIPTION = IrrigationSensorDescription(
    key="water_total",
    translation_key="water_total",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
    value_fn=lambda snapshot: snapshot.installation_total_liters,
)
UNASSIGNED_WATER_TOTAL_DESCRIPTION = IrrigationSensorDescription(
    key="unassigned_water_total",
    translation_key="unassigned_water_total",
    device_class=SensorDeviceClass.WATER,
    state_class=SensorStateClass.TOTAL,
    native_unit_of_measurement=UnitOfVolume.LITERS,
    suggested_display_precision=1,
    value_fn=lambda snapshot: snapshot.unassigned_total_liters,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create installation and per-zone water sensors."""
    installation_id = entry.unique_id or entry.entry_id
    async_add_entities(
        [
            InstallationWaterSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                description=WATER_TOTAL_DESCRIPTION,
            ),
            InstallationWaterSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                description=UNASSIGNED_WATER_TOTAL_DESCRIPTION,
            ),
            InstallationStatusSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                config_entry_id=entry.entry_id,
            ),
            ActiveZoneSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                zone_names={
                    (subentry.unique_id or subentry.subentry_id): subentry.title
                    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
                },
            ),
            IrrigationQueueSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                key="pending_requests",
            ),
            IrrigationQueueSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                key="current_dose",
            ),
            IrrigationQueueSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                key="remaining_target",
            ),
        ]
    )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE):
        zone_id = subentry.unique_id or subentry.subentry_id
        async_add_entities(
            [
                ZoneWaterSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    config_entry_id=entry.entry_id,
                    zone_subentry_id=subentry.subentry_id,
                ),
                ZoneLastDeliveredSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
                ZoneLastDurationSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
                ZoneMeasurementQualitySensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="water_deficit",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="automatic_target",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="next_watering_window",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="planning_reason",
                ),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class InstallationWaterSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Cumulative water consumption of one installation."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        description: IrrigationSensorDescription,
    ) -> None:
        """Initialize the installation-level cumulative water sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._value_fn = description.value_fn
        self._attr_unique_id = f"{installation_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> Decimal:
        """Return the normalized cumulative total."""
        return Decimal(str(self._value_fn(self.coordinator.data)))

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the origin and quality of unassigned consumption."""
        if self.entity_description.key != "unassigned_water_total":
            return None
        return {
            "measurement_quality": self.coordinator.data.unassigned_measurement_quality,
            "measurement_origin": self.coordinator.data.unassigned_measurement_origin,
        }


class InstallationStatusSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Current operating state of one irrigation installation."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        config_entry_id: str,
    ) -> None:
        """Initialize the installation status entity."""
        super().__init__(coordinator)
        self._config_entry_id = config_entry_id
        self._attr_options = [
            "idle",
            "watering",
            "soaking",
            "error",
            "safety_lock",
            "emergency_stop",
        ]
        self._attr_unique_id = f"{installation_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> str:
        """Return the current installation status."""
        return self.coordinator.data.status

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the native-action installation identifier."""
        return {"config_entry_id": self._config_entry_id}


class ActiveZoneSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Human-readable active irrigation zone."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_zone"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_names: dict[str, str],
    ) -> None:
        """Initialize the active-zone entity."""
        super().__init__(coordinator)
        self._zone_names = zone_names
        self._attr_unique_id = f"{installation_id}_active_zone"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return the active zone name or no value while idle."""
        active_zone_id = self.coordinator.data.active_zone_id
        return self._zone_names.get(active_zone_id) if active_zone_id else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str | float] | None:
        """Expose the active target, remaining value, and current quality."""
        snapshot = self.coordinator.data
        if snapshot.active_target_type is None:
            return None
        attributes: dict[str, str | float] = {
            "target_type": snapshot.active_target_type,
            "target_value": snapshot.active_target_value or 0.0,
            "remaining_value": snapshot.active_remaining_value or 0.0,
        }
        if snapshot.active_measurement_quality is not None:
            attributes["measurement_quality"] = snapshot.active_measurement_quality
        return attributes


class IrrigationQueueSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Expose persisted request and split-dose progress."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        key: str,
    ) -> None:
        """Initialize one installation request-progress sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{installation_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> int | Decimal | None:
        """Return queue count, current dose number, or overall remaining target."""
        snapshot = self.coordinator.data
        if self._key == "pending_requests":
            return snapshot.pending_request_count
        if self._key == "current_dose":
            return snapshot.current_dose_number
        return (
            Decimal(str(snapshot.active_remaining_value))
            if snapshot.active_remaining_value is not None
            else None
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Identify the selected request/execution and remaining target type."""
        snapshot = self.coordinator.data
        attributes = {
            key: value
            for key, value in {
                "request_id": snapshot.active_request_id,
                "execution_id": snapshot.active_execution_id,
                "zone_subentry_id": snapshot.active_zone_subentry_id,
                "target_type": snapshot.active_target_type,
            }.items()
            if value is not None
        }
        return attributes or None


class ZoneWaterSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Cumulative water consumption attributed to one zone."""

    _attr_has_entity_name = True
    _attr_translation_key = "water_total"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
        config_entry_id: str,
        zone_subentry_id: str,
    ) -> None:
        """Initialize a cumulative water sensor for one zone."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._config_entry_id = config_entry_id
        self._zone_subentry_id = zone_subentry_id
        self._attr_unique_id = f"{zone_id}_water_total"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=zone_name,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation zone",
            via_device=(DOMAIN, installation_id),
        )

    @property
    @override
    def native_value(self) -> Decimal:
        """Return the total attributed to this zone."""
        return Decimal(str(self.coordinator.data.zone_totals_liters.get(self._zone_id, 0.0)))

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose quality and identifiers accepted by native actions."""
        return {
            "config_entry_id": self._config_entry_id,
            "zone_subentry_id": self._zone_subentry_id,
            "measurement_quality": self.coordinator.data.zone_measurement_quality.get(
                self._zone_id, "unknown"
            ),
        }


class _ZoneObservationSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Base entity for a zone's latest delivery observations."""

    _attr_has_entity_name = True
    _observation_key: str
    _enum_options: tuple[str, ...] | None = None

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
    ) -> None:
        """Initialize one zone observation entity."""
        super().__init__(coordinator)
        if self._enum_options is not None:
            self._attr_options = list(self._enum_options)
        self._zone_id = zone_id
        self._attr_unique_id = f"{zone_id}_{self._observation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=zone_name,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation zone",
            via_device=(DOMAIN, installation_id),
        )


class ZoneLastDeliveredSensor(_ZoneObservationSensor):
    """Water delivered by the latest irrigation dose."""

    _attr_translation_key = "last_delivered"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 1
    _observation_key = "last_delivered"

    @property
    @override
    def native_value(self) -> Decimal | None:
        """Return the latest delivered amount."""
        value = self.coordinator.data.zone_last_delivered_liters.get(self._zone_id)
        return Decimal(str(value)) if value is not None else None


class ZoneLastDurationSensor(_ZoneObservationSensor):
    """Watering duration of the latest irrigation dose."""

    _attr_translation_key = "last_duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_display_precision = 1
    _observation_key = "last_duration"

    @property
    @override
    def native_value(self) -> Decimal | None:
        """Return the latest delivered duration."""
        value = self.coordinator.data.zone_last_duration_seconds.get(self._zone_id)
        return Decimal(str(value)) if value is not None else None


class ZoneMeasurementQualitySensor(_ZoneObservationSensor):
    """Measurement quality of the latest irrigation dose."""

    _attr_translation_key = "measurement_quality"
    _attr_device_class = SensorDeviceClass.ENUM
    _observation_key = "measurement_quality"
    _enum_options = ("measured", "estimated", "unknown")

    @property
    @override
    def native_value(self) -> str:
        """Return the latest contribution's measurement quality."""
        return self.coordinator.data.zone_measurement_quality.get(self._zone_id, "unknown")


class ZonePlanningValueSensor(_ZoneObservationSensor):
    """Expose one current automatic-planning value for a zone."""

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
        key: str,
    ) -> None:
        """Initialize one planning sensor with the appropriate native metadata."""
        self._observation_key = key
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            installation_id=installation_id,
            zone_id=zone_id,
            zone_name=zone_name,
        )
        self._attr_translation_key = key
        if key == "water_deficit":
            self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
        elif key == "automatic_target":
            self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
        elif key == "next_watering_window":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    @override
    def native_value(self) -> Decimal | datetime | str | None:
        """Return the selected planning value from the atomic coordinator snapshot."""
        snapshot = self.coordinator.data
        if self._observation_key == "water_deficit":
            return Decimal(str(snapshot.zone_deficit_mm.get(self._zone_id, 0.0)))
        if self._observation_key == "automatic_target":
            return Decimal(str(snapshot.zone_target_liters.get(self._zone_id, 0.0)))
        if self._observation_key == "next_watering_window":
            value = snapshot.zone_next_window.get(self._zone_id)
            return datetime.fromisoformat(value) if value is not None else None
        return snapshot.zone_planning_reason.get(self._zone_id, "automation_disabled")
