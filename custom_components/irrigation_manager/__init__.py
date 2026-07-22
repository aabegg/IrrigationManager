"""Irrigation Manager integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AGRONOMIC_VALUES_CONFIRMED,
    CONF_AUTOMATION_ENABLED,
    CONF_CUSTOM_PROFILES,
    CONF_EXTERNAL_FAILURE_POLICY,
    DOMAIN,
    EXTERNAL_FAILURE_FAIL_SAFE,
)
from .coordinator import IrrigationCoordinator
from .frontend import async_register_frontend, async_unregister_frontend
from .manager import IrrigationManager
from .models import InstallationSnapshot
from .runtime import IrrigationConfigEntry, IrrigationRuntimeData
from .services import async_register_services
from .storage import IrrigationStore

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]
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
    """Mark legacy entries compatible with additive automatic-planning defaults."""
    if entry.version != 1:
        return False
    if entry.minor_version < 2:
        for subentry in entry.get_subentries_of_type("zone"):
            if CONF_AGRONOMIC_VALUES_CONFIRMED not in subentry.data:
                hass.config_entries.async_update_subentry(
                    entry,
                    subentry,
                    data={**subentry.data, CONF_AGRONOMIC_VALUES_CONFIRMED: True},
                )
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_CUSTOM_PROFILES: {}, **entry.data},
            minor_version=2,
        )
    if entry.minor_version < 3:
        hass.config_entries.async_update_entry(entry, minor_version=3)
    if entry.minor_version < 4:
        for subentry in entry.get_subentries_of_type("zone"):
            if CONF_EXTERNAL_FAILURE_POLICY not in subentry.data:
                hass.config_entries.async_update_subentry(
                    entry,
                    subentry,
                    data={
                        CONF_EXTERNAL_FAILURE_POLICY: EXTERNAL_FAILURE_FAIL_SAFE,
                        **subentry.data,
                    },
                )
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_EXTERNAL_FAILURE_POLICY: EXTERNAL_FAILURE_FAIL_SAFE,
                **entry.data,
            },
            minor_version=4,
        )
    if entry.minor_version < 5:
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_AUTOMATION_ENABLED: True, **entry.data},
            minor_version=5,
        )
    if entry.minor_version < 6:
        hass.config_entries.async_update_entry(entry, minor_version=6)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IrrigationConfigEntry) -> bool:
    """Unload one irrigation installation."""
    await entry.runtime_data.manager.async_shutdown()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await async_unregister_frontend(hass, entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete installation storage when its config entry is removed."""
    await IrrigationStore(hass, entry.entry_id).async_remove()
