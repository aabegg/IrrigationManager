"""Pure lifecycle decisions for partial irrigation deliveries and soak pauses."""

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from .models import (
    IrrigationExecutionState,
    IrrigationPortionState,
    PortionPolicySnapshot,
)


class TargetType(StrEnum):
    """Supported irrigation target dimensions."""

    DURATION = "duration"
    VOLUME = "volume"


class ProcessStatus(StrEnum):
    """Lifecycle states of one accepted irrigation order."""

    WATERING = "watering"
    SOAKING = "soaking"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PortionStatus(StrEnum):
    """Lifecycle states of one subordinate partial delivery."""

    PREPARED = "prepared"
    WATERING = "watering"
    SETTLED = "settled"
    INTERRUPTED = "interrupted"


def _timestamp(value: str | None) -> datetime:
    """Parse one required timezone-aware durable timestamp."""
    if value is None:
        raise ValueError("required process timestamp is missing")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("process timestamp must be timezone-aware")
    return parsed


def _optional_timestamp(value: str | None) -> datetime | None:
    """Parse one optional durable timestamp."""
    return None if value is None else _timestamp(value)


def _policy(process: IrrigationExecutionState) -> PortionPolicySnapshot:
    """Return the immutable partial-delivery snapshot of a gated process."""
    if process.portion_policy is None:
        raise ValueError("partial irrigation process has no policy snapshot")
    return process.portion_policy


def _initial_process(
    order: OrderSnapshot,
    policy: PortionPolicySnapshot,
    *,
    status: ProcessStatus,
    now: datetime,
    process_deadline: datetime,
    next_portion_sequence: int,
) -> IrrigationExecutionState:
    """Create the sole durable aggregate used by the pure process module."""
    return IrrigationExecutionState(
        execution_id=order.execution_id,
        request_id=order.request_id,
        zone_id=order.zone_id,
        target_type=order.target_type.value,
        target_value=order.target_value,
        remaining_value=order.target_value,
        status=status,
        created_at=now.isoformat(),
        operation_deadline_at=order.operation_deadline_at.isoformat(),
        delivery_runtime_limit_seconds=order.delivery_runtime_limit_seconds,
        portion_policy=policy,
        process_started_at=now.isoformat(),
        process_deadline_at=process_deadline.isoformat(),
        hydraulic_overhead_seconds_per_portion=(order.hydraulic_overhead_seconds_per_portion),
        next_portion_sequence=next_portion_sequence,
    )


@dataclass(frozen=True, slots=True)
class OrderSnapshot:
    """Immutable order values required to start one irrigation process."""

    execution_id: str
    request_id: str
    zone_id: str
    target_type: TargetType
    target_value: float
    operation_deadline_at: datetime
    delivery_runtime_limit_seconds: float | None = None
    hydraulic_overhead_seconds_per_portion: float = 0.0

    def __post_init__(self) -> None:
        """Reject an unusable immutable irrigation target."""
        if (
            isinstance(self.target_value, bool)
            or not math.isfinite(self.target_value)
            or self.target_value <= 0
        ):
            raise ValueError("target value must be finite and positive")
        if (
            isinstance(self.hydraulic_overhead_seconds_per_portion, bool)
            or not math.isfinite(self.hydraulic_overhead_seconds_per_portion)
            or self.hydraulic_overhead_seconds_per_portion < 0
        ):
            raise ValueError("hydraulic overhead must be finite and non-negative")
        if self.target_type == TargetType.VOLUME and (
            isinstance(self.delivery_runtime_limit_seconds, bool)
            or self.delivery_runtime_limit_seconds is None
            or not math.isfinite(self.delivery_runtime_limit_seconds)
            or self.delivery_runtime_limit_seconds <= 0
        ):
            raise ValueError("delivery runtime limit must be finite and positive")
        if self.operation_deadline_at.utcoffset() is None:
            raise ValueError("operation deadline must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PortionLimits:
    """Validated partial-delivery limits used to start one durable process."""

    maximum_portion_target: float
    minimum_soak_seconds: float
    maximum_portions: int
    maximum_lifetime_seconds: float

    def __post_init__(self) -> None:
        """Reject unusable or unbounded process safety limits."""
        if (
            isinstance(self.maximum_portion_target, bool)
            or not math.isfinite(self.maximum_portion_target)
            or self.maximum_portion_target <= 0
        ):
            raise ValueError("maximum portion target must be finite and positive")
        if (
            isinstance(self.minimum_soak_seconds, bool)
            or not math.isfinite(self.minimum_soak_seconds)
            or self.minimum_soak_seconds <= 0
        ):
            raise ValueError("minimum soak must be finite and positive")
        if (
            isinstance(self.maximum_portions, bool)
            or not isinstance(self.maximum_portions, int)
            or self.maximum_portions <= 0
        ):
            raise ValueError("maximum portions must be a positive integer")
        if (
            isinstance(self.maximum_lifetime_seconds, bool)
            or not math.isfinite(self.maximum_lifetime_seconds)
            or self.maximum_lifetime_seconds <= 0
        ):
            raise ValueError("maximum lifetime must be finite and positive")


@dataclass(frozen=True, slots=True)
class PreparePortion:
    """Persist and then execute one bounded partial delivery."""

    portion_id: str
    target_type: TargetType
    target_value: float
    hard_time_limit_seconds: float | None


@dataclass(frozen=True, slots=True)
class FailClosed:
    """Refuse further actuation after an unsafe process decision."""

    reason: str
    safety_lock_required: bool


@dataclass(frozen=True, slots=True)
class CompleteProcess:
    """Persist the one successful terminal result of an irrigation process."""

    result: str


@dataclass(frozen=True, slots=True)
class StopActivePortion:
    """Stop one active executor before terminally cancelling its process."""

    portion_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class CancelProcess:
    """Persist one terminal cancellation after hardware is known closed."""

    reason: str


@dataclass(frozen=True, slots=True)
class WaitUntil:
    """Release hardware and wake the dispatcher no earlier than one instant."""

    when: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class PortionSettled:
    """Belastable result observed after one partial delivery was closed."""

    portion_id: str
    delivered_liters: float
    delivered_duration_seconds: float
    target_reached: bool
    measurement_quality: str
    safety_violation: str | None = None
    stopped: bool = False
    recovered: bool = False
    result_override: str | None = None

    def __post_init__(self) -> None:
        """Reject delivery evidence that cannot be safely aggregated."""
        if (
            isinstance(self.delivered_liters, bool)
            or not math.isfinite(self.delivered_liters)
            or self.delivered_liters < 0
        ):
            raise ValueError("delivered liters must be finite and non-negative")
        if (
            isinstance(self.delivered_duration_seconds, bool)
            or not math.isfinite(self.delivered_duration_seconds)
            or self.delivered_duration_seconds < 0
        ):
            raise ValueError("delivered duration must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class PortionStarted:
    """Confirmed valve-opening evidence for one prepared partial delivery."""

    portion_id: str


@dataclass(frozen=True, slots=True)
class PortionOpening:
    """Persist that the adapter is about to issue a possible opening command."""

    portion_id: str


@dataclass(frozen=True, slots=True)
class CancelRequested:
    """Persist a request to cancel the entire irrigation process."""

    reason: str


@dataclass(frozen=True, slots=True)
class RecoveryObserved:
    """Fail-closed valve and delivery evidence collected during startup recovery."""

    valves_confirmed_closed: bool
    portion_id: str | None = None
    delivery_reliable: bool = False
    delivered_liters: float | None = None
    delivered_duration_seconds: float | None = None
    measurement_quality: str = "unknown"
    active_checkpoint_present: bool = False
    checkpoint_consistent: bool = True

    def __post_init__(self) -> None:
        """Reject malformed recovery evidence before it reaches safety decisions."""
        for name, value in (
            ("delivered liters", self.delivered_liters),
            ("delivered duration", self.delivered_duration_seconds),
        ):
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ResumeDue:
    """Request preparation of a process whose minimum soak pause elapsed."""


@dataclass(frozen=True, slots=True)
class NoOp:
    """Record an idempotent state observation without a follow-up side effect."""

    reason: str


@dataclass(frozen=True, slots=True)
class ProcessTransition:
    """Complete pure result of one process decision."""

    process: IrrigationExecutionState
    portions: tuple[IrrigationPortionState, ...]
    action: (
        PreparePortion
        | StopActivePortion
        | WaitUntil
        | CompleteProcess
        | CancelProcess
        | FailClosed
        | NoOp
    )


@dataclass(frozen=True, slots=True)
class _AccountedSettlement:
    """Internally grouped aggregate and evidence from one unique settlement."""

    process: IrrigationExecutionState
    portions: tuple[IrrigationPortionState, ...]
    portion: IrrigationPortionState


class IrrigationProcessModule:
    """Decide safe partial-delivery process transitions without performing I/O."""

    @staticmethod
    def _fail_transition(
        process: IrrigationExecutionState,
        portions: tuple[IrrigationPortionState, ...],
        *,
        now: datetime,
        reason: str,
        safety_lock_required: bool,
    ) -> ProcessTransition:
        """Return one terminal fail-closed state and retire every open portion."""
        retired_portions = tuple(
            replace(
                portion,
                status=PortionStatus.INTERRUPTED,
                watering_ended_at=now.isoformat(),
                result=reason,
            )
            if portion.status in {PortionStatus.PREPARED, PortionStatus.WATERING}
            else portion
            for portion in portions
        )
        return ProcessTransition(
            process=replace(
                process,
                status=ProcessStatus.FAILED,
                next_portion_at=None,
                ended_at=now.isoformat(),
                result=reason,
            ),
            portions=retired_portions,
            action=FailClosed(
                reason=reason,
                safety_lock_required=safety_lock_required,
            ),
        )

    @staticmethod
    def _state_is_consistent(
        process: IrrigationExecutionState,
        portions: tuple[IrrigationPortionState, ...],
    ) -> bool:
        """Validate persisted cross-record invariants before any action is emitted."""
        try:
            _timestamp(process.process_started_at)
            process_deadline = _timestamp(process.process_deadline_at)
            next_portion_at = _optional_timestamp(process.next_portion_at)
            policy = _policy(process)
            for portion in portions:
                _timestamp(portion.prepared_at)
                _optional_timestamp(portion.opening_attempted_at)
                _optional_timestamp(portion.watering_started_at)
                _optional_timestamp(portion.watering_ended_at)
        except ValueError:
            return False
        if (
            not math.isfinite(process.target_value)
            or process.target_value <= 0
            or not math.isfinite(process.remaining_value)
            or not 0 <= process.remaining_value <= process.target_value
            or not math.isfinite(process.delivered_liters)
            or process.delivered_liters < 0
            or not math.isfinite(process.delivered_duration_seconds)
            or process.delivered_duration_seconds < 0
            or not math.isfinite(process.hydraulic_overhead_seconds_per_portion)
            or process.hydraulic_overhead_seconds_per_portion < 0
            or policy.target_type != process.target_type
            or process_deadline < _timestamp(process.process_started_at)
        ):
            return False
        open_portions = tuple(
            portion
            for portion in portions
            if portion.status in {PortionStatus.PREPARED, PortionStatus.WATERING}
        )
        if len(open_portions) > 1:
            return False
        if any(
            portion.execution_id != process.execution_id
            or portion.target_type != process.target_type
            or portion.sequence <= 0
            or portion.portion_id != f"{process.execution_id}:{portion.sequence}"
            or not math.isfinite(portion.target_value)
            or portion.target_value <= 0
            or portion.target_value > _policy(process).maximum_portion_target
            or not math.isfinite(portion.delivered_liters)
            or portion.delivered_liters < 0
            or not math.isfinite(portion.delivered_duration_seconds)
            or portion.delivered_duration_seconds < 0
            for portion in portions
        ):
            return False
        sequences = tuple(portion.sequence for portion in portions)
        if sequences != tuple(range(1, len(portions) + 1)):
            return False
        if process.completed_portion_count != sum(
            portion.status == PortionStatus.SETTLED for portion in portions
        ):
            return False
        if portions and process.next_portion_sequence != max(sequences) + 1:
            return False
        delivered_target = (
            process.delivered_liters
            if process.target_type == TargetType.VOLUME
            else process.delivered_duration_seconds
        )
        if not math.isclose(
            process.remaining_value,
            max(0.0, process.target_value - delivered_target),
            abs_tol=1e-9,
        ):
            return False
        if process.status == ProcessStatus.WATERING:
            return len(open_portions) == 1 and process.next_portion_at is None
        if process.status == ProcessStatus.SOAKING:
            return len(open_portions) == 0 and next_portion_at is not None
        return len(open_portions) == 0 and process.next_portion_at is None

    @staticmethod
    def _remaining_tail_failure(
        process: IrrigationExecutionState,
        *,
        now: datetime,
        pause_before_first: bool,
    ) -> str | None:
        """Return why the conservative remaining span violates immutable limits."""
        required_portions = math.ceil(
            process.remaining_value / _policy(process).maximum_portion_target
        )
        if (
            required_portions <= 0
            or process.completed_portion_count + required_portions
            > _policy(process).maximum_portions
        ):
            return "portion_limit_exceeded"
        remaining_delivery_seconds = (
            process.remaining_value
            if process.target_type == TargetType.DURATION
            else max(
                0.0,
                (process.delivery_runtime_limit_seconds or 0.0)
                - process.delivered_duration_seconds,
            )
        )
        pause_count = required_portions if pause_before_first else required_portions - 1
        remaining_span_seconds = (
            remaining_delivery_seconds
            + required_portions * process.hydraulic_overhead_seconds_per_portion
            + pause_count * _policy(process).minimum_soak_seconds
        )
        if now + timedelta(seconds=remaining_span_seconds) > _timestamp(
            process.process_deadline_at
        ):
            return "process_window_not_fit"
        return None

    def _redispatch_prepared(
        self,
        process: IrrigationExecutionState,
        portions: tuple[IrrigationPortionState, ...],
        *,
        portion_index: int,
        now: datetime,
    ) -> ProcessTransition:
        """Re-arm one provably dry prepared portion without consuming its identity."""
        tail_failure = self._remaining_tail_failure(
            process,
            now=now,
            pause_before_first=False,
        )
        if tail_failure is not None:
            return self._fail_transition(
                process,
                portions,
                now=now,
                reason=tail_failure,
                safety_lock_required=False,
            )
        portion = replace(portions[portion_index], opening_attempted_at=None)
        remaining_runtime = (
            None
            if process.delivery_runtime_limit_seconds is None
            else max(
                0.0,
                process.delivery_runtime_limit_seconds - process.delivered_duration_seconds,
            )
        )
        return ProcessTransition(
            process=process,
            portions=(*portions[:portion_index], portion, *portions[portion_index + 1 :]),
            action=PreparePortion(
                portion_id=portion.portion_id,
                target_type=TargetType(portion.target_type),
                target_value=portion.target_value,
                hard_time_limit_seconds=remaining_runtime,
            ),
        )

    @staticmethod
    def _account_settlement(
        process: IrrigationExecutionState,
        portions: tuple[IrrigationPortionState, ...],
        *,
        portion_index: int,
        event: PortionSettled,
        result: str,
        now: datetime,
    ) -> _AccountedSettlement:
        """Settle one unique portion and update aggregate delivery exactly once."""
        portion = portions[portion_index]
        delivered_liters = process.delivered_liters + event.delivered_liters
        delivered_duration = process.delivered_duration_seconds + event.delivered_duration_seconds
        delivered_target = (
            delivered_liters if process.target_type == TargetType.VOLUME else delivered_duration
        )
        settled = replace(
            portion,
            status=PortionStatus.SETTLED,
            watering_ended_at=now.isoformat(),
            delivered_liters=event.delivered_liters,
            delivered_duration_seconds=event.delivered_duration_seconds,
            result=result,
            measurement_quality=event.measurement_quality,
            measurement_origin=(
                "meter" if event.measurement_quality == "measured" else "unavailable"
            ),
        )
        return _AccountedSettlement(
            process=replace(
                process,
                remaining_value=max(0.0, process.target_value - delivered_target),
                completed_portion_count=process.completed_portion_count + 1,
                delivered_liters=delivered_liters,
                delivered_duration_seconds=delivered_duration,
                measurement_quality=event.measurement_quality,
                measurement_origin=(
                    "meter" if event.measurement_quality == "measured" else "unavailable"
                ),
            ),
            portions=(
                *portions[:portion_index],
                settled,
                *portions[portion_index + 1 :],
            ),
            portion=portion,
        )

    @staticmethod
    def feasibility_failure(
        order: OrderSnapshot,
        policy: PortionLimits,
        *,
        now: datetime,
    ) -> str | None:
        """Prove that a complete order fits before planning or acceptance."""
        if now.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        required_portions = math.ceil(order.target_value / policy.maximum_portion_target)
        if required_portions > policy.maximum_portions:
            return "portion_limit_exceeded"
        delivery_seconds = (
            order.target_value
            if order.target_type == TargetType.DURATION
            else order.delivery_runtime_limit_seconds
        )
        if delivery_seconds is None:
            raise ValueError("Volume irrigation requires a delivery runtime limit")
        process_deadline = min(
            order.operation_deadline_at,
            now + timedelta(seconds=policy.maximum_lifetime_seconds),
        )
        required_seconds = (
            delivery_seconds
            + required_portions * order.hydraulic_overhead_seconds_per_portion
            + (required_portions - 1) * policy.minimum_soak_seconds
        )
        if now + timedelta(seconds=required_seconds) > process_deadline:
            return "process_window_not_fit"
        return None

    def start(
        self,
        order: OrderSnapshot,
        policy: PortionLimits,
        *,
        now: datetime,
    ) -> ProcessTransition:
        """Create one process and prepare only its first bounded portion."""
        if now.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        process_deadline = min(
            order.operation_deadline_at,
            now + timedelta(seconds=policy.maximum_lifetime_seconds),
        )
        policy_snapshot = PortionPolicySnapshot(
            target_type=order.target_type.value,
            maximum_portion_target=policy.maximum_portion_target,
            minimum_soak_seconds=policy.minimum_soak_seconds,
            maximum_portions=policy.maximum_portions,
            maximum_lifetime_seconds=policy.maximum_lifetime_seconds,
        )
        failure = self.feasibility_failure(order, policy, now=now)
        if failure == "portion_limit_exceeded":
            return ProcessTransition(
                process=replace(
                    _initial_process(
                        order,
                        policy_snapshot,
                        status=ProcessStatus.FAILED,
                        now=now,
                        process_deadline=process_deadline,
                        next_portion_sequence=1,
                    ),
                    ended_at=now.isoformat(),
                    result="portion_limit_exceeded",
                ),
                portions=(),
                action=FailClosed(
                    reason="portion_limit_exceeded",
                    safety_lock_required=False,
                ),
            )
        if failure == "process_window_not_fit":
            return ProcessTransition(
                process=replace(
                    _initial_process(
                        order,
                        policy_snapshot,
                        status=ProcessStatus.FAILED,
                        now=now,
                        process_deadline=process_deadline,
                        next_portion_sequence=1,
                    ),
                    ended_at=now.isoformat(),
                    result="process_window_not_fit",
                ),
                portions=(),
                action=FailClosed(
                    reason="process_window_not_fit",
                    safety_lock_required=False,
                ),
            )
        target = min(order.target_value, policy.maximum_portion_target)
        portion_id = f"{order.execution_id}:1"
        process = _initial_process(
            order,
            policy_snapshot,
            status=ProcessStatus.WATERING,
            now=now,
            process_deadline=process_deadline,
            next_portion_sequence=2,
        )
        portion = IrrigationPortionState(
            portion_id=portion_id,
            execution_id=order.execution_id,
            sequence=1,
            target_type=order.target_type.value,
            target_value=target,
            status=PortionStatus.PREPARED,
            prepared_at=now.isoformat(),
        )
        return ProcessTransition(
            process=process,
            portions=(portion,),
            action=PreparePortion(
                portion_id=portion_id,
                target_type=order.target_type,
                target_value=target,
                hard_time_limit_seconds=order.delivery_runtime_limit_seconds,
            ),
        )

    def advance(
        self,
        process: IrrigationExecutionState,
        portions: tuple[IrrigationPortionState, ...],
        event: (
            PortionSettled
            | PortionOpening
            | PortionStarted
            | ResumeDue
            | CancelRequested
            | RecoveryObserved
        ),
        *,
        now: datetime,
    ) -> ProcessTransition:
        """Apply one observed process event without performing I/O."""
        if now.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        if (
            isinstance(event, RecoveryObserved)
            and event.active_checkpoint_present
            and process.status != ProcessStatus.WATERING
        ):
            return self._fail_transition(
                process,
                portions,
                now=now,
                reason="portion_state_inconsistent",
                safety_lock_required=True,
            )
        if not self._state_is_consistent(process, portions):
            return self._fail_transition(
                process,
                portions,
                now=now,
                reason="process_state_inconsistent",
                safety_lock_required=True,
            )
        if process.status in {
            ProcessStatus.COMPLETED,
            ProcessStatus.CANCELLED,
            ProcessStatus.FAILED,
        } and not isinstance(event, PortionSettled):
            return ProcessTransition(
                process=process,
                portions=portions,
                action=NoOp(reason="process_already_terminal"),
            )
        if isinstance(event, ResumeDue) and process.status != ProcessStatus.SOAKING:
            return self._fail_transition(
                process,
                portions,
                now=now,
                reason="invalid_process_transition",
                safety_lock_required=True,
            )
        if isinstance(event, (PortionOpening, PortionStarted, CancelRequested)) and (
            process.status not in {ProcessStatus.WATERING, ProcessStatus.SOAKING}
            or (
                isinstance(event, (PortionOpening, PortionStarted))
                and process.status != ProcessStatus.WATERING
            )
        ):
            return self._fail_transition(
                process,
                portions,
                now=now,
                reason="invalid_process_transition",
                safety_lock_required=True,
            )
        if isinstance(event, PortionSettled):
            matching_portion = next(
                (portion for portion in portions if portion.portion_id == event.portion_id),
                None,
            )
            if matching_portion is None:
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="process_state_inconsistent",
                    safety_lock_required=True,
                )
            if matching_portion.status != PortionStatus.SETTLED and (
                process.status != ProcessStatus.WATERING
                or matching_portion.status != PortionStatus.WATERING
            ):
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="invalid_process_transition",
                    safety_lock_required=True,
                )
        if isinstance(event, RecoveryObserved):
            if not event.valves_confirmed_closed:
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="portion_recovery_unsafe",
                    safety_lock_required=True,
                )
            if not event.checkpoint_consistent:
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="portion_state_inconsistent",
                    safety_lock_required=True,
                )
            if process.status == ProcessStatus.SOAKING:
                if process.next_portion_at is None:
                    return self._fail_transition(
                        process,
                        portions,
                        now=now,
                        reason="process_state_inconsistent",
                        safety_lock_required=True,
                    )
                next_portion_at = _timestamp(process.next_portion_at)
                if now >= _timestamp(process.process_deadline_at):
                    return self._fail_transition(
                        process,
                        portions,
                        now=now,
                        reason="process_deadline_exceeded",
                        safety_lock_required=False,
                    )
                tail_failure = self._remaining_tail_failure(
                    process,
                    now=max(now, next_portion_at),
                    pause_before_first=False,
                )
                if tail_failure is not None:
                    return self._fail_transition(
                        process,
                        portions,
                        now=now,
                        reason=tail_failure,
                        safety_lock_required=False,
                    )
                return ProcessTransition(
                    process=process,
                    portions=portions,
                    action=WaitUntil(when=next_portion_at, reason="soak_pause"),
                )
            portion_index = next(
                (
                    index
                    for index, portion in enumerate(portions)
                    if portion.portion_id == event.portion_id
                    and portion.status in {PortionStatus.PREPARED, PortionStatus.WATERING}
                ),
                None,
            )
            if portion_index is None:
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="process_state_inconsistent",
                    safety_lock_required=True,
                )
            recovered_portion = portions[portion_index]
            no_delivery_evidence = (
                not event.delivery_reliable
                and event.delivered_liters is None
                and event.delivered_duration_seconds is None
            )
            if (
                recovered_portion.status == PortionStatus.PREPARED
                and recovered_portion.opening_attempted_at is None
                and no_delivery_evidence
            ):
                return self._redispatch_prepared(
                    process,
                    portions,
                    portion_index=portion_index,
                    now=now,
                )
            proven_zero_delivery = (
                event.delivery_reliable
                and event.delivered_liters == 0.0
                and event.delivered_duration_seconds == 0.0
            )
            if (
                recovered_portion.status == PortionStatus.PREPARED
                and recovered_portion.opening_attempted_at is not None
                and proven_zero_delivery
            ):
                return self._redispatch_prepared(
                    process,
                    portions,
                    portion_index=portion_index,
                    now=now,
                )
            if portion_index is not None and (
                not event.delivery_reliable
                or event.delivered_liters is None
                or event.delivered_duration_seconds is None
            ):
                interrupted = replace(
                    portions[portion_index],
                    status=PortionStatus.INTERRUPTED,
                    watering_ended_at=now.isoformat(),
                    result="portion_recovery_unsafe",
                    measurement_quality=event.measurement_quality,
                )
                return ProcessTransition(
                    process=replace(
                        process,
                        status=ProcessStatus.FAILED,
                        next_portion_at=None,
                        ended_at=now.isoformat(),
                        result="portion_recovery_unsafe",
                    ),
                    portions=(
                        *portions[:portion_index],
                        interrupted,
                        *portions[portion_index + 1 :],
                    ),
                    action=FailClosed(
                        reason="portion_recovery_unsafe",
                        safety_lock_required=True,
                    ),
                )
            if (
                portion_index is not None
                and event.delivery_reliable
                and event.delivered_liters is not None
                and event.delivered_duration_seconds is not None
            ):
                if recovered_portion.status == PortionStatus.PREPARED:
                    recovered_portion = replace(
                        recovered_portion,
                        status=PortionStatus.WATERING,
                        watering_started_at=recovered_portion.opening_attempted_at,
                    )
                    portions = (
                        *portions[:portion_index],
                        recovered_portion,
                        *portions[portion_index + 1 :],
                    )
                recovered_target = (
                    event.delivered_liters
                    if process.target_type == TargetType.VOLUME
                    else event.delivered_duration_seconds
                )
                return self.advance(
                    process,
                    portions,
                    PortionSettled(
                        portion_id=recovered_portion.portion_id,
                        delivered_liters=event.delivered_liters,
                        delivered_duration_seconds=event.delivered_duration_seconds,
                        target_reached=recovered_target >= recovered_portion.target_value,
                        measurement_quality=event.measurement_quality,
                        recovered=True,
                        result_override="restart_recovered",
                    ),
                    now=now,
                )
            raise ValueError("active recovery evidence is incomplete")
        if isinstance(event, CancelRequested):
            if process.status == ProcessStatus.SOAKING:
                return ProcessTransition(
                    process=replace(
                        process,
                        status=ProcessStatus.CANCELLED,
                        cancellation_requested=True,
                        cancellation_reason=event.reason,
                        next_portion_at=None,
                        ended_at=now.isoformat(),
                        result=event.reason,
                    ),
                    portions=portions,
                    action=CancelProcess(reason=event.reason),
                )
            active = next(
                (
                    portion
                    for portion in reversed(portions)
                    if portion.status in {PortionStatus.PREPARED, PortionStatus.WATERING}
                ),
                None,
            )
            if active is None:
                raise ValueError("watering process has no active portion")
            return ProcessTransition(
                process=replace(
                    process,
                    cancellation_requested=True,
                    cancellation_reason=event.reason,
                ),
                portions=portions,
                action=StopActivePortion(
                    portion_id=active.portion_id,
                    reason=event.reason,
                ),
            )
        if isinstance(event, (PortionOpening, PortionStarted)):
            portion_index = next(
                (
                    index
                    for index, portion in enumerate(portions)
                    if portion.portion_id == event.portion_id
                ),
                None,
            )
            if portion_index is None:
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="process_state_inconsistent",
                    safety_lock_required=True,
                )
            portion = portions[portion_index]
            if isinstance(event, PortionOpening):
                if (
                    portion.status == PortionStatus.PREPARED
                    and portion.opening_attempted_at is None
                ):
                    opening = replace(portion, opening_attempted_at=now.isoformat())
                    return ProcessTransition(
                        process=process,
                        portions=(
                            *portions[:portion_index],
                            opening,
                            *portions[portion_index + 1 :],
                        ),
                        action=NoOp(reason="portion_opening_recorded"),
                    )
                if portion.opening_attempted_at == now.isoformat():
                    return ProcessTransition(
                        process=process,
                        portions=portions,
                        action=NoOp(reason="portion_opening_already_recorded"),
                    )
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="invalid_process_transition",
                    safety_lock_required=True,
                )
            if (
                portion.status == PortionStatus.WATERING
                and portion.watering_started_at == now.isoformat()
            ):
                return ProcessTransition(
                    process=process,
                    portions=portions,
                    action=NoOp(reason="portion_already_started"),
                )
            if portion.status != PortionStatus.PREPARED:
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason="invalid_process_transition",
                    safety_lock_required=True,
                )
            watering = replace(
                portion,
                status=PortionStatus.WATERING,
                opening_attempted_at=portion.opening_attempted_at or now.isoformat(),
                watering_started_at=now.isoformat(),
            )
            return ProcessTransition(
                process=process,
                portions=(*portions[:portion_index], watering, *portions[portion_index + 1 :]),
                action=NoOp(reason="portion_started"),
            )
        if isinstance(event, ResumeDue):
            if process.next_portion_at is None:
                raise ValueError("process has no scheduled continuation")
            next_portion_at = _timestamp(process.next_portion_at)
            if now < next_portion_at:
                return ProcessTransition(
                    process=process,
                    portions=portions,
                    action=WaitUntil(when=next_portion_at, reason="soak_pause"),
                )
            tail_failure = self._remaining_tail_failure(
                process,
                now=now,
                pause_before_first=False,
            )
            if tail_failure is not None:
                return self._fail_transition(
                    process,
                    portions,
                    now=now,
                    reason=tail_failure,
                    safety_lock_required=False,
                )
            sequence = process.next_portion_sequence
            portion_id = f"{process.execution_id}:{sequence}"
            target = min(process.remaining_value, _policy(process).maximum_portion_target)
            remaining_runtime = (
                None
                if process.delivery_runtime_limit_seconds is None
                else max(
                    0.0,
                    process.delivery_runtime_limit_seconds - process.delivered_duration_seconds,
                )
            )
            portion = IrrigationPortionState(
                portion_id=portion_id,
                execution_id=process.execution_id,
                sequence=sequence,
                target_type=process.target_type,
                target_value=target,
                status=PortionStatus.PREPARED,
                prepared_at=now.isoformat(),
            )
            return ProcessTransition(
                process=replace(
                    process,
                    status=ProcessStatus.WATERING,
                    next_portion_at=None,
                    next_portion_sequence=sequence + 1,
                ),
                portions=(*portions, portion),
                action=PreparePortion(
                    portion_id=portion_id,
                    target_type=TargetType(process.target_type),
                    target_value=target,
                    hard_time_limit_seconds=remaining_runtime,
                ),
            )
        try:
            portion_index = next(
                index
                for index, portion in enumerate(portions)
                if portion.portion_id == event.portion_id
            )
        except StopIteration as err:
            raise ValueError("settled portion does not belong to the process") from err
        portion = portions[portion_index]
        settlement_result = event.result_override or (
            event.safety_violation
            or ("target_reached" if event.target_reached else "target_not_reached")
        )
        if (
            portion.status == PortionStatus.SETTLED
            and portion.delivered_liters == event.delivered_liters
            and portion.delivered_duration_seconds == event.delivered_duration_seconds
            and portion.measurement_quality == event.measurement_quality
            and portion.result == settlement_result
        ):
            return ProcessTransition(
                process=process,
                portions=portions,
                action=NoOp(reason="portion_already_settled"),
            )
        if portion.status == PortionStatus.SETTLED:
            return ProcessTransition(
                process=replace(
                    process,
                    status=ProcessStatus.FAILED,
                    ended_at=now.isoformat(),
                    result="conflicting_portion_settlement",
                ),
                portions=portions,
                action=FailClosed(
                    reason="conflicting_portion_settlement",
                    safety_lock_required=True,
                ),
            )
        accounted = self._account_settlement(
            process,
            portions,
            portion_index=portion_index,
            event=event,
            result=settlement_result,
            now=now,
        )
        if event.safety_violation is not None:
            return self._fail_transition(
                accounted.process,
                accounted.portions,
                now=now,
                reason=event.safety_violation,
                safety_lock_required=True,
            )
        portion_delivered_target = (
            event.delivered_liters
            if process.target_type == TargetType.VOLUME
            else event.delivered_duration_seconds
        )
        if (
            event.target_reached
            and not event.stopped
            and not process.cancellation_requested
            and portion_delivered_target < accounted.portion.target_value
        ):
            return self._fail_transition(
                accounted.process,
                accounted.portions,
                now=now,
                reason="portion_result_inconsistent",
                safety_lock_required=True,
            )
        if (
            process.delivery_runtime_limit_seconds is not None
            and accounted.process.delivered_duration_seconds
            > process.delivery_runtime_limit_seconds
        ):
            return self._fail_transition(
                accounted.process,
                accounted.portions,
                now=now,
                reason="delivery_runtime_exceeded",
                safety_lock_required=True,
            )
        if now > _timestamp(process.process_deadline_at):
            return self._fail_transition(
                accounted.process,
                accounted.portions,
                now=now,
                reason="process_deadline_exceeded",
                safety_lock_required=False,
            )
        if process.cancellation_requested or event.stopped:
            cancellation_reason = process.cancellation_reason or "stopped"
            cancelled = replace(
                accounted.process,
                status=ProcessStatus.CANCELLED,
                next_portion_at=None,
                ended_at=now.isoformat(),
                result=cancellation_reason,
            )
            return ProcessTransition(
                process=cancelled,
                portions=accounted.portions,
                action=CancelProcess(reason=cancellation_reason),
            )
        if not event.target_reached and not event.recovered:
            target_failure = (
                "volume_target_not_reached"
                if process.target_type == TargetType.VOLUME
                else "duration_target_not_reached"
            )
            return self._fail_transition(
                accounted.process,
                accounted.portions,
                now=now,
                reason=target_failure,
                safety_lock_required=True,
            )
        if accounted.process.remaining_value == 0.0:
            completed = replace(
                accounted.process,
                remaining_value=0.0,
                status=ProcessStatus.COMPLETED,
                next_portion_at=None,
                ended_at=now.isoformat(),
                result="target_reached",
            )
            return ProcessTransition(
                process=completed,
                portions=accounted.portions,
                action=CompleteProcess(result="target_reached"),
            )
        tail_failure = self._remaining_tail_failure(
            accounted.process,
            now=now,
            pause_before_first=True,
        )
        if tail_failure is not None:
            return self._fail_transition(
                accounted.process,
                accounted.portions,
                now=now,
                reason=tail_failure,
                safety_lock_required=False,
            )
        next_portion_at = now + timedelta(seconds=_policy(process).minimum_soak_seconds)
        updated_process = replace(
            accounted.process,
            status=ProcessStatus.SOAKING,
            next_portion_at=next_portion_at.isoformat(),
        )
        return ProcessTransition(
            process=updated_process,
            portions=accounted.portions,
            action=WaitUntil(when=next_portion_at, reason="soak_pause"),
        )
