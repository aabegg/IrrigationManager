"""Home Assistant actions for the version 2 irrigation model."""

from typing import Any, cast

import voluptuous as vol
from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .manager import IrrigationManager

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_ZONE_SUBENTRY_ID = "zone_subentry_id"
ATTR_DURATION = "duration"
ATTR_AMOUNT = "amount"
ATTR_HARD_TIME_LIMIT = "hard_time_limit"
ATTR_EXPIRY = "expiry"
ATTR_START_AT = "start_at"
ATTR_REQUEST_ID = "request_id"
ATTR_EXECUTION_ID = "execution_id"
ATTR_CONFLICT_POLICY = "conflict_policy"
ATTR_ENABLED = "enabled"
ATTR_STOP_ACTIVE = "stop_active"
ATTR_PHYSICAL_TOTAL = "physical_total"
ATTR_REASON = "reason"
ATTR_OFFSET = "offset"
ATTR_LIMIT = "limit"
ATTR_SOURCE = "source"
ATTR_RESULT = "result"

SERVICE_START_MANUAL = "start_manual"
SERVICE_CREATE_MANUAL = "create_manual"
SERVICE_START_MANUAL_FROM_CARD = "start_manual_from_card"
SERVICE_CANCEL_REQUEST = "cancel_request"
SERVICE_STOP = "stop"
SERVICE_EMERGENCY_STOP = "emergency_stop"
SERVICE_SET_INSTALLATION_OPERATION = "set_installation_operation"
SERVICE_SET_INSTALLATION_AUTOMATION = "set_installation_automation"
SERVICE_SET_ZONE_OPERATION = "set_zone_operation"
SERVICE_SET_ZONE_AUTOMATION = "set_zone_automation"
SERVICE_RESET_SAFETY_LOCK = "reset_safety_lock"
SERVICE_PLAN_AUTOMATIC = "plan_automatic"
SERVICE_CORRECT_PHYSICAL_METER = "correct_physical_meter"
SERVICE_LIST_CARD_ORDERS = "list_card_orders"
SERVICE_LIST_ZONE_HISTORY = "list_zone_history"


def _validate_manual_target(data: dict[str, object]) -> dict[str, object]:
    """Require one complete timed or volume target."""
    if sum(key in data for key in (ATTR_DURATION, ATTR_AMOUNT)) != 1:
        raise vol.Invalid("Exactly one of duration or amount must be provided")
    if ATTR_AMOUNT in data and ATTR_HARD_TIME_LIMIT not in data:
        raise vol.Invalid("Amount targets require hard_time_limit")
    if ATTR_DURATION in data and ATTR_HARD_TIME_LIMIT in data:
        raise vol.Invalid("hard_time_limit is only valid for amount targets")
    return data


_MANUAL_TARGET_FIELDS: dict[vol.Marker, object] = {
    vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.001, max=604_800)),
    vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
    vol.Optional(ATTR_HARD_TIME_LIMIT): vol.All(
        vol.Coerce(float), vol.Range(min=0.001, max=604_800)
    ),
}

START_MANUAL_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
            **_MANUAL_TARGET_FIELDS,
            vol.Optional(ATTR_EXPIRY): vol.All(
                vol.Coerce(float), vol.Range(min=0.001, max=604_800)
            ),
            vol.Optional(ATTR_START_AT): cv.datetime,
        }
    ),
    _validate_manual_target,
)
START_MANUAL_FROM_CARD_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
            **_MANUAL_TARGET_FIELDS,
            vol.Required(ATTR_CONFLICT_POLICY): vol.In(
                {"start_now", "stop_active", "priority_next"}
            ),
        }
    ),
    _validate_manual_target,
)
INSTALLATION_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})
REQUEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_REQUEST_ID): cv.string,
    }
)
STOP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_EXECUTION_ID): cv.string,
    }
)
INSTALLATION_OPERATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ENABLED): cv.boolean,
    }
)
INSTALLATION_AUTOMATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ENABLED): cv.boolean,
        vol.Optional(ATTR_STOP_ACTIVE, default=False): cv.boolean,
    }
)
ZONE_OPERATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_ENABLED): cv.boolean,
    }
)
ZONE_AUTOMATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_ENABLED): cv.boolean,
        vol.Optional(ATTR_STOP_ACTIVE, default=False): cv.boolean,
    }
)
CORRECT_PHYSICAL_METER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PHYSICAL_TOTAL): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(ATTR_REASON): cv.string,
    }
)
ZONE_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Optional(ATTR_OFFSET, default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_LIMIT, default=20): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        vol.Optional(ATTR_SOURCE): vol.In({"manual", "automatic", "calibration"}),
        vol.Optional(ATTR_RESULT): cv.string,
    }
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register the version 2 action surface."""

    def manager_for(call: ServiceCall) -> IrrigationManager:
        manager = hass.data[DOMAIN].get(call.data[ATTR_CONFIG_ENTRY_ID])
        if not isinstance(manager, IrrigationManager):
            raise HomeAssistantError("The irrigation installation is not loaded")
        return manager

    async def require_admin(call: ServiceCall) -> User | None:
        user_id = call.context.user_id
        if user_id is None:
            return None
        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            raise Unauthorized(context=call.context)
        return user

    async def require_manual_control(
        call: ServiceCall,
        manager: IrrigationManager,
        *,
        zone_subentry_ids: tuple[str, ...] = (),
        request_ids: tuple[str, ...] = (),
        execution_ids: tuple[str, ...] = (),
    ) -> None:
        user_id = call.context.user_id
        if user_id is None:
            return
        user = await hass.auth.async_get_user(user_id)
        entity_ids = manager.manual_control_entity_ids(
            zone_subentry_ids=zone_subentry_ids,
            request_ids=request_ids,
            execution_ids=execution_ids,
        )
        if user is None or any(
            not user.permissions.check_entity(entity_id, POLICY_CONTROL) for entity_id in entity_ids
        ):
            raise Unauthorized(context=call.context, permission=POLICY_CONTROL)

    async def request_manual(call: ServiceCall, *, wait: bool) -> dict[str, Any]:
        manager = manager_for(call)
        zone_subentry_id = cast(str, call.data[ATTR_ZONE_SUBENTRY_ID])
        await require_manual_control(call, manager, zone_subentry_ids=(zone_subentry_id,))
        return await manager.async_start_manual(
            zone_subentry_id=zone_subentry_id,
            duration_seconds=cast(float | None, call.data.get(ATTR_DURATION)),
            amount_liters=cast(float | None, call.data.get(ATTR_AMOUNT)),
            hard_time_limit_seconds=cast(float | None, call.data.get(ATTR_HARD_TIME_LIMIT)),
            expiry_seconds=cast(float | None, call.data.get(ATTR_EXPIRY)),
            requested_start_at=cast(Any, call.data.get(ATTR_START_AT)),
            wait_for_completion=wait,
        )

    async def start_manual(call: ServiceCall) -> dict[str, Any]:
        return await request_manual(call, wait=True)

    async def create_manual(call: ServiceCall) -> dict[str, Any]:
        return await request_manual(call, wait=False)

    async def start_manual_from_card(call: ServiceCall) -> dict[str, Any]:
        manager = manager_for(call)
        zone_subentry_id = cast(str, call.data[ATTR_ZONE_SUBENTRY_ID])
        await require_manual_control(call, manager, zone_subentry_ids=(zone_subentry_id,))
        return await manager.async_start_manual(
            zone_subentry_id=zone_subentry_id,
            duration_seconds=cast(float | None, call.data.get(ATTR_DURATION)),
            amount_liters=cast(float | None, call.data.get(ATTR_AMOUNT)),
            hard_time_limit_seconds=cast(float | None, call.data.get(ATTR_HARD_TIME_LIMIT)),
            wait_for_completion=False,
            conflict_policy=cast(str, call.data[ATTR_CONFLICT_POLICY]),
        )

    async def cancel_request(call: ServiceCall) -> None:
        manager = manager_for(call)
        request_id = cast(str, call.data[ATTR_REQUEST_ID])
        await require_manual_control(call, manager, request_ids=(request_id,))
        await manager.async_cancel_request(request_id)

    async def stop(call: ServiceCall) -> None:
        manager = manager_for(call)
        execution_id = cast(str, call.data[ATTR_EXECUTION_ID])
        await require_manual_control(call, manager, execution_ids=(execution_id,))
        await manager.async_stop(execution_id=execution_id)

    async def emergency_stop(call: ServiceCall) -> None:
        manager = manager_for(call)
        user_id = call.context.user_id
        if user_id is not None:
            user = await hass.auth.async_get_user(user_id)
            entities = manager.emergency_control_entity_ids()
            if user is None or (
                not user.is_admin
                and any(
                    not user.permissions.check_entity(entity_id, POLICY_CONTROL)
                    for entity_id in entities
                )
            ):
                raise Unauthorized(context=call.context, permission=POLICY_CONTROL)
        await manager.async_emergency_stop()

    async def set_installation_operation(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_set_installation_operation(
            enabled=cast(bool, call.data[ATTR_ENABLED])
        )

    async def set_installation_automation(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_set_installation_automation(
            enabled=cast(bool, call.data[ATTR_ENABLED]),
            stop_active=cast(bool, call.data[ATTR_STOP_ACTIVE]),
        )

    async def set_zone_operation(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_set_zone_operation(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            enabled=cast(bool, call.data[ATTR_ENABLED]),
        )

    async def set_zone_automation(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_set_zone_automation(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            enabled=cast(bool, call.data[ATTR_ENABLED]),
            stop_active=cast(bool, call.data[ATTR_STOP_ACTIVE]),
        )

    async def reset_safety_lock(call: ServiceCall) -> None:
        await require_admin(call)
        await manager_for(call).async_reset_safety_lock()

    async def plan_automatic(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_plan_automatic()

    async def correct_physical_meter(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_correct_physical_meter(
            physical_total_liters=cast(float, call.data[ATTR_PHYSICAL_TOTAL]),
            reason=cast(str | None, call.data.get(ATTR_REASON)),
        )

    async def list_card_orders(call: ServiceCall) -> dict[str, Any]:
        return {"orders": manager_for(call).card_open_orders()}

    async def list_zone_history(call: ServiceCall) -> dict[str, Any]:
        return manager_for(call).zone_history_page(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            offset=cast(int, call.data[ATTR_OFFSET]),
            limit=cast(int, call.data[ATTR_LIMIT]),
            source=cast(str | None, call.data.get(ATTR_SOURCE)),
            result=cast(str | None, call.data.get(ATTR_RESULT)),
        )

    for service, handler in (
        (SERVICE_START_MANUAL, start_manual),
        (SERVICE_CREATE_MANUAL, create_manual),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=START_MANUAL_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MANUAL_FROM_CARD,
        start_manual_from_card,
        schema=START_MANUAL_FROM_CARD_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_REQUEST, cancel_request, schema=REQUEST_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP, stop, schema=STOP_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_EMERGENCY_STOP, emergency_stop, schema=INSTALLATION_SCHEMA
    )
    for service, handler, schema in (
        (
            SERVICE_SET_INSTALLATION_OPERATION,
            set_installation_operation,
            INSTALLATION_OPERATION_SCHEMA,
        ),
        (
            SERVICE_SET_INSTALLATION_AUTOMATION,
            set_installation_automation,
            INSTALLATION_AUTOMATION_SCHEMA,
        ),
        (SERVICE_SET_ZONE_OPERATION, set_zone_operation, ZONE_OPERATION_SCHEMA),
        (SERVICE_SET_ZONE_AUTOMATION, set_zone_automation, ZONE_AUTOMATION_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=schema,
            supports_response=SupportsResponse.ONLY,
        )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_SAFETY_LOCK, reset_safety_lock, schema=INSTALLATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAN_AUTOMATIC,
        plan_automatic,
        schema=INSTALLATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CORRECT_PHYSICAL_METER,
        correct_physical_meter,
        schema=CORRECT_PHYSICAL_METER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_CARD_ORDERS,
        list_card_orders,
        schema=INSTALLATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_ZONE_HISTORY,
        list_zone_history,
        schema=ZONE_HISTORY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
