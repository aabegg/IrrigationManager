"""Irrigation Manager integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import IrrigationCoordinator
from .manager import IrrigationManager
from .models import InstallationSnapshot
from .runtime import IrrigationConfigEntry, IrrigationRuntimeData
from .services import async_register_services
from .storage import IrrigationStore

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
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
            status="emergency_stop" if stored_state.emergency_stop else "idle",
            emergency_stop=stored_state.emergency_stop,
            installation_safety_lock=stored_state.installation_safety_lock,
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IrrigationConfigEntry) -> bool:
    """Unload one irrigation installation."""
    await entry.runtime_data.manager.async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete installation storage when its config entry is removed."""
    await IrrigationStore(hass, entry.entry_id).async_remove()
