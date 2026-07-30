"""Pure atomic persistence transitions shared by irrigation execution paths."""

import math
from dataclasses import replace

from .models import (
    ActiveExecutionState,
    IrrigationExecutionState,
    IrrigationPortionState,
    ManualIrrigationRequest,
    StoredInstallationState,
    WaterConsumptionRecord,
)


def apply_safety_lock(
    state: StoredInstallationState,
    *,
    reason: str,
    recorded_at: str,
) -> StoredInstallationState:
    """Apply one installation-wide safety lock without changing other state."""
    if not reason or not recorded_at:
        raise ValueError("Safety lock evidence must not be empty")
    return replace(
        state,
        installation_safety_lock=reason,
        installation_safety_lock_at=recorded_at,
    )


def prepare_execution_state(
    state: StoredInstallationState,
    *,
    request: ManualIrrigationRequest,
    execution: IrrigationExecutionState,
    active: ActiveExecutionState,
    portion: IrrigationPortionState | None = None,
) -> StoredInstallationState:
    """Return the complete durable checkpoint required before actuation."""
    matching_requests = tuple(
        item for item in state.manual_requests if item.request_id == request.request_id
    )
    if len(matching_requests) != 1:
        raise ValueError("Prepared request does not have one durable predecessor")
    if state.active_execution is not None:
        raise ValueError("Prepared execution cannot replace an active hardware checkpoint")
    if (
        request.status != "executing"
        or execution.status != "watering"
        or request.execution_id != execution.execution_id
        or active.execution_id != execution.execution_id
        or execution.request_id != request.request_id
        or active.request_id != request.request_id
        or execution.zone_id != request.zone_id
        or active.zone_id != request.zone_id
        or execution.target_type != request.target_type
        or execution.portion_policy != request.portion_policy
    ):
        raise ValueError("Prepared execution records are inconsistent")
    if portion is None:
        if (
            request.portion_policy is not None
            or active.portion_id is not None
            or active.portion_sequence is not None
        ):
            raise ValueError("Prepared legacy execution has partial-irrigation records")
    else:
        policy = request.portion_policy
        same_execution_portions = tuple(
            item
            for item in state.irrigation_portions
            if item.execution_id == execution.execution_id
        )
        matching_portions = tuple(
            item for item in same_execution_portions if item.portion_id == portion.portion_id
        )
        other_open_portions = tuple(
            item
            for item in same_execution_portions
            if item.portion_id != portion.portion_id and item.status in {"prepared", "watering"}
        )
        duplicate_sequence = any(
            item.portion_id != portion.portion_id and item.sequence == portion.sequence
            for item in same_execution_portions
        )
        if (
            policy is None
            or policy.target_type != execution.target_type
            or portion.status != "prepared"
            or portion.execution_id != execution.execution_id
            or portion.target_type != execution.target_type
            or portion.target_value > policy.maximum_portion_target
            or portion.target_value > execution.remaining_value
            or portion.portion_id != f"{execution.execution_id}:{portion.sequence}"
            or execution.next_portion_sequence != portion.sequence + 1
            or active.portion_id != portion.portion_id
            or active.portion_sequence != portion.sequence
            or len(matching_portions) > 1
            or (matching_portions and matching_portions[0].status not in {"prepared"})
            or other_open_portions
            or duplicate_sequence
        ):
            raise ValueError("Prepared portion checkpoint is inconsistent")
    requests = tuple(
        request if item.request_id == request.request_id else item for item in state.manual_requests
    )
    existing_execution = any(
        item.execution_id == execution.execution_id for item in state.irrigation_executions
    )
    executions = tuple(
        execution if item.execution_id == execution.execution_id else item
        for item in state.irrigation_executions
    )
    if not existing_execution:
        executions = (*executions, execution)
    portions = state.irrigation_portions
    if portion is not None:
        existing_portion = any(item.portion_id == portion.portion_id for item in portions)
        portions = tuple(
            portion if item.portion_id == portion.portion_id else item for item in portions
        )
        if not existing_portion:
            portions = (*portions, portion)
    return replace(
        state,
        manual_requests=requests,
        irrigation_executions=executions,
        irrigation_portions=portions,
        active_execution=active,
    )


def settle_execution_state(
    state: StoredInstallationState,
    *,
    request: ManualIrrigationRequest,
    execution: IrrigationExecutionState,
    portion: IrrigationPortionState | None = None,
    delivered_liters: float,
    delivered_duration_seconds: float,
    recorded_at: str,
    safety_lock_reason: str | None = None,
) -> StoredInstallationState:
    """Atomically settle known delivery into aggregate and durable evidence."""
    if any(
        isinstance(value, bool) or not math.isfinite(value) or value < 0
        for value in (delivered_liters, delivered_duration_seconds)
    ):
        raise ValueError("Settlement delivery values are malformed")
    active = state.active_execution
    previous_request = next(
        (item for item in state.manual_requests if item.request_id == request.request_id),
        None,
    )
    previous_execution = next(
        (
            item
            for item in state.irrigation_executions
            if item.execution_id == execution.execution_id
        ),
        None,
    )
    previous_portion = (
        next(
            (item for item in state.irrigation_portions if item.portion_id == portion.portion_id),
            None,
        )
        if portion is not None
        else None
    )
    matching_consumptions = (
        tuple(
            record
            for record in state.water_consumption_history
            if record.execution_id == execution.execution_id
            and record.portion_id == portion.portion_id
        )
        if portion is not None
        else ()
    )
    if (
        portion is not None
        and active is None
        and previous_request == request
        and previous_execution == execution
        and previous_portion == portion
        and portion.status == "settled"
        and delivered_liters == portion.delivered_liters
        and delivered_duration_seconds == portion.delivered_duration_seconds
        and (
            not matching_consumptions
            if delivered_liters == 0.0
            else len(matching_consumptions) == 1
            and matching_consumptions[0].amount_liters == delivered_liters
            and matching_consumptions[0].zone_id == request.zone_id
            and matching_consumptions[0].source == request.source
            and matching_consumptions[0].quality == execution.measurement_quality
            and matching_consumptions[0].request_id == request.request_id
            and matching_consumptions[0].execution_id == execution.execution_id
            and matching_consumptions[0].portion_id == portion.portion_id
            and matching_consumptions[0].warnings == ()
        )
    ):
        return state
    if (
        active is None
        or previous_request is None
        or previous_execution is None
        or active.request_id != request.request_id
        or active.execution_id != execution.execution_id
        or execution.request_id != request.request_id
        or execution.zone_id != request.zone_id
        or execution.delivered_liters != previous_execution.delivered_liters + delivered_liters
        or execution.delivered_duration_seconds
        != previous_execution.delivered_duration_seconds + delivered_duration_seconds
    ):
        raise ValueError("Settlement records are inconsistent")
    if portion is None:
        if active.portion_id is not None or active.portion_sequence is not None:
            raise ValueError("Legacy settlement has a partial-irrigation checkpoint")
    elif (
        previous_portion is None
        or previous_portion.status not in {"prepared", "watering"}
        or portion.status != "settled"
        or portion.execution_id != execution.execution_id
        or portion.target_type != execution.target_type
        or portion.delivered_liters != delivered_liters
        or portion.delivered_duration_seconds != delivered_duration_seconds
        or active.portion_id != portion.portion_id
        or active.portion_sequence != portion.sequence
    ):
        raise ValueError("Portion settlement records are inconsistent")
    requests = tuple(
        request if item.request_id == request.request_id else item for item in state.manual_requests
    )
    executions = tuple(
        execution if item.execution_id == execution.execution_id else item
        for item in state.irrigation_executions
    )
    portions = tuple(
        portion if portion is not None and item.portion_id == portion.portion_id else item
        for item in state.irrigation_portions
    )
    zone_totals = dict(state.zone_totals_liters)
    zone_totals[request.zone_id] = zone_totals.get(request.zone_id, 0.0) + delivered_liters
    qualities = dict(state.zone_measurement_quality)
    qualities[request.zone_id] = execution.measurement_quality
    last_liters = dict(state.zone_last_delivered_liters)
    last_liters[request.zone_id] = delivered_liters
    last_duration = dict(state.zone_last_duration_seconds)
    last_duration[request.zone_id] = delivered_duration_seconds
    history = state.water_consumption_history
    if delivered_liters > 0:
        history = (
            *history,
            WaterConsumptionRecord(
                recorded_at=recorded_at,
                amount_liters=delivered_liters,
                zone_id=request.zone_id,
                source=request.source,
                quality=execution.measurement_quality,
                request_id=request.request_id,
                execution_id=execution.execution_id,
                portion_id=portion.portion_id if portion is not None else None,
            ),
        )[-50_000:]
    settled = replace(
        state,
        installation_total_liters=state.installation_total_liters + delivered_liters,
        zone_totals_liters=zone_totals,
        zone_measurement_quality=qualities,
        zone_last_delivered_liters=last_liters,
        zone_last_duration_seconds=last_duration,
        manual_requests=requests,
        irrigation_executions=executions,
        irrigation_portions=portions,
        active_execution=None,
        water_consumption_history=history,
    )
    return (
        settled
        if safety_lock_reason is None
        else apply_safety_lock(
            settled,
            reason=safety_lock_reason,
            recorded_at=recorded_at,
        )
    )
