"""Tests for the single destructive rc6-to-v2 storage migration."""

from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    IrrigationExecutionState,
    ManualIrrigationRequest,
    StoredInstallationState,
    WaterConsumptionRecord,
)
from custom_components.irrigation_manager.storage import _StateStore


def _request(
    request_id: str,
    *,
    source: str = "manual",
    status: str = "completed",
    execution_id: str | None = None,
) -> ManualIrrigationRequest:
    return ManualIrrigationRequest(
        request_id=request_id,
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id="subentry-1",
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=0,
        created_at="2026-07-24T10:00:00+00:00",
        expires_at="2026-07-24T11:00:00+00:00",
        status=status,
        source=source,
        execution_id=execution_id,
        delivery_runtime_limit_seconds=60,
        operation_deadline_at="2026-07-24T11:00:00+00:00",
    )


def _execution(execution_id: str, request_id: str, *, status: str) -> IrrigationExecutionState:
    return IrrigationExecutionState(
        execution_id=execution_id,
        request_id=request_id,
        zone_id="zone-1",
        target_type="duration",
        target_value=60,
        remaining_value=0,
        status=status,
        created_at="2026-07-24T10:00:00+00:00",
        delivered_liters=12,
        delivered_duration_seconds=60,
        ended_at=("2026-07-24T10:01:00+00:00" if status == "completed" else None),
    )


async def test_rc6_migration_preserves_only_valid_v2_state() -> None:
    """Keep accounting, releases, lock state, and completed history."""
    completed_request = _request("completed")
    completed_execution = _execution("execution-completed", "completed", status="completed")
    history = WaterConsumptionRecord(
        recorded_at="2026-07-24T10:01:00+00:00",
        amount_liters=12,
        zone_id="zone-1",
        source="manual",
        quality="measured",
    )
    old_data = StoredInstallationState(
        installation_total_liters=120,
        zone_totals_liters={"zone-1": 100},
        unassigned_total_liters=20,
        meter_accumulated_liters=1_000,
        meter_last_raw_liters=10,
        meter_correction_liters=5,
        meter_reset_count=2,
        manual_requests=(completed_request,),
        irrigation_executions=(completed_execution,),
        water_consumption_history=(history,),
        emergency_stop=True,
        installation_safety_lock="valve_error",
        installation_safety_lock_at="2026-07-24T10:02:00+00:00",
        operation_enabled=False,
        automation_enabled=True,
        zone_operation_enabled={"zone-1": False},
        zone_automation_enabled={"zone-1": True},
    ).as_dict()
    old_data.update(
        {
            "weather_failure_since": "legacy",
            "zone_deficit_mm": {"zone-1": 9},
            "winter_lock": True,
            "archived_zones": {"zone-old": "legacy"},
            "installation_cost": 99,
        }
    )
    executions = old_data["irrigation_executions"]
    history_records = old_data["water_consumption_history"]
    assert isinstance(executions, list)
    assert isinstance(history_records, list)
    executions[0].update(
        {
            "dose_number": 3,
            "doses": [{"dose_number": 3, "duration_seconds": 60}],
        }
    )
    history_records[0]["dose_number"] = 3

    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None, 1, 29, old_data
    )
    state = StoredInstallationState.from_dict(migrated)

    assert state.installation_total_liters == 120
    assert state.zone_totals_liters == {"zone-1": 100}
    assert state.unassigned_total_liters == 20
    assert state.meter_accumulated_liters == 1_000
    assert state.meter_last_raw_liters == 10
    assert state.meter_correction_liters == 5
    assert state.meter_reset_count == 2
    assert state.manual_requests == (completed_request,)
    assert state.irrigation_executions == (completed_execution,)
    assert state.water_consumption_history == (history,)
    assert "dose_number" not in state.irrigation_executions[0].as_dict()
    assert "doses" not in state.irrigation_executions[0].as_dict()
    assert "dose_number" not in state.water_consumption_history[0].as_dict()
    assert state.emergency_stop is True
    assert state.installation_safety_lock == "valve_error"
    assert state.operation_enabled is False
    assert state.automation_enabled is True
    assert state.zone_operation_enabled == {"zone-1": False}
    assert state.zone_automation_enabled == {"zone-1": True}
    assert set(migrated) == set(StoredInstallationState().as_dict())


async def test_rc6_migration_discards_stale_automatic_and_legacy_work() -> None:
    """Drop pending automatic and malformed legacy records."""
    old_data = StoredInstallationState(
        manual_requests=(
            _request("manual-pending", status="pending"),
            _request("automatic-pending", source="automatic", status="pending"),
        )
    ).as_dict()
    requests = old_data["manual_requests"]
    assert isinstance(requests, list)
    requests.extend(
        [
            {**_request("paused").as_dict(), "status": "paused"},
            {**_request("soaking").as_dict(), "status": "soaking"},
            {"request_id": "malformed"},
        ]
    )

    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None, 1, 29, old_data
    )
    state = StoredInstallationState.from_dict(migrated)

    assert [request.request_id for request in state.manual_requests] == ["manual-pending"]
    assert state.active_execution is None


async def test_rc6_migration_preserves_only_coherent_active_v2_execution() -> None:
    """Retain an active checkpoint only with both linked durable records."""
    request = _request(
        "automatic-active",
        source="automatic",
        status="executing",
        execution_id="execution-active",
    )
    execution = _execution("execution-active", "automatic-active", status="watering")
    active = ActiveExecutionState(
        zone_id="zone-1",
        zone_valve="switch.lawn",
        main_valve=None,
        meter_raw_baseline_liters=100,
        prepared_at="2026-07-24T10:00:00+00:00",
        watering_started_at="2026-07-24T10:00:01+00:00",
        requested_duration_seconds=60,
        request_id=request.request_id,
        execution_id=execution.execution_id,
    )
    old_data = StoredInstallationState(
        active_execution=active,
        manual_requests=(request,),
        irrigation_executions=(execution,),
    ).as_dict()
    active_data = old_data["active_execution"]
    assert isinstance(active_data, dict)
    active_data.update(
        {
            "estimated_flow_l_min": 12,
            "dose_number": 2,
            "dose_target_value": 30,
            "fallback_started_at": "2026-07-24T10:00:30+00:00",
        }
    )

    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None, 1, 29, old_data
    )
    state = StoredInstallationState.from_dict(migrated)

    assert state.active_execution == active
    assert (
        not {
            "estimated_flow_l_min",
            "dose_number",
            "dose_target_value",
            "fallback_started_at",
        }
        & state.active_execution.as_dict().keys()
    )
    assert state.manual_requests == (request,)
    assert state.irrigation_executions == (execution,)

    executions = old_data["irrigation_executions"]
    assert isinstance(executions, list)
    executions.clear()
    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None, 1, 29, old_data
    )
    discarded = StoredInstallationState.from_dict(migrated)
    assert discarded.active_execution is None
    assert all(request.status != "executing" for request in discarded.manual_requests)
    assert all(execution.status != "watering" for execution in discarded.irrigation_executions)


def test_emergency_stop_load_normalizes_missing_safety_lock() -> None:
    """Keep emergency stop independently fail-closed after malformed persistence."""
    state = StoredInstallationState.from_dict({"emergency_stop": True})

    assert state.emergency_stop is True
    assert state.installation_safety_lock == "Emergency stop activated"


async def test_migration_normalizes_emergency_stop_without_legacy_lock() -> None:
    """Persist the same fail-closed invariant directly in migrated storage."""
    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None, 1, 29, {"emergency_stop": True}
    )

    assert migrated["emergency_stop"] is True
    assert migrated["installation_safety_lock"] == "Emergency stop activated"
