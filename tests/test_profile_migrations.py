"""Migration tests for immutable resolved calculation inputs."""

from types import MappingProxyType

from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager import async_migrate_entry
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

    assert migrated["manual_requests"] == [
        {
            "request_id": "request-1",
            "resolved_inputs": {},
            "balance_total_available_water_mm": None,
            "balance_readily_available_water_mm": None,
        }
    ]
    assert migrated["irrigation_executions"] == [
        {
            "execution_id": "execution-1",
            "resolved_inputs": {},
            "measurement_quality": "unknown",
            "measurement_origin": "unknown",
            "warnings": [],
            "doses": [],
            "balance_total_available_water_mm": None,
            "balance_readily_available_water_mm": None,
        }
    ]
    assert migrated["active_execution"] == {
        "zone_id": "zone-1",
        "resolved_inputs": {},
        "fallback_quality": "estimated",
        "balance_total_available_water_mm": None,
        "balance_readily_available_water_mm": None,
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
        balance_total_available_water_mm=60,
        balance_readily_available_water_mm=24,
    )

    restored = ManualIrrigationRequest.from_dict(request.as_dict())

    assert restored.resolved_inputs == request.resolved_inputs
    assert restored.balance_total_available_water_mm == 60
    assert restored.balance_readily_available_water_mm == 24


async def test_storage_27_preserves_legacy_one_limit_as_equal_taw_and_raw() -> None:
    """Migrate persisted snapshots without changing legacy scheduling behavior."""
    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None,
        1,
        26,
        {
            "manual_requests": [{"request_id": "request-1", "balance_maximum_deficit_mm": 40}],
            "irrigation_executions": [],
        },
    )

    request = migrated["manual_requests"][0]
    assert request["balance_total_available_water_mm"] == 40
    assert request["balance_readily_available_water_mm"] == 40


async def test_config_entry_3_adds_fail_safe_external_policy(hass: HomeAssistant) -> None:
    """Migrate existing installations and zones without weakening external inputs."""
    entry = MockConfigEntry(
        domain="irrigation_manager",
        title="Garden",
        data={"name": "Garden"},
        version=1,
        minor_version=3,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType({"name": "Lawn", "zone_valve": "switch.lawn"}),
        subentry_id="zone-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    assert await async_migrate_entry(hass, entry)
    assert entry.minor_version == 6
    assert entry.data["automation_enabled"] is True
    assert entry.data["external_failure_policy"] == "fail_safe"
    assert entry.subentries["zone-1"].data["external_failure_policy"] == "fail_safe"
    assert "plant_profile" not in entry.subentries["zone-1"].data
