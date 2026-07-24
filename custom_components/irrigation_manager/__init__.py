"""Irrigation Manager integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTOMATION_ENABLED,
    CONF_CONTROL_TYPE,
    CONF_LITERS_PER_COUNT,
    CONF_LITERS_PER_PULSE,
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
    CONF_METER_TYPE,
    CONF_NEEDS_RECONFIGURATION,
    CONF_OPERATION_ENABLED,
    CONF_RAW_METER,
    CONF_WATER_METER,
    CONF_WEEKLY_SCHEDULE,
    CONF_ZONE_VALVE,
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
from .services import async_register_services
from .storage import IrrigationStore

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up global Irrigation Manager actions."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IrrigationConfigEntry) -> bool:
    """Set up one irrigation installation from a config entry."""
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
            zone_safety_locks=stored_state.zone_safety_locks,
            zone_safety_lock_at=stored_state.zone_safety_lock_at,
            unassigned_total_liters=stored_state.unassigned_total_liters,
            unassigned_available_liters=stored_state.unassigned_available_liters,
            unassigned_measurement_quality=stored_state.unassigned_measurement_quality,
            unassigned_measurement_origin=stored_state.unassigned_measurement_origin,
            status=(
                "emergency_stop"
                if stored_state.emergency_stop
                else "winter_lock"
                if stored_state.winter_lock
                else "safety_lock"
                if stored_state.installation_safety_lock is not None
                else "idle"
            ),
            emergency_stop=stored_state.emergency_stop,
            installation_safety_lock=stored_state.installation_safety_lock,
            installation_safety_lock_at=stored_state.installation_safety_lock_at,
            winter_lock=stored_state.winter_lock,
            maintenance_active=stored_state.maintenance_test is not None,
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_frontend(hass, entry.entry_id)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply persisted updates now or defer them until the runtime is completely idle."""
    manager = hass.data[DOMAIN].get(entry.entry_id)
    if isinstance(manager, IrrigationManager):
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
        }
        if isinstance(entry.data.get(CONF_MAIN_VALVE), str):
            migrated_data[CONF_MAIN_VALVE] = entry.data[CONF_MAIN_VALVE]
        if isinstance(source_entity, str):
            migrated_data[CONF_METER_ENTITY] = source_entity
        if meter_type == METER_TYPE_PULSE and isinstance(
            entry.data.get(CONF_LITERS_PER_COUNT), int | float
        ):
            migrated_data[CONF_LITERS_PER_PULSE] = float(entry.data[CONF_LITERS_PER_COUNT])
        empty_schedule = [
            {"weekday": weekday, "start": None, "end": None, "target": None} for weekday in WEEKDAYS
        ]
        for subentry in entry.get_subentries_of_type("zone"):
            zone_data: dict[str, object] = {
                "name": subentry.data.get("name", subentry.title),
                CONF_CONTROL_TYPE: CONTROL_TYPE_TIME,
                CONF_OPERATION_ENABLED: False,
                CONF_AUTOMATION_ENABLED: False,
                CONF_WEEKLY_SCHEDULE: empty_schedule,
                CONF_NEEDS_RECONFIGURATION: True,
            }
            if isinstance(subentry.data.get(CONF_ZONE_VALVE), str):
                zone_data[CONF_ZONE_VALVE] = subentry.data[CONF_ZONE_VALVE]
            hass.config_entries.async_update_subentry(entry, subentry, data=zone_data)
        hass.config_entries.async_update_entry(
            entry,
            data=migrated_data,
            version=2,
            minor_version=0,
        )
        return True
    return entry.version == 2


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
