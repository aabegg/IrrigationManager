"""Small deterministic helpers used by the version-2 runtime."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from .models import IrrigationExecutionState, ManualIrrigationRequest


@dataclass(frozen=True, slots=True)
class ResumeCandidate:
    """Conservative reservation for one paused irrigation process."""

    execution_id: str
    request_id: str
    zone_id: str
    earliest_start: datetime
    latest_safe_start: datetime
    conservative_occupancy_seconds: float

    def __post_init__(self) -> None:
        """Reject a reservation that cannot be compared safely."""
        if (
            not self.execution_id
            or not self.request_id
            or not self.zone_id
            or self.earliest_start.utcoffset() is None
            or self.latest_safe_start.utcoffset() is None
            or self.latest_safe_start < self.earliest_start
            or isinstance(self.conservative_occupancy_seconds, bool)
            or not math.isfinite(self.conservative_occupancy_seconds)
            or self.conservative_occupancy_seconds <= 0
        ):
            raise ValueError("Resume candidate is malformed")


@dataclass(frozen=True, slots=True)
class DispatchDecision:
    """Exactly one safe order start or process continuation."""

    order: ManualIrrigationRequest | None = None
    resumption: ResumeCandidate | None = None

    def __post_init__(self) -> None:
        """Keep dispatch work as a closed exclusive choice."""
        if (self.order is None) == (self.resumption is None):
            raise ValueError("Dispatch decision must contain exactly one work item")

    @classmethod
    def for_order(cls, order: ManualIrrigationRequest) -> DispatchDecision:
        """Select one not-yet-started irrigation order."""
        return cls(order=order)

    @classmethod
    def for_resumption(cls, candidate: ResumeCandidate) -> DispatchDecision:
        """Select one paused irrigation process continuation."""
        return cls(resumption=candidate)


def resume_candidate_from_execution(
    process: IrrigationExecutionState,
) -> ResumeCandidate:
    """Derive one conservative dispatcher reservation from a soaking process."""
    policy = process.portion_policy
    if process.status != "soaking":
        raise ValueError("Resume candidate requires a soaking process")
    if (
        policy is None
        or policy.target_type != process.target_type
        or process.next_portion_at is None
        or process.process_deadline_at is None
        or process.remaining_value <= 0
    ):
        raise ValueError("Soaking process has incomplete continuation evidence")
    required_portions = math.ceil(process.remaining_value / policy.maximum_portion_target)
    if (
        required_portions <= 0
        or process.completed_portion_count + required_portions > policy.maximum_portions
    ):
        raise ValueError("Soaking process has no safe continuation")
    remaining_delivery_seconds = (
        process.remaining_value
        if process.target_type == "duration"
        else (process.delivery_runtime_limit_seconds or 0.0) - process.delivered_duration_seconds
    )
    if remaining_delivery_seconds <= 0:
        raise ValueError("Soaking process has no safe continuation")
    remaining_span_seconds = (
        remaining_delivery_seconds
        + required_portions * process.hydraulic_overhead_seconds_per_portion
        + (required_portions - 1) * policy.minimum_soak_seconds
    )
    deadline = datetime.fromisoformat(process.process_deadline_at)
    earliest_start = datetime.fromisoformat(process.next_portion_at)
    latest_safe_start = deadline - timedelta(seconds=remaining_span_seconds)
    if latest_safe_start < earliest_start:
        raise ValueError("Soaking process has no safe continuation")
    next_delivery_seconds = (
        min(process.remaining_value, policy.maximum_portion_target)
        if process.target_type == "duration"
        else remaining_delivery_seconds
    )
    return ResumeCandidate(
        execution_id=process.execution_id,
        request_id=process.request_id,
        zone_id=process.zone_id,
        earliest_start=earliest_start,
        latest_safe_start=latest_safe_start,
        conservative_occupancy_seconds=(
            next_delivery_seconds + process.hydraulic_overhead_seconds_per_portion
        ),
    )


def select_dispatch_work(
    *,
    now: datetime,
    orders: Iterable[ManualIrrigationRequest],
    resumptions: Iterable[ResumeCandidate],
    hydraulic_overhead_seconds: float = 0.0,
) -> DispatchDecision | None:
    """Select work without consuming any paused process's safe continuation window."""
    if now.utcoffset() is None:
        raise ValueError("Dispatch time must be timezone-aware")
    if (
        isinstance(hydraulic_overhead_seconds, bool)
        or not math.isfinite(hydraulic_overhead_seconds)
        or hydraulic_overhead_seconds < 0
    ):
        raise ValueError("Hydraulic overhead must be finite and non-negative")
    reservations = tuple(resumptions)
    blocked_zones = {candidate.zone_id for candidate in reservations}
    safe_orders: list[ManualIrrigationRequest] = []
    for order in orders:
        if order.zone_id in blocked_zones or not _order_is_ready(order, now=now):
            continue
        occupancy = _order_occupancy_seconds(order)
        if occupancy is None:
            continue
        finishes_at = now + timedelta(
            seconds=occupancy + hydraulic_overhead_seconds,
        )
        deadline = datetime.fromisoformat(order.operation_deadline_at or order.expires_at)
        if finishes_at > deadline or any(
            finishes_at > candidate.latest_safe_start for candidate in reservations
        ):
            continue
        safe_orders.append(order)
    selected_order = min(safe_orders, key=request_priority, default=None)
    if selected_order is not None:
        return DispatchDecision.for_order(selected_order)
    due_resumptions = tuple(
        candidate for candidate in reservations if candidate.earliest_start <= now
    )
    overdue_resumption = min(
        (candidate for candidate in due_resumptions if candidate.latest_safe_start < now),
        key=lambda candidate: (
            candidate.latest_safe_start,
            candidate.execution_id,
        ),
        default=None,
    )
    if overdue_resumption is not None:
        # The adapter feeds this back into the process core. The core will emit a
        # non-actuating FailClosed transition because the complete tail no longer fits.
        return DispatchDecision.for_resumption(overdue_resumption)
    safe_resumptions = tuple(
        candidate
        for candidate in due_resumptions
        if now <= candidate.latest_safe_start
        and all(
            other.execution_id == candidate.execution_id
            or now + timedelta(seconds=candidate.conservative_occupancy_seconds)
            <= other.latest_safe_start
            for other in reservations
        )
    )
    selected_resumption = min(
        safe_resumptions,
        key=lambda candidate: (
            candidate.latest_safe_start,
            candidate.earliest_start,
            candidate.execution_id,
        ),
        default=None,
    )
    return (
        DispatchDecision.for_resumption(selected_resumption)
        if selected_resumption is not None
        else None
    )


def _order_is_ready(request: ManualIrrigationRequest, *, now: datetime) -> bool:
    """Return whether one order may be considered at this instant."""
    return (
        request.status == "pending"
        and datetime.fromisoformat(request.operation_deadline_at or request.expires_at) > now
        and (
            request.requested_start_at is None
            or datetime.fromisoformat(request.requested_start_at) <= now
        )
    )


def _order_occupancy_seconds(request: ManualIrrigationRequest) -> float | None:
    """Return the conservative full hydraulic occupancy of one order."""
    value = (
        request.remaining_value
        if request.target_type == "duration"
        else request.delivery_runtime_limit_seconds or request.hard_time_limit_seconds
    )
    if value is None or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        return None
    return value


def planned_volume_duration_seconds(
    *, target_liters: float, max_runtime_seconds: float, expected_flow_l_min: float | None
) -> float:
    """Estimate volume delivery from a flow profile or reserve the hard limit."""
    if (
        expected_flow_l_min is None
        or not math.isfinite(expected_flow_l_min)
        or expected_flow_l_min <= 0
    ):
        return max_runtime_seconds
    estimated = target_liters * 60 / expected_flow_l_min
    return min(estimated, max_runtime_seconds)


def resolve_local_wall_time(day: date, value: time, timezone: tzinfo | None) -> datetime:
    """Resolve a wall time using fold=0 and normalize DST gaps through UTC."""
    return datetime.combine(day, value, tzinfo=timezone).replace(fold=0).astimezone(UTC)


def select_manual_request(
    *, now: datetime, requests: Iterable[ManualIrrigationRequest]
) -> ManualIrrigationRequest | None:
    """Select the next ready v2 order in stable priority order."""
    ready = (request for request in requests if _order_is_ready(request, now=now))
    return min(ready, key=request_priority, default=None)


def request_priority(request: ManualIrrigationRequest) -> tuple[object, ...]:
    """Keep manual FIFO ahead of ordered automatic work."""
    if request.source != "automatic":
        return (0, request.sequence, request.request_id)
    return (
        1,
        datetime.fromisoformat(request.automatic_window_end or request.expires_at).timestamp(),
        request.zone_id,
        request.request_id,
    )
