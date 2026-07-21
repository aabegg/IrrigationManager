"""Deterministic planning of irrigation orders."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .models import IrrigationExecutionState, ManualIrrigationRequest


class WateringMode(StrEnum):
    """Decide whether calculated demand or a guaranteed minimum applies."""

    DEMAND = "demand"
    MINIMUM = "minimum"


@dataclass(frozen=True, slots=True)
class ZonePlanningInput:
    """Validated zone state at one planning instant."""

    zone_id: str
    mode: WateringMode
    calculated_target_liters: float
    minimum_target_liters: float
    maximum_target_liters: float
    minimum_effective_liters: float
    flow_liters_per_minute: float
    relative_need: float
    priority: int
    window_end: datetime
    enabled: bool = True
    blocked: bool = False


@dataclass(frozen=True, slots=True)
class PlannedOrder:
    """One executable zone target produced by the scheduler."""

    zone_id: str
    target_liters: float
    expected_duration_seconds: float
    is_partial: bool
    window_end: datetime


def plan_orders(*, now: datetime, zones: Iterable[ZonePlanningInput]) -> list[PlannedOrder]:
    """Return executable orders in deterministic priority order."""
    candidates: list[tuple[ZonePlanningInput, PlannedOrder]] = []
    for zone in zones:
        order = _plan_zone(now=now, zone=zone)
        if order is not None:
            candidates.append((zone, order))

    candidates.sort(
        key=lambda candidate: (
            candidate[0].window_end,
            -candidate[0].relative_need,
            -candidate[0].priority,
            candidate[0].zone_id,
        )
    )
    return [order for _, order in candidates]


def _plan_zone(*, now: datetime, zone: ZonePlanningInput) -> PlannedOrder | None:
    """Create one order if the zone can deliver a useful target now."""
    if not zone.enabled or zone.blocked or zone.flow_liters_per_minute <= 0:
        return None

    target_liters = max(0.0, zone.calculated_target_liters)
    if zone.mode is WateringMode.MINIMUM:
        target_liters = max(target_liters, zone.minimum_target_liters)
    target_liters = min(target_liters, zone.maximum_target_liters)
    if target_liters <= 0:
        return None

    remaining_minutes = max(0.0, (zone.window_end - now).total_seconds() / 60)
    available_liters = remaining_minutes * zone.flow_liters_per_minute
    planned_liters = min(target_liters, available_liters)
    if planned_liters < zone.minimum_effective_liters:
        return None

    return PlannedOrder(
        zone_id=zone.zone_id,
        target_liters=planned_liters,
        expected_duration_seconds=(planned_liters / zone.flow_liters_per_minute * 60),
        is_partial=planned_liters < target_liters,
        window_end=zone.window_end,
    )


def select_manual_request(
    *,
    now: datetime,
    requests: Iterable[ManualIrrigationRequest],
    executions: Iterable[IrrigationExecutionState] = (),
) -> ManualIrrigationRequest | None:
    """Select the next hydraulically ready manual order in stable FIFO order."""
    requests = tuple(requests)
    soaking_request_ids_by_zone: dict[str, set[str]] = {}
    for execution in executions:
        if execution.status == "soaking":
            soaking_request_ids_by_zone.setdefault(execution.zone_id, set()).add(
                execution.request_id
            )
    for request in requests:
        if request.status == "soaking":
            soaking_request_ids_by_zone.setdefault(request.zone_id, set()).add(request.request_id)
    ready = [
        request
        for request in requests
        if request.status in {"pending", "soaking"}
        and not (soaking_request_ids_by_zone.get(request.zone_id, set()) - {request.request_id})
        and not (
            request.request_id in soaking_request_ids_by_zone.get(request.zone_id, set())
            and request.status != "soaking"
        )
        and datetime.fromisoformat(request.expires_at) > now
        and (
            request.status == "pending"
            or request.soak_until is None
            or datetime.fromisoformat(request.soak_until) <= now
        )
    ]
    return min(ready, key=lambda request: (request.sequence, request.request_id), default=None)


def dose_target(request: ManualIrrigationRequest) -> float:
    """Bound the next dose while preserving the order's remaining target."""
    if request.max_dose_value is None or request.max_dose_value <= 0:
        return request.remaining_value
    return min(request.remaining_value, request.max_dose_value)
