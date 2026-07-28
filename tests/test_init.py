"""Focused Home Assistant lifecycle and storage tests for version 2."""

from dataclasses import replace
from types import MappingProxyType

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_OFF, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    DispatcherDiagnosticEntry,
    DispatcherDiagnosticState,
    IrrigationExecutionState,
    ManualIrrigationRequest,
    StoredInstallationState,
)
from custom_components.irrigation_manager.services import START_MANUAL_SCHEMA
from custom_components.irrigation_manager.storage import IrrigationStore


@pytest.mark.parametrize(
    "targets",
    [
        {},
        {"duration": 1, "amount": 1},
        {"amount": 1},
        {"duration": 1, "hard_time_limit": 2},
    ],
)
def test_manual_action_requires_exactly_one_complete_target(
    targets: dict[str, float],
) -> None:
    """Reject missing, ambiguous, and incomplete action targets."""
    with pytest.raises(vol.Invalid):
        START_MANUAL_SCHEMA(
            {
                "config_entry_id": "installation-1",
                "zone_subentry_id": "zone-1",
                **targets,
            }
        )


def test_manual_action_converts_structured_duration_fields_to_seconds() -> None:
    """Keep service-facing duration fields separate from persisted numeric seconds."""
    result = START_MANUAL_SCHEMA(
        {
            "config_entry_id": "installation-1",
            "zone_subentry_id": "zone-1",
            "duration": {"hours": 30, "minutes": 2, "seconds": 3},
            "expiry": {"hours": 2, "minutes": 0, "seconds": 0},
        }
    )

    assert result["duration"] == 108_123
    assert result["expiry"] == 7_200

    volume_result = START_MANUAL_SCHEMA(
        {
            "config_entry_id": "installation-1",
            "zone_subentry_id": "zone-1",
            "amount": 10,
            "hard_time_limit": {"hours": 0, "minutes": 45, "seconds": 0},
        }
    )
    assert volume_result["hard_time_limit"] == 2_700


async def test_fresh_store_uses_only_current_v2_schema(hass: HomeAssistant) -> None:
    """Return the compact current schema for a new installation."""
    state = await IrrigationStore(hass, "fresh-v2").async_load()

    assert state == StoredInstallationState()
    assert set(state.as_dict()) == {
        "installation_total_liters",
        "zone_totals_liters",
        "zone_measurement_quality",
        "zone_last_delivered_liters",
        "zone_last_duration_seconds",
        "unassigned_total_liters",
        "unassigned_available_liters",
        "unassigned_measurement_quality",
        "unassigned_measurement_origin",
        "idle_meter_raw_baseline_liters",
        "emergency_stop",
        "installation_safety_lock",
        "installation_safety_lock_at",
        "calibration_proposal",
        "active_execution",
        "manual_requests",
        "irrigation_executions",
        "next_request_sequence",
        "meter_accumulated_liters",
        "meter_last_raw_liters",
        "meter_correction_liters",
        "meter_correction_history",
        "meter_reset_count",
        "meter_source_entity_id",
        "meter_source_liters_per_count",
        "water_consumption_history",
        "water_history_incomplete",
        "operation_enabled",
        "automation_enabled",
        "zone_operation_enabled",
        "zone_automation_enabled",
        "planning_rejections",
        "dispatcher_diagnostic",
        "dispatcher_diagnostic_history",
    }


async def test_dispatch_diagnostics_round_trip_independently_of_operational_state(
    hass: HomeAssistant,
) -> None:
    """Persist bounded dispatcher evidence without coupling it to entities."""
    diagnostic = DispatcherDiagnosticState(
        current_reason="operation_disabled",
        current_request_id="request-1",
        current_zone_id="zone-1",
        blocked_since="2026-07-28T06:00:00+00:00",
        next_wake_at="2026-07-28T07:00:00+00:00",
        boot_id="boot-1",
        boot_started_at="2026-07-28T05:59:00+00:00",
        clean_shutdown=False,
    )
    event = DispatcherDiagnosticEntry(
        recorded_at="2026-07-28T06:00:00+00:00",
        request_id="request-1",
        zone_id="zone-1",
        old_reason="waiting_for_start",
        new_reason="operation_disabled",
        releases={"operation": False},
        locks={"operation_disabled": True},
        next_wake_at="2026-07-28T07:00:00+00:00",
    )
    store = IrrigationStore(hass, "diagnostics-round-trip")

    await store.async_save(
        StoredInstallationState(
            installation_total_liters=12.5,
            dispatcher_diagnostic=diagnostic,
            dispatcher_diagnostic_history=(event,),
        )
    )

    loaded = await store.async_load()
    assert loaded.installation_total_liters == 12.5
    assert loaded.dispatcher_diagnostic == diagnostic
    assert loaded.dispatcher_diagnostic_history == (event,)


def test_malformed_dispatch_diagnostics_do_not_invalidate_operational_state() -> None:
    """Treat optional telemetry corruption as non-fatal for irrigation state."""
    state = StoredInstallationState.from_dict(
        {
            "installation_total_liters": 7,
            "dispatcher_diagnostic": {"current_reason": 3},
            "dispatcher_diagnostic_history": [
                {"new_reason": "ready"},
                "broken",
            ],
        }
    )

    assert state.installation_total_liters == 7
    assert state.dispatcher_diagnostic is None
    assert state.dispatcher_diagnostic_history == ()


def test_dispatch_diagnostic_history_is_limited_to_last_one_hundred() -> None:
    """Bound persisted telemetry independently of how much work was performed."""
    history = [
        DispatcherDiagnosticEntry(
            recorded_at=f"2026-07-28T06:{index:02d}:00+00:00",
            request_id=f"request-{index}",
            zone_id="zone-1",
            old_reason="waiting_for_start",
            new_reason="ready",
        ).as_dict()
        for index in range(105)
    ]

    state = StoredInstallationState.from_dict({"dispatcher_diagnostic_history": history})

    assert len(state.dispatcher_diagnostic_history) == 100
    assert state.dispatcher_diagnostic_history[0].request_id == "request-5"
    assert state.dispatcher_diagnostic_history[-1].request_id == "request-104"


async def test_store_migrates_shipped_rc6_data_to_v2(hass: HomeAssistant) -> None:
    """Run the Home Assistant Store migration from the shipped rc6 version."""
    await Store[dict[str, object]](
        hass,
        1,
        "irrigation_manager.rc6",
        atomic_writes=True,
        minor_version=29,
    ).async_save(
        {
            "installation_total_liters": 12.0,
            "zone_totals_liters": {"zone-1": 12.0},
            "winter_lock": True,
            "weather_failure_since": "legacy",
        }
    )

    state = await IrrigationStore(hass, "rc6").async_load()

    assert state.installation_total_liters == 12
    assert state.zone_totals_liters == {"zone-1": 12}
    assert "winter_lock" not in state.as_dict()
    assert "weather_failure_since" not in state.as_dict()


async def test_store_minor_migration_adds_empty_dispatch_diagnostics(
    hass: HomeAssistant,
) -> None:
    """Upgrade rc18 storage without changing operational irrigation data."""
    await Store[dict[str, object]](
        hass,
        2,
        "irrigation_manager.pre-diagnostics",
        atomic_writes=True,
        minor_version=0,
    ).async_save(StoredInstallationState(installation_total_liters=19).as_dict())

    state = await IrrigationStore(hass, "pre-diagnostics").async_load()

    assert state.installation_total_liters == 19
    assert state.dispatcher_diagnostic is None
    assert state.dispatcher_diagnostic_history == ()


async def test_store_minor_migration_adds_persistent_planning_rejections(
    hass: HomeAssistant,
) -> None:
    """Upgrade a complete rc19 runtime without changing operational state."""
    manual = ManualIrrigationRequest(
        request_id="manual-pending",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id="zone-subentry-1",
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve="switch.main",
        target_type="duration",
        target_value=300,
        remaining_value=300,
        created_at="2026-07-28T04:00:00+00:00",
        expires_at="2026-07-28T06:00:00+00:00",
    )
    automatic = ManualIrrigationRequest(
        request_id="automatic-pending",
        sequence=2,
        zone_id="zone-1",
        zone_subentry_id="zone-subentry-1",
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve="switch.main",
        target_type="duration",
        target_value=600,
        remaining_value=600,
        created_at="2026-07-28T04:00:00+00:00",
        expires_at="2026-07-29T05:00:00+00:00",
        requested_start_at="2026-07-29T04:00:00+00:00",
        status="pending",
        source="automatic",
        automatic_window_end="2026-07-29T05:00:00+00:00",
        resolved_inputs={"base_target": 600.0},
    )
    executing = ManualIrrigationRequest(
        request_id="automatic-active",
        sequence=3,
        zone_id="zone-2",
        zone_subentry_id="zone-subentry-2",
        zone_name="Beds",
        zone_valve="switch.beds",
        main_valve="switch.main",
        target_type="duration",
        target_value=420,
        remaining_value=240,
        created_at="2026-07-28T04:00:00+00:00",
        expires_at="2026-07-28T05:00:00+00:00",
        status="executing",
        source="automatic",
        execution_id="execution-active",
    )
    execution = IrrigationExecutionState(
        execution_id="execution-active",
        request_id=executing.request_id,
        zone_id=executing.zone_id,
        target_type="duration",
        target_value=420,
        remaining_value=240,
        status="watering",
        created_at="2026-07-28T04:00:00+00:00",
        delivered_duration_seconds=180,
    )
    active = ActiveExecutionState(
        zone_id=executing.zone_id,
        zone_valve=executing.zone_valve,
        main_valve=executing.main_valve,
        meter_raw_baseline_liters=1200,
        prepared_at="2026-07-28T04:00:00+00:00",
        watering_started_at="2026-07-28T04:00:05+00:00",
        requested_duration_seconds=420,
        request_id=executing.request_id,
        execution_id=execution.execution_id,
    )
    rc19_state = StoredInstallationState(
        installation_total_liters=23,
        emergency_stop=False,
        installation_safety_lock="maintenance_lock",
        installation_safety_lock_at="2026-07-28T03:55:00+00:00",
        active_execution=active,
        manual_requests=(manual, automatic, executing),
        irrigation_executions=(execution,),
        next_request_sequence=4,
        operation_enabled=False,
        automation_enabled=True,
        zone_operation_enabled={"zone-1": True, "zone-2": False},
        zone_automation_enabled={"zone-1": True, "zone-2": True},
    )
    old_data = rc19_state.as_dict()
    old_data.pop("planning_rejections")
    await Store[dict[str, object]](
        hass,
        2,
        "irrigation_manager.pre-planning-rejections",
        atomic_writes=True,
        minor_version=1,
    ).async_save(old_data)

    state = await IrrigationStore(hass, "pre-planning-rejections").async_load()

    assert state == rc19_state
    assert state.as_dict()["planning_rejections"] == []


async def test_setup_publishes_v2_initial_snapshot_without_legacy_fields(
    hass: HomeAssistant,
) -> None:
    """Initialize the coordinator exclusively from current persisted state."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "none",
            "operation_enabled": True,
            "automation_enabled": True,
        },
        unique_id="installation-v2",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    "name": "Lawn",
                    "zone_valve": "switch.lawn",
                    "control_type": "time",
                    "operation_enabled": True,
                    "automation_enabled": True,
                    "weekly_schedule": [],
                }
            ),
            subentry_id="zone-subentry",
            subentry_type="zone",
            title="Lawn",
            unique_id="zone-v2",
        ),
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    snapshot = entry.runtime_data.coordinator.data
    assert snapshot.status == "idle"
    assert snapshot.operation_enabled is True
    assert snapshot.automation_enabled is True
    assert not hasattr(snapshot, "winter_lock")
    assert not hasattr(snapshot, "zone_safety_locks")
    assert not hasattr(snapshot, "maintenance_active")

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_zone_status_anchor_publishes_live_meter_capability_and_volume_limit(
    hass: HomeAssistant,
) -> None:
    """Integrate configured meter limits with the state consumed by the bundled card."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    hass.states.async_set("sensor.water", "100", {"unit_of_measurement": UnitOfVolume.LITERS})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "cumulative",
            "meter_entity": "sensor.water",
            "operation_enabled": True,
            "automation_enabled": True,
        },
        unique_id="installation-metered",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "volume",
                "volume_max_runtime": 900,
                "operation_enabled": True,
                "automation_enabled": True,
                "weekly_schedule": [],
            }
        ),
        subentry_id="zone-subentry",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-metered",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    anchor_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-metered_zone_status")
    installation_anchor_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-metered_status"
    )
    assert anchor_id is not None
    assert installation_anchor_id is not None
    anchor = hass.states.get(anchor_id)
    installation_anchor = hass.states.get(installation_anchor_id)
    assert anchor is not None
    assert installation_anchor is not None
    assert anchor.attributes["volume_control_available"] is True
    assert anchor.attributes["max_manual_volume_runtime_seconds"] == 900
    assert "max_manual_duration_seconds" not in anchor.attributes
    assert installation_anchor.attributes["volume_control_available"] is True
    assert "physical_meter" in installation_anchor.attributes["card_entities"]

    coordinator = entry.runtime_data.coordinator
    coordinator.set_snapshot(
        replace(
            coordinator.data,
            active_zone_id="zone-metered",
            active_execution_id="execution-1",
        )
    )
    await hass.async_block_till_done()
    active_anchor = hass.states.get(anchor_id)
    assert active_anchor is not None
    assert active_anchor.attributes["active_execution_id"] == "execution-1"

    coordinator.set_snapshot(replace(coordinator.data, active_zone_id="another-zone"))
    await hass.async_block_till_done()
    inactive_anchor = hass.states.get(anchor_id)
    assert inactive_anchor is not None
    assert "active_execution_id" not in inactive_anchor.attributes

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_metered_to_unmetered_setup_removes_renamed_meter_entities_by_unique_id(
    hass: HomeAssistant,
) -> None:
    """Retire every meter-only registry entity even after users renamed entity IDs."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    hass.states.async_set("sensor.water", "100", {"unit_of_measurement": UnitOfVolume.LITERS})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "cumulative",
            "meter_entity": "sensor.water",
            "operation_enabled": True,
            "automation_enabled": True,
        },
        unique_id="installation-transition",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "time",
                "operation_enabled": True,
                "automation_enabled": True,
                "weekly_schedule": [],
            }
        ),
        subentry_id="zone-subentry",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-transition",
    )
    hass.config_entries.async_add_subentry(entry, zone)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    physical_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-transition_physical_meter"
    )
    zone_water_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-transition_water_total")
    assert physical_id is not None
    assert zone_water_id is not None
    registry.async_update_entity(physical_id, new_entity_id="sensor.renamed_physical_meter")
    registry.async_update_entity(zone_water_id, new_entity_id="sensor.renamed_zone_water")

    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_entry(
        entry,
        data={
            "name": "Garden",
            "meter_type": "none",
            "operation_enabled": True,
            "automation_enabled": True,
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        registry.async_get_entity_id("sensor", DOMAIN, "installation-transition_physical_meter")
        is None
    )
    assert registry.async_get_entity_id("sensor", DOMAIN, "zone-transition_water_total") is None
    assert registry.async_get("sensor.renamed_physical_meter") is None
    assert registry.async_get("sensor.renamed_zone_water") is None

    assert await hass.config_entries.async_unload(entry.entry_id)
