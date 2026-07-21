"""Sensor platform for Irrigation Manager."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
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
                )
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
    ) -> None:
        """Initialize a cumulative water sensor for one zone."""
        super().__init__(coordinator)
        self._zone_id = zone_id
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
        """Expose whether the latest contribution was measured or estimated."""
        return {
            "measurement_quality": self.coordinator.data.zone_measurement_quality.get(
                self._zone_id, "unknown"
            )
        }
