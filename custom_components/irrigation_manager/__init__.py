"""Irrigation Manager integration."""

import logging
import math

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTOMATION_ENABLED,
    CONF_BASE_TARGET,
    CONF_CONTROL_TYPE,
    CONF_LITERS_PER_COUNT,
    CONF_LITERS_PER_PULSE,
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
    CONF_METER_TYPE,
    CONF_NEEDS_RECONFIGURATION,
    CONF_OPERATION_ENABLED,
    CONF_PLANT_SITE_MODULE_ENABLED,
    CONF_RAW_METER,
    CONF_SEASONAL_FACTORS,
    CONF_SEASONAL_MODULE_ENABLED,
    CONF_SOAK_MODULE_ENABLED,
    CONF_SUBAREAS,
    CONF_USE_FORECAST_POSTPONEMENT,
    CONF_USE_PLANT_SITE_MODEL,
    CONF_USE_SEASONAL_ADJUSTMENT,
    CONF_USE_WEATHER_ADJUSTMENT,
    CONF_WATER_METER,
    CONF_WEATHER_MODULE_ENABLED,
    CONF_WEATHER_SOURCES,
    CONF_WEEKLY_SCHEDULE,
    CONF_ZONE_VALVE,
    CONFIG_ENTRY_MINOR_VERSION,
    CONTROL_TYPE_TIME,
    DOMAIN,
    METER_TYPE_CUMULATIVE,
    METER_TYPE_NONE,
    METER_TYPE_PULSE,
    WEEKDAYS,
)
from .coordinator import IrrigationCoordinator
from .frontend import async_register_frontend, async_unregister_frontend
from .manager import IrrigationManager
from .models import InstallationSnapshot
from .runtime import IrrigationConfigEntry, IrrigationRuntimeData
from .seasonal import MONTHS
from .services import async_register_services
from .storage import IrrigationStore

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
LOGGER = logging.getLogger(__name__)

ENTITY_SURFACE_MINOR_VERSION = 1
METER_INSTALLATION_ENTITY_SUFFIXES = frozenset(
    {"water_total", "unassigned_water_total", "water_today", "water_month", "physical_meter"}
)
METER_ZONE_ENTITY_SUFFIXES = frozenset({"water_total", "water_today", "water_month"})
REMOVED_INSTALLATION_ENTITY_SUFFIXES = frozenset(
    {
        "active_zone",
        "automation_release",
        "calendar",
        "current_dose",
        "current_flow",
        "external_safety",
        "frost_safety",
        "maintenance_due",
        "maintenance_mode",
        "measured_rain",
        "meter_measurement_quality",
        "rain_stop",
        "reference_evapotranspiration",
        "remaining_target",
        "water_cost",
        "water_week",
        "water_year",
        "weather_model_quality",
        "winter_lock",
    }
)
REMOVED_ZONE_ENTITY_SUFFIXES = frozenset(
    {
        "actual_flow",
        "archived",
        "automatic_target",
        "automation_needed",
        "automation_release",
        "crop_evapotranspiration",
        "demand_coverage",
        "effective_rain",
        "expected_flow",
        "external_safety",
        "flow_deviation",
        "hardware_health",
        "last_delivered",
        "last_duration",
        "last_effective_irrigation",
        "measurement_quality",
        "next_watering_window",
        "planning_reason",
        "provisional_water_deficit",
        "safety_lock",
        "soil_moisture_status",
        "water_cost",
        "water_deficit",
        "wind_interlock",
        "zone_priority",
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up global Irrigation Manager actions."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IrrigationConfigEntry) -> bool:
    """Set up one irrigation installation from a config entry."""
    if entry.version == 2 and entry.minor_version < ENTITY_SURFACE_MINOR_VERSION:
        _remove_legacy_entity_surface(hass, entry)
    if entry.data.get(CONF_METER_TYPE, METER_TYPE_NONE) == METER_TYPE_NONE:
        _remove_disabled_meter_entities(hass, entry)
    store = IrrigationStore(hass, entry.entry_id)
    stored_state = await store.async_load()
    coordinator = IrrigationCoordinator(
        hass,
        logger=LOGGER,
        config_entry=entry,
        name=entry.title,
        always_update=False,
    )
    coordinator.set_snapshot(
        InstallationSnapshot(
            installation_total_liters=stored_state.installation_total_liters,
            zone_totals_liters=stored_state.zone_totals_liters,
            zone_measurement_quality=stored_state.zone_measurement_quality,
            zone_last_delivered_liters=stored_state.zone_last_delivered_liters,
            zone_last_duration_seconds=stored_state.zone_last_duration_seconds,
            unassigned_total_liters=stored_state.unassigned_total_liters,
            status=(
                "emergency_stop"
                if stored_state.emergency_stop
                else "safety_lock"
                if stored_state.installation_safety_lock is not None
                else "idle"
            ),
            emergency_stop=stored_state.emergency_stop,
            installation_safety_lock=stored_state.installation_safety_lock,
            installation_safety_lock_at=stored_state.installation_safety_lock_at,
        )
    )
    manager = IrrigationManager(
        hass=hass,
        entry=entry,
        coordinator=coordinator,
        store=store,
        stored_state=stored_state,
    )
    await manager.async_initialize()
    entry.runtime_data = IrrigationRuntimeData(
        coordinator=coordinator,
        store=store,
        manager=manager,
    )
    hass.data[DOMAIN][entry.entry_id] = entry.runtime_data.manager
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    async def _async_stop_on_home_assistant_stop(_event: Event) -> None:
        """Persist the final runtime state before Home Assistant stops."""
        await manager.async_shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            _async_stop_on_home_assistant_stop,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_frontend(hass, entry.entry_id)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply persisted updates now or defer them until the runtime is completely idle."""
    manager = hass.data[DOMAIN].get(entry.entry_id)
    if isinstance(manager, IrrigationManager):
        if not manager.requires_config_reload(entry.data):
            manager.refresh_weather_sources(entry.data)
            return
        await manager.async_request_config_reload()
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reset legacy demand configuration into a disabled v2 reconfiguration shell."""
    if entry.version == 1:
        source_entity = entry.data.get(CONF_WATER_METER) or entry.data.get(CONF_RAW_METER)
        meter_type = (
            METER_TYPE_CUMULATIVE
            if entry.data.get(CONF_WATER_METER)
            else METER_TYPE_PULSE
            if entry.data.get(CONF_RAW_METER)
            else METER_TYPE_NONE
        )
        migrated_data: dict[str, object] = {
            "name": entry.data.get("name", entry.title),
            CONF_METER_TYPE: meter_type,
            CONF_OPERATION_ENABLED: False,
            CONF_AUTOMATION_ENABLED: False,
            CONF_NEEDS_RECONFIGURATION: True,
            CONF_PLANT_SITE_MODULE_ENABLED: False,
            CONF_SEASONAL_MODULE_ENABLED: False,
            CONF_WEATHER_MODULE_ENABLED: False,
            CONF_WEATHER_SOURCES: {},
            CONF_SOAK_MODULE_ENABLED: False,
        }
        if isinstance(entry.data.get(CONF_MAIN_VALVE), str):
            migrated_data[CONF_MAIN_VALVE] = entry.data[CONF_MAIN_VALVE]
        if isinstance(source_entity, str):
            migrated_data[CONF_METER_ENTITY] = source_entity
        if meter_type == METER_TYPE_PULSE and isinstance(
            entry.data.get(CONF_LITERS_PER_COUNT), int | float
        ):
            migrated_data[CONF_LITERS_PER_PULSE] = float(entry.data[CONF_LITERS_PER_COUNT])
        for subentry in entry.get_subentries_of_type("zone"):
            zone_data: dict[str, object] = {
                "name": subentry.data.get("name", subentry.title),
                CONF_CONTROL_TYPE: CONTROL_TYPE_TIME,
                CONF_OPERATION_ENABLED: False,
                CONF_AUTOMATION_ENABLED: False,
                CONF_WEEKLY_SCHEDULE: [
                    {"weekday": weekday, "start": None, "end": None, "target": None}
                    for weekday in WEEKDAYS
                ],
                CONF_NEEDS_RECONFIGURATION: True,
                CONF_USE_PLANT_SITE_MODEL: False,
                CONF_USE_SEASONAL_ADJUSTMENT: False,
                CONF_USE_WEATHER_ADJUSTMENT: False,
                CONF_SEASONAL_FACTORS: {month: 1.0 for month in MONTHS},
                CONF_SUBAREAS: [],
            }
            if isinstance(subentry.data.get(CONF_ZONE_VALVE), str):
                zone_data[CONF_ZONE_VALVE] = subentry.data[CONF_ZONE_VALVE]
            hass.config_entries.async_update_subentry(entry, subentry, data=zone_data)
        hass.config_entries.async_update_entry(
            entry,
            data=migrated_data,
            version=2,
            minor_version=CONFIG_ENTRY_MINOR_VERSION,
        )
        _remove_legacy_entity_surface(hass, entry)
        return True
    if entry.version != 2:
        return False
    original_minor = entry.minor_version
    if original_minor < ENTITY_SURFACE_MINOR_VERSION:
        _remove_legacy_entity_surface(hass, entry)
    if original_minor < CONFIG_ENTRY_MINOR_VERSION:
        migrated_data = dict(entry.data)
        migrated_data.setdefault(CONF_PLANT_SITE_MODULE_ENABLED, False)
        migrated_data.setdefault(CONF_SEASONAL_MODULE_ENABLED, False)
        if original_minor < 5:
            migrated_data[CONF_WEATHER_MODULE_ENABLED] = False
        migrated_data.setdefault(CONF_WEATHER_SOURCES, {})
        migrated_data.setdefault(CONF_SOAK_MODULE_ENABLED, False)
        for subentry in entry.get_subentries_of_type("zone"):
            zone_data = dict(subentry.data)
            zone_data.setdefault(CONF_USE_PLANT_SITE_MODEL, False)
            zone_data.setdefault(CONF_SUBAREAS, [])
            zone_data.setdefault(CONF_USE_SEASONAL_ADJUSTMENT, False)
            zone_data.setdefault(CONF_SEASONAL_FACTORS, {month: 1.0 for month in MONTHS})
            if original_minor < 5:
                zone_data[CONF_USE_WEATHER_ADJUSTMENT] = False
            if original_minor < 6:
                zone_data[CONF_USE_FORECAST_POSTPONEMENT] = False
            if CONF_BASE_TARGET not in zone_data:
                schedule = zone_data.get(CONF_WEEKLY_SCHEDULE)
                if isinstance(schedule, list):
                    for row in schedule:
                        if not isinstance(row, dict):
                            continue
                        target = row.get("target")
                        if (
                            isinstance(target, int | float)
                            and not isinstance(target, bool)
                            and math.isfinite(target)
                            and target > 0
                        ):
                            zone_data[CONF_BASE_TARGET] = float(target)
                            break
            hass.config_entries.async_update_subentry(entry, subentry, data=zone_data)
        hass.config_entries.async_update_entry(
            entry,
            data=migrated_data,
            minor_version=CONFIG_ENTRY_MINOR_VERSION,
        )
    return True


def _remove_legacy_entity_surface(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove registry identities retired by the authoritative v2 entity contract."""
    registry = er.async_get(hass)
    installation_id = entry.unique_id or entry.entry_id
    removed_unique_ids = {
        f"{installation_id}_{suffix}" for suffix in REMOVED_INSTALLATION_ENTITY_SUFFIXES
    }
    for subentry in entry.get_subentries_of_type("zone"):
        zone_id = subentry.unique_id or subentry.subentry_id
        removed_unique_ids.update(f"{zone_id}_{suffix}" for suffix in REMOVED_ZONE_ENTITY_SUFFIXES)
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.unique_id in removed_unique_ids:
            registry.async_remove(entity.entity_id)


def _remove_disabled_meter_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove meter-only entities by unique ID, including registry-renamed entities."""
    registry = er.async_get(hass)
    installation_id = entry.unique_id or entry.entry_id
    removed_unique_ids = {
        f"{installation_id}_{suffix}" for suffix in METER_INSTALLATION_ENTITY_SUFFIXES
    }
    for subentry in entry.get_subentries_of_type("zone"):
        zone_id = subentry.unique_id or subentry.subentry_id
        removed_unique_ids.update(f"{zone_id}_{suffix}" for suffix in METER_ZONE_ENTITY_SUFFIXES)
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.unique_id in removed_unique_ids:
            registry.async_remove(entity.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: IrrigationConfigEntry) -> bool:
    """Unload one irrigation installation."""
    runtime_data = getattr(entry, "runtime_data", None)
    if runtime_data is not None:
        await runtime_data.manager.async_shutdown()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await async_unregister_frontend(hass, entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete installation storage when its config entry is removed."""
    await IrrigationStore(hass, entry.entry_id).async_remove()
