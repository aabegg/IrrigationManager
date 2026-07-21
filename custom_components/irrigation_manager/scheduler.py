"""Deterministic planning of irrigation orders."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
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


@dataclass(frozen=True, slots=True)
class WateringWindow:
    """One resolved daily watering opportunity."""

    start: datetime
    end: datetime

    @property
    def opportunity_id(self) -> str:
        """Return a stable identity for restart-safe automatic planning."""
        return self.start.isoformat()


@dataclass(frozen=True, slots=True)
class ZoneScheduleDecision:
    """Explain whether a zone should produce an order at one instant."""

    order: PlannedOrder | None
    needed: bool
    target_liters: float
    reason: str
    active_window: WateringWindow | None
    next_window_start: datetime | None


def parse_daily_window(value: str) -> tuple[time, time]:
    """Parse a UI-storable fixed daily window in HH:MM-HH:MM form."""
    try:
        start_value, end_value = value.split("-", maxsplit=1)
        start = time.fromisoformat(start_value.strip())
        end = time.fromisoformat(end_value.strip())
    except (TypeError, ValueError) as err:
        raise ValueError("Watering windows must use HH:MM-HH:MM") from err
    if start == end:
        raise ValueError("Watering window start and end must differ")
    return start, end


def resolve_daily_windows(*, now: datetime, values: Iterable[str]) -> list[WateringWindow]:
    """Resolve current and next fixed daily windows, including midnight crossings."""
    windows: list[WateringWindow] = []
    for value in values:
        start_time, end_time = parse_daily_window(value)
        for day_offset in (-1, 0, 1):
            day = now.date() + timedelta(days=day_offset)
            start = _combine(day, start_time, now)
            end_day = day + timedelta(days=1) if end_time <= start_time else day
            end = _combine(end_day, end_time, now)
            if end > now or start > now:
                windows.append(WateringWindow(start=start, end=end))
    return sorted(set(windows), key=lambda window: (window.start, window.end))


def active_and_next_window(
    *, now: datetime, values: Iterable[str]
) -> tuple[WateringWindow | None, datetime | None]:
    """Return the active opportunity and next future start."""
    windows = resolve_daily_windows(now=now, values=values)
    active = next((window for window in windows if window.start <= now < window.end), None)
    next_start = next((window.start for window in windows if window.start > now), None)
    return active, next_start


def _combine(day: date, value: time, reference: datetime) -> datetime:
    """Combine a wall-clock value using the planning instant's timezone."""
    return datetime.combine(day, value, tzinfo=reference.tzinfo)


def decide_zone_schedule(
    *,
    now: datetime,
    zone: ZonePlanningInput,
    watering_windows: Iterable[str],
    last_effective_irrigation: datetime | None,
    minimum_interval: timedelta,
    maximum_interval: timedelta,
    minimum_trigger_liters: float,
) -> ZoneScheduleDecision:
    """Apply rhythm and window policy before producing one deterministic order."""
    active_window, next_window_start = active_and_next_window(now=now, values=watering_windows)
    age = now - last_effective_irrigation if last_effective_irrigation is not None else None
    if not zone.enabled:
        return ZoneScheduleDecision(
            None, False, 0.0, "automation_disabled", None, next_window_start
        )
    if zone.blocked:
        return ZoneScheduleDecision(None, False, 0.0, "safety_blocked", None, next_window_start)
    if age is not None and age < minimum_interval:
        return ZoneScheduleDecision(
            None, False, 0.0, "minimum_interval", active_window, next_window_start
        )

    calculated = max(0.0, zone.calculated_target_liters)
    maximum_due = age is None or age >= maximum_interval
    mandatory_due = zone.mode is WateringMode.MINIMUM and maximum_due
    target = max(calculated, zone.minimum_target_liters if mandatory_due else 0.0)
    target = min(target, zone.maximum_target_liters)
    needed = mandatory_due or target >= minimum_trigger_liters
    if not needed:
        return ZoneScheduleDecision(
            None, False, target, "demand_below_trigger", active_window, next_window_start
        )
    if active_window is None:
        return ZoneScheduleDecision(
            None, True, target, "outside_watering_window", None, next_window_start
        )

    planning_input = ZonePlanningInput(
        zone_id=zone.zone_id,
        mode=WateringMode.DEMAND,
        calculated_target_liters=target,
        minimum_target_liters=0.0,
        maximum_target_liters=zone.maximum_target_liters,
        minimum_effective_liters=zone.minimum_effective_liters,
        flow_liters_per_minute=zone.flow_liters_per_minute,
        relative_need=zone.relative_need,
        priority=zone.priority,
        window_end=active_window.end,
        enabled=True,
        blocked=False,
    )
    order = _plan_zone(now=now, zone=planning_input)
    return ZoneScheduleDecision(
        order,
        True,
        target,
        "planned" if order is not None else "insufficient_window_time",
        active_window,
        next_window_start,
    )


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
    return min(ready, key=_request_priority, default=None)


def _request_priority(request: ManualIrrigationRequest) -> tuple[object, ...]:
    """Keep manual FIFO ahead of lexicographically ordered automatic work."""
    if request.source == "manual":
        return (0, request.sequence, request.request_id)
    window_end = request.automatic_window_end or request.expires_at
    return (
        1,
        datetime.fromisoformat(window_end).timestamp(),
        -(request.automatic_relative_need or 0.0),
        -(request.automatic_priority or 0),
        request.zone_id,
        request.request_id,
    )


def dose_target(request: ManualIrrigationRequest) -> float:
    """Bound the next dose while preserving the order's remaining target."""
    if request.max_dose_value is None or request.max_dose_value <= 0:
        return request.remaining_value
    return min(request.remaining_value, request.max_dose_value)
