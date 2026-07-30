"""Public behavior of the pure partial-delivery process module."""

import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.irrigation_manager.portioning import (
    CancelProcess,
    CancelRequested,
    CompleteProcess,
    FailClosed,
    IrrigationProcessModule,
    NoOp,
    OrderSnapshot,
    PortionLimits,
    PortionOpening,
    PortionSettled,
    PortionStarted,
    PortionStatus,
    PreparePortion,
    ProcessStatus,
    ProcessTransition,
    RecoveryObserved,
    ResumeDue,
    StopActivePortion,
    TargetType,
    WaitUntil,
)

NOW = datetime(2026, 7, 29, 6, tzinfo=UTC)


def _started_duration_process(
    *, execution_id: str, target: float = 900.0, maximum_portions: int = 1
) -> ProcessTransition:
    """Build the common safe duration-process fixture through the public seam."""
    return IrrigationProcessModule().start(
        OrderSnapshot(
            execution_id=execution_id,
            request_id=f"request-{execution_id}",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=target,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=maximum_portions,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )


def _confirm_active_portion(
    module: IrrigationProcessModule,
    transition: ProcessTransition,
    *,
    now: datetime,
) -> ProcessTransition:
    """Drive the persistent automaton through prepared to confirmed watering."""
    active = next(
        portion for portion in transition.portions if portion.status is PortionStatus.PREPARED
    )
    return module.advance(
        transition.process,
        transition.portions,
        PortionStarted(portion_id=active.portion_id),
        now=now,
    )


def _record_opening_attempt(
    module: IrrigationProcessModule,
    transition: ProcessTransition,
    *,
    now: datetime,
) -> ProcessTransition:
    """Persist the recovery boundary immediately before possible actuation."""
    active = next(
        portion for portion in transition.portions if portion.status is PortionStatus.PREPARED
    )
    return module.advance(
        transition.process,
        transition.portions,
        PortionOpening(portion_id=active.portion_id),
        now=now,
    )


def test_start_prepares_only_the_first_bounded_duration_portion() -> None:
    """One accepted order remains one process with a bounded first portion."""
    transition = IrrigationProcessModule().start(
        OrderSnapshot(
            execution_id="execution-1",
            request_id="request-1",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=2_700.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    assert transition.process.status is ProcessStatus.WATERING
    assert transition.process.target_value == 2_700.0
    assert transition.process.remaining_value == 2_700.0
    assert transition.process.completed_portion_count == 0
    assert len(transition.portions) == 1
    assert transition.portions[0].portion_id == "execution-1:1"
    assert transition.portions[0].target_value == 900.0
    assert transition.action == PreparePortion(
        portion_id="execution-1:1",
        target_type=TargetType.DURATION,
        target_value=900.0,
        hard_time_limit_seconds=None,
    )


def test_start_passes_the_total_volume_runtime_budget_to_the_first_portion() -> None:
    """A volume portion may consume only the process's cumulative runtime budget."""
    transition = IrrigationProcessModule().start(
        OrderSnapshot(
            execution_id="execution-volume",
            request_id="request-volume",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=2_000.0,
            operation_deadline_at=NOW + timedelta(hours=3),
            delivery_runtime_limit_seconds=7_200.0,
        ),
        PortionLimits(
            maximum_portion_target=500.0,
            minimum_soak_seconds=600.0,
            maximum_portions=4,
            maximum_lifetime_seconds=10_800.0,
        ),
        now=NOW,
    )

    assert transition.action == PreparePortion(
        portion_id="execution-volume:1",
        target_type=TargetType.VOLUME,
        target_value=500.0,
        hard_time_limit_seconds=7_200.0,
    )


def test_start_fails_closed_when_the_configured_portion_count_cannot_cover_target() -> None:
    """The process must never enlarge a portion to compensate for an unsafe policy."""
    transition = IrrigationProcessModule().start(
        OrderSnapshot(
            execution_id="execution-too-large",
            request_id="request-too-large",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=2_701.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.portions == ()
    assert transition.action == FailClosed(
        reason="portion_limit_exceeded",
        safety_lock_required=False,
    )


def test_feasibility_rejects_an_order_before_a_process_is_created() -> None:
    """Expose the same conservative proof for planning and order acceptance."""
    module = IrrigationProcessModule()
    failure = module.feasibility_failure(
        OrderSnapshot(
            execution_id="feasibility-check",
            request_id="request-too-large",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_501.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=300.0,
            minimum_soak_seconds=300.0,
            maximum_portions=5,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    assert failure == "portion_limit_exceeded"


def test_start_fails_closed_when_delivery_and_minimum_pause_do_not_fit_deadline() -> None:
    """A process must prove that its full conservative span fits before actuation."""
    transition = IrrigationProcessModule().start(
        OrderSnapshot(
            execution_id="execution-window",
            request_id="request-window",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(seconds=2_000),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.action == FailClosed(
        reason="process_window_not_fit",
        safety_lock_required=False,
    )


def test_start_reserves_hydraulic_overhead_for_every_required_portion() -> None:
    """Valve and feedback budgets are part of the conservative process span."""
    transition = IrrigationProcessModule().start(
        OrderSnapshot(
            execution_id="execution-overhead",
            request_id="request-overhead",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(seconds=2_200),
            hydraulic_overhead_seconds_per_portion=100.0,
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.action == FailClosed(
        reason="process_window_not_fit",
        safety_lock_required=False,
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"maximum_portion_target": 0.0}, "maximum portion target"),
        ({"minimum_soak_seconds": float("nan")}, "minimum soak"),
        ({"maximum_portions": 0}, "maximum portions"),
        ({"maximum_lifetime_seconds": float("inf")}, "maximum lifetime"),
    ],
)
def test_policy_rejects_non_positive_or_non_finite_safety_limits(
    overrides: dict[str, float | int],
    message: str,
) -> None:
    """Invalid safety envelopes must be rejected before a process can start."""
    values: dict[str, float | int] = {
        "maximum_portion_target": 900.0,
        "minimum_soak_seconds": 300.0,
        "maximum_portions": 3,
        "maximum_lifetime_seconds": 7_200.0,
        **overrides,
    }

    with pytest.raises(ValueError, match=message):
        PortionLimits(**values)  # type: ignore[arg-type]


def test_order_snapshot_rejects_non_finite_target_before_process_start() -> None:
    """An immutable process may never be created from an invalid target."""
    with pytest.raises(ValueError, match="target value"):
        OrderSnapshot(
            execution_id="execution-invalid",
            request_id="request-invalid",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=float("nan"),
            operation_deadline_at=NOW + timedelta(hours=1),
        )


def test_volume_order_requires_a_positive_finite_runtime_budget() -> None:
    """Every volume process must carry its cumulative hard stop in the snapshot."""
    with pytest.raises(ValueError, match="delivery runtime limit"):
        OrderSnapshot(
            execution_id="execution-invalid-volume",
            request_id="request-invalid-volume",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=500.0,
            operation_deadline_at=NOW + timedelta(hours=1),
            delivery_runtime_limit_seconds=0.0,
        )


def test_order_deadline_must_be_timezone_aware() -> None:
    """Process lifetime comparisons must never mix local-naive and UTC instants."""
    with pytest.raises(ValueError, match="deadline"):
        OrderSnapshot(
            execution_id="execution-naive",
            request_id="request-naive",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=datetime(2026, 7, 29, 7),
        )


def test_process_start_requires_timezone_aware_current_time() -> None:
    """The pure module must reject ambiguous wall-clock inputs explicitly."""
    with pytest.raises(ValueError, match="current time"):
        IrrigationProcessModule().start(
            OrderSnapshot(
                execution_id="execution-naive-now",
                request_id="request-naive-now",
                zone_id="lawn",
                target_type=TargetType.DURATION,
                target_value=900.0,
                operation_deadline_at=NOW + timedelta(hours=1),
            ),
            PortionLimits(
                maximum_portion_target=900.0,
                minimum_soak_seconds=300.0,
                maximum_portions=1,
                maximum_lifetime_seconds=3_600.0,
            ),
            now=datetime(2026, 7, 29, 6),
        )


def test_process_advance_requires_timezone_aware_current_time() -> None:
    """Every lifecycle transition uses unambiguous instants."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-naive-advance",
            request_id="request-naive-advance",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    with pytest.raises(ValueError, match="current time"):
        module.advance(
            started.process,
            started.portions,
            PortionStarted(portion_id="execution-naive-advance:1"),
            now=datetime(2026, 7, 29, 6),
        )


def test_settled_first_portion_preserves_rest_target_and_enters_soak_pause() -> None:
    """A settled portion updates the aggregate without completing the order early."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-soak",
            request_id="request-soak",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=2_700.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    settled_at = NOW + timedelta(seconds=900)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-soak:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=settled_at,
    )

    assert transition.process.status is ProcessStatus.SOAKING
    assert transition.process.remaining_value == 1_800.0
    assert transition.process.delivered_duration_seconds == 900.0
    assert transition.process.completed_portion_count == 1
    assert transition.portions[0].status is PortionStatus.SETTLED
    assert transition.portions[0].delivered_duration_seconds == 900.0
    assert transition.action == WaitUntil(
        when=settled_at + timedelta(seconds=300),
        reason="soak_pause",
    )


def test_due_resume_prepares_the_next_portion_without_creating_an_order() -> None:
    """A due continuation appends one subordinate portion to the same process."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-resume",
            request_id="request-resume",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    settled = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-resume:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=900),
    )
    resume_at = NOW + timedelta(seconds=1_200)

    transition = module.advance(
        settled.process,
        settled.portions,
        ResumeDue(),
        now=resume_at,
    )

    assert transition.process.execution_id == "execution-resume"
    assert transition.process.status is ProcessStatus.WATERING
    assert len(transition.portions) == 2
    assert transition.portions[1].portion_id == "execution-resume:2"
    assert transition.action == PreparePortion(
        portion_id="execution-resume:2",
        target_type=TargetType.DURATION,
        target_value=900.0,
        hard_time_limit_seconds=None,
    )


def test_late_resume_does_not_prepare_an_unfinishable_remaining_tail() -> None:
    """A pause may extend only while the full rest target still fits its deadline."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-late-resume",
            request_id="request-late-resume",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(seconds=2_100),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=2_100.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    soaking = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-late-resume:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=900),
    )

    transition = module.advance(
        soaking.process,
        soaking.portions,
        ResumeDue(),
        now=NOW + timedelta(seconds=1_201),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert len(transition.portions) == 1
    assert transition.action == FailClosed(
        reason="process_window_not_fit",
        safety_lock_required=False,
    )


def test_final_settled_portion_completes_the_shared_process() -> None:
    """Only the complete target produces the one terminal process result."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-complete",
            request_id="request-complete",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-complete:1",
            delivered_liters=12.5,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=900),
    )

    assert transition.process.status is ProcessStatus.COMPLETED
    assert transition.process.remaining_value == 0.0
    assert transition.process.delivered_liters == 12.5
    assert transition.process.delivered_duration_seconds == 900.0
    assert transition.action == CompleteProcess(result="target_reached")


def test_confirmed_valve_opening_marks_only_the_current_portion_watering() -> None:
    """Opening evidence must belong to the stable subordinate portion ID."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-opened",
            request_id="request-opened",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    opened_at = NOW + timedelta(seconds=2)

    transition = module.advance(
        started.process,
        started.portions,
        PortionStarted(portion_id="execution-opened:1"),
        now=opened_at,
    )

    assert transition.portions[0].status is PortionStatus.WATERING
    assert transition.portions[0].watering_started_at == opened_at.isoformat()
    assert transition.process.status is ProcessStatus.WATERING


def test_duplicate_identical_opening_confirmation_is_idempotent() -> None:
    """A retried persistence callback must not create conflicting opening evidence."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-opened-twice",
            request_id="request-opened-twice",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    opened_at = NOW + timedelta(seconds=2)
    opened = module.advance(
        started.process,
        started.portions,
        PortionStarted(portion_id="execution-opened-twice:1"),
        now=opened_at,
    )

    duplicate = module.advance(
        opened.process,
        opened.portions,
        PortionStarted(portion_id="execution-opened-twice:1"),
        now=opened_at,
    )

    assert duplicate.process == opened.process
    assert duplicate.portions == opened.portions
    assert duplicate.action == NoOp(reason="portion_already_started")


def test_duplicate_identical_settlement_is_an_idempotent_no_op() -> None:
    """A repeated executor result must never credit the same portion twice."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-idempotent",
            request_id="request-idempotent",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    result = PortionSettled(
        portion_id="execution-idempotent:1",
        delivered_liters=10.0,
        delivered_duration_seconds=900.0,
        target_reached=True,
        measurement_quality="measured",
    )
    settled = module.advance(
        started.process,
        started.portions,
        result,
        now=NOW + timedelta(seconds=900),
    )

    duplicate = module.advance(
        settled.process,
        settled.portions,
        result,
        now=NOW + timedelta(seconds=901),
    )

    assert duplicate.process == settled.process
    assert duplicate.portions == settled.portions
    assert duplicate.action == NoOp(reason="portion_already_settled")


def test_conflicting_duplicate_settlement_fails_closed_without_recrediting() -> None:
    """Different evidence for an already settled ID is persistent-state corruption."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-conflict",
            request_id="request-conflict",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    settled = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-conflict:1",
            delivered_liters=10.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=900),
    )

    conflicting = module.advance(
        settled.process,
        settled.portions,
        PortionSettled(
            portion_id="execution-conflict:1",
            delivered_liters=11.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=901),
    )

    assert conflicting.process.status is ProcessStatus.FAILED
    assert conflicting.process.delivered_liters == 10.0
    assert conflicting.action == FailClosed(
        reason="conflicting_portion_settlement",
        safety_lock_required=True,
    )


def test_safety_violation_settles_known_delivery_and_ends_the_entire_process() -> None:
    """A hardware safety fault may not open another portion of the shared process."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-safety",
            request_id="request-safety",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=2_700.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-safety:1",
            delivered_liters=2.0,
            delivered_duration_seconds=100.0,
            target_reached=False,
            measurement_quality="measured",
            safety_violation="unexpected_flow",
        ),
        now=NOW + timedelta(seconds=100),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.process.remaining_value == 2_600.0
    assert transition.process.delivered_duration_seconds == 100.0
    assert transition.process.completed_portion_count == 1
    assert transition.action == FailClosed(
        reason="unexpected_flow",
        safety_lock_required=True,
    )


def test_unreached_volume_portion_exhausts_the_process_instead_of_retrying() -> None:
    """A volume executor timeout must not be converted into another partial delivery."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-volume-failed",
            request_id="request-volume-failed",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=500.0,
            operation_deadline_at=NOW + timedelta(hours=1),
            delivery_runtime_limit_seconds=600.0,
        ),
        PortionLimits(
            maximum_portion_target=500.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-volume-failed:1",
            delivered_liters=400.0,
            delivered_duration_seconds=600.0,
            target_reached=False,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=600),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.process.remaining_value == 100.0
    assert transition.action == FailClosed(
        reason="volume_target_not_reached",
        safety_lock_required=True,
    )


def test_unreached_duration_portion_fails_instead_of_consuming_extra_portion() -> None:
    """Only explicit recovery may continue after a partial duration delivery."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-duration-failed",
            request_id="request-duration-failed",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-duration-failed:1",
            delivered_liters=0.0,
            delivered_duration_seconds=400.0,
            target_reached=False,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=400),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.process.remaining_value == 500.0
    assert transition.action == FailClosed(
        reason="duration_target_not_reached",
        safety_lock_required=True,
    )


def test_cumulative_volume_runtime_limit_is_enforced_before_completion() -> None:
    """A result beyond the immutable hard runtime budget is never accepted as success."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-runtime",
            request_id="request-runtime",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=500.0,
            operation_deadline_at=NOW + timedelta(hours=1),
            delivery_runtime_limit_seconds=600.0,
        ),
        PortionLimits(
            maximum_portion_target=500.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-runtime:1",
            delivered_liters=500.0,
            delivered_duration_seconds=601.0,
            target_reached=True,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=601),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.action == FailClosed(
        reason="delivery_runtime_exceeded",
        safety_lock_required=True,
    )


def test_volume_process_completes_exactly_on_cumulative_runtime_limit() -> None:
    """The immutable hard limit is inclusive and rejects only actual overruns."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-runtime-boundary",
            request_id="request-runtime-boundary",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=500.0,
            operation_deadline_at=NOW + timedelta(hours=1),
            delivery_runtime_limit_seconds=600.0,
        ),
        PortionLimits(
            maximum_portion_target=500.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    watering = _confirm_active_portion(module, started, now=NOW)

    transition = module.advance(
        watering.process,
        watering.portions,
        PortionSettled(
            portion_id="execution-runtime-boundary:1",
            delivered_liters=500.0,
            delivered_duration_seconds=600.0,
            target_reached=True,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=600),
    )

    assert transition.process.status is ProcessStatus.COMPLETED
    assert transition.process.delivered_duration_seconds == 600.0
    assert transition.action == CompleteProcess(result="target_reached")


def test_result_after_process_deadline_is_not_accepted_as_success() -> None:
    """The total lifetime limit includes the final delivery and remains immutable."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-deadline",
            request_id="request-deadline",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(seconds=1_000),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=1_000.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-deadline:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=1_001),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.process.delivered_duration_seconds == 900.0
    assert transition.action == FailClosed(
        reason="process_deadline_exceeded",
        safety_lock_required=False,
    )


def test_target_reached_evidence_below_portion_target_fails_closed() -> None:
    """Contradictory executor evidence must not create an extra compensating portion."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-inconsistent",
            request_id="request-inconsistent",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    started = _confirm_active_portion(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-inconsistent:1",
            delivered_liters=0.0,
            delivered_duration_seconds=899.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=899),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.process.delivered_duration_seconds == 899.0
    assert transition.action == FailClosed(
        reason="portion_result_inconsistent",
        safety_lock_required=True,
    )


def test_settlement_rejects_negative_or_non_finite_delivery_evidence() -> None:
    """Invalid measurements cannot participate in aggregate process arithmetic."""
    with pytest.raises(ValueError, match="delivered liters"):
        PortionSettled(
            portion_id="execution-invalid-result:1",
            delivered_liters=-1.0,
            delivered_duration_seconds=1.0,
            target_reached=False,
            measurement_quality="measured",
        )
    with pytest.raises(ValueError, match="delivered duration"):
        PortionSettled(
            portion_id="execution-invalid-result:1",
            delivered_liters=0.0,
            delivered_duration_seconds=float("nan"),
            target_reached=False,
            measurement_quality="measured",
        )


def test_cancel_during_watering_persists_intent_before_stopping_executor() -> None:
    """An active process is not terminal until its valve closure can be settled."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-cancel-active",
            request_id="request-cancel-active",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    transition = module.advance(
        started.process,
        started.portions,
        CancelRequested(reason="user_requested"),
        now=NOW + timedelta(seconds=100),
    )

    assert transition.process.status is ProcessStatus.WATERING
    assert transition.process.cancellation_requested is True
    assert transition.action == StopActivePortion(
        portion_id="execution-cancel-active:1",
        reason="user_requested",
    )


def test_stopped_portion_settles_known_delivery_before_process_cancellation() -> None:
    """Cancellation keeps actual delivery but never schedules another portion."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-cancelled",
            request_id="request-cancelled",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    cancelling = module.advance(
        started.process,
        started.portions,
        CancelRequested(reason="user_requested"),
        now=NOW + timedelta(seconds=100),
    )

    transition = module.advance(
        cancelling.process,
        cancelling.portions,
        PortionSettled(
            portion_id="execution-cancelled:1",
            delivered_liters=1.5,
            delivered_duration_seconds=100.0,
            target_reached=False,
            measurement_quality="measured",
            stopped=True,
        ),
        now=NOW + timedelta(seconds=100),
    )

    assert transition.process.status is ProcessStatus.CANCELLED
    assert transition.process.remaining_value == 1_700.0
    assert transition.process.delivered_duration_seconds == 100.0
    assert transition.process.completed_portion_count == 1
    assert transition.action == CancelProcess(reason="user_requested")


def test_cancel_during_soak_pause_is_terminal_without_hardware_action() -> None:
    """A paused process has no executor to stop and can be cancelled atomically."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-cancel-soak",
            request_id="request-cancel-soak",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    soaking = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-cancel-soak:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=900),
    )

    transition = module.advance(
        soaking.process,
        soaking.portions,
        CancelRequested(reason="zone_disabled"),
        now=NOW + timedelta(seconds=901),
    )

    assert transition.process.status is ProcessStatus.CANCELLED
    assert transition.process.remaining_value == 900.0
    assert transition.action == CancelProcess(reason="zone_disabled")


def test_recovery_of_closed_soak_pause_keeps_hardware_free_and_waits() -> None:
    """A persisted pause is restored without preparing or opening a valve."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-recover-soak",
            request_id="request-recover-soak",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    settled_at = NOW + timedelta(seconds=900)
    soaking = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-recover-soak:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=settled_at,
    )

    transition = module.advance(
        soaking.process,
        soaking.portions,
        RecoveryObserved(valves_confirmed_closed=True),
        now=settled_at + timedelta(seconds=10),
    )

    assert transition.process == soaking.process
    assert transition.portions == soaking.portions
    assert transition.action == WaitUntil(
        when=settled_at + timedelta(seconds=300),
        reason="soak_pause",
    )


def test_recovery_without_confirmed_valve_closure_fails_closed_and_locks() -> None:
    """No persisted process state may override an unverified physical valve state."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-recover-open",
            request_id="request-recover-open",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    transition = module.advance(
        started.process,
        started.portions,
        RecoveryObserved(valves_confirmed_closed=False),
        now=NOW + timedelta(seconds=10),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.action == FailClosed(
        reason="portion_recovery_unsafe",
        safety_lock_required=True,
    )


def test_recovery_with_unknown_active_delivery_fails_closed_without_retry() -> None:
    """Unknown water delivery may never be interpreted as zero remaining progress."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-recover-unknown",
            request_id="request-recover-unknown",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(hours=1),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    started = _record_opening_attempt(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-recover-unknown:1",
            delivery_reliable=False,
        ),
        now=NOW + timedelta(seconds=10),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.portions[0].status is PortionStatus.INTERRUPTED
    assert transition.action == FailClosed(
        reason="portion_recovery_unsafe",
        safety_lock_required=True,
    )


def test_reliable_recovery_settles_known_progress_before_a_new_soak_pause() -> None:
    """Reconstructed delivery reduces the rest target exactly once before resuming."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-recover-known",
            request_id="request-recover-known",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )
    started = _record_opening_attempt(module, started, now=NOW)
    recovered_at = NOW + timedelta(seconds=400)

    transition = module.advance(
        started.process,
        started.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-recover-known:1",
            delivery_reliable=True,
            delivered_liters=5.0,
            delivered_duration_seconds=400.0,
            measurement_quality="measured",
        ),
        now=recovered_at,
    )

    assert transition.process.status is ProcessStatus.SOAKING
    assert transition.process.remaining_value == 1_400.0
    assert transition.process.delivered_duration_seconds == 400.0
    assert transition.process.completed_portion_count == 1
    assert transition.portions[0].status is PortionStatus.SETTLED
    assert transition.action == WaitUntil(
        when=recovered_at + timedelta(seconds=300),
        reason="soak_pause",
    )


def test_recovered_partial_delivery_never_exceeds_maximum_portion_count() -> None:
    """Recovery may not enlarge the remaining portion or exceed the immutable count."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-recover-limit",
            request_id="request-recover-limit",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(hours=2),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )

    started = _record_opening_attempt(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-recover-limit:1",
            delivery_reliable=True,
            delivered_liters=5.0,
            delivered_duration_seconds=400.0,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=400),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.process.remaining_value == 1_400.0
    assert transition.process.delivered_duration_seconds == 400.0
    assert transition.action == FailClosed(
        reason="portion_limit_exceeded",
        safety_lock_required=False,
    )


def test_recovered_tail_must_still_fit_the_immutable_process_deadline() -> None:
    """A late restart may account for water but may not reopen an unfinishable process."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-recover-deadline",
            request_id="request-recover-deadline",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=1_800.0,
            operation_deadline_at=NOW + timedelta(seconds=2_400),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=2_400.0,
        ),
        now=NOW,
    )

    started = _record_opening_attempt(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-recover-deadline:1",
            delivery_reliable=True,
            delivered_liters=5.0,
            delivered_duration_seconds=400.0,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=500),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.process.remaining_value == 1_400.0
    assert transition.action == FailClosed(
        reason="process_window_not_fit",
        safety_lock_required=False,
    )


@pytest.mark.parametrize(
    ("target", "maximum_portion", "expected_portions"),
    [
        (1.0, 1.0, 1),
        (901.0, 900.0, 2),
        (2_701.0, 900.0, 4),
        (2.5, 1.0, 3),
    ],
)
def test_duration_process_properties_hold_for_complete_fixed_cap_sequences(
    target: float,
    maximum_portion: float,
    expected_portions: int,
) -> None:
    """Rest target is monotone and portions are bounded for representative inputs."""
    module = IrrigationProcessModule()
    transition = module.start(
        OrderSnapshot(
            execution_id="execution-properties",
            request_id="request-properties",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=target,
            operation_deadline_at=NOW + timedelta(days=1),
        ),
        PortionLimits(
            maximum_portion_target=maximum_portion,
            minimum_soak_seconds=10.0,
            maximum_portions=expected_portions,
            maximum_lifetime_seconds=86_400.0,
        ),
        now=NOW,
    )
    previous_remaining = transition.process.remaining_value
    cursor = NOW

    while isinstance(transition.action, PreparePortion):
        portion_action = transition.action
        transition = _confirm_active_portion(module, transition, now=cursor)
        cursor += timedelta(seconds=portion_action.target_value)
        transition = module.advance(
            transition.process,
            transition.portions,
            PortionSettled(
                portion_id=portion_action.portion_id,
                delivered_liters=0.0,
                delivered_duration_seconds=portion_action.target_value,
                target_reached=True,
                measurement_quality="unavailable",
            ),
            now=cursor,
        )
        assert 0.0 <= transition.process.remaining_value <= previous_remaining
        previous_remaining = transition.process.remaining_value
        if isinstance(transition.action, WaitUntil):
            cursor = transition.action.when
            transition = module.advance(
                transition.process,
                transition.portions,
                ResumeDue(),
                now=cursor,
            )

    assert transition.process.status is ProcessStatus.COMPLETED
    assert transition.process.remaining_value == 0.0
    assert transition.process.delivered_duration_seconds == pytest.approx(target)
    assert transition.process.completed_portion_count == expected_portions
    assert [portion.sequence for portion in transition.portions] == list(
        range(1, expected_portions + 1)
    )
    assert all(portion.target_value <= maximum_portion for portion in transition.portions)


def test_next_volume_portion_receives_only_the_remaining_runtime_budget() -> None:
    """Soak pauses do not reset or consume the cumulative volume hard limit."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-volume-budget",
            request_id="request-volume-budget",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=1_000.0,
            operation_deadline_at=NOW + timedelta(hours=1),
            delivery_runtime_limit_seconds=1_200.0,
        ),
        PortionLimits(
            maximum_portion_target=500.0,
            minimum_soak_seconds=300.0,
            maximum_portions=2,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )
    started = _confirm_active_portion(module, started, now=NOW)
    soaking = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-volume-budget:1",
            delivered_liters=500.0,
            delivered_duration_seconds=400.0,
            target_reached=True,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=400),
    )

    resumed = module.advance(
        soaking.process,
        soaking.portions,
        ResumeDue(),
        now=NOW + timedelta(seconds=700),
    )

    assert resumed.action == PreparePortion(
        portion_id="execution-volume-budget:2",
        target_type=TargetType.VOLUME,
        target_value=500.0,
        hard_time_limit_seconds=800.0,
    )


def test_reliable_partial_volume_recovery_may_continue_with_known_rest_target() -> None:
    """A restart is not treated as a normal volume timeout when delivery is measurable."""
    module = IrrigationProcessModule()
    started = module.start(
        OrderSnapshot(
            execution_id="execution-volume-recovery",
            request_id="request-volume-recovery",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=1_000.0,
            operation_deadline_at=NOW + timedelta(hours=1),
            delivery_runtime_limit_seconds=1_200.0,
        ),
        PortionLimits(
            maximum_portion_target=500.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=3_600.0,
        ),
        now=NOW,
    )

    started = _record_opening_attempt(module, started, now=NOW)
    transition = module.advance(
        started.process,
        started.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-volume-recovery:1",
            delivery_reliable=True,
            delivered_liters=200.0,
            delivered_duration_seconds=200.0,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=200),
    )

    assert transition.process.status is ProcessStatus.SOAKING
    assert transition.process.remaining_value == 800.0
    assert transition.process.delivered_liters == 200.0
    assert transition.portions[0].result == "restart_recovered"


def test_prepared_portion_is_redispatched_after_safe_recovery_without_opening_attempt() -> None:
    """A committed portion that never reached actuation remains safely dispatchable."""
    module = IrrigationProcessModule()
    started = _started_duration_process(execution_id="execution-prepared-recovery")

    recovered = module.advance(
        started.process,
        started.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-prepared-recovery:1",
        ),
        now=NOW + timedelta(seconds=10),
    )

    assert recovered.process == started.process
    assert recovered.portions == started.portions
    assert recovered.action == started.action


def test_unknown_delivery_after_persisted_opening_attempt_fails_closed() -> None:
    """A crash between opening command and confirmation must never assume zero water."""
    module = IrrigationProcessModule()
    started = _started_duration_process(execution_id="execution-opening-recovery")
    opening = module.advance(
        started.process,
        started.portions,
        PortionOpening(portion_id="execution-opening-recovery:1"),
        now=NOW + timedelta(seconds=1),
    )

    recovered = module.advance(
        opening.process,
        opening.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-opening-recovery:1",
        ),
        now=NOW + timedelta(seconds=10),
    )

    assert recovered.process.status is ProcessStatus.FAILED
    assert recovered.portions[0].status is PortionStatus.INTERRUPTED
    assert recovered.action == FailClosed(
        reason="portion_recovery_unsafe",
        safety_lock_required=True,
    )


def test_proven_zero_delivery_after_opening_attempt_redispatches_same_portion() -> None:
    """Reliable zero evidence must not consume a portion or create a soak pause."""
    module = IrrigationProcessModule()
    started = _started_duration_process(
        execution_id="execution-zero-recovery", target=1_800.0, maximum_portions=2
    )
    opening = _record_opening_attempt(module, started, now=NOW)

    recovered = module.advance(
        opening.process,
        opening.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-zero-recovery:1",
            delivery_reliable=True,
            delivered_liters=0.0,
            delivered_duration_seconds=0.0,
            measurement_quality="measured",
        ),
        now=NOW + timedelta(seconds=10),
    )

    assert recovered.process == started.process
    assert recovered.process.completed_portion_count == 0
    assert recovered.portions == started.portions
    assert recovered.action == started.action


def test_recovery_of_expired_soak_pause_fails_without_redispatch() -> None:
    """Recovery may retain a pause only while its immutable process window is valid."""
    module = IrrigationProcessModule()
    started = _started_duration_process(
        execution_id="execution-expired-soak", target=1_800.0, maximum_portions=2
    )
    opened = module.advance(
        started.process,
        started.portions,
        PortionStarted(portion_id="execution-expired-soak:1"),
        now=NOW,
    )
    soaking = module.advance(
        opened.process,
        opened.portions,
        PortionSettled(
            portion_id="execution-expired-soak:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=900),
    )

    recovered = module.advance(
        soaking.process,
        soaking.portions,
        RecoveryObserved(valves_confirmed_closed=True),
        now=datetime.fromisoformat(soaking.process.process_deadline_at or ""),
    )

    assert recovered.process.status is ProcessStatus.FAILED
    assert recovered.action == FailClosed(
        reason="process_deadline_exceeded",
        safety_lock_required=False,
    )


def test_terminal_process_with_active_checkpoint_fails_closed() -> None:
    """A terminal process may never silently discard contradictory hardware ownership."""
    module = IrrigationProcessModule()
    started = _started_duration_process(execution_id="execution-terminal-checkpoint")
    terminal = replace(
        started.process,
        status=ProcessStatus.COMPLETED,
        remaining_value=0.0,
        ended_at=(NOW + timedelta(seconds=1)).isoformat(),
        result="target_reached",
    )

    recovered = module.advance(
        terminal,
        started.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id="execution-terminal-checkpoint:1",
            active_checkpoint_present=True,
        ),
        now=NOW + timedelta(seconds=2),
    )

    assert recovered.process.status is ProcessStatus.FAILED
    assert recovered.action == FailClosed(
        reason="portion_state_inconsistent",
        safety_lock_required=True,
    )


def test_soaking_process_with_active_checkpoint_fails_closed() -> None:
    """A hardware-free soak pause may never retain an active hydraulic checkpoint."""
    module = IrrigationProcessModule()
    started = _started_duration_process(
        execution_id="execution-soaking-checkpoint",
        target=1_800.0,
        maximum_portions=2,
    )
    opened = _confirm_active_portion(module, started, now=NOW)
    soaking = module.advance(
        opened.process,
        opened.portions,
        PortionSettled(
            portion_id="execution-soaking-checkpoint:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=900),
    )

    recovered = module.advance(
        soaking.process,
        soaking.portions,
        RecoveryObserved(
            valves_confirmed_closed=True,
            active_checkpoint_present=True,
        ),
        now=NOW + timedelta(seconds=901),
    )

    assert recovered.process.status is ProcessStatus.FAILED
    assert recovered.action == FailClosed(
        reason="portion_state_inconsistent",
        safety_lock_required=True,
    )


def test_resume_is_rejected_when_persistent_state_already_has_an_open_portion() -> None:
    """No event may create a second unsettled portion from contradictory state."""
    module = IrrigationProcessModule()
    started = _started_duration_process(
        execution_id="execution-double-open", target=1_800.0, maximum_portions=2
    )
    contradictory_process = replace(
        started.process,
        status=ProcessStatus.SOAKING,
        next_portion_at=NOW.isoformat(),
    )

    transition = module.advance(
        contradictory_process,
        started.portions,
        ResumeDue(),
        now=NOW,
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert len(transition.portions) == 1
    assert transition.action == FailClosed(
        reason="process_state_inconsistent",
        safety_lock_required=True,
    )


def test_normal_settlement_requires_confirmed_watering_state() -> None:
    """The persistent portion automaton may not skip prepared-to-watering."""
    module = IrrigationProcessModule()
    started = _started_duration_process(execution_id="execution-skip-watering")

    transition = module.advance(
        started.process,
        started.portions,
        PortionSettled(
            portion_id="execution-skip-watering:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=900),
    )

    assert transition.process.status is ProcessStatus.FAILED
    assert transition.action == FailClosed(
        reason="invalid_process_transition",
        safety_lock_required=True,
    )


def test_resume_event_is_forbidden_while_a_portion_is_watering() -> None:
    """A continuation event cannot bypass the single-open-portion invariant."""
    module = IrrigationProcessModule()
    started = _started_duration_process(execution_id="execution-resume-watering")
    watering = _confirm_active_portion(module, started, now=NOW)

    transition = module.advance(
        watering.process,
        watering.portions,
        ResumeDue(),
        now=NOW + timedelta(seconds=1),
    )

    assert transition.action == FailClosed(
        reason="invalid_process_transition",
        safety_lock_required=True,
    )


@pytest.mark.parametrize(
    "event",
    [
        PortionOpening(portion_id="execution-soaking-matrix:2"),
        PortionStarted(portion_id="execution-soaking-matrix:2"),
    ],
)
def test_opening_events_are_forbidden_during_soak_pause(
    event: PortionOpening | PortionStarted,
) -> None:
    """The event matrix never permits hardware actuation while the process soaks."""
    module = IrrigationProcessModule()
    started = _started_duration_process(
        execution_id="execution-soaking-matrix", target=1_800.0, maximum_portions=2
    )
    watering = _confirm_active_portion(module, started, now=NOW)
    soaking = module.advance(
        watering.process,
        watering.portions,
        PortionSettled(
            portion_id="execution-soaking-matrix:1",
            delivered_liters=0.0,
            delivered_duration_seconds=900.0,
            target_reached=True,
            measurement_quality="unavailable",
        ),
        now=NOW + timedelta(seconds=900),
    )

    transition = module.advance(
        soaking.process,
        soaking.portions,
        event,
        now=NOW + timedelta(seconds=901),
    )

    assert transition.action == FailClosed(
        reason="invalid_process_transition",
        safety_lock_required=True,
    )


def test_two_open_portions_in_persistent_state_fail_before_event_dispatch() -> None:
    """Cross-record corruption is detected centrally before any adapter action."""
    module = IrrigationProcessModule()
    started = _started_duration_process(
        execution_id="execution-two-open", target=1_800.0, maximum_portions=2
    )
    second = replace(
        started.portions[0],
        portion_id="execution-two-open:2",
        sequence=2,
    )
    contradictory_process = replace(started.process, next_portion_sequence=3)

    transition = module.advance(
        contradictory_process,
        (*started.portions, second),
        CancelRequested(reason="user_requested"),
        now=NOW,
    )

    assert transition.action == FailClosed(
        reason="process_state_inconsistent",
        safety_lock_required=True,
    )
    assert all(portion.status is PortionStatus.INTERRUPTED for portion in transition.portions)


@pytest.mark.parametrize(
    ("available_seconds", "accepted"),
    [(900.0, True), (899.999, False)],
)
def test_process_window_boundary_is_checked_on_both_sides(
    available_seconds: float,
    accepted: bool,
) -> None:
    """The exact conservative deadline fits; any shorter window is rejected."""
    transition = IrrigationProcessModule().start(
        OrderSnapshot(
            execution_id=f"execution-boundary-{available_seconds}",
            request_id="request-boundary",
            zone_id="lawn",
            target_type=TargetType.DURATION,
            target_value=900.0,
            operation_deadline_at=NOW + timedelta(seconds=available_seconds),
        ),
        PortionLimits(
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=1,
            maximum_lifetime_seconds=available_seconds,
        ),
        now=NOW,
    )

    assert isinstance(transition.action, PreparePortion) is accepted


@pytest.mark.parametrize(("target", "cap"), [(1_001.0, 500.0), (2.5, 1.0)])
def test_volume_process_properties_hold_for_non_divisible_targets(
    target: float,
    cap: float,
) -> None:
    """Volume rest targets and IDs remain monotone for uneven fixed-cap tails."""
    module = IrrigationProcessModule()
    expected_portions = math.ceil(target / cap)
    transition = module.start(
        OrderSnapshot(
            execution_id=f"execution-volume-properties-{target}",
            request_id="request-volume-properties",
            zone_id="hedge",
            target_type=TargetType.VOLUME,
            target_value=target,
            operation_deadline_at=NOW + timedelta(hours=2),
            delivery_runtime_limit_seconds=3_600.0,
        ),
        PortionLimits(
            maximum_portion_target=cap,
            minimum_soak_seconds=10.0,
            maximum_portions=expected_portions,
            maximum_lifetime_seconds=7_200.0,
        ),
        now=NOW,
    )
    cursor = NOW
    previous_remaining = target

    while isinstance(transition.action, PreparePortion):
        action = transition.action
        transition = _confirm_active_portion(module, transition, now=cursor)
        cursor += timedelta(seconds=1)
        transition = module.advance(
            transition.process,
            transition.portions,
            PortionSettled(
                portion_id=action.portion_id,
                delivered_liters=action.target_value,
                delivered_duration_seconds=1.0,
                target_reached=True,
                measurement_quality="measured",
            ),
            now=cursor,
        )
        assert transition.process.remaining_value <= previous_remaining
        previous_remaining = transition.process.remaining_value
        if isinstance(transition.action, WaitUntil):
            cursor = transition.action.when
            transition = module.advance(
                transition.process,
                transition.portions,
                ResumeDue(),
                now=cursor,
            )

    assert transition.process.status is ProcessStatus.COMPLETED
    assert transition.process.delivered_liters == pytest.approx(target)
    assert transition.process.completed_portion_count == expected_portions


@pytest.mark.parametrize(
    ("status_name", "event_name"),
    [
        (status_name, event_name)
        for status_name in ("prepared", "watering", "soaking", "completed")
        for event_name in (
            "opening",
            "started",
            "settled",
            "resume",
            "cancel",
            "recovery",
        )
    ],
)
def test_process_status_event_matrix_rejects_only_forbidden_transitions(
    status_name: str,
    event_name: str,
) -> None:
    """Every public event is classified for each non-failed persistent status."""
    module = IrrigationProcessModule()
    execution_id = f"execution-event-matrix-{status_name}"
    target = 1_800.0 if status_name == "soaking" else 900.0
    transition = _started_duration_process(
        execution_id=execution_id,
        target=target,
        maximum_portions=2 if status_name == "soaking" else 1,
    )
    if status_name in {"watering", "soaking", "completed"}:
        transition = _confirm_active_portion(module, transition, now=NOW)
    if status_name in {"soaking", "completed"}:
        transition = module.advance(
            transition.process,
            transition.portions,
            PortionSettled(
                portion_id=f"{execution_id}:1",
                delivered_liters=0.0,
                delivered_duration_seconds=900.0,
                target_reached=True,
                measurement_quality="unavailable",
            ),
            now=NOW + timedelta(seconds=900),
        )

    active = next(
        (
            portion
            for portion in transition.portions
            if portion.status in {PortionStatus.PREPARED, PortionStatus.WATERING}
        ),
        None,
    )
    evidence = transition.portions[0]
    now = NOW + timedelta(seconds=1)
    event: (
        PortionOpening
        | PortionStarted
        | PortionSettled
        | ResumeDue
        | CancelRequested
        | RecoveryObserved
    )
    if event_name == "opening":
        event = PortionOpening(
            portion_id=active.portion_id if active is not None else f"{execution_id}:2"
        )
        if active is not None and active.opening_attempted_at is not None:
            now = datetime.fromisoformat(active.opening_attempted_at)
    elif event_name == "started":
        event = PortionStarted(
            portion_id=active.portion_id if active is not None else f"{execution_id}:2"
        )
        if active is not None and active.watering_started_at is not None:
            now = datetime.fromisoformat(active.watering_started_at)
    elif event_name == "settled":
        event = PortionSettled(
            portion_id=evidence.portion_id,
            delivered_liters=evidence.delivered_liters,
            delivered_duration_seconds=(
                evidence.delivered_duration_seconds
                if evidence.status is PortionStatus.SETTLED
                else evidence.target_value
            ),
            target_reached=True,
            measurement_quality=(
                evidence.measurement_quality
                if evidence.status is PortionStatus.SETTLED
                else "unavailable"
            ),
        )
    elif event_name == "resume":
        event = ResumeDue()
        now = (
            datetime.fromisoformat(transition.process.next_portion_at)
            if transition.process.next_portion_at is not None
            else now
        )
    elif event_name == "cancel":
        event = CancelRequested(reason="matrix_check")
    else:
        event = RecoveryObserved(
            valves_confirmed_closed=True,
            portion_id=active.portion_id if active is not None else None,
        )

    result = module.advance(
        transition.process,
        transition.portions,
        event,
        now=now,
    )

    forbidden = (status_name, event_name) in {
        ("prepared", "settled"),
        ("prepared", "resume"),
        ("watering", "resume"),
        ("soaking", "opening"),
        ("soaking", "started"),
    }
    assert (
        isinstance(result.action, FailClosed)
        and result.action.reason == "invalid_process_transition"
    ) is forbidden
