"""Native Home Assistant actions exposed by Irrigation Manager."""

from typing import Any, cast

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .manager import IrrigationManager

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_ZONE_SUBENTRY_ID = "zone_subentry_id"
ATTR_DURATION = "duration"
ATTR_AMOUNT = "amount"
ATTR_HARD_TIME_LIMIT = "hard_time_limit"
ATTR_EXPIRY = "expiry"
ATTR_REQUEST_ID = "request_id"
ATTR_EXECUTION_ID = "execution_id"

SERVICE_START_MANUAL = "start_manual"
SERVICE_CREATE_MANUAL = "create_manual"
SERVICE_LIST_REQUESTS = "list_requests"
SERVICE_CANCEL_REQUEST = "cancel_request"
SERVICE_PAUSE_REQUEST = "pause_request"
SERVICE_RESUME_REQUEST = "resume_request"
SERVICE_STOP = "stop"
SERVICE_EMERGENCY_STOP = "emergency_stop"
SERVICE_RESET_EMERGENCY_STOP = "reset_emergency_stop"
SERVICE_RESET_ZONE_SAFETY = "reset_zone_safety"
SERVICE_RESET_INSTALLATION_SAFETY = "reset_installation_safety"
SERVICE_ASSIGN_WATER = "assign_water"


def _validate_manual_target(data: dict[str, object]) -> dict[str, object]:
    """Require exactly one target and a hard limit for volume control."""
    target_count = sum(key in data for key in (ATTR_DURATION, ATTR_AMOUNT))
    if target_count != 1:
        raise vol.Invalid("Exactly one of duration or amount must be provided")
    if ATTR_AMOUNT in data and ATTR_HARD_TIME_LIMIT not in data:
        raise vol.Invalid("Amount targets require hard_time_limit")
    if ATTR_DURATION in data and ATTR_HARD_TIME_LIMIT in data:
        raise vol.Invalid("hard_time_limit is only valid for amount targets")
    return data


START_MANUAL_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
            vol.Optional(ATTR_DURATION): vol.All(
                vol.Coerce(float), vol.Range(min=0.001, max=14_400)
            ),
            vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
            vol.Optional(ATTR_HARD_TIME_LIMIT): vol.All(
                vol.Coerce(float), vol.Range(min=0.001, max=14_400)
            ),
            vol.Optional(ATTR_EXPIRY, default=3600): vol.All(
                vol.Coerce(float), vol.Range(min=0.001, max=604_800)
            ),
        }
    ),
    _validate_manual_target,
)
INSTALLATION_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})
STOP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Exclusive(ATTR_REQUEST_ID, "target"): cv.string,
        vol.Exclusive(ATTR_EXECUTION_ID, "target"): cv.string,
    }
)
REQUEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_REQUEST_ID): cv.string,
    }
)
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

    async def request_manual(call: ServiceCall, *, wait: bool) -> dict[str, Any]:
        return await manager_for(call).async_start_manual(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            duration_seconds=cast(float | None, call.data.get(ATTR_DURATION)),
            amount_liters=cast(float | None, call.data.get(ATTR_AMOUNT)),
            hard_time_limit_seconds=cast(float | None, call.data.get(ATTR_HARD_TIME_LIMIT)),
            expiry_seconds=cast(float, call.data[ATTR_EXPIRY]),
            wait_for_completion=wait,
        )

    async def start_manual(call: ServiceCall) -> dict[str, Any]:
        return await request_manual(call, wait=True)

    async def create_manual(call: ServiceCall) -> dict[str, Any]:
        return await request_manual(call, wait=False)

    async def list_requests(call: ServiceCall) -> dict[str, Any]:
        manager = manager_for(call)
        return {
            "requests": manager.list_manual_requests(),
            "executions": manager.list_irrigation_executions(),
        }

    async def stop(call: ServiceCall) -> None:
        await manager_for(call).async_stop(
            request_id=cast(str | None, call.data.get(ATTR_REQUEST_ID)),
            execution_id=cast(str | None, call.data.get(ATTR_EXECUTION_ID)),
        )

    async def cancel_request(call: ServiceCall) -> None:
        await manager_for(call).async_cancel_request(cast(str, call.data[ATTR_REQUEST_ID]))

    async def pause_request(call: ServiceCall) -> None:
        await manager_for(call).async_pause_request(cast(str, call.data[ATTR_REQUEST_ID]))

    async def resume_request(call: ServiceCall) -> None:
        await manager_for(call).async_resume_request(cast(str, call.data[ATTR_REQUEST_ID]))

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
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_MANUAL,
        create_manual,
        schema=START_MANUAL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_REQUESTS,
        list_requests,
        schema=INSTALLATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP, stop, schema=STOP_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_REQUEST, cancel_request, schema=REQUEST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE_REQUEST, pause_request, schema=REQUEST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESUME_REQUEST, resume_request, schema=REQUEST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EMERGENCY_STOP,
        emergency_stop,
        schema=INSTALLATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_EMERGENCY_STOP,
        reset_emergency_stop,
        schema=INSTALLATION_SCHEMA,
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
        schema=INSTALLATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN_WATER,
        assign_water,
        schema=ASSIGN_WATER_SCHEMA,
    )
