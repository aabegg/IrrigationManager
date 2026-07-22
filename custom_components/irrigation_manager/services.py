"""Native Home Assistant actions exposed by Irrigation Manager."""

from datetime import date
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
ATTR_REQUEST_ID = "request_id"
ATTR_EXECUTION_ID = "execution_id"
ATTR_DRY_RUN = "dry_run"
ATTR_AT = "at"
ATTR_START_AT = "start_at"
ATTR_EXPIRES_AT = "expires_at"
ATTR_ITEMS = "items"
ATTR_REQUEST_IDS = "request_ids"
ATTR_PLAN_ID = "plan_id"
ATTR_PERIOD_ID = "period_id"
ATTR_REFERENCE_EVAPOTRANSPIRATION = "reference_evapotranspiration"
ATTR_RAIN = "rain"
ATTR_FORMAT = "format"
ATTR_LIMIT = "limit"
ATTR_RECONCILIATION_ID = "reconciliation_id"
ATTR_RESOLUTION = "resolution"
ATTR_TEST_ID = "test_id"
ATTR_BYPASS_CHECKS = "bypass_checks"
ATTR_PROPOSAL_ID = "proposal_id"
ATTR_PROFILE_ID = "profile_id"
ATTR_SOURCE_PROFILE_ID = "source_profile_id"
ATTR_NEW_PROFILE_ID = "new_profile_id"
ATTR_NAME = "name"
ATTR_CONFIG_HASH = "config_hash"
ATTR_PHYSICAL_TOTAL = "physical_total"
ATTR_PAYLOAD = "payload"
ATTR_ENTITY_REMAPPING = "entity_remapping"
ATTR_ZONE_REMAPPING = "zone_remapping"
ATTR_CONFIRM_OVERWRITE = "confirm_overwrite"
ATTR_UNTIL = "until"
ATTR_TASK_ID = "task_id"
ATTR_ITEM_ID = "item_id"
ATTR_COMPLETED = "completed"
ATTR_KIND = "kind"
ATTR_WATER_ATTRIBUTION = "water_attribution"

SERVICE_START_MANUAL = "start_manual"
SERVICE_CREATE_MANUAL = "create_manual"
SERVICE_LIST_REQUESTS = "list_requests"
SERVICE_CANCEL_REQUEST = "cancel_request"
SERVICE_EDIT_REQUEST = "edit_request"
SERVICE_REORDER_REQUESTS = "reorder_requests"
SERVICE_CREATE_MANUAL_PLAN = "create_manual_plan"
SERVICE_PAUSE_REQUEST = "pause_request"
SERVICE_RESUME_REQUEST = "resume_request"
SERVICE_STOP = "stop"
SERVICE_STOP_AND_SKIP = "stop_and_skip"
SERVICE_EMERGENCY_STOP = "emergency_stop"
SERVICE_RESET_EMERGENCY_STOP = "reset_emergency_stop"
SERVICE_RESET_ZONE_SAFETY = "reset_zone_safety"
SERVICE_RESET_INSTALLATION_SAFETY = "reset_installation_safety"
SERVICE_ASSIGN_WATER = "assign_water"
SERVICE_PLAN_AUTOMATIC = "plan_automatic"
SERVICE_FINALIZE_DAILY_WEATHER = "finalize_daily_weather"
SERVICE_SKIP_AUTOMATIC = "skip_automatic"
SERVICE_CLEAR_FORECAST_DEFERRAL = "clear_forecast_deferral"
SERVICE_EXPORT_CONFIG = "export_config"
SERVICE_EXPORT_HISTORY = "export_history"
SERVICE_RESOLVE_BALANCE_RECONCILIATION = "resolve_balance_reconciliation"
SERVICE_SET_WINTER_LOCK = "set_winter_lock"
SERVICE_CLEAR_WINTER_LOCK = "clear_winter_lock"
SERVICE_START_MAINTENANCE_TEST = "start_maintenance_test"
SERVICE_CONFIRM_MAINTENANCE_TEST = "confirm_maintenance_test"
SERVICE_STOP_MAINTENANCE_TEST = "stop_maintenance_test"
SERVICE_START_CALIBRATION = "start_calibration"
SERVICE_GET_CALIBRATION_PROPOSAL = "get_calibration_proposal"
SERVICE_RESOLVE_CALIBRATION = "resolve_calibration"
SERVICE_LIST_PROFILES = "list_profiles"
SERVICE_PREVIEW_PROFILE_IMPACT = "preview_profile_impact"
SERVICE_COPY_PROFILE = "copy_profile"
SERVICE_CORRECT_PHYSICAL_METER = "correct_physical_meter"
SERVICE_IMPORT_CONFIG = "import_config"
SERVICE_ARCHIVE_ZONE = "archive_zone"
SERVICE_RESTORE_ZONE = "restore_zone"
SERVICE_SUSPEND_AUTOMATIC = "suspend_automatic"
SERVICE_RESUME_AUTOMATIC = "resume_automatic"
SERVICE_LIST_MAINTENANCE = "list_maintenance"
SERVICE_COMPLETE_MAINTENANCE_TASK = "complete_maintenance_task"
SERVICE_SNOOZE_MAINTENANCE_TASK = "snooze_maintenance_task"
SERVICE_UPDATE_SPRING_CHECKLIST = "update_spring_checklist"


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
            vol.Optional(ATTR_START_AT): cv.datetime,
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
EDIT_REQUEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_REQUEST_ID): cv.string,
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.001, max=14_400)),
        vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
        vol.Optional(ATTR_HARD_TIME_LIMIT): vol.All(
            vol.Coerce(float), vol.Range(min=0.001, max=14_400)
        ),
        vol.Optional(ATTR_START_AT): cv.datetime,
        vol.Optional(ATTR_EXPIRES_AT): cv.datetime,
    }
)
PLAN_ITEM_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
            vol.Optional(ATTR_DURATION): vol.All(
                vol.Coerce(float), vol.Range(min=0.001, max=14_400)
            ),
            vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
            vol.Optional(ATTR_HARD_TIME_LIMIT): vol.All(
                vol.Coerce(float), vol.Range(min=0.001, max=14_400)
            ),
        }
    ),
    _validate_manual_target,
)
CREATE_MANUAL_PLAN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ITEMS): vol.All(cv.ensure_list, [PLAN_ITEM_SCHEMA], vol.Length(min=1)),
        vol.Optional(ATTR_START_AT): cv.datetime,
        vol.Optional(ATTR_EXPIRY, default=3600): vol.All(
            vol.Coerce(float), vol.Range(min=0.001, max=604_800)
        ),
        vol.Optional(ATTR_PLAN_ID): cv.string,
    }
)
REORDER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_REQUEST_IDS): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
    }
)
ASSIGN_WATER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
    }
)
PLAN_AUTOMATIC_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
        vol.Optional(ATTR_AT): cv.datetime,
    }
)
FINALIZE_DAILY_WEATHER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PERIOD_ID): cv.string,
        vol.Required(ATTR_REFERENCE_EVAPOTRANSPIRATION): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
        vol.Required(ATTR_RAIN): vol.All(vol.Coerce(float), vol.Range(min=0, max=1_000)),
    }
)
EXPORT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_FORMAT, default="json"): vol.In({"json", "csv"}),
        vol.Optional(ATTR_LIMIT, default=100): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1_000)
        ),
    }
)
RECONCILIATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_RECONCILIATION_ID): cv.string,
        vol.Required(ATTR_RESOLUTION): vol.In({"apply", "discard"}),
    }
)
SUPERVISED_TEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
        vol.Optional(ATTR_BYPASS_CHECKS, default=[]): vol.All(
            cv.ensure_list,
            [vol.In({"feedback", "flow", "weather", "external"})],
        ),
        vol.Optional(ATTR_KIND, default="maintenance"): vol.In(
            {"maintenance", "spring_recommission"}
        ),
        vol.Optional(ATTR_WATER_ATTRIBUTION, default="zone"): vol.In({"zone", "unassigned"}),
    }
)
CALIBRATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
    }
)
TEST_ID_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_TEST_ID): cv.string,
    }
)
CALIBRATION_RESOLUTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PROPOSAL_ID): cv.string,
        vol.Required(ATTR_RESOLUTION): vol.In({"accept", "discard"}),
    }
)
PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PROFILE_ID): cv.string,
    }
)
COPY_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_SOURCE_PROFILE_ID): cv.string,
        vol.Required(ATTR_NEW_PROFILE_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_CONFIG_HASH): cv.string,
    }
)
CORRECT_PHYSICAL_METER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PHYSICAL_TOTAL): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
IMPORT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_PAYLOAD): dict,
        vol.Optional(ATTR_ENTITY_REMAPPING, default={}): dict,
        vol.Optional(ATTR_ZONE_REMAPPING, default={}): dict,
        vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
        vol.Optional(ATTR_CONFIRM_OVERWRITE, default=False): cv.boolean,
        vol.Optional(ATTR_CONFIG_HASH): cv.string,
    }
)
ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
    }
)
SUSPEND_AUTOMATIC_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_ZONE_SUBENTRY_ID): cv.string,
        vol.Required(ATTR_UNTIL): cv.datetime,
    }
)
RESUME_AUTOMATIC_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_ZONE_SUBENTRY_ID): cv.string,
    }
)
MAINTENANCE_TASK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_TASK_ID): cv.string,
    }
)
SNOOZE_MAINTENANCE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_TASK_ID): cv.string,
        vol.Required(ATTR_UNTIL): cv.date,
    }
)
SPRING_CHECKLIST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ITEM_ID): cv.string,
        vol.Required(ATTR_COMPLETED): cv.boolean,
    }
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration actions once per Home Assistant process."""

    def manager_for(call: ServiceCall) -> IrrigationManager:
        manager = hass.data[DOMAIN].get(call.data[ATTR_CONFIG_ENTRY_ID])
        if not isinstance(manager, IrrigationManager):
            raise HomeAssistantError("The irrigation installation is not loaded")
        return manager

    async def require_admin(call: ServiceCall) -> User | None:
        """Apply Home Assistant's admin-service semantics to lifecycle mutations."""
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
        all_open_requests: bool = False,
    ) -> None:
        """Require control permission for every valve affected by a manual action."""
        user_id = call.context.user_id
        if user_id is None:
            return
        user = await hass.auth.async_get_user(user_id)
        entity_ids = manager.manual_control_entity_ids(
            zone_subentry_ids=zone_subentry_ids,
            request_ids=request_ids,
            execution_ids=execution_ids,
            all_open_requests=all_open_requests,
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
            expiry_seconds=cast(float, call.data[ATTR_EXPIRY]),
            requested_start_at=cast(Any, call.data.get(ATTR_START_AT)),
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
            "uncredited_balance_deliveries": (manager.list_uncredited_balance_deliveries()),
        }

    async def stop(call: ServiceCall) -> None:
        manager = manager_for(call)
        request_id = cast(str | None, call.data.get(ATTR_REQUEST_ID))
        execution_id = cast(str | None, call.data.get(ATTR_EXECUTION_ID))
        if request_id is None and execution_id is None and manager.maintenance_test_active:
            await require_admin(call)
        await require_manual_control(
            call,
            manager,
            request_ids=(() if request_id is None else (request_id,)),
            execution_ids=(() if execution_id is None else (execution_id,)),
            all_open_requests=request_id is None and execution_id is None,
        )
        await manager.async_stop(
            request_id=request_id,
            execution_id=execution_id,
        )

    async def stop_and_skip(call: ServiceCall) -> dict[str, Any]:
        manager = manager_for(call)
        request_id = cast(str | None, call.data.get(ATTR_REQUEST_ID))
        execution_id = cast(str | None, call.data.get(ATTR_EXECUTION_ID))
        await require_manual_control(
            call,
            manager,
            request_ids=(() if request_id is None else (request_id,)),
            execution_ids=(() if execution_id is None else (execution_id,)),
            all_open_requests=request_id is None and execution_id is None,
        )
        return await manager.async_stop_and_skip(
            request_id=request_id,
            execution_id=execution_id,
            now=cast(Any, call.data.get(ATTR_AT)),
        )

    async def cancel_request(call: ServiceCall) -> None:
        manager = manager_for(call)
        request_id = cast(str, call.data[ATTR_REQUEST_ID])
        await require_manual_control(call, manager, request_ids=(request_id,))
        await manager.async_cancel_request(request_id)

    async def edit_request(call: ServiceCall) -> dict[str, Any]:
        manager = manager_for(call)
        request_id = cast(str, call.data[ATTR_REQUEST_ID])
        await require_manual_control(call, manager, request_ids=(request_id,))
        return await manager.async_edit_request(
            request_id=request_id,
            duration_seconds=cast(float | None, call.data.get(ATTR_DURATION)),
            amount_liters=cast(float | None, call.data.get(ATTR_AMOUNT)),
            hard_time_limit_seconds=cast(float | None, call.data.get(ATTR_HARD_TIME_LIMIT)),
            requested_start_at=cast(Any, call.data.get(ATTR_START_AT)),
            expires_at=cast(Any, call.data.get(ATTR_EXPIRES_AT)),
        )

    async def reorder_requests(call: ServiceCall) -> dict[str, Any]:
        manager = manager_for(call)
        request_ids = tuple(cast(list[str], call.data[ATTR_REQUEST_IDS]))
        await require_manual_control(call, manager, request_ids=request_ids)
        order = await manager.async_reorder_requests(request_ids)
        return {"request_ids": order}

    async def create_manual_plan(call: ServiceCall) -> dict[str, Any]:
        manager = manager_for(call)
        items = tuple(cast(list[dict[str, object]], call.data[ATTR_ITEMS]))
        await require_manual_control(
            call,
            manager,
            zone_subentry_ids=tuple(cast(str, item[ATTR_ZONE_SUBENTRY_ID]) for item in items),
        )
        return await manager.async_create_manual_plan(
            items=items,
            requested_start_at=cast(Any, call.data.get(ATTR_START_AT)),
            expiry_seconds=cast(float, call.data[ATTR_EXPIRY]),
            plan_id=cast(str | None, call.data.get(ATTR_PLAN_ID)),
        )

    async def pause_request(call: ServiceCall) -> None:
        manager = manager_for(call)
        request_id = cast(str, call.data[ATTR_REQUEST_ID])
        await require_manual_control(call, manager, request_ids=(request_id,))
        await manager.async_pause_request(request_id)

    async def resume_request(call: ServiceCall) -> None:
        manager = manager_for(call)
        request_id = cast(str, call.data[ATTR_REQUEST_ID])
        await require_manual_control(call, manager, request_ids=(request_id,))
        await manager.async_resume_request(request_id)

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

    async def plan_automatic(call: ServiceCall) -> dict[str, Any]:
        return await manager_for(call).async_plan_automatic(
            dry_run=cast(bool, call.data[ATTR_DRY_RUN]),
            now=cast(Any, call.data.get(ATTR_AT)),
        )

    async def finalize_daily_weather(call: ServiceCall) -> dict[str, Any]:
        return await manager_for(call).async_finalize_daily_weather(
            period_id=cast(str, call.data[ATTR_PERIOD_ID]),
            reference_evapotranspiration_mm=cast(
                float, call.data[ATTR_REFERENCE_EVAPOTRANSPIRATION]
            ),
            rain_mm=cast(float, call.data[ATTR_RAIN]),
        )

    async def skip_automatic(call: ServiceCall) -> dict[str, Any]:
        return await manager_for(call).async_skip_automatic(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            now=cast(Any, call.data.get(ATTR_AT)),
        )

    async def clear_forecast_deferral(call: ServiceCall) -> dict[str, Any]:
        return await manager_for(call).async_clear_forecast_deferral(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID])
        )

    async def export_config(call: ServiceCall) -> dict[str, Any]:
        return manager_for(call).export_portable_config()

    async def export_history(call: ServiceCall) -> dict[str, Any]:
        return manager_for(call).export_history(
            limit=cast(int, call.data[ATTR_LIMIT]),
            export_format=cast(str, call.data[ATTR_FORMAT]),
        )

    async def resolve_balance_reconciliation(call: ServiceCall) -> dict[str, Any]:
        return await manager_for(call).async_resolve_balance_reconciliation(
            reconciliation_id=cast(str, call.data[ATTR_RECONCILIATION_ID]),
            resolution=cast(str, call.data[ATTR_RESOLUTION]),
        )

    async def set_winter_lock(call: ServiceCall) -> None:
        await require_admin(call)
        await manager_for(call).async_set_winter_lock()

    async def clear_winter_lock(call: ServiceCall) -> None:
        await require_admin(call)
        await manager_for(call).async_clear_winter_lock()

    async def start_maintenance_test(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_start_maintenance_test(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            duration_seconds=cast(float, call.data[ATTR_DURATION]),
            bypass_checks=tuple(cast(list[str], call.data[ATTR_BYPASS_CHECKS])),
            kind=cast(str, call.data[ATTR_KIND]),
            water_attribution=cast(str, call.data[ATTR_WATER_ATTRIBUTION]),
        )

    async def confirm_maintenance_test(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_confirm_maintenance_test(
            test_id=cast(str, call.data[ATTR_TEST_ID])
        )

    async def stop_maintenance_test(call: ServiceCall) -> None:
        await require_admin(call)
        await manager_for(call).async_stop_maintenance_test()

    async def start_calibration(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_start_maintenance_test(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]),
            duration_seconds=cast(float, call.data[ATTR_DURATION]),
            kind="calibration",
        )

    async def get_calibration_proposal(call: ServiceCall) -> dict[str, Any]:
        return {"proposal": manager_for(call).calibration_proposal()}

    async def resolve_calibration(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_resolve_calibration(
            proposal_id=cast(str, call.data[ATTR_PROPOSAL_ID]),
            resolution=cast(str, call.data[ATTR_RESOLUTION]),
        )

    async def list_profiles(call: ServiceCall) -> dict[str, Any]:
        return manager_for(call).list_profiles()

    async def preview_profile_impact(call: ServiceCall) -> dict[str, Any]:
        return manager_for(call).preview_profile_impact(cast(str, call.data[ATTR_PROFILE_ID]))

    async def copy_profile_service(call: ServiceCall) -> dict[str, Any]:
        return await manager_for(call).async_copy_profile(
            source_id=cast(str, call.data[ATTR_SOURCE_PROFILE_ID]),
            new_id=cast(str, call.data[ATTR_NEW_PROFILE_ID]),
            name=cast(str, call.data[ATTR_NAME]),
            expected_config_hash=cast(str | None, call.data.get(ATTR_CONFIG_HASH)),
        )

    async def correct_physical_meter(call: ServiceCall) -> dict[str, Any]:
        return await manager_for(call).async_correct_physical_meter(
            physical_total_liters=cast(float, call.data[ATTR_PHYSICAL_TOTAL])
        )

    async def import_config(call: ServiceCall) -> dict[str, Any]:
        user = await require_admin(call)
        return await manager_for(call).async_import_portable_config(
            payload=cast(dict[str, object], call.data[ATTR_PAYLOAD]),
            entity_remapping=cast(dict[str, str], call.data[ATTR_ENTITY_REMAPPING]),
            zone_remapping=cast(dict[str, str], call.data[ATTR_ZONE_REMAPPING]),
            dry_run=cast(bool, call.data[ATTR_DRY_RUN]),
            confirm_overwrite=cast(bool, call.data[ATTR_CONFIRM_OVERWRITE]),
            expected_config_hash=cast(str | None, call.data.get(ATTR_CONFIG_HASH)),
            user=user,
        )

    async def archive_zone(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_set_zone_archived(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]), archived=True
        )

    async def restore_zone(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_set_zone_archived(
            zone_subentry_id=cast(str, call.data[ATTR_ZONE_SUBENTRY_ID]), archived=False
        )

    async def suspend_automatic(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_suspend_automatic(
            until=cast(Any, call.data[ATTR_UNTIL]),
            zone_subentry_id=cast(str | None, call.data.get(ATTR_ZONE_SUBENTRY_ID)),
        )

    async def resume_automatic(call: ServiceCall) -> None:
        await require_admin(call)
        await manager_for(call).async_resume_automatic(
            zone_subentry_id=cast(str | None, call.data.get(ATTR_ZONE_SUBENTRY_ID))
        )

    async def list_maintenance(call: ServiceCall) -> dict[str, Any]:
        return manager_for(call).list_maintenance()

    async def complete_maintenance_task(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_complete_maintenance_task(
            task_id=cast(str, call.data[ATTR_TASK_ID])
        )

    async def snooze_maintenance_task(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        until = call.data[ATTR_UNTIL]
        return await manager_for(call).async_snooze_maintenance_task(
            task_id=cast(str, call.data[ATTR_TASK_ID]),
            until=until if isinstance(until, date) else date.fromisoformat(str(until)),
        )

    async def update_spring_checklist(call: ServiceCall) -> dict[str, Any]:
        await require_admin(call)
        return await manager_for(call).async_update_spring_checklist(
            item_id=cast(str, call.data[ATTR_ITEM_ID]),
            completed=cast(bool, call.data[ATTR_COMPLETED]),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MANUAL,
        start_manual,
        schema=START_MANUAL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    for service, handler in (
        (SERVICE_ARCHIVE_ZONE, archive_zone),
        (SERVICE_RESTORE_ZONE, restore_zone),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=ZONE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SUSPEND_AUTOMATIC,
        suspend_automatic,
        schema=SUSPEND_AUTOMATIC_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME_AUTOMATIC,
        resume_automatic,
        schema=RESUME_AUTOMATIC_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_MAINTENANCE,
        list_maintenance,
        schema=INSTALLATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_MAINTENANCE_TASK,
        complete_maintenance_task,
        schema=MAINTENANCE_TASK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SNOOZE_MAINTENANCE_TASK,
        snooze_maintenance_task,
        schema=SNOOZE_MAINTENANCE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_SPRING_CHECKLIST,
        update_spring_checklist,
        schema=SPRING_CHECKLIST_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_WINTER_LOCK, set_winter_lock, schema=INSTALLATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_WINTER_LOCK, clear_winter_lock, schema=INSTALLATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MAINTENANCE_TEST,
        start_maintenance_test,
        schema=SUPERVISED_TEST_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CONFIRM_MAINTENANCE_TEST,
        confirm_maintenance_test,
        schema=TEST_ID_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_MAINTENANCE_TEST,
        stop_maintenance_test,
        schema=INSTALLATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CALIBRATION,
        start_calibration,
        schema=CALIBRATION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CALIBRATION_PROPOSAL,
        get_calibration_proposal,
        schema=INSTALLATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESOLVE_CALIBRATION,
        resolve_calibration,
        schema=CALIBRATION_RESOLUTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_PROFILES,
        list_profiles,
        schema=INSTALLATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PREVIEW_PROFILE_IMPACT,
        preview_profile_impact,
        schema=PROFILE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_COPY_PROFILE,
        copy_profile_service,
        schema=COPY_PROFILE_SCHEMA,
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
        SERVICE_IMPORT_CONFIG,
        import_config,
        schema=IMPORT_CONFIG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_CONFIG,
        export_config,
        schema=INSTALLATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_HISTORY,
        export_history,
        schema=EXPORT_HISTORY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESOLVE_BALANCE_RECONCILIATION,
        resolve_balance_reconciliation,
        schema=RECONCILIATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SKIP_AUTOMATIC,
        skip_automatic,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
                vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
                vol.Optional(ATTR_AT): cv.datetime,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_FORECAST_DEFERRAL,
        clear_forecast_deferral,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
                vol.Required(ATTR_ZONE_SUBENTRY_ID): cv.string,
            }
        ),
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
        SERVICE_CREATE_MANUAL_PLAN,
        create_manual_plan,
        schema=CREATE_MANUAL_PLAN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
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
        DOMAIN,
        SERVICE_STOP_AND_SKIP,
        stop_and_skip,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
                vol.Exclusive(ATTR_REQUEST_ID, "target"): cv.string,
                vol.Exclusive(ATTR_EXECUTION_ID, "target"): cv.string,
                vol.Optional(ATTR_AT): cv.datetime,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_REQUEST, cancel_request, schema=REQUEST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EDIT_REQUEST,
        edit_request,
        schema=EDIT_REQUEST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REORDER_REQUESTS,
        reorder_requests,
        schema=REORDER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAN_AUTOMATIC,
        plan_automatic,
        schema=PLAN_AUTOMATIC_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FINALIZE_DAILY_WEATHER,
        finalize_daily_weather,
        schema=FINALIZE_DAILY_WEATHER_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
