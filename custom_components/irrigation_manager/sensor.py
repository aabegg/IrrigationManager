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
    UnitOfTime,
    UnitOfVolume,
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
    CONF_VOLUME_MAX_RUNTIME,
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
    meter_configured = entry.data.get(CONF_METER_TYPE, METER_TYPE_NONE) != METER_TYPE_NONE
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
                for period in ("today", "month")
            ],
            InstallationMeterSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
            ),
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
            PendingRequestsSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
                installation_id=installation_id,
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
                ZoneNextIrrigationSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entry=entry,
                    installation_id=installation_id,
                    zone_id=zone_id,
                    zone_name=subentry.title,
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
                    meter_configured=meter_configured,
                    max_manual_volume_runtime_seconds=subentry.data.get(CONF_VOLUME_MAX_RUNTIME),
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
    """Expose the corrected physical water-meter total."""

    _attr_has_entity_name = True
    _attr_translation_key = "physical_meter"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the installation meter sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_physical_meter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> Decimal | None:
        """Return the corrected physical meter value."""
        value = self.coordinator.data.physical_meter_liters
        return Decimal(str(value)) if value is not None else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose physical resolution and future-facing correction semantics."""
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
        self._meter_configured = entry.data.get(CONF_METER_TYPE, METER_TYPE_NONE) != METER_TYPE_NONE
        self._attr_options = [
            "idle",
            "watering",
            "soaking",
            "error",
            "safety_lock",
            "emergency_stop",
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
        snapshot = self.coordinator.data
        attributes: dict[str, object] = {
            "config_entry_id": self._config_entry_id,
            "card_name": self._card_name,
            "card_entities": registry_card_entities(
                self._hass, self._installation_id, INSTALLATION_CARD_ROLES
            ),
            "volume_control_available": (
                self._meter_configured and snapshot.meter_measurement_quality == "measured"
            ),
            "recent_history": list(snapshot.recent_history),
            "irrigation_processes": [process.as_dict() for process in snapshot.partial_processes],
        }
        if snapshot.partial_remaining_value is not None:
            attributes.update(
                {
                    "irrigation_process_id": snapshot.active_execution_id,
                    "irrigation_request_id": snapshot.active_request_id,
                    "partial_zone_id": snapshot.partial_zone_id,
                    "target_type": snapshot.partial_processes[0].target_type,
                    "remaining_target": snapshot.partial_remaining_value,
                    "next_portion_at": snapshot.partial_next_portion_at,
                    "current_portion": snapshot.partial_current_portion,
                    "maximum_portions": snapshot.partial_maximum_portions,
                    "latest_safe_start": snapshot.partial_latest_safe_start,
                }
            )
        return attributes

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


class PendingRequestsSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Expose the number of pending irrigation requests."""

    _attr_has_entity_name = True
    _attr_translation_key = "pending_requests"

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
    ) -> None:
        """Initialize the pending-request sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{installation_id}_pending_requests"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=entry.title,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation installation",
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the pending request count."""
        return self.coordinator.data.pending_request_count


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


class _ZoneSensor(CoordinatorEntity[IrrigationCoordinator], SensorEntity):
    """Base entity for a zone sensor."""

    _attr_has_entity_name = True
    _suffix: str

    def __init__(
        self,
        *,
        coordinator: IrrigationCoordinator,
        entry: IrrigationConfigEntry,
        installation_id: str,
        zone_id: str,
        zone_name: str,
    ) -> None:
        """Initialize one zone sensor."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{zone_id}_{self._suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=zone_name,
            manufacturer=INTEGRATION_NAME,
            model="Irrigation zone",
            via_device=(DOMAIN, installation_id),
        )


class ZoneNextIrrigationSensor(_ZoneSensor):
    """Expose the next scheduled irrigation for one zone."""

    _attr_translation_key = "next_irrigation"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _suffix = "next_irrigation"

    @property
    @override
    def native_value(self) -> datetime | None:
        timestamp = self.coordinator.data.zone_next_irrigation.get(self._zone_id)
        return datetime.fromisoformat(timestamp) if timestamp is not None else None


class ZoneStatusContractSensor(_ZoneSensor):
    """Effective zone status and stable card action/capability anchor."""

    _attr_translation_key = "zone_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _suffix = "zone_status"

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        config_entry_id: str,
        zone_subentry_id: str,
        meter_configured: bool,
        max_manual_volume_runtime_seconds: object,
        **kwargs: object,
    ) -> None:
        """Initialize the zone card anchor."""
        self._hass = hass
        self._installation_id = str(kwargs["installation_id"])
        self._config_entry_id = config_entry_id
        self._zone_subentry_id = zone_subentry_id
        self._card_name = str(kwargs["zone_name"])
        self._meter_configured = meter_configured
        self._max_manual_volume_runtime_seconds = (
            float(max_manual_volume_runtime_seconds)
            if isinstance(max_manual_volume_runtime_seconds, int | float)
            and not isinstance(max_manual_volume_runtime_seconds, bool)
            else None
        )
        self._attr_options = [
            "idle",
            "watering",
            "soaking",
            "safety_lock",
            "disabled",
            "installation_disabled",
            "automatic_disabled",
            "needs_reconfiguration",
        ]
        super().__init__(**kwargs)  # type: ignore[arg-type]

    @property
    @override
    def native_value(self) -> str:
        return self.coordinator.data.zone_status.get(self._zone_id, "idle")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        snapshot = self.coordinator.data
        partial_process = next(
            (process for process in snapshot.partial_processes if process.zone_id == self._zone_id),
            None,
        )
        attributes: dict[str, object] = {
            "config_entry_id": self._config_entry_id,
            "zone_subentry_id": self._zone_subentry_id,
            "card_name": self._card_name,
            "card_entities": registry_card_entities(self._hass, self._zone_id, ZONE_CARD_ROLES),
            "installation_card_entities": registry_card_entities(
                self._hass, self._installation_id, INSTALLATION_CARD_ROLES
            ),
            "volume_control_available": (
                self._meter_configured and snapshot.meter_measurement_quality == "measured"
            ),
            "active_execution": (
                snapshot.active_zone_id == self._zone_id
                and snapshot.active_execution_id is not None
            ),
        }
        if snapshot.active_zone_id == self._zone_id and snapshot.active_execution_id:
            attributes["active_execution_id"] = snapshot.active_execution_id
        if partial_process is not None:
            attributes.update(
                {
                    "irrigation_process_id": partial_process.execution_id,
                    "irrigation_request_id": partial_process.request_id,
                    "target_type": partial_process.target_type,
                    "remaining_target": partial_process.remaining_value,
                    "next_portion_at": partial_process.next_portion_at,
                    "current_portion": partial_process.current_portion,
                    "maximum_portions": partial_process.maximum_portions,
                    "latest_safe_start": partial_process.latest_safe_start,
                }
            )
        if self._max_manual_volume_runtime_seconds is not None:
            attributes["max_manual_volume_runtime_seconds"] = (
                self._max_manual_volume_runtime_seconds
            )
        return attributes

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
