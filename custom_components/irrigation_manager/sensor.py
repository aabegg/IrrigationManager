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
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .card_entities import (
    INSTALLATION_CARD_ROLES,
    ZONE_CARD_ROLES,
    registry_card_entities,
)
from .const import (
    CONF_METER_TYPE,
    CONF_RAW_METER,
    CONF_WATER_METER,
    CONF_WATER_TARIFF_PER_M3,
    DOMAIN,
    INTEGRATION_NAME,
    METER_TYPE_NONE,
    SUBENTRY_TYPE_ZONE,
)
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
    state_class=SensorStateClass.TOTAL_INCREASING,
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
    meter_configured = (
        entry.version < 2
        or entry.data.get(CONF_METER_TYPE, METER_TYPE_NONE) != METER_TYPE_NONE
        or CONF_WATER_METER in entry.data
        or CONF_RAW_METER in entry.data
    )
    water_entities = (
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
            *[
                InstallationPeriodWaterSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    period=period,
                )
                for period in ("today", "week", "month", "year")
            ],
            *[
                InstallationMeterSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    key=key,
                )
                for key in ("current_flow", "physical_meter", "meter_measurement_quality")
            ],
        ]
        if meter_configured
        else []
    )
    async_add_entities(
        [
            *water_entities,
            InstallationStatusSensor(
                hass=hass,
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
            InstallationRuntimeSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                period="today",
            ),
            InstallationRuntimeSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                period="month",
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
            WeatherModelSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                key="weather_model_quality",
            ),
            WeatherModelSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                key="reference_evapotranspiration",
            ),
            WeatherModelSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                key="measured_rain",
            ),
            InstallationNextSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                zone_names={
                    (subentry.unique_id or subentry.subentry_id): subentry.title
                    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
                },
                key="next_zone",
            ),
            InstallationNextSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
                zone_names={},
                key="next_start",
            ),
            MaintenanceSummarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
            *(
                [
                    IrrigationCostSensor(
                        coordinator=entry.runtime_data.coordinator,
                        entry=entry,
                        installation_id=installation_id,
                        zone_id=None,
                        zone_name=None,
                        currency=hass.config.currency,
                    )
                ]
                if CONF_WATER_TARIFF_PER_M3 in entry.data
                else []
            ),
        ]
    )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE):
        zone_id = subentry.unique_id or subentry.subentry_id
        zone_water_entities = (
            [
                ZoneWaterSensor(
                    hass=hass,
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    config_entry_id=entry.entry_id,
                    zone_subentry_id=subentry.subentry_id,
                ),
                ZonePeriodSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    period="today",
                    metric="water",
                ),
                ZonePeriodSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    period="month",
                    metric="water",
                ),
            ]
            if meter_configured
            else []
        )
        async_add_entities(
            [
                *zone_water_entities,
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
                ZonePeriodSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    period="today",
                    metric="runtime",
                ),
                ZonePeriodSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    period="month",
                    metric="runtime",
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
                    key="next_irrigation",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="planning_reason",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="provisional_water_deficit",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="crop_evapotranspiration",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="effective_rain",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="soil_moisture_status",
                ),
                ZonePlanningValueSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    key="hardware_health",
                ),
                ZoneStatusContractSensor(
                    hass=hass,
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
                    config_entry_id=entry.entry_id,
                    zone_subentry_id=subentry.subentry_id,
                ),
                *[
                    ZoneContractSensor(
                        coordinator=entry.runtime_data.coordinator,
                        entry=entry,
                        installation_id=installation_id,
                        zone_id=zone_id,
                        zone_name=subentry.title,
                        key=key,
                    )
                    for key in (
                        "zone_priority",
                        "last_effective_irrigation",
                        "demand_coverage",
                        "expected_flow",
                        "actual_flow",
                        "flow_deviation",
                    )
                ],
                *(
                    [
                        IrrigationCostSensor(
                            coordinator=entry.runtime_data.coordinator,
                            entry=entry,
                            installation_id=installation_id,
                            zone_id=zone_id,
                            zone_name=subentry.title,
                            currency=hass.config.currency,
                        )
                    ]
                    if CONF_WATER_TARIFF_PER_M3 in entry.data
                    else []
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
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose Energy Dashboard compatibility and unassigned provenance."""
        if self.entity_description.key != "unassigned_water_total":
            return {"water_energy_dashboard_compatible": True}
        return {
            "measurement_quality": self.coordinator.data.unassigned_measurement_quality,
            "measurement_origin": self.coordinator.data.unassigned_measurement_origin,
            "available_for_assignment_liters": self.coordinator.data.unassigned_available_liters,
            "water_energy_dashboard_compatible": True,
        }


class InstallationPeriodWaterSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Period consumption derived from the persisted contribution ledger."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        period: str,
    ) -> None:
        """Initialize one local-calendar period sensor."""
        super().__init__(coordinator)
        self._period = period
        self._attr_translation_key = f"water_{period}"
        self._attr_unique_id = f"{installation_id}_water_{period}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> Decimal:
        """Return the derived period sum without maintaining another total."""
        return Decimal(str(self.coordinator.data.water_period_liters.get(self._period, 0.0)))

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose whether a protective record cap made this period incomplete."""
        return {"history_quality": self.coordinator.data.water_period_quality}


class InstallationRuntimeSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Completed irrigation runtime in a local calendar period."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        period: str,
    ) -> None:
        """Initialize one installation runtime period."""
        super().__init__(coordinator)
        self._period = period
        self._attr_translation_key = f"runtime_{period}"
        self._attr_unique_id = f"{installation_id}_runtime_{period}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> Decimal:
        value = (
            self.coordinator.data.runtime_today_seconds
            if self._period == "today"
            else self.coordinator.data.runtime_month_seconds
        )
        return Decimal(str(value))


class InstallationMeterSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Expose current flow, corrected physical total, or meter quality."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        key: str,
    ) -> None:
        """Initialize one installation metering sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{installation_id}_{key}"
        if key == "current_flow":
            self._attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
        elif key == "physical_meter":
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_state_class = SensorStateClass.TOTAL
            self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        else:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["measured", "integrated", "estimated", "unknown"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> Decimal | str | None:
        """Return the selected metering value."""
        snapshot = self.coordinator.data
        if self._key == "current_flow":
            value = snapshot.current_flow_l_min
        elif self._key == "physical_meter":
            value = snapshot.physical_meter_liters
        else:
            return snapshot.meter_measurement_quality
        return Decimal(str(value)) if value is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Expose physical resolution and future-facing correction semantics."""
        if self._key != "physical_meter":
            return None
        return {
            "measurement_quality": self.coordinator.data.meter_measurement_quality,
            "resolution_liters": self.coordinator.data.meter_resolution_liters,
            "correction_is_future_facing": True,
        }


class InstallationStatusSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Current operating state of one irrigation installation."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        config_entry_id: str,
    ) -> None:
        """Initialize the installation status entity."""
        super().__init__(coordinator)
        self._hass = hass
        self._installation_id = installation_id
        self._card_name = entry.title
        self._config_entry_id = config_entry_id
        self._attr_options = [
            "idle",
            "watering",
            "soaking",
            "error",
            "safety_lock",
            "emergency_stop",
            "winter_lock",
            "maintenance",
            "disabled",
            "automatic_disabled",
            "needs_reconfiguration",
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
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose the native-action installation identifier."""
        return {
            "config_entry_id": self._config_entry_id,
            "card_name": self._card_name,
            "card_entities": registry_card_entities(
                self._hass, self._installation_id, INSTALLATION_CARD_ROLES
            ),
            "volume_control_available": (
                self.coordinator.data.meter_measurement_quality == "measured"
            ),
            "recent_history": list(self.coordinator.data.recent_history),
        }

    @override
    async def async_added_to_hass(self) -> None:
        """Refresh the mapping after entity-registry renames."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_registry_update
            )
        )

    @callback
    def _handle_registry_update(self, event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Publish current entity IDs after any registry mutation."""
        self.async_write_ha_state()


class WeatherModelSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Expose the latest finalized installation weather result."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        key: str,
    ) -> None:
        """Initialize one weather model sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{installation_id}_{key}"
        if key == "weather_model_quality":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = [
                "observed",
                "external_service",
                "calculated_high",
                "calculated_reduced",
                "calculated_partial",
                "degraded",
                "provided",
                "unknown",
                "unavailable",
            ]
        else:
            self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 2
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> Decimal | str | None:
        """Return quality, ET0, or measured rain."""
        snapshot = self.coordinator.data
        if self._key == "weather_model_quality":
            return snapshot.weather_model_quality
        value = (
            snapshot.reference_evapotranspiration_mm
            if self._key == "reference_evapotranspiration"
            else snapshot.measured_rain_mm
        )
        return Decimal(str(value)) if value is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose model provenance, period, availability, and forecast separately."""
        snapshot = self.coordinator.data
        return {
            "method": snapshot.weather_model_method,
            "period_id": snapshot.weather_period_id,
            "last_finalized_at": snapshot.weather_last_finalized_at,
            "automation_available": snapshot.weather_automation_available,
            "rain_forecast": snapshot.rain_forecast,
        }


class InstallationNextSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Expose the next queued zone and its production-derived expected start."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_names: dict[str, str],
        key: str,
    ) -> None:
        """Initialize one next-zone or next-start entity."""
        super().__init__(coordinator)
        self._key = key
        self._zone_names = zone_names
        self._attr_translation_key = key
        self._attr_unique_id = f"{installation_id}_{key}"
        if key == "next_start":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> datetime | str | None:
        snapshot = self.coordinator.data
        if self._key == "next_start":
            return (
                datetime.fromisoformat(snapshot.next_start_at) if snapshot.next_start_at else None
            )
        return self._zone_names.get(snapshot.next_zone_id) if snapshot.next_zone_id else None


class MaintenanceSummarySensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Expose real recurring-maintenance and spring recommission state."""

    _attr_has_entity_name = True
    _attr_translation_key = "maintenance_due"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the installation maintenance summary."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_maintenance_due"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> int:
        return self.coordinator.data.maintenance_due_count

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        snapshot = self.coordinator.data
        return {
            "next_due": snapshot.maintenance_next_due,
            "spring_checklist_status": snapshot.spring_checklist_status,
            "spring_test_status": snapshot.spring_test_status,
        }


class IrrigationCostSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Expose tariff-at-delivery cumulative cost without repricing history."""

    _attr_has_entity_name = True
    _attr_translation_key = "water_cost"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str | None,
        zone_name: str | None,
        currency: str,
    ) -> None:
        """Initialize one installation or zone cumulative-cost sensor."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_native_unit_of_measurement = currency
        self._attr_unique_id = f"{zone_id or installation_id}_water_cost"
        if zone_id is None:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, installation_id)},
                name=entry.title,
                manufacturer=INTEGRATION_NAME,
                model="Irrigation installation",
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, zone_id)},
                name=zone_name,
                manufacturer=INTEGRATION_NAME,
                model="Irrigation zone",
                via_device=(DOMAIN, installation_id),
            )

    @property
    @override
    def native_value(self) -> Decimal | None:
        snapshot = self.coordinator.data
        value = (
            snapshot.installation_cost
            if self._zone_id is None
            else snapshot.zone_costs.get(self._zone_id, 0.0)
        )
        return Decimal(str(value)) if value is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "tariff_per_m3": self.coordinator.data.water_tariff_per_m3,
            "tariff_applied_at_delivery": True,
        }


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
        hass: HomeAssistant,
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
        self._hass = hass
        self._installation_id = installation_id
        self._card_name = zone_name
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
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose quality and identifiers accepted by native actions."""
        return {
            "config_entry_id": self._config_entry_id,
            "zone_subentry_id": self._zone_subentry_id,
            "card_name": self._card_name,
            "card_entities": registry_card_entities(self._hass, self._zone_id, ZONE_CARD_ROLES),
            "installation_card_entities": registry_card_entities(
                self._hass, self._installation_id, INSTALLATION_CARD_ROLES
            ),
            "measurement_quality": self.coordinator.data.zone_measurement_quality.get(
                self._zone_id, "unknown"
            ),
            "water_energy_dashboard_compatible": True,
            "recent_history": [
                value
                for value in self.coordinator.data.recent_history
                if value.get("zone_id") == self._zone_id
            ],
        }

    @override
    async def async_added_to_hass(self) -> None:
        """Refresh the mappings after entity-registry renames."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_registry_update
            )
        )

    @callback
    def _handle_registry_update(self, event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Publish current entity IDs after any registry mutation."""
        self.async_write_ha_state()


class ZonePeriodSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Zone runtime or measured water for one local calendar period."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
        period: str,
        metric: str,
    ) -> None:
        """Initialize one zone period metric."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._period = period
        self._metric = metric
        self._attr_translation_key = f"{metric}_{period}"
        self._attr_unique_id = f"{zone_id}_{metric}_{period}"
        if metric == "water":
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
            self._attr_suggested_display_precision = 1
        else:
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
            self._attr_suggested_display_precision = 0
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
        snapshot = self.coordinator.data
        if self._metric == "water":
            value = snapshot.zone_water_period_liters.get(self._zone_id, {}).get(self._period, 0.0)
        else:
            values = (
                snapshot.zone_runtime_today_seconds
                if self._period == "today"
                else snapshot.zone_runtime_month_seconds
            )
            value = values.get(self._zone_id, 0.0)
        return Decimal(str(value))


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
    _enum_options = ("measured", "integrated", "estimated", "unknown")

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
        if key in {
            "water_deficit",
            "provisional_water_deficit",
            "crop_evapotranspiration",
            "effective_rain",
        }:
            self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
        elif key == "automatic_target":
            self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1
        elif key in {"next_watering_window", "next_irrigation"}:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif key in {"soil_moisture_status", "hardware_health"}:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_entity_registry_enabled_default = False
            self._attr_options = (
                ["not_configured", "valid", "partial", "unavailable"]
                if key == "soil_moisture_status"
                else ["not_configured", "healthy", "blocked"]
            )

    @property
    @override
    def native_value(self) -> Decimal | datetime | str | None:
        """Return the selected planning value from the atomic coordinator snapshot."""
        snapshot = self.coordinator.data
        if self._observation_key == "water_deficit":
            return Decimal(str(snapshot.zone_deficit_mm.get(self._zone_id, 0.0)))
        if self._observation_key == "automatic_target":
            return Decimal(str(snapshot.zone_target_liters.get(self._zone_id, 0.0)))
        if self._observation_key == "provisional_water_deficit":
            value = snapshot.zone_provisional_deficit_mm.get(self._zone_id)
            return Decimal(str(value)) if value is not None else None
        if self._observation_key == "crop_evapotranspiration":
            value = snapshot.zone_crop_evapotranspiration_mm.get(self._zone_id)
            return Decimal(str(value)) if value is not None else None
        if self._observation_key == "effective_rain":
            value = snapshot.zone_effective_rain_mm.get(self._zone_id)
            return Decimal(str(value)) if value is not None else None
        if self._observation_key == "next_watering_window":
            timestamp = snapshot.zone_next_window.get(self._zone_id)
            return datetime.fromisoformat(timestamp) if timestamp is not None else None
        if self._observation_key == "next_irrigation":
            timestamp = snapshot.zone_next_irrigation.get(self._zone_id)
            return datetime.fromisoformat(timestamp) if timestamp is not None else None
        if self._observation_key == "soil_moisture_status":
            moisture = snapshot.zone_soil_moisture.get(self._zone_id)
            return str(moisture.get("status", "not_configured")) if moisture else "not_configured"
        if self._observation_key == "hardware_health":
            hardware = snapshot.zone_hardware_health.get(self._zone_id)
            return str(hardware.get("status", "not_configured")) if hardware else "not_configured"
        return snapshot.zone_planning_reason.get(self._zone_id, "automation_disabled")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Expose the complete latest calculation explanation on model sensors."""
        if self._observation_key not in {
            "water_deficit",
            "provisional_water_deficit",
            "crop_evapotranspiration",
            "effective_rain",
            "automatic_target",
            "soil_moisture_status",
            "hardware_health",
        }:
            return None
        snapshot = self.coordinator.data
        return {
            "calculation": snapshot.zone_calculation_explanations.get(self._zone_id),
            "effective_profile": snapshot.zone_effective_profiles.get(self._zone_id),
            "soil_moisture": snapshot.zone_soil_moisture.get(self._zone_id),
            "hardware_health": snapshot.zone_hardware_health.get(self._zone_id),
        }


class ZoneContractSensor(_ZoneObservationSensor):
    """Expose contracted zone state only when the runtime has production data."""

    def __init__(self, *, key: str, **kwargs: object) -> None:
        """Initialize one zone contract value."""
        self._observation_key = key
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._attr_translation_key = key
        if key == "zone_status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = [
                "idle",
                "watering_needed",
                "watering",
                "suspended",
                "safety_lock",
                "archived",
                "disabled",
                "installation_disabled",
                "automatic_disabled",
                "needs_reconfiguration",
            ]
        elif key == "last_effective_irrigation":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif key in {"expected_flow", "actual_flow"}:
            self._attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
            self._attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key in {"demand_coverage", "flow_deviation"}:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    @override
    def native_value(self) -> Decimal | datetime | str | int | None:
        snapshot = self.coordinator.data
        key = self._observation_key
        if key == "zone_status":
            return snapshot.zone_status.get(self._zone_id, "idle")
        if key == "zone_priority":
            return snapshot.zone_priority.get(self._zone_id)
        if key == "last_effective_irrigation":
            timestamp_value = snapshot.zone_last_effective_irrigation.get(self._zone_id)
            return datetime.fromisoformat(timestamp_value) if timestamp_value is not None else None
        values = {
            "demand_coverage": snapshot.zone_coverage_percent,
            "expected_flow": snapshot.zone_expected_flow_l_min,
            "actual_flow": snapshot.zone_actual_flow_l_min,
            "flow_deviation": snapshot.zone_flow_deviation_percent,
        }[key]
        numeric_value = values.get(self._zone_id)
        return Decimal(str(numeric_value)) if numeric_value is not None else None


class ZoneStatusContractSensor(ZoneContractSensor):
    """Effective zone status and stable card action/capability anchor."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        config_entry_id: str,
        zone_subentry_id: str,
        **kwargs: object,
    ) -> None:
        """Initialize the zone card anchor."""
        self._hass = hass
        self._installation_id = str(kwargs["installation_id"])
        self._config_entry_id = config_entry_id
        self._zone_subentry_id = zone_subentry_id
        self._card_name = str(kwargs["zone_name"])
        super().__init__(key="zone_status", **kwargs)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        snapshot = self.coordinator.data
        return {
            "config_entry_id": self._config_entry_id,
            "zone_subentry_id": self._zone_subentry_id,
            "card_name": self._card_name,
            "card_entities": registry_card_entities(self._hass, self._zone_id, ZONE_CARD_ROLES),
            "installation_card_entities": registry_card_entities(
                self._hass, self._installation_id, INSTALLATION_CARD_ROLES
            ),
            "volume_control_available": snapshot.meter_measurement_quality == "measured",
            "active_execution": snapshot.active_execution_id is not None,
        }

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_registry_update
            )
        )

    @callback
    def _handle_registry_update(self, event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        self.async_write_ha_state()
