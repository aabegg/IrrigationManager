"""Native Home Assistant actions exposed by Irrigation Manager."""

from typing import cast

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .manager import IrrigationManager

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_ZONE_SUBENTRY_ID = "zone_subentry_id"
ATTR_DURATION = "duration"
ATTR_AMOUNT = "amount"

SERVICE_START_MANUAL = "start_manual"
SERVICE_STOP = "stop"
SERVICE_EMERGENCY_STOP = "emergency_stop"
SERVICE_RESET_EMERGENCY_STOP = "reset_emergency_stop"
SERVICE_RESET_ZONE_SAFETY = "reset_zone_safety"
SERVICE_RESET_INSTALLATION_SAFETY = "reset_installation_safety"
SERVICE_ASSIGN_WATER = "assign_water"

START_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.001, max=14_400)),
    }
)
STOP_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})
ASSIGN_WATER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
    }
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration actions once per Home Assistant process."""

    def manager_for(call: ServiceCall) -> IrrigationManager:
        manager = hass.data[DOMAIN].get(call.data[ATTR_CONFIG_ENTRY_ID])
        if not isinstance(manager, IrrigationManager):
            raise HomeAssistantError("The irrigation installation is not loaded")
        return manager

    async def start_manual(call: ServiceCall) -> None:
        await manager_for(call).async_start_manual(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            duration_seconds=cast(float, call.data[ATTR_DURATION]),
        )

    async def stop(call: ServiceCall) -> None:
        await manager_for(call).async_stop()

    async def emergency_stop(call: ServiceCall) -> None:
        await manager_for(call).async_emergency_stop()

    async def reset_emergency_stop(call: ServiceCall) -> None:
        await manager_for(call).async_reset_emergency_stop()

    async def reset_zone_safety(call: ServiceCall) -> None:
        await manager_for(call).async_reset_zone_safety(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID])
        )

    async def reset_installation_safety(call: ServiceCall) -> None:
        await manager_for(call).async_reset_installation_safety()

    async def assign_water(call: ServiceCall) -> None:
        await manager_for(call).async_assign_water(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            amount_liters=cast(float, call.data[ATTR_AMOUNT]),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MANUAL,
        start_manual,
        schema=START_MANUAL_SCHEMA,
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP, stop, schema=STOP_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_EMERGENCY_STOP,
        emergency_stop,
        schema=STOP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_EMERGENCY_STOP,
        reset_emergency_stop,
        schema=STOP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_ZONE_SAFETY,
        reset_zone_safety,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
                vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_INSTALLATION_SAFETY,
        reset_installation_safety,
        schema=STOP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN_WATER,
        assign_water,
        schema=ASSIGN_WATER_SCHEMA,
    )
