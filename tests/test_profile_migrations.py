"""Migration tests for immutable resolved calculation inputs."""

from custom_components.irrigation_manager.models import ManualIrrigationRequest
from custom_components.irrigation_manager.storage import _StateStore


async def test_storage_21_adds_resolved_inputs_to_durable_records() -> None:
    """Keep legacy history readable while marking unavailable old inputs explicitly."""
    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None,
        1,
        21,
        {
            "manual_requests": [{"request_id": "request-1"}],
            "irrigation_executions": [{"execution_id": "execution-1"}],
            "active_execution": {"zone_id": "zone-1"},
        },
    )

    assert migrated["manual_requests"] == [{"request_id": "request-1", "resolved_inputs": {}}]
    assert migrated["irrigation_executions"] == [
        {
            "execution_id": "execution-1",
            "resolved_inputs": {},
            "measurement_quality": "unknown",
            "measurement_origin": "unknown",
            "warnings": [],
            "doses": [],
        }
    ]
    assert migrated["active_execution"] == {
        "zone_id": "zone-1",
        "resolved_inputs": {},
        "fallback_quality": "estimated",
    }


async def test_storage_22_adds_meter_continuity_and_monotonic_unassigned_balance() -> None:
    """Preserve old unassigned water while adding future continuity records."""
    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None,
        1,
        22,
        {"unassigned_total_liters": 12.0, "irrigation_executions": []},
    )

    assert migrated["unassigned_available_liters"] == 12
    assert migrated["meter_last_raw_liters"] is None
    assert migrated["water_consumption_history"] == []


async def test_storage_24_adds_meter_source_identity_and_history_quality() -> None:
    """Mark legacy continuity identity unknown and retained periods complete."""
    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None,
        1,
        24,
        {},
    )

    assert migrated["meter_source_entity_id"] is None
    assert migrated["meter_source_liters_per_count"] is None
    assert migrated["water_history_incomplete"] is False


def test_request_round_trip_retains_resolved_profile_snapshot() -> None:
    """Do not re-resolve historical execution inputs after profile edits."""
    request = ManualIrrigationRequest(
        request_id="request-1",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id="subentry-1",
        zone_name="Bed",
        zone_valve="switch.bed",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        created_at="2026-07-22T00:00:00+00:00",
        expires_at="2026-07-22T01:00:00+00:00",
        resolved_inputs={"profile_schema_version": 1, "area_m2": 12.0},
    )

    restored = ManualIrrigationRequest.from_dict(request.as_dict())

    assert restored.resolved_inputs == request.resolved_inputs
