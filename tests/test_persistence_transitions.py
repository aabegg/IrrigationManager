"""Public persistence contracts shared by legacy and partial irrigation paths."""

from dataclasses import replace

import pytest

from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    IrrigationExecutionState,
    IrrigationPortionState,
    ManualIrrigationRequest,
    PortionPolicySnapshot,
    StoredInstallationState,
    WaterConsumptionRecord,
)
from custom_components.irrigation_manager.state_transitions import (
    apply_safety_lock,
    prepare_execution_state,
    settle_execution_state,
)


def _legacy_request(*, status: str = "pending", revision: int = 1) -> ManualIrrigationRequest:
    """Create one legacy order without a partial-irrigation snapshot."""
    return ManualIrrigationRequest(
        request_id="request-legacy",
        sequence=1,
        zone_id="lawn",
        zone_subentry_id="zone-lawn",
        zone_name="Rasen",
        zone_valve="switch.lawn",
        main_valve="switch.main",
        target_type="duration",
        target_value=900.0,
        remaining_value=900.0,
        created_at="2026-07-29T06:00:00+00:00",
        expires_at="2026-07-29T08:00:00+00:00",
        status=status,
        execution_id="execution-legacy" if status == "executing" else None,
        revision=revision,
    )


def _legacy_execution() -> IrrigationExecutionState:
    """Create the corresponding legacy execution record."""
    return IrrigationExecutionState(
        execution_id="execution-legacy",
        request_id="request-legacy",
        zone_id="lawn",
        target_type="duration",
        target_value=900.0,
        remaining_value=900.0,
        status="watering",
        created_at="2026-07-29T06:00:00+00:00",
    )


def _legacy_active() -> ActiveExecutionState:
    """Create the corresponding legacy hardware checkpoint."""
    return ActiveExecutionState(
        zone_id="lawn",
        zone_valve="switch.lawn",
        main_valve="switch.main",
        meter_raw_baseline_liters=1_200.0,
        prepared_at="2026-07-29T06:00:00+00:00",
        watering_started_at=None,
        requested_duration_seconds=900.0,
        request_id="request-legacy",
        execution_id="execution-legacy",
    )


def test_partial_irrigation_records_round_trip_as_one_installation_state() -> None:
    """Process, portion, checkpoint and consumption evidence survive one restart."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=3,
        maximum_lifetime_seconds=7_200.0,
    )
    request = ManualIrrigationRequest(
        request_id="request-1",
        sequence=1,
        zone_id="lawn",
        zone_subentry_id="zone-lawn",
        zone_name="Rasen",
        zone_valve="switch.lawn",
        main_valve="switch.main",
        target_type="duration",
        target_value=2_700.0,
        remaining_value=1_800.0,
        created_at="2026-07-29T06:00:00+00:00",
        expires_at="2026-07-29T08:00:00+00:00",
        status="executing",
        execution_id="execution-1",
        portion_policy=policy,
    )
    execution = IrrigationExecutionState(
        execution_id="execution-1",
        request_id="request-1",
        zone_id="lawn",
        target_type="duration",
        target_value=2_700.0,
        remaining_value=1_800.0,
        status="watering",
        created_at="2026-07-29T06:00:00+00:00",
        portion_policy=policy,
        process_started_at="2026-07-29T06:00:00+00:00",
        process_deadline_at="2026-07-29T08:00:00+00:00",
        hydraulic_overhead_seconds_per_portion=12.5,
        next_portion_sequence=2,
        completed_portion_count=0,
    )
    portion = IrrigationPortionState(
        portion_id="execution-1:1",
        execution_id="execution-1",
        sequence=1,
        target_type="duration",
        target_value=900.0,
        status="watering",
        prepared_at="2026-07-29T06:00:00+00:00",
        opening_attempted_at="2026-07-29T06:00:01+00:00",
        watering_started_at="2026-07-29T06:00:02+00:00",
    )
    active = ActiveExecutionState(
        zone_id="lawn",
        zone_valve="switch.lawn",
        main_valve="switch.main",
        meter_raw_baseline_liters=1_200.0,
        prepared_at="2026-07-29T06:00:00+00:00",
        watering_started_at="2026-07-29T06:00:02+00:00",
        requested_duration_seconds=900.0,
        request_id="request-1",
        execution_id="execution-1",
        portion_id="execution-1:1",
        portion_sequence=1,
    )
    consumption = WaterConsumptionRecord(
        recorded_at="2026-07-29T05:00:00+00:00",
        amount_liters=12.5,
        zone_id="lawn",
        source="manual",
        quality="measured",
        request_id="older-request",
        execution_id="older-execution",
        portion_id="older-execution:1",
    )
    state = StoredInstallationState(
        manual_requests=(request,),
        irrigation_executions=(execution,),
        irrigation_portions=(portion,),
        active_execution=active,
        water_consumption_history=(consumption,),
    )

    restored = StoredInstallationState.from_dict(state.as_dict())

    assert restored == state
    assert restored.irrigation_portions == (portion,)
    assert restored.active_execution == active


def test_prepare_transition_atomically_claims_legacy_order_and_hardware() -> None:
    """One immutable result contains every record required before valve opening."""
    pending = _legacy_request()
    initial = StoredInstallationState(manual_requests=(pending,))
    claimed = replace(
        pending,
        status="executing",
        execution_id="execution-legacy",
        revision=2,
    )
    execution = _legacy_execution()
    active = _legacy_active()

    prepared = prepare_execution_state(
        initial,
        request=claimed,
        execution=execution,
        active=active,
    )

    assert initial == StoredInstallationState(manual_requests=(pending,))
    assert prepared == replace(
        initial,
        manual_requests=(claimed,),
        irrigation_executions=(execution,),
        active_execution=active,
    )


def test_prepare_transition_persists_process_portion_and_checkpoint_together() -> None:
    """A partial delivery is never durable without its process and hardware reference."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=2,
        maximum_lifetime_seconds=3_600.0,
    )
    pending = replace(_legacy_request(), target_value=1_800.0, remaining_value=1_800.0)
    claimed = replace(
        pending,
        status="executing",
        execution_id="execution-legacy",
        portion_policy=policy,
        revision=2,
    )
    execution = replace(
        _legacy_execution(),
        target_value=1_800.0,
        remaining_value=1_800.0,
        portion_policy=policy,
        process_started_at="2026-07-29T06:00:00+00:00",
        process_deadline_at="2026-07-29T07:00:00+00:00",
        next_portion_sequence=2,
    )
    portion = IrrigationPortionState(
        portion_id="execution-legacy:1",
        execution_id="execution-legacy",
        sequence=1,
        target_type="duration",
        target_value=900.0,
        status="prepared",
        prepared_at="2026-07-29T06:00:00+00:00",
    )
    active = replace(
        _legacy_active(),
        portion_id=portion.portion_id,
        portion_sequence=portion.sequence,
    )
    initial = StoredInstallationState(manual_requests=(pending,))

    prepared = prepare_execution_state(
        initial,
        request=claimed,
        execution=execution,
        active=active,
        portion=portion,
    )

    assert prepared == replace(
        initial,
        manual_requests=(claimed,),
        irrigation_executions=(execution,),
        irrigation_portions=(portion,),
        active_execution=active,
    )


def test_prepare_transition_rejects_mismatched_portion_checkpoint() -> None:
    """No atomic checkpoint may reference a different subordinate portion."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=2,
        maximum_lifetime_seconds=3_600.0,
    )
    pending = replace(_legacy_request(), portion_policy=policy)
    claimed = replace(
        pending,
        status="executing",
        execution_id="execution-legacy",
        revision=2,
    )
    execution = replace(_legacy_execution(), portion_policy=policy)
    portion = IrrigationPortionState(
        portion_id="execution-legacy:1",
        execution_id="execution-legacy",
        sequence=1,
        target_type="duration",
        target_value=900.0,
        status="prepared",
        prepared_at="2026-07-29T06:00:00+00:00",
    )
    active = replace(
        _legacy_active(),
        portion_id="execution-legacy:2",
        portion_sequence=2,
    )

    with pytest.raises(ValueError, match="portion checkpoint"):
        prepare_execution_state(
            StoredInstallationState(manual_requests=(pending,)),
            request=claimed,
            execution=execution,
            active=active,
            portion=portion,
        )


@pytest.mark.parametrize(
    ("invalid_target", "maximum_portion_target"),
    [(901.0, 900.0), (1_801.0, 2_700.0)],
)
def test_prepare_transition_rejects_portion_outside_policy_or_remaining_target(
    invalid_target: float,
    maximum_portion_target: float,
) -> None:
    """The durable actuation boundary enforces both target caps independently."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=maximum_portion_target,
        minimum_soak_seconds=300.0,
        maximum_portions=3,
        maximum_lifetime_seconds=3_600.0,
    )
    pending = replace(
        _legacy_request(),
        target_value=2_700.0,
        remaining_value=1_800.0,
    )
    claimed = replace(
        pending,
        status="executing",
        execution_id="execution-legacy",
        portion_policy=policy,
        revision=2,
    )
    execution = replace(
        _legacy_execution(),
        target_value=2_700.0,
        remaining_value=1_800.0,
        portion_policy=policy,
        next_portion_sequence=2,
    )
    portion = IrrigationPortionState(
        portion_id="execution-legacy:1",
        execution_id="execution-legacy",
        sequence=1,
        target_type="duration",
        target_value=invalid_target,
        status="prepared",
        prepared_at="2026-07-29T06:00:00+00:00",
    )

    with pytest.raises(ValueError, match="portion checkpoint"):
        prepare_execution_state(
            StoredInstallationState(manual_requests=(pending,)),
            request=claimed,
            execution=execution,
            active=replace(
                _legacy_active(),
                portion_id=portion.portion_id,
                portion_sequence=portion.sequence,
            ),
            portion=portion,
        )


def test_prepare_transition_rejects_a_second_unsettled_portion() -> None:
    """One process can never acquire hardware while another portion remains open."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=3,
        maximum_lifetime_seconds=3_600.0,
    )
    request = replace(
        _legacy_request(status="executing", revision=2),
        target_value=2_700.0,
        remaining_value=1_800.0,
        portion_policy=policy,
    )
    execution = replace(
        _legacy_execution(),
        target_value=2_700.0,
        remaining_value=1_800.0,
        status="soaking",
        portion_policy=policy,
        next_portion_sequence=3,
    )
    first = IrrigationPortionState(
        portion_id="execution-legacy:1",
        execution_id="execution-legacy",
        sequence=1,
        target_type="duration",
        target_value=900.0,
        status="prepared",
        prepared_at="2026-07-29T06:00:00+00:00",
    )
    second = replace(
        first,
        portion_id="execution-legacy:2",
        sequence=2,
        prepared_at="2026-07-29T06:20:00+00:00",
    )
    active = replace(
        _legacy_active(),
        portion_id=second.portion_id,
        portion_sequence=second.sequence,
    )

    with pytest.raises(ValueError, match="portion checkpoint"):
        prepare_execution_state(
            StoredInstallationState(
                manual_requests=(request,),
                irrigation_executions=(execution,),
                irrigation_portions=(first,),
            ),
            request=request,
            execution=replace(execution, status="watering"),
            active=active,
            portion=second,
        )


def test_settlement_transition_preserves_legacy_aggregate_trace() -> None:
    """Legacy settlement updates the same totals, history and terminal records atomically."""
    pending = _legacy_request()
    claimed = replace(
        pending,
        status="executing",
        execution_id="execution-legacy",
        revision=2,
    )
    execution = _legacy_execution()
    prepared = prepare_execution_state(
        StoredInstallationState(
            installation_total_liters=5.0,
            zone_totals_liters={"lawn": 2.0},
            manual_requests=(pending,),
        ),
        request=claimed,
        execution=execution,
        active=_legacy_active(),
    )
    completed_request = replace(
        claimed,
        remaining_value=0.0,
        status="completed",
        revision=3,
    )
    completed_execution = replace(
        execution,
        remaining_value=0.0,
        status="completed",
        delivered_liters=12.5,
        delivered_duration_seconds=900.0,
        ended_at="2026-07-29T06:15:00+00:00",
        result="target_reached",
        measurement_quality="measured",
        measurement_origin="meter",
    )

    settled = settle_execution_state(
        prepared,
        request=completed_request,
        execution=completed_execution,
        delivered_liters=12.5,
        delivered_duration_seconds=900.0,
        recorded_at="2026-07-29T06:15:00+00:00",
    )

    consumption = WaterConsumptionRecord(
        recorded_at="2026-07-29T06:15:00+00:00",
        amount_liters=12.5,
        zone_id="lawn",
        source="manual",
        quality="measured",
        request_id="request-legacy",
        execution_id="execution-legacy",
    )
    expected = replace(
        prepared,
        installation_total_liters=17.5,
        zone_totals_liters={"lawn": 14.5},
        zone_measurement_quality={"lawn": "measured"},
        zone_last_delivered_liters={"lawn": 12.5},
        zone_last_duration_seconds={"lawn": 900.0},
        manual_requests=(completed_request,),
        irrigation_executions=(completed_execution,),
        active_execution=None,
        water_consumption_history=(consumption,),
    )

    assert settled == expected


def test_partial_settlement_updates_portion_and_releases_hardware_atomically() -> None:
    """A closed portion, aggregate progress and consumption share one result state."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=2,
        maximum_lifetime_seconds=3_600.0,
    )
    request = replace(
        _legacy_request(status="executing", revision=2),
        target_value=1_800.0,
        remaining_value=900.0,
        portion_policy=policy,
    )
    execution = replace(
        _legacy_execution(),
        target_value=1_800.0,
        remaining_value=1_800.0,
        portion_policy=policy,
        next_portion_sequence=2,
    )
    watering = IrrigationPortionState(
        portion_id="execution-legacy:1",
        execution_id="execution-legacy",
        sequence=1,
        target_type="duration",
        target_value=900.0,
        status="watering",
        prepared_at="2026-07-29T06:00:00+00:00",
        opening_attempted_at="2026-07-29T06:00:01+00:00",
        watering_started_at="2026-07-29T06:00:02+00:00",
    )
    active = replace(
        _legacy_active(),
        watering_started_at=watering.watering_started_at,
        portion_id=watering.portion_id,
        portion_sequence=watering.sequence,
    )
    initial = StoredInstallationState(
        manual_requests=(request,),
        irrigation_executions=(execution,),
        irrigation_portions=(watering,),
        active_execution=active,
    )
    settled_portion = replace(
        watering,
        status="settled",
        watering_ended_at="2026-07-29T06:15:02+00:00",
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        result="target_reached",
        measurement_quality="measured",
        measurement_origin="meter",
    )
    soaking_execution = replace(
        execution,
        remaining_value=900.0,
        status="soaking",
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        next_portion_at="2026-07-29T06:20:02+00:00",
        completed_portion_count=1,
        measurement_quality="measured",
        measurement_origin="meter",
    )

    settled = settle_execution_state(
        initial,
        request=request,
        execution=soaking_execution,
        portion=settled_portion,
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        recorded_at="2026-07-29T06:15:02+00:00",
    )

    assert settled.irrigation_portions == (settled_portion,)
    assert settled.irrigation_executions == (soaking_execution,)
    assert settled.active_execution is None
    assert settled.water_consumption_history[0].portion_id == settled_portion.portion_id

    duplicate = settle_execution_state(
        settled,
        request=request,
        execution=soaking_execution,
        portion=settled_portion,
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        recorded_at="2026-07-29T06:15:02+00:00",
    )

    assert duplicate == settled


def test_conflicting_duplicate_settlement_is_rejected_without_state_change() -> None:
    """The same stable portion ID can never account for different delivery evidence."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=2,
        maximum_lifetime_seconds=3_600.0,
    )
    request = replace(
        _legacy_request(status="executing", revision=2),
        target_value=1_800.0,
        remaining_value=900.0,
        portion_policy=policy,
    )
    execution = replace(
        _legacy_execution(),
        target_value=1_800.0,
        remaining_value=900.0,
        status="soaking",
        portion_policy=policy,
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        next_portion_sequence=2,
        completed_portion_count=1,
    )
    settled_portion = IrrigationPortionState(
        portion_id="execution-legacy:1",
        execution_id="execution-legacy",
        sequence=1,
        target_type="duration",
        target_value=900.0,
        status="settled",
        prepared_at="2026-07-29T06:00:00+00:00",
        watering_started_at="2026-07-29T06:00:02+00:00",
        watering_ended_at="2026-07-29T06:15:02+00:00",
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        result="target_reached",
        measurement_quality="measured",
        measurement_origin="meter",
    )
    consumption = WaterConsumptionRecord(
        recorded_at="2026-07-29T06:15:02+00:00",
        amount_liters=10.0,
        zone_id="lawn",
        source="manual",
        quality="measured",
        request_id=request.request_id,
        execution_id=execution.execution_id,
        portion_id=settled_portion.portion_id,
    )
    settled = StoredInstallationState(
        installation_total_liters=10.0,
        zone_totals_liters={"lawn": 10.0},
        manual_requests=(request,),
        irrigation_executions=(execution,),
        irrigation_portions=(settled_portion,),
        water_consumption_history=(consumption,),
    )
    conflicting_portion = replace(
        settled_portion,
        delivered_liters=11.0,
    )

    with pytest.raises(ValueError, match="Settlement records"):
        settle_execution_state(
            settled,
            request=request,
            execution=replace(execution, delivered_liters=11.0),
            portion=conflicting_portion,
            delivered_liters=11.0,
            delivered_duration_seconds=900.0,
            recorded_at="2026-07-29T06:15:02+00:00",
        )

    assert settled.irrigation_portions == (settled_portion,)
    assert settled.water_consumption_history == (consumption,)

    with pytest.raises(ValueError, match="Settlement records"):
        settle_execution_state(
            settled,
            request=request,
            execution=execution,
            portion=settled_portion,
            delivered_liters=10.0,
            delivered_duration_seconds=901.0,
            recorded_at="2026-07-29T06:30:00+00:00",
        )


def test_exact_duplicate_settlement_does_not_depend_on_replay_time() -> None:
    """A retry reuses durable evidence instead of inventing a new consumption time."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=1,
        maximum_lifetime_seconds=1_800.0,
    )
    request = replace(
        _legacy_request(status="executing", revision=2),
        remaining_value=0.0,
        portion_policy=policy,
    )
    execution = replace(
        _legacy_execution(),
        remaining_value=0.0,
        status="completed",
        portion_policy=policy,
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        completed_portion_count=1,
        measurement_quality="measured",
        measurement_origin="meter",
    )
    portion = IrrigationPortionState(
        portion_id="execution-legacy:1",
        execution_id="execution-legacy",
        sequence=1,
        target_type="duration",
        target_value=900.0,
        status="settled",
        prepared_at="2026-07-29T06:00:00+00:00",
        watering_started_at="2026-07-29T06:00:02+00:00",
        watering_ended_at="2026-07-29T06:15:02+00:00",
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        result="target_reached",
        measurement_quality="measured",
        measurement_origin="meter",
    )
    consumption = WaterConsumptionRecord(
        recorded_at="2026-07-29T06:15:02+00:00",
        amount_liters=10.0,
        zone_id="lawn",
        source="manual",
        quality="measured",
        request_id=request.request_id,
        execution_id=execution.execution_id,
        portion_id=portion.portion_id,
    )
    settled = StoredInstallationState(
        manual_requests=(request,),
        irrigation_executions=(execution,),
        irrigation_portions=(portion,),
        water_consumption_history=(consumption,),
    )

    duplicate = settle_execution_state(
        settled,
        request=request,
        execution=execution,
        portion=portion,
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        recorded_at="2026-07-29T07:00:00+00:00",
    )

    assert duplicate is settled


def test_safety_transition_changes_only_the_installation_lock_evidence() -> None:
    """Every caller applies the same durable installation-wide safety primitive."""
    initial = StoredInstallationState(
        installation_total_liters=12.5,
        operation_enabled=True,
        automation_enabled=False,
    )

    locked = apply_safety_lock(
        initial,
        reason="unexpected_flow",
        recorded_at="2026-07-29T06:15:02+00:00",
    )

    assert locked == replace(
        initial,
        installation_safety_lock="unexpected_flow",
        installation_safety_lock_at="2026-07-29T06:15:02+00:00",
    )


def test_failed_settlement_applies_safety_lock_in_the_same_result_state() -> None:
    """No failed settlement can be persisted without its installation lock."""
    pending = _legacy_request()
    claimed = replace(
        pending,
        status="executing",
        execution_id="execution-legacy",
        revision=2,
    )
    execution = _legacy_execution()
    prepared = prepare_execution_state(
        StoredInstallationState(manual_requests=(pending,)),
        request=claimed,
        execution=execution,
        active=_legacy_active(),
    )
    failed_request = replace(
        claimed,
        remaining_value=800.0,
        status="cancelled",
        revision=3,
    )
    failed_execution = replace(
        execution,
        remaining_value=800.0,
        status="failed",
        delivered_liters=2.0,
        delivered_duration_seconds=100.0,
        ended_at="2026-07-29T06:01:40+00:00",
        result="unexpected_flow",
        measurement_quality="measured",
        measurement_origin="meter",
        warnings=("unexpected_flow",),
    )

    failed = settle_execution_state(
        prepared,
        request=failed_request,
        execution=failed_execution,
        delivered_liters=2.0,
        delivered_duration_seconds=100.0,
        recorded_at="2026-07-29T06:01:40+00:00",
        safety_lock_reason="unexpected_flow",
    )

    assert failed.installation_safety_lock == "unexpected_flow"
    assert failed.installation_safety_lock_at == "2026-07-29T06:01:40+00:00"
    assert failed.active_execution is None
