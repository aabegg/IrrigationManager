"""Public scheduling behavior for orders competing with soaking processes."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.irrigation_manager.models import (
    IrrigationExecutionState,
    ManualIrrigationRequest,
    PortionPolicySnapshot,
)
from custom_components.irrigation_manager.scheduler import (
    DispatchDecision,
    ResumeCandidate,
    resume_candidate_from_execution,
    select_dispatch_work,
)

NOW = datetime(2026, 7, 29, 6, tzinfo=UTC)


def _order(
    request_id: str,
    *,
    zone_id: str,
    duration_seconds: float,
    sequence: int = 1,
) -> ManualIrrigationRequest:
    """Create one ready manual duration order with a conservative deadline."""
    return ManualIrrigationRequest(
        request_id=request_id,
        sequence=sequence,
        zone_id=zone_id,
        zone_subentry_id=f"subentry-{zone_id}",
        zone_name=zone_id,
        zone_valve=f"switch.{zone_id}",
        main_valve="switch.main",
        target_type="duration",
        target_value=duration_seconds,
        remaining_value=duration_seconds,
        created_at=(NOW - timedelta(minutes=1)).isoformat(),
        expires_at=(NOW + timedelta(hours=2)).isoformat(),
        operation_deadline_at=(NOW + timedelta(hours=2)).isoformat(),
    )


def _resume(
    execution_id: str,
    *,
    zone_id: str,
    earliest_offset_seconds: float,
    latest_offset_seconds: float,
    occupancy_seconds: float = 300.0,
) -> ResumeCandidate:
    """Create one paused process reservation around the fixed test instant."""
    return ResumeCandidate(
        execution_id=execution_id,
        request_id=f"request-{execution_id}",
        zone_id=zone_id,
        earliest_start=NOW + timedelta(seconds=earliest_offset_seconds),
        latest_safe_start=NOW + timedelta(seconds=latest_offset_seconds),
        conservative_occupancy_seconds=occupancy_seconds,
    )


def test_dispatch_without_resumptions_preserves_legacy_order_priority() -> None:
    """The partial path selects the same FIFO manual order when no process is paused."""
    later = _order("later", zone_id="beds", duration_seconds=60.0, sequence=2)
    first = _order("first", zone_id="lawn", duration_seconds=60.0, sequence=1)

    decision = select_dispatch_work(now=NOW, orders=(later, first), resumptions=())

    assert decision == DispatchDecision.for_order(first)


def test_due_resumption_wins_when_an_order_would_cross_its_latest_safe_start() -> None:
    """A long order can never consume a reserved continuation deadline."""
    order = _order("too-long", zone_id="beds", duration_seconds=301.0)
    resume = _resume(
        "lawn-process",
        zone_id="lawn",
        earliest_offset_seconds=0.0,
        latest_offset_seconds=300.0,
    )

    decision = select_dispatch_work(now=NOW, orders=(order,), resumptions=(resume,))

    assert decision == DispatchDecision.for_resumption(resume)


def test_other_zone_order_may_fill_gap_before_latest_safe_start() -> None:
    """A conservative short order may use the soak pause without delaying its owner."""
    order = _order("gap-filler", zone_id="beds", duration_seconds=240.0)
    resume = _resume(
        "lawn-process",
        zone_id="lawn",
        earliest_offset_seconds=0.0,
        latest_offset_seconds=300.0,
    )

    decision = select_dispatch_work(
        now=NOW,
        orders=(order,),
        resumptions=(resume,),
        hydraulic_overhead_seconds=30.0,
    )

    assert decision == DispatchDecision.for_order(order)


def test_order_for_same_zone_is_excluded_while_process_is_soaking() -> None:
    """A second order cannot start for a zone that still owns an open process."""
    same_zone = _order("duplicate-zone", zone_id="lawn", duration_seconds=30.0)
    future_resume = _resume(
        "lawn-process",
        zone_id="lawn",
        earliest_offset_seconds=60.0,
        latest_offset_seconds=120.0,
    )

    decision = select_dispatch_work(
        now=NOW,
        orders=(same_zone,),
        resumptions=(future_resume,),
    )

    assert decision is None


def test_earliest_deadline_resumption_is_selected_when_no_order_fits() -> None:
    """Multiple paused processes retain the most urgent safe continuation first."""
    long_order = _order("too-long", zone_id="trees", duration_seconds=301.0)
    later = _resume(
        "beds-process",
        zone_id="beds",
        earliest_offset_seconds=0.0,
        latest_offset_seconds=600.0,
    )
    urgent = _resume(
        "lawn-process",
        zone_id="lawn",
        earliest_offset_seconds=0.0,
        latest_offset_seconds=300.0,
    )

    decision = select_dispatch_work(
        now=NOW,
        orders=(long_order,),
        resumptions=(later, urgent),
    )

    assert decision == DispatchDecision.for_resumption(urgent)


def test_resumption_choice_preserves_every_other_latest_safe_start() -> None:
    """A later-deadline short portion may need to precede a long urgent portion."""
    urgent_but_long = _resume(
        "lawn-process",
        zone_id="lawn",
        earliest_offset_seconds=0.0,
        latest_offset_seconds=100.0,
        occupancy_seconds=300.0,
    )
    later_but_short = _resume(
        "beds-process",
        zone_id="beds",
        earliest_offset_seconds=0.0,
        latest_offset_seconds=200.0,
        occupancy_seconds=50.0,
    )

    decision = select_dispatch_work(
        now=NOW,
        orders=(),
        resumptions=(urgent_but_long, later_but_short),
    )

    assert decision == DispatchDecision.for_resumption(later_but_short)


def test_overdue_resumption_is_returned_for_non_actuating_core_resolution() -> None:
    """An overdue process must be failed terminally instead of sleeping forever."""
    overdue = _resume(
        "overdue-process",
        zone_id="lawn",
        earliest_offset_seconds=-20.0,
        latest_offset_seconds=-1.0,
    )

    decision = select_dispatch_work(now=NOW, orders=(), resumptions=(overdue,))

    assert decision == DispatchDecision.for_resumption(overdue)


def test_resume_candidate_reserves_the_complete_remaining_duration_tail() -> None:
    """Latest safe start is worked backwards from all delivery and hydraulic budgets."""
    process = IrrigationExecutionState(
        execution_id="lawn-process",
        request_id="request-lawn",
        zone_id="lawn",
        target_type="duration",
        target_value=2_700.0,
        remaining_value=1_800.0,
        status="soaking",
        created_at=NOW.isoformat(),
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=900.0,
            minimum_soak_seconds=300.0,
            maximum_portions=3,
            maximum_lifetime_seconds=10_000.0,
        ),
        process_started_at=NOW.isoformat(),
        process_deadline_at=(NOW + timedelta(seconds=3_000)).isoformat(),
        hydraulic_overhead_seconds_per_portion=20.0,
        next_portion_at=(NOW + timedelta(seconds=600)).isoformat(),
        next_portion_sequence=2,
        completed_portion_count=1,
    )

    candidate = resume_candidate_from_execution(process)

    assert candidate == ResumeCandidate(
        execution_id="lawn-process",
        request_id="request-lawn",
        zone_id="lawn",
        earliest_start=NOW + timedelta(seconds=600),
        latest_safe_start=NOW + timedelta(seconds=860),
        conservative_occupancy_seconds=920.0,
    )


def test_resume_candidate_rejects_non_soaking_or_unfinishable_process() -> None:
    """Invalid persisted reservations never become dispatchable work."""
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=900.0,
        minimum_soak_seconds=300.0,
        maximum_portions=2,
        maximum_lifetime_seconds=3_600.0,
    )
    process = IrrigationExecutionState(
        execution_id="lawn-process",
        request_id="request-lawn",
        zone_id="lawn",
        target_type="duration",
        target_value=1_800.0,
        remaining_value=900.0,
        status="watering",
        created_at=NOW.isoformat(),
        portion_policy=policy,
        process_started_at=NOW.isoformat(),
        process_deadline_at=(NOW + timedelta(seconds=1_000)).isoformat(),
        next_portion_at=(NOW + timedelta(seconds=600)).isoformat(),
        next_portion_sequence=2,
        completed_portion_count=1,
    )

    with pytest.raises(ValueError, match="soaking"):
        resume_candidate_from_execution(process)

    with pytest.raises(ValueError, match="safe continuation"):
        resume_candidate_from_execution(
            IrrigationExecutionState.from_dict(
                {
                    **process.as_dict(),
                    "status": "soaking",
                    "process_deadline_at": (NOW + timedelta(seconds=800)).isoformat(),
                }
            )
        )
