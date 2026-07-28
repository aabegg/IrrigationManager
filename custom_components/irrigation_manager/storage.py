"""Versioned Home Assistant storage for the version-2 runtime."""

import math
from collections.abc import Callable
from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import (
    ActiveExecutionState,
    CalibrationProposal,
    IrrigationExecutionState,
    ManualIrrigationRequest,
    StoredInstallationState,
    WaterConsumptionRecord,
)

STORAGE_VERSION = 2
STORAGE_MINOR_VERSION = 3


def _valid_records[T](value: object, loader: Callable[[dict[str, object]], T]) -> tuple[T, ...]:
    """Load independently valid records and discard malformed legacy entries."""
    if not isinstance(value, list):
        return ()
    result: list[T] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            result.append(loader(item))
        except TypeError, ValueError:
            continue
    return tuple(result)


def _valid_optional[T](value: object, loader: Callable[[dict[str, object]], T]) -> T | None:
    """Load one optional current record without carrying malformed legacy data."""
    if not isinstance(value, dict):
        return None
    try:
        return loader(value)
    except TypeError, ValueError:
        return None


def _number(value: object, default: float = 0.0) -> float:
    """Copy one valid JSON number or use a safe default."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    return default


def _optional_number(value: object) -> float | None:
    """Copy one valid optional JSON number."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    return None


def _number_dict(value: object) -> dict[str, float]:
    """Copy only valid numeric map entries."""
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
        if isinstance(item, int | float)
        and not isinstance(item, bool)
        and math.isfinite(float(item))
    }


def _string_dict(value: object) -> dict[str, str]:
    """Copy only valid string map entries."""
    if not isinstance(value, dict):
        return {}
    return {
        key: item for key, item in value.items() if isinstance(key, str) and isinstance(item, str)
    }


def _bool_dict(value: object) -> dict[str, bool]:
    """Copy only valid release entries."""
    if not isinstance(value, dict):
        return {}
    return {
        key: item for key, item in value.items() if isinstance(key, str) and isinstance(item, bool)
    }


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _string_or(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _bool_or(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _migrate_rc6(old_data: dict[str, object]) -> dict[str, object]:
    """Copy only valid v2 state from the shipped rc6 storage schema."""
    active = _valid_optional(old_data.get("active_execution"), ActiveExecutionState.from_dict)
    active_request_id = active.request_id if active is not None else None
    active_execution_id = active.execution_id if active is not None else None

    requests = _valid_records(old_data.get("manual_requests"), ManualIrrigationRequest.from_dict)
    requests = tuple(
        request
        for request in requests
        if (
            request.source != "automatic"
            or (
                request.status == "executing"
                and request.request_id == active_request_id
                and request.execution_id == active_execution_id
            )
        )
    )
    executions = _valid_records(
        old_data.get("irrigation_executions"), IrrigationExecutionState.from_dict
    )
    executions = tuple(
        execution
        for execution in executions
        if execution.status in {"completed", "failed", "cancelled", "interrupted"}
        or (execution.execution_id == active_execution_id and execution.status == "watering")
    )
    if active is not None and not (
        any(
            request.request_id == active_request_id and request.status == "executing"
            for request in requests
        )
        and any(
            execution.execution_id == active_execution_id and execution.status == "watering"
            for execution in executions
        )
    ):
        active = None
        requests = tuple(request for request in requests if request.status != "executing")
        executions = tuple(execution for execution in executions if execution.status != "watering")

    reset_count = old_data.get("meter_reset_count", 0)
    next_sequence = old_data.get("next_request_sequence", 1)
    emergency_stop = _bool_or(old_data.get("emergency_stop"), False)
    installation_lock = _optional_string(old_data.get("installation_safety_lock"))
    if emergency_stop and installation_lock is None:
        installation_lock = "Emergency stop activated"
    state = StoredInstallationState(
        installation_total_liters=_number(old_data.get("installation_total_liters")),
        zone_totals_liters=_number_dict(old_data.get("zone_totals_liters")),
        zone_measurement_quality=_string_dict(old_data.get("zone_measurement_quality")),
        zone_last_delivered_liters=_number_dict(old_data.get("zone_last_delivered_liters")),
        zone_last_duration_seconds=_number_dict(old_data.get("zone_last_duration_seconds")),
        unassigned_total_liters=_number(old_data.get("unassigned_total_liters")),
        unassigned_available_liters=_number(
            old_data.get("unassigned_available_liters"),
            _number(old_data.get("unassigned_total_liters")),
        ),
        unassigned_measurement_quality=_string_or(
            old_data.get("unassigned_measurement_quality"), "unknown"
        ),
        unassigned_measurement_origin=_string_or(
            old_data.get("unassigned_measurement_origin"), "unknown"
        ),
        idle_meter_raw_baseline_liters=_optional_number(
            old_data.get("idle_meter_raw_baseline_liters")
        ),
        emergency_stop=emergency_stop,
        installation_safety_lock=installation_lock,
        installation_safety_lock_at=_optional_string(old_data.get("installation_safety_lock_at")),
        calibration_proposal=_valid_optional(
            old_data.get("calibration_proposal"), CalibrationProposal.from_dict
        ),
        active_execution=active,
        manual_requests=requests,
        irrigation_executions=executions,
        next_request_sequence=max(
            (
                next_sequence
                if isinstance(next_sequence, int) and not isinstance(next_sequence, bool)
                else 1
            ),
            max((request.sequence for request in requests), default=0) + 1,
        ),
        meter_accumulated_liters=_optional_number(old_data.get("meter_accumulated_liters")),
        meter_last_raw_liters=_optional_number(old_data.get("meter_last_raw_liters")),
        meter_correction_liters=_number(old_data.get("meter_correction_liters")),
        meter_reset_count=(
            reset_count if isinstance(reset_count, int) and not isinstance(reset_count, bool) else 0
        ),
        meter_source_entity_id=_optional_string(old_data.get("meter_source_entity_id")),
        meter_source_liters_per_count=_optional_number(
            old_data.get("meter_source_liters_per_count")
        ),
        water_consumption_history=_valid_records(
            old_data.get("water_consumption_history"), WaterConsumptionRecord.from_dict
        ),
        water_history_incomplete=_bool_or(old_data.get("water_history_incomplete"), False),
        operation_enabled=_optional_bool(old_data.get("operation_enabled")),
        automation_enabled=_optional_bool(old_data.get("automation_enabled")),
        zone_operation_enabled=_bool_dict(old_data.get("zone_operation_enabled")),
        zone_automation_enabled=_bool_dict(old_data.get("zone_automation_enabled")),
    )
    return state.as_dict()


class _StateStore(Store[dict[str, object]]):
    """Apply the single destructive migration into the v2 schema."""

    @override
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, object],
    ) -> dict[str, object]:
        if old_major_version == 1:
            return _migrate_rc6(old_data)
        if old_major_version == 2 and old_minor_version < STORAGE_MINOR_VERSION:
            return StoredInstallationState.from_dict(old_data).as_dict()
        raise NotImplementedError


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
