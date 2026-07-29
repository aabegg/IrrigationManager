"""Version-2 runtime and durable models."""

import logging
import math
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import cast

from .water_balance import ZoneWaterBalanceState

_LOGGER = logging.getLogger(__name__)


def _number(value: object, *, default: float | None = None) -> float:
    """Read one persisted JSON number without accepting booleans."""
    if value is None and default is not None:
        return default
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Stored irrigation value is not numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("Stored irrigation value is not finite")
    return numeric


def _optional_number(data: dict[str, object], key: str) -> float | None:
    value = data.get(key)
    return None if value is None else _number(value)


def _optional_string(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Stored {key} is malformed")
    return value


def _required_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Stored {key} is malformed")
    return value


def _stored_string(data: dict[str, object], key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"Stored {key} is malformed")
    return value


def _string_tuple(data: dict[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Stored {key} is malformed")
    return tuple(value)


def _object_dict(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Stored {key} is malformed")
    return deepcopy(value)


@dataclass(frozen=True, slots=True)
class ManualIrrigationRequest:
    """Durable irrigation order with an immutable zone snapshot."""

    request_id: str
    sequence: int
    zone_id: str
    zone_subentry_id: str
    zone_name: str
    zone_valve: str
    main_valve: str | None
    target_type: str
    target_value: float
    remaining_value: float
    created_at: str
    expires_at: str
    requested_start_at: str | None = None
    status: str = "pending"
    source: str = "manual"
    automatic_window_end: str | None = None
    execution_id: str | None = None
    hard_time_limit_seconds: float | None = None
    delivery_runtime_limit_seconds: float | None = None
    operation_deadline_at: str | None = None
    resolved_inputs: dict[str, object] = field(default_factory=dict)
    revision: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ManualIrrigationRequest:
        """Deserialize one v2 irrigation order."""
        target_type = _required_string(data, "target_type")
        status = _required_string(data, "status") if "status" in data else "pending"
        source = _required_string(data, "source") if "source" in data else "manual"
        if target_type not in {"duration", "volume"}:
            raise ValueError("Stored irrigation target type is malformed")
        if status not in {"pending", "executing", "completed", "cancelled", "expired"}:
            raise ValueError("Stored irrigation order status is malformed")
        if source not in {"manual", "automatic", "calibration"}:
            raise ValueError("Stored irrigation order source is malformed")
        return cls(
            request_id=_required_string(data, "request_id"),
            sequence=int(_number(data.get("sequence"))),
            zone_id=_required_string(data, "zone_id"),
            zone_subentry_id=_required_string(data, "zone_subentry_id"),
            zone_name=_required_string(data, "zone_name"),
            zone_valve=_required_string(data, "zone_valve"),
            main_valve=_optional_string(data, "main_valve"),
            target_type=target_type,
            target_value=_number(data.get("target_value")),
            remaining_value=_number(data.get("remaining_value")),
            created_at=_required_string(data, "created_at"),
            expires_at=_required_string(data, "expires_at"),
            requested_start_at=_optional_string(data, "requested_start_at"),
            status=status,
            source=source,
            automatic_window_end=_optional_string(data, "automatic_window_end"),
            execution_id=_optional_string(data, "execution_id"),
            hard_time_limit_seconds=_optional_number(data, "hard_time_limit_seconds"),
            delivery_runtime_limit_seconds=_optional_number(data, "delivery_runtime_limit_seconds"),
            operation_deadline_at=_optional_string(data, "operation_deadline_at"),
            resolved_inputs=_object_dict(data, "resolved_inputs"),
            revision=int(_number(data.get("revision"), default=1)),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one irrigation order."""
        result = {item.name: getattr(self, item.name) for item in fields(self)}
        result["resolved_inputs"] = deepcopy(self.resolved_inputs)
        return result


AUTOMATIC_CANCELLATION_REASON_KEY = "automatic_cancellation_reason"


class AutomaticCancellationReason(StrEnum):
    """Persisted reason why an automatic irrigation order was cancelled."""

    AUTOMATION_RELEASE_REVOKED = "automation_release_revoked"
    CONFIGURATION_CHANGED = "configuration_changed"
    EXECUTION_FAILED = "execution_failed"
    PLANNING_REPLACED = "planning_replaced"
    RESTART_INTERRUPTED = "restart_interrupted"
    USER_REQUESTED = "user_requested"


REPLANNABLE_AUTOMATIC_CANCELLATION_REASONS = frozenset(
    {
        AutomaticCancellationReason.AUTOMATION_RELEASE_REVOKED,
        AutomaticCancellationReason.CONFIGURATION_CHANGED,
        AutomaticCancellationReason.PLANNING_REPLACED,
    }
)


def automatic_request_has_unclassified_legacy_cancellation(
    request: ManualIrrigationRequest,
) -> bool:
    """Return whether a legacy automatic cancellation has no trusted reason."""
    if request.source != "automatic" or request.status != "cancelled":
        return False
    raw_reason = request.resolved_inputs.get(AUTOMATIC_CANCELLATION_REASON_KEY)
    if not isinstance(raw_reason, str):
        return True
    try:
        AutomaticCancellationReason(raw_reason)
    except ValueError:
        return True
    return False


def automatic_request_is_terminal_tombstone(
    request: ManualIrrigationRequest,
) -> bool:
    """Return whether automatic planning must never recreate this request ID."""
    if request.source != "automatic":
        return False
    if request.status in {"completed", "expired"}:
        return True
    if request.status != "cancelled":
        return False
    raw_reason = request.resolved_inputs.get(AUTOMATIC_CANCELLATION_REASON_KEY)
    if not isinstance(raw_reason, str):
        return True
    try:
        reason = AutomaticCancellationReason(raw_reason)
    except ValueError:
        return True
    return reason not in REPLANNABLE_AUTOMATIC_CANCELLATION_REASONS


def _deduplicate_requests(
    requests: tuple[ManualIrrigationRequest, ...],
) -> tuple[ManualIrrigationRequest, ...]:
    """Keep one safety-conservative winner for every durable request ID."""

    def rank(request: ManualIrrigationRequest) -> tuple[int, int, int]:
        terminal_tombstone = request.status in {"completed", "expired"} or (
            request.status == "cancelled"
            and (request.source != "automatic" or automatic_request_is_terminal_tombstone(request))
        )
        lifecycle_rank = (
            3
            if request.status == "executing"
            else 2
            if terminal_tombstone
            else 1
            if request.status == "pending"
            else 0
        )
        return lifecycle_rank, request.sequence, request.revision

    winners: dict[str, tuple[int, ManualIrrigationRequest]] = {}
    for index, request in enumerate(requests):
        existing = winners.get(request.request_id)
        if existing is None or rank(request) > rank(existing[1]):
            winners[request.request_id] = index, request
    return tuple(request for _index, request in sorted(winners.values()))


@dataclass(frozen=True, slots=True)
class IrrigationExecutionState:
    """Durable lifecycle and measured result of one accepted order."""

    execution_id: str
    request_id: str
    zone_id: str
    target_type: str
    target_value: float
    remaining_value: float
    status: str
    created_at: str
    operation_deadline_at: str | None = None
    delivery_runtime_limit_seconds: float | None = None
    delivered_liters: float = 0.0
    delivered_duration_seconds: float = 0.0
    watering_started_at: str | None = None
    watering_ended_at: str | None = None
    ended_at: str | None = None
    result: str | None = None
    measurement_quality: str = "unknown"
    measurement_origin: str = "unknown"
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> IrrigationExecutionState:
        """Deserialize one v2 execution."""
        target_type = _required_string(data, "target_type")
        if target_type not in {"duration", "volume"}:
            raise ValueError("Stored irrigation execution target is malformed")
        return cls(
            execution_id=_required_string(data, "execution_id"),
            request_id=_required_string(data, "request_id"),
            zone_id=_required_string(data, "zone_id"),
            target_type=target_type,
            target_value=_number(data.get("target_value")),
            remaining_value=_number(data.get("remaining_value")),
            status=_required_string(data, "status"),
            created_at=_required_string(data, "created_at"),
            operation_deadline_at=_optional_string(data, "operation_deadline_at"),
            delivery_runtime_limit_seconds=_optional_number(data, "delivery_runtime_limit_seconds"),
            delivered_liters=_number(data.get("delivered_liters"), default=0.0),
            delivered_duration_seconds=_number(data.get("delivered_duration_seconds"), default=0.0),
            watering_started_at=_optional_string(data, "watering_started_at"),
            watering_ended_at=_optional_string(data, "watering_ended_at"),
            ended_at=_optional_string(data, "ended_at"),
            result=_optional_string(data, "result"),
            measurement_quality=_stored_string(data, "measurement_quality", "unknown"),
            measurement_origin=_stored_string(data, "measurement_origin", "unknown"),
            warnings=_string_tuple(data, "warnings"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one irrigation execution."""
        result = {item.name: getattr(self, item.name) for item in fields(self)}
        result["warnings"] = list(self.warnings)
        return result


@dataclass(frozen=True, slots=True)
class WaterConsumptionRecord:
    """One measured contribution used to derive period totals."""

    recorded_at: str
    amount_liters: float
    zone_id: str | None
    source: str
    quality: str
    request_id: str | None = None
    execution_id: str | None = None
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> WaterConsumptionRecord:
        """Deserialize one measured-water history record."""
        return cls(
            recorded_at=_required_string(data, "recorded_at"),
            amount_liters=_number(data.get("amount_liters")),
            zone_id=_optional_string(data, "zone_id"),
            source=_required_string(data, "source"),
            quality=_required_string(data, "quality"),
            request_id=_optional_string(data, "request_id"),
            execution_id=_optional_string(data, "execution_id"),
            warnings=_string_tuple(data, "warnings"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one measured-water history record."""
        return {
            "recorded_at": self.recorded_at,
            "amount_liters": self.amount_liters,
            "zone_id": self.zone_id,
            "source": self.source,
            "quality": self.quality,
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class InstallationSnapshot:
    """Current published state of one irrigation installation."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    zone_last_delivered_liters: dict[str, float] = field(default_factory=dict)
    zone_last_duration_seconds: dict[str, float] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    unassigned_available_liters: float = 0.0
    unassigned_measurement_quality: str = "unknown"
    unassigned_measurement_origin: str = "unknown"
    water_period_liters: dict[str, float] = field(default_factory=dict)
    zone_water_period_liters: dict[str, dict[str, float]] = field(default_factory=dict)
    water_period_quality: str = "complete"
    physical_meter_liters: float | None = None
    meter_measurement_quality: str = "unknown"
    meter_resolution_liters: float | None = None
    status: str = "idle"
    active_zone_id: str | None = None
    emergency_stop: bool = False
    installation_safety_lock: str | None = None
    installation_safety_lock_at: str | None = None
    pending_request_count: int = 0
    active_request_id: str | None = None
    active_execution_id: str | None = None
    automation_enabled: bool = True
    operation_enabled: bool = True
    zone_operation_enabled: dict[str, bool] = field(default_factory=dict)
    zone_automation_enabled: dict[str, bool] = field(default_factory=dict)
    next_zone_id: str | None = None
    next_start_at: str | None = None
    zone_next_irrigation: dict[str, str] = field(default_factory=dict)
    zone_status: dict[str, str] = field(default_factory=dict)
    recent_history: tuple[dict[str, object], ...] = ()
    runtime_today_seconds: float = 0.0
    runtime_month_seconds: float = 0.0
    zone_runtime_today_seconds: dict[str, float] = field(default_factory=dict)
    zone_runtime_month_seconds: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActiveExecutionState:
    """Minimum durable state needed to recover an interrupted execution."""

    zone_id: str
    zone_valve: str
    main_valve: str | None
    meter_raw_baseline_liters: float | None
    prepared_at: str
    watering_started_at: str | None
    requested_duration_seconds: float
    watering_ended_at: str | None = None
    requested_amount_liters: float | None = None
    hard_time_limit_seconds: float | None = None
    delivery_deadline_at: str | None = None
    operation_deadline_at: str | None = None
    zone_opening_at: str | None = None
    request_id: str | None = None
    execution_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ActiveExecutionState:
        """Deserialize one v2 active execution checkpoint."""
        return cls(
            zone_id=_required_string(data, "zone_id"),
            zone_valve=_required_string(data, "zone_valve"),
            main_valve=_optional_string(data, "main_valve"),
            meter_raw_baseline_liters=_optional_number(data, "meter_raw_baseline_liters"),
            prepared_at=_required_string(data, "prepared_at"),
            watering_started_at=_optional_string(data, "watering_started_at"),
            requested_duration_seconds=_number(data.get("requested_duration_seconds")),
            watering_ended_at=_optional_string(data, "watering_ended_at"),
            requested_amount_liters=_optional_number(data, "requested_amount_liters"),
            hard_time_limit_seconds=_optional_number(data, "hard_time_limit_seconds"),
            delivery_deadline_at=_optional_string(data, "delivery_deadline_at"),
            operation_deadline_at=_optional_string(data, "operation_deadline_at"),
            zone_opening_at=_optional_string(data, "zone_opening_at"),
            request_id=_optional_string(data, "request_id"),
            execution_id=_optional_string(data, "execution_id"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one active execution checkpoint."""
        return {item.name: getattr(self, item.name) for item in fields(self)}


@dataclass(frozen=True, slots=True)
class CalibrationProposal:
    """Measured flow-profile values awaiting an explicit decision."""

    proposal_id: str
    zone_id: str
    zone_subentry_id: str
    zone_valve: str
    zone_config_hash: str
    created_at: str
    delivered_liters: float
    duration_seconds: float
    average_flow_l_min: float
    opening_latency_seconds: float
    post_run_liters: float
    proposed_min_flow_l_min: float
    proposed_max_flow_l_min: float
    status: str = "pending"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CalibrationProposal:
        """Deserialize one calibration proposal."""
        return cls(
            proposal_id=_required_string(data, "proposal_id"),
            zone_id=_required_string(data, "zone_id"),
            zone_subentry_id=_required_string(data, "zone_subentry_id"),
            zone_valve=_required_string(data, "zone_valve"),
            zone_config_hash=_required_string(data, "zone_config_hash"),
            created_at=_required_string(data, "created_at"),
            delivered_liters=_number(data.get("delivered_liters")),
            duration_seconds=_number(data.get("duration_seconds")),
            average_flow_l_min=_number(data.get("average_flow_l_min")),
            opening_latency_seconds=_number(data.get("opening_latency_seconds")),
            post_run_liters=_number(data.get("post_run_liters")),
            proposed_min_flow_l_min=_number(data.get("proposed_min_flow_l_min")),
            proposed_max_flow_l_min=_number(data.get("proposed_max_flow_l_min")),
            status=_required_string(data, "status") if "status" in data else "pending",
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one calibration proposal."""
        return {item.name: getattr(self, item.name) for item in fields(self)}


@dataclass(frozen=True, slots=True)
class MeterCorrectionRecord:
    """Audited correction of the future-facing physical meter total."""

    previous_total_liters: float
    new_total_liters: float
    difference_liters: float
    corrected_at: str
    reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MeterCorrectionRecord:
        """Deserialize one physical-meter correction."""
        return cls(
            previous_total_liters=_number(data.get("previous_total_liters")),
            new_total_liters=_number(data.get("new_total_liters")),
            difference_liters=_number(data.get("difference_liters")),
            corrected_at=_required_string(data, "corrected_at"),
            reason=_optional_string(data, "reason"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one physical-meter correction."""
        return {item.name: getattr(self, item.name) for item in fields(self)}


class DispatchReason(StrEnum):
    """Stable persisted vocabulary for planning and dispatcher transitions."""

    WAITING_FOR_START = "waiting_for_start"
    READY = "ready"
    OPERATION_DISABLED = "operation_disabled"
    ZONE_DISABLED = "zone_disabled"
    AUTOMATION_DISABLED = "automation_disabled"
    ZONE_AUTOMATION_DISABLED = "zone_automation_disabled"
    SAFETY_LOCK = "safety_lock"
    EMERGENCY_STOP = "emergency_stop"
    RECONFIGURATION_REQUIRED = "reconfiguration_required"
    CONFIG_RELOAD_PENDING = "config_reload_pending"
    AUTOMATIC_PLANNING_IN_PROGRESS = "automatic_planning_in_progress"
    ACTUATOR_SNAPSHOT_MISMATCH = "actuator_snapshot_mismatch"
    WINDOW_NO_LONGER_FITS = "window_no_longer_fits"
    EXPIRED = "expired"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STARTUP = "startup"
    CLEAN_SHUTDOWN = "clean_shutdown"
    CONFIG_RELOAD = "config_reload"
    UNCLEAN_RESTART = "unclean_restart"
    DISPATCHER_ERROR = "dispatcher_error"
    AUTOMATIC_PLANNING_ERROR = "automatic_planning_error"


class PlanningRejectionReason(StrEnum):
    """Closed vocabulary for automatic orders rejected during planning."""

    SEASONAL_TARGET_DOES_NOT_FIT = "seasonal_target_does_not_fit"
    WATER_DEFICIT_BELOW_THRESHOLD = "water_deficit_below_threshold"
    WATER_BALANCE_TARGET_DOES_NOT_FIT = "water_balance_target_does_not_fit"


@dataclass(frozen=True, slots=True)
class PlanningRejection:
    """Current reason why one expected automatic order could not be planned."""

    request_id: str
    zone_id: str
    reason: PlanningRejectionReason

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> PlanningRejection:
        """Deserialize one current planning rejection."""
        return cls(
            request_id=_required_string(data, "request_id"),
            zone_id=_required_string(data, "zone_id"),
            reason=PlanningRejectionReason(_required_string(data, "reason")),
        )

    def as_dict(self) -> dict[str, str]:
        """Return a diagnostics-safe representation."""
        return {
            "request_id": self.request_id,
            "zone_id": self.zone_id,
            "reason": self.reason.value,
        }


@dataclass(frozen=True, slots=True)
class DispatcherDiagnosticEntry:
    """One durable dispatcher decision transition."""

    recorded_at: str
    request_id: str | None
    zone_id: str | None
    old_reason: DispatchReason | None
    new_reason: DispatchReason
    releases: dict[str, bool] = field(default_factory=dict)
    locks: dict[str, str | bool] = field(default_factory=dict)
    next_wake_at: str | None = None
    error_class: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DispatcherDiagnosticEntry:
        """Deserialize one optional diagnostic transition."""
        old_reason = _optional_string(data, "old_reason")
        return cls(
            recorded_at=_required_string(data, "recorded_at"),
            request_id=_optional_string(data, "request_id"),
            zone_id=_optional_string(data, "zone_id"),
            old_reason=DispatchReason(old_reason) if old_reason is not None else None,
            new_reason=DispatchReason(_required_string(data, "new_reason")),
            releases=StoredInstallationState._bool_dict(data, "releases"),
            locks=cls._lock_dict(data),
            next_wake_at=_optional_string(data, "next_wake_at"),
            error_class=_optional_string(data, "error_class"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one diagnostic transition."""
        return {
            "recorded_at": self.recorded_at,
            "request_id": self.request_id,
            "zone_id": self.zone_id,
            "old_reason": self.old_reason,
            "new_reason": self.new_reason,
            "releases": dict(self.releases),
            "locks": dict(self.locks),
            "next_wake_at": self.next_wake_at,
            "error_class": self.error_class,
        }

    @staticmethod
    def _lock_dict(data: dict[str, object]) -> dict[str, str | bool]:
        value = data.get("locks", {})
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str | bool) for key, item in value.items()
        ):
            raise ValueError("Stored dispatcher locks are malformed")
        return cast(dict[str, str | bool], value)


@dataclass(frozen=True, slots=True)
class DispatcherDiagnosticState:
    """Current durable dispatcher and integration lifecycle evidence."""

    current_reason: DispatchReason
    current_request_id: str | None
    current_zone_id: str | None
    blocked_since: str | None
    next_wake_at: str | None
    boot_id: str
    boot_started_at: str
    clean_shutdown: bool
    last_error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DispatcherDiagnosticState:
        """Deserialize current dispatcher evidence."""
        clean_shutdown = data.get("clean_shutdown")
        if not isinstance(clean_shutdown, bool):
            raise ValueError("Stored dispatcher clean-shutdown flag is malformed")
        return cls(
            current_reason=DispatchReason(_required_string(data, "current_reason")),
            current_request_id=_optional_string(data, "current_request_id"),
            current_zone_id=_optional_string(data, "current_zone_id"),
            blocked_since=_optional_string(data, "blocked_since"),
            next_wake_at=_optional_string(data, "next_wake_at"),
            boot_id=_required_string(data, "boot_id"),
            boot_started_at=_required_string(data, "boot_started_at"),
            clean_shutdown=clean_shutdown,
            last_error=_optional_string(data, "last_error"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize current dispatcher evidence."""
        return {item.name: getattr(self, item.name) for item in fields(self)}


@dataclass(frozen=True, slots=True)
class StoredInstallationState:
    """Current version-2 state persisted independently of entities."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    zone_last_delivered_liters: dict[str, float] = field(default_factory=dict)
    zone_last_duration_seconds: dict[str, float] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    unassigned_available_liters: float = 0.0
    unassigned_measurement_quality: str = "unknown"
    unassigned_measurement_origin: str = "unknown"
    idle_meter_raw_baseline_liters: float | None = None
    emergency_stop: bool = False
    installation_safety_lock: str | None = None
    installation_safety_lock_at: str | None = None
    calibration_proposal: CalibrationProposal | None = None
    active_execution: ActiveExecutionState | None = None
    manual_requests: tuple[ManualIrrigationRequest, ...] = ()
    irrigation_executions: tuple[IrrigationExecutionState, ...] = ()
    next_request_sequence: int = 1
    meter_accumulated_liters: float | None = None
    meter_last_raw_liters: float | None = None
    meter_correction_liters: float = 0.0
    meter_reset_count: int = 0
    meter_source_entity_id: str | None = None
    meter_source_liters_per_count: float | None = None
    meter_correction_history: tuple[MeterCorrectionRecord, ...] = ()
    water_consumption_history: tuple[WaterConsumptionRecord, ...] = ()
    water_history_incomplete: bool = False
    operation_enabled: bool | None = None
    automation_enabled: bool | None = None
    zone_operation_enabled: dict[str, bool] = field(default_factory=dict)
    zone_automation_enabled: dict[str, bool] = field(default_factory=dict)
    planning_rejections: tuple[PlanningRejection, ...] = ()
    dispatcher_diagnostic: DispatcherDiagnosticState | None = None
    dispatcher_diagnostic_history: tuple[DispatcherDiagnosticEntry, ...] = ()
    zone_water_balances: dict[str, ZoneWaterBalanceState] = field(default_factory=dict)

    _float = staticmethod(_number)

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> StoredInstallationState:
        """Deserialize current storage data with strict field validation."""
        if data is None:
            return cls()
        raw_requests = data.get("manual_requests", [])
        raw_executions = data.get("irrigation_executions", [])
        raw_history = data.get("water_consumption_history", [])
        raw_corrections = data.get("meter_correction_history", [])
        if not all(
            isinstance(value, list) and all(isinstance(item, dict) for item in value)
            for value in (raw_requests, raw_executions, raw_history, raw_corrections)
        ):
            raise ValueError("Stored irrigation records are malformed")
        raw_active = data.get("active_execution")
        raw_proposal = data.get("calibration_proposal")
        if raw_active is not None and not isinstance(raw_active, dict):
            raise ValueError("Stored active execution is malformed")
        if raw_proposal is not None and not isinstance(raw_proposal, dict):
            raise ValueError("Stored calibration proposal is malformed")
        emergency_stop = data.get("emergency_stop", False)
        history_incomplete = data.get("water_history_incomplete", False)
        if not isinstance(emergency_stop, bool) or not isinstance(history_incomplete, bool):
            raise ValueError("Stored irrigation flags are malformed")
        reset_count = data.get("meter_reset_count", 0)
        if isinstance(reset_count, bool) or not isinstance(reset_count, int):
            raise ValueError("Stored meter reset count is malformed")
        next_sequence = data.get("next_request_sequence", 1)
        if isinstance(next_sequence, bool) or not isinstance(next_sequence, int):
            raise ValueError("Stored request sequence is malformed")
        installation_lock = _optional_string(data, "installation_safety_lock")
        if emergency_stop and installation_lock is None:
            installation_lock = "Emergency stop activated"
        dispatcher_diagnostic = None
        raw_dispatcher_diagnostic = data.get("dispatcher_diagnostic")
        if isinstance(raw_dispatcher_diagnostic, dict):
            with suppress(TypeError, ValueError):
                dispatcher_diagnostic = DispatcherDiagnosticState.from_dict(
                    raw_dispatcher_diagnostic
                )
        dispatcher_history: list[DispatcherDiagnosticEntry] = []
        raw_dispatcher_history = data.get("dispatcher_diagnostic_history", [])
        if isinstance(raw_dispatcher_history, list):
            for item in raw_dispatcher_history:
                if not isinstance(item, dict):
                    continue
                try:
                    dispatcher_history.append(DispatcherDiagnosticEntry.from_dict(item))
                except TypeError, ValueError:
                    continue
        planning_rejections: list[PlanningRejection] = []
        raw_planning_rejections = data.get("planning_rejections", [])
        if isinstance(raw_planning_rejections, list):
            for item in raw_planning_rejections:
                if not isinstance(item, dict):
                    continue
                try:
                    planning_rejections.append(PlanningRejection.from_dict(item))
                except TypeError, ValueError:
                    continue
        raw_zone_balances = data.get("zone_water_balances", {})
        if not isinstance(raw_zone_balances, dict) or not all(
            isinstance(zone_id, str) and isinstance(value, dict)
            for zone_id, value in raw_zone_balances.items()
        ):
            raise ValueError("Stored zone water balances are malformed")
        zone_water_balances: dict[str, ZoneWaterBalanceState] = {}
        for zone_id, value in cast(dict[str, dict[str, object]], raw_zone_balances).items():
            try:
                zone_water_balances[zone_id] = ZoneWaterBalanceState.from_dict(value)
            except TypeError, ValueError:
                _LOGGER.warning(
                    "Ignoring malformed persisted water balance for zone %s",
                    zone_id,
                    exc_info=True,
                )
                continue
        requests = tuple(
            ManualIrrigationRequest.from_dict(item)
            for item in cast(list[dict[str, object]], raw_requests)
        )
        deduplicated_requests = _deduplicate_requests(requests)
        if len(deduplicated_requests) != len(requests):
            _LOGGER.warning(
                "Discarded %d duplicate persisted irrigation request record(s)",
                len(requests) - len(deduplicated_requests),
            )
        return cls(
            installation_total_liters=_number(data.get("installation_total_liters"), default=0.0),
            zone_totals_liters=cls._number_dict(data, "zone_totals_liters"),
            zone_measurement_quality=cls._string_dict(data, "zone_measurement_quality"),
            zone_last_delivered_liters=cls._number_dict(data, "zone_last_delivered_liters"),
            zone_last_duration_seconds=cls._number_dict(data, "zone_last_duration_seconds"),
            unassigned_total_liters=_number(data.get("unassigned_total_liters"), default=0.0),
            unassigned_available_liters=_number(
                data.get("unassigned_available_liters"), default=0.0
            ),
            unassigned_measurement_quality=_stored_string(
                data, "unassigned_measurement_quality", "unknown"
            ),
            unassigned_measurement_origin=_stored_string(
                data, "unassigned_measurement_origin", "unknown"
            ),
            idle_meter_raw_baseline_liters=_optional_number(data, "idle_meter_raw_baseline_liters"),
            emergency_stop=emergency_stop,
            installation_safety_lock=installation_lock,
            installation_safety_lock_at=_optional_string(data, "installation_safety_lock_at"),
            calibration_proposal=(
                CalibrationProposal.from_dict(raw_proposal)
                if isinstance(raw_proposal, dict)
                else None
            ),
            active_execution=(
                ActiveExecutionState.from_dict(raw_active) if isinstance(raw_active, dict) else None
            ),
            manual_requests=deduplicated_requests,
            irrigation_executions=tuple(
                IrrigationExecutionState.from_dict(item)
                for item in cast(list[dict[str, object]], raw_executions)
            ),
            next_request_sequence=next_sequence,
            meter_accumulated_liters=_optional_number(data, "meter_accumulated_liters"),
            meter_last_raw_liters=_optional_number(data, "meter_last_raw_liters"),
            meter_correction_liters=_number(data.get("meter_correction_liters"), default=0.0),
            meter_reset_count=reset_count,
            meter_source_entity_id=_optional_string(data, "meter_source_entity_id"),
            meter_source_liters_per_count=_optional_number(data, "meter_source_liters_per_count"),
            meter_correction_history=tuple(
                MeterCorrectionRecord.from_dict(item)
                for item in cast(list[dict[str, object]], raw_corrections)
            ),
            water_consumption_history=tuple(
                WaterConsumptionRecord.from_dict(item)
                for item in cast(list[dict[str, object]], raw_history)
            ),
            water_history_incomplete=history_incomplete,
            operation_enabled=cls._optional_bool(data, "operation_enabled"),
            automation_enabled=cls._optional_bool(data, "automation_enabled"),
            zone_operation_enabled=cls._bool_dict(data, "zone_operation_enabled"),
            zone_automation_enabled=cls._bool_dict(data, "zone_automation_enabled"),
            planning_rejections=tuple(planning_rejections),
            dispatcher_diagnostic=dispatcher_diagnostic,
            dispatcher_diagnostic_history=tuple(dispatcher_history[-100:]),
            zone_water_balances=zone_water_balances,
        )

    @staticmethod
    def _mapping(data: dict[str, object], key: str) -> dict[object, object]:
        value = data.get(key, {})
        if not isinstance(value, dict):
            raise ValueError(f"Stored {key} is malformed")
        return value

    @classmethod
    def _number_dict(cls, data: dict[str, object], key: str) -> dict[str, float]:
        return {str(name): _number(value) for name, value in cls._mapping(data, key).items()}

    @classmethod
    def _string_dict(cls, data: dict[str, object], key: str) -> dict[str, str]:
        value = cls._mapping(data, key)
        if not all(isinstance(name, str) and isinstance(item, str) for name, item in value.items()):
            raise ValueError(f"Stored {key} is malformed")
        return cast(dict[str, str], value)

    @classmethod
    def _bool_dict(cls, data: dict[str, object], key: str) -> dict[str, bool]:
        value = cls._mapping(data, key)
        if not all(
            isinstance(name, str) and isinstance(item, bool) for name, item in value.items()
        ):
            raise ValueError(f"Stored {key} is malformed")
        return cast(dict[str, bool], value)

    @staticmethod
    def _optional_bool(data: dict[str, object], key: str) -> bool | None:
        value = data.get(key)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"Stored {key} is malformed")
        return value

    def as_dict(self) -> dict[str, object]:
        """Serialize current state to JSON-compatible storage data."""
        return {
            "installation_total_liters": self.installation_total_liters,
            "zone_totals_liters": dict(self.zone_totals_liters),
            "zone_measurement_quality": dict(self.zone_measurement_quality),
            "zone_last_delivered_liters": dict(self.zone_last_delivered_liters),
            "zone_last_duration_seconds": dict(self.zone_last_duration_seconds),
            "unassigned_total_liters": self.unassigned_total_liters,
            "unassigned_available_liters": self.unassigned_available_liters,
            "unassigned_measurement_quality": self.unassigned_measurement_quality,
            "unassigned_measurement_origin": self.unassigned_measurement_origin,
            "idle_meter_raw_baseline_liters": self.idle_meter_raw_baseline_liters,
            "emergency_stop": self.emergency_stop,
            "installation_safety_lock": self.installation_safety_lock,
            "installation_safety_lock_at": self.installation_safety_lock_at,
            "calibration_proposal": (
                self.calibration_proposal.as_dict()
                if self.calibration_proposal is not None
                else None
            ),
            "active_execution": (
                self.active_execution.as_dict() if self.active_execution is not None else None
            ),
            "manual_requests": [request.as_dict() for request in self.manual_requests],
            "irrigation_executions": [
                execution.as_dict() for execution in self.irrigation_executions
            ],
            "next_request_sequence": self.next_request_sequence,
            "meter_accumulated_liters": self.meter_accumulated_liters,
            "meter_last_raw_liters": self.meter_last_raw_liters,
            "meter_correction_liters": self.meter_correction_liters,
            "meter_reset_count": self.meter_reset_count,
            "meter_source_entity_id": self.meter_source_entity_id,
            "meter_source_liters_per_count": self.meter_source_liters_per_count,
            "meter_correction_history": [
                record.as_dict() for record in self.meter_correction_history
            ],
            "water_consumption_history": [
                record.as_dict() for record in self.water_consumption_history
            ],
            "water_history_incomplete": self.water_history_incomplete,
            "operation_enabled": self.operation_enabled,
            "automation_enabled": self.automation_enabled,
            "zone_operation_enabled": dict(self.zone_operation_enabled),
            "zone_automation_enabled": dict(self.zone_automation_enabled),
            "planning_rejections": [rejection.as_dict() for rejection in self.planning_rejections],
            "dispatcher_diagnostic": (
                self.dispatcher_diagnostic.as_dict()
                if self.dispatcher_diagnostic is not None
                else None
            ),
            "dispatcher_diagnostic_history": [
                event.as_dict() for event in self.dispatcher_diagnostic_history[-100:]
            ],
            "zone_water_balances": {
                zone_id: balance.as_dict() for zone_id, balance in self.zone_water_balances.items()
            },
        }
