"""Versioned Home Assistant storage for critical irrigation state."""

from datetime import datetime, timedelta
from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import StoredInstallationState

STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 25


class _StateStore(Store[dict[str, object]]):
    """Migrate durable irrigation state between additive schema revisions."""

    @override
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, object],
    ) -> dict[str, object]:
        """Add fields introduced by additive 1.x schema revisions."""
        if old_major_version == 1 and old_minor_version in {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
        }:
            migrated = dict(old_data)
            if old_minor_version == 1:
                migrated["active_execution"] = None
            if old_minor_version < 3:
                migrated["zone_last_delivered_liters"] = {}
                migrated["zone_last_duration_seconds"] = {}
            if old_minor_version < 4:
                migrated["zone_safety_locks"] = {}
            if old_minor_version < 5:
                migrated["installation_safety_lock"] = None
            if old_minor_version < 6:
                migrated["unassigned_measurement_quality"] = "unknown"
                migrated["unassigned_measurement_origin"] = "unknown"
                migrated["idle_meter_raw_baseline_liters"] = None
            if old_minor_version == 6:
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    raw_active = dict(raw_active)
                    raw_active["requested_amount_liters"] = None
                    raw_active["hard_time_limit_seconds"] = None
                    raw_active["meter_failure_strategy"] = "abort"
                    raw_active["zone_opening_at"] = None
                    raw_active["fallback_started_at"] = None
                    raw_active["fallback_checkpoint_at"] = None
                    raw_active["delivered_liters_at_fallback"] = 0.0
                    migrated["active_execution"] = raw_active
            if old_minor_version < 8:
                migrated["manual_requests"] = []
                migrated["irrigation_executions"] = []
                migrated["next_request_sequence"] = 1
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    raw_active = dict(raw_active)
                    raw_active["request_id"] = None
                    raw_active["execution_id"] = None
                    raw_active["dose_number"] = 1
                    raw_active["dose_target_value"] = None
                    migrated["active_execution"] = raw_active
            if old_minor_version < 9:
                raw_requests = migrated.get("manual_requests", [])
                if isinstance(raw_requests, list):
                    migrated["manual_requests"] = [
                        {**request, "revision": 1} if isinstance(request, dict) else request
                        for request in raw_requests
                    ]
            if old_minor_version < 10:
                migrated["zone_deficit_mm"] = {}
                migrated["zone_last_effective_irrigation"] = {}
                migrated["finalized_weather_periods"] = {}
            if old_minor_version < 11:
                migrated["suppressed_automatic_opportunities"] = []
                snapshot_defaults = {
                    "balance_area_m2": None,
                    "balance_application_efficiency": None,
                    "balance_maximum_deficit_mm": None,
                    "balance_minimum_effective_liters": None,
                }
                for key in ("manual_requests", "irrigation_executions"):
                    records = migrated.get(key, [])
                    if isinstance(records, list):
                        migrated[key] = [
                            {**record, **snapshot_defaults} if isinstance(record, dict) else record
                            for record in records
                        ]
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    migrated["active_execution"] = {**raw_active, **snapshot_defaults}
            if old_minor_version < 12:
                migrated["uncredited_balance_deliveries"] = []
                requests = migrated.get("manual_requests", [])
                executions = migrated.get("irrigation_executions", [])
                request_records = requests if isinstance(requests, list) else []
                execution_records = executions if isinstance(executions, list) else []
                request_by_id = {
                    request.get("request_id"): request
                    for request in request_records
                    if isinstance(request, dict) and isinstance(request.get("request_id"), str)
                }
                execution_by_id = {
                    execution.get("execution_id"): execution
                    for execution in execution_records
                    if isinstance(execution, dict)
                    and isinstance(execution.get("execution_id"), str)
                }
                for execution in execution_by_id.values():
                    linked_request = request_by_id.get(execution.get("request_id"))
                    if isinstance(linked_request, dict):
                        _backfill_balance_snapshot(execution, linked_request)
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    linked_execution = execution_by_id.get(raw_active.get("execution_id"))
                    linked_request = request_by_id.get(raw_active.get("request_id"))
                    if isinstance(linked_execution, dict):
                        _backfill_balance_snapshot(raw_active, linked_execution)
                    if isinstance(linked_request, dict):
                        _backfill_balance_snapshot(raw_active, linked_request)
            if old_minor_version < 13:
                migrated["winter_lock"] = False
                migrated["maintenance_test"] = None
                migrated["calibration_proposal"] = None
            if old_minor_version < 14:
                raw_proposal = migrated.get("calibration_proposal")
                if isinstance(raw_proposal, dict):
                    migrated["calibration_proposal"] = {
                        **raw_proposal,
                        "zone_valve": "",
                        "zone_config_hash": "",
                    }
            if old_minor_version < 15:
                requests = migrated.get("manual_requests", [])
                if isinstance(requests, list):
                    migrated["manual_requests"] = [
                        {
                            **request,
                            "delivery_runtime_limit_seconds": request.get(
                                "hard_time_limit_seconds"
                            ),
                            "operation_deadline_at": request.get("expires_at"),
                        }
                        if isinstance(request, dict)
                        else request
                        for request in requests
                    ]
                executions = migrated.get("irrigation_executions", [])
                if isinstance(executions, list):
                    migrated["irrigation_executions"] = [
                        {
                            **execution,
                            "delivery_runtime_limit_seconds": None,
                            "operation_deadline_at": None,
                        }
                        if isinstance(execution, dict)
                        else execution
                        for execution in executions
                    ]
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    migrated["active_execution"] = {
                        **raw_active,
                        "delivery_deadline_at": None,
                        "operation_deadline_at": None,
                    }
            if old_minor_version < 16:
                requests = migrated.get("manual_requests", [])
                if isinstance(requests, list):
                    migrated["manual_requests"] = [
                        _migrate_request_runtime_limits(request)
                        if isinstance(request, dict)
                        else request
                        for request in requests
                    ]
                executions = migrated.get("irrigation_executions", [])
                if isinstance(executions, list):
                    migrated["irrigation_executions"] = [
                        _migrate_execution_runtime_limits(execution)
                        if isinstance(execution, dict)
                        else execution
                        for execution in executions
                    ]
            if old_minor_version < 17:
                migrated["weather_calculation_snapshots"] = {}
                migrated["weather_failure_since"] = None
            if old_minor_version < 18:
                migrated["forecast_deferral_started"] = {}
            if old_minor_version < 19:
                migrated["forecast_deferral_deadlines"] = {}
            if old_minor_version < 20:
                migrated["cancelled_forecast_deferrals"] = []
            if old_minor_version < 21:
                migrated["budget_usage_liters"] = {}
                requests = migrated.get("manual_requests", [])
                if isinstance(requests, list):
                    migrated["manual_requests"] = [
                        {
                            **request,
                            "requested_start_at": None,
                            "pause_until": None,
                            "plan_id": None,
                        }
                        if isinstance(request, dict)
                        else request
                        for request in requests
                    ]
            if old_minor_version < 22:
                for key in ("manual_requests", "irrigation_executions"):
                    records = migrated.get(key, [])
                    if isinstance(records, list):
                        migrated[key] = [
                            {**record, "resolved_inputs": {}}
                            if isinstance(record, dict)
                            else record
                            for record in records
                        ]
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    migrated["active_execution"] = {**raw_active, "resolved_inputs": {}}
            if old_minor_version < 23:
                migrated["unassigned_available_liters"] = migrated.get(
                    "unassigned_total_liters", 0.0
                )
                migrated["meter_accumulated_liters"] = None
                migrated["meter_last_raw_liters"] = None
                migrated["meter_correction_liters"] = 0.0
                migrated["meter_reset_count"] = 0
                executions = migrated.get("irrigation_executions", [])
                if isinstance(executions, list):
                    migrated["water_consumption_history"] = [
                        {
                            "recorded_at": execution["ended_at"],
                            "amount_liters": execution.get("delivered_liters", 0.0),
                            "zone_id": execution.get("zone_id"),
                            "source": "historical_execution",
                            "quality": execution.get("measurement_quality", "unknown"),
                            "request_id": execution.get("request_id"),
                            "execution_id": execution.get("execution_id"),
                            "dose_number": execution.get("dose_number"),
                            "warnings": [],
                        }
                        for execution in executions
                        if isinstance(execution, dict)
                        and isinstance(execution.get("ended_at"), str)
                        and isinstance(execution.get("delivered_liters"), int | float)
                        and execution.get("delivered_liters", 0.0) > 0
                    ]
                    migrated["irrigation_executions"] = [
                        {
                            **execution,
                            "measurement_quality": "unknown",
                            "measurement_origin": "unknown",
                            "warnings": [],
                            "doses": [],
                        }
                        if isinstance(execution, dict)
                        else execution
                        for execution in executions
                    ]
                else:
                    migrated["water_consumption_history"] = []
            if old_minor_version < 24:
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    migrated["active_execution"] = {
                        **raw_active,
                        "fallback_quality": "estimated",
                    }
            if old_minor_version < 25:
                migrated["meter_source_entity_id"] = None
                migrated["meter_source_liters_per_count"] = None
                migrated["water_history_incomplete"] = False
            return migrated
        raise NotImplementedError


def _backfill_balance_snapshot(target: dict[str, object], source: dict[str, object]) -> None:
    """Copy only missing immutable balance fields between linked durable records."""
    for field in (
        "balance_area_m2",
        "balance_application_efficiency",
        "balance_maximum_deficit_mm",
        "balance_minimum_effective_liters",
    ):
        if target.get(field) is None and source.get(field) is not None:
            target[field] = source[field]


def _conservative_deadline(data: dict[str, object], *, lifetime_seconds: float) -> str:
    """Derive a bounded deadline using only fields available inside storage migration."""
    created_at = data.get("created_at")
    expires_at = data.get("expires_at")
    if not isinstance(created_at, str):
        raise ValueError("Stored irrigation runtime has no creation timestamp")
    deadline = datetime.fromisoformat(created_at) + timedelta(seconds=lifetime_seconds)
    if isinstance(expires_at, str):
        deadline = min(deadline, datetime.fromisoformat(expires_at))
    return deadline.isoformat()


def _migrate_request_runtime_limits(request: dict[str, object]) -> dict[str, object]:
    """Give every legacy request conservative non-null limits pending config derivation."""
    hard_limit = request.get("hard_time_limit_seconds")
    delivery_limit = float(hard_limit) if isinstance(hard_limit, int | float) else 3_600.0
    return {
        **request,
        "delivery_runtime_limit_seconds": delivery_limit,
        "operation_deadline_at": _conservative_deadline(request, lifetime_seconds=14_400),
        "runtime_limits_need_config_derivation": True,
    }


def _migrate_execution_runtime_limits(execution: dict[str, object]) -> dict[str, object]:
    """Give every legacy execution conservative non-null limits pending config derivation."""
    return {
        **execution,
        "delivery_runtime_limit_seconds": 3_600.0,
        "operation_deadline_at": _conservative_deadline(execution, lifetime_seconds=14_400),
        "runtime_limits_need_config_derivation": True,
    }


class IrrigationStore:
    """Persist one irrigation installation independently of entity restore."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage isolated by config entry ID."""
        self._store = _StateStore(
            hass,
            STORAGE_VERSION,
            f"irrigation_manager.{entry_id}",
            atomic_writes=True,
            minor_version=STORAGE_MINOR_VERSION,
        )

    async def async_load(self) -> StoredInstallationState:
        """Load the installation state or return a clean initial state."""
        return StoredInstallationState.from_dict(await self._store.async_load())

    async def async_save(self, state: StoredInstallationState) -> None:
        """Atomically persist a critical state transition."""
        await self._store.async_save(state.as_dict())

    async def async_remove(self) -> None:
        """Remove storage after the config entry is deleted."""
        await self._store.async_remove()
