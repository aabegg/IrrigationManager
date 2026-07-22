"""Deterministic planning of irrigation orders."""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
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


type SunResolver = Callable[[str, date], datetime | None]

_WEEKDAYS = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}
_SUN_ENDPOINT = re.compile(
    r"^(sunrise|sunset)(?:(?P<sign>[+-])(?P<hours>\d{1,2}):(?P<minutes>\d{2}))?$"
)


@dataclass(frozen=True, slots=True)
class WateringWindowRule:
    """One default, weekday, or exact-date watering-window rule."""

    selector: str
    start: str | None
    end: str | None

    def applies(self, day: date) -> bool:
        """Return whether this rule selects the supplied local date."""
        if self.selector == "default":
            return True
        if self.selector.startswith("date:"):
            return day == date.fromisoformat(self.selector.removeprefix("date:"))
        return day.weekday() in {
            _WEEKDAYS[value] for value in self.selector.removeprefix("days:").split(",")
        }


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


def parse_window_rule(value: str) -> WateringWindowRule:
    """Parse a compact UI-storable window rule.

    Accepted forms are legacy ``HH:MM-HH:MM``, ``mon,tue@...``, and
    ``2026-07-22@...``. Sun endpoints use ``..`` as the range delimiter,
    for example ``weekdays@sunrise-00:30..07:00``. ``@closed`` is an
    explicit weekday or date override with no windows.
    """
    selector_value = "default"
    range_value = value.strip().lower()
    if "@" in range_value:
        raw_selector, range_value = range_value.split("@", maxsplit=1)
        if raw_selector == "weekdays":
            raw_selector = "mon,tue,wed,thu,fri"
        elif raw_selector == "weekends":
            raw_selector = "sat,sun"
        try:
            selected_date = date.fromisoformat(raw_selector)
        except ValueError:
            days = raw_selector.split(",")
            if not days or any(day not in _WEEKDAYS for day in days):
                raise ValueError("Invalid watering-window selector") from None
            selector_value = f"days:{','.join(dict.fromkeys(days))}"
        else:
            selector_value = f"date:{selected_date.isoformat()}"
    if range_value == "closed":
        if selector_value == "default":
            raise ValueError("A default watering window cannot be closed")
        return WateringWindowRule(selector_value, None, None)
    if ".." in range_value:
        start, end = range_value.split("..", maxsplit=1)
    else:
        start_time, end_time = parse_daily_window(range_value)
        start, end = start_time.isoformat(), end_time.isoformat()
    _validate_endpoint(start)
    _validate_endpoint(end)
    if start == end:
        raise ValueError("Watering window start and end must differ")
    return WateringWindowRule(selector_value, start, end)


def _validate_endpoint(value: str) -> None:
    """Validate a fixed wall time or a supported sun-event expression."""
    if _SUN_ENDPOINT.fullmatch(value):
        return
    time.fromisoformat(value)


def resolve_daily_windows(
    *,
    now: datetime,
    values: Iterable[str],
    sun_resolver: SunResolver | None = None,
) -> list[WateringWindow]:
    """Resolve selected local windows to UTC, including midnight and DST crossings."""
    rules = [parse_window_rule(value) for value in values]
    windows: list[WateringWindow] = []
    local_now = now
    for day_offset in (-1, 0, 1, 2):
        day = local_now.date() + timedelta(days=day_offset)
        date_rules = [rule for rule in rules if rule.selector == f"date:{day.isoformat()}"]
        weekday_rules = [
            rule for rule in rules if rule.selector.startswith("days:") and rule.applies(day)
        ]
        selected = (
            date_rules or weekday_rules or [rule for rule in rules if rule.selector == "default"]
        )
        for rule in selected:
            if rule.start is None or rule.end is None:
                continue
            start = _resolve_endpoint(day, rule.start, local_now, sun_resolver)
            end = _resolve_endpoint(day, rule.end, local_now, sun_resolver)
            if start is None or end is None:
                continue
            if end <= start:
                end = _resolve_endpoint(day + timedelta(days=1), rule.end, local_now, sun_resolver)
            if end is not None and (end > now.astimezone(UTC) or start > now.astimezone(UTC)):
                windows.append(WateringWindow(start=start, end=end))
    return sorted(set(windows), key=lambda window: (window.start, window.end))


def active_and_next_window(
    *, now: datetime, values: Iterable[str], sun_resolver: SunResolver | None = None
) -> tuple[WateringWindow | None, datetime | None]:
    """Return the active opportunity and next future start."""
    windows = resolve_daily_windows(now=now, values=values, sun_resolver=sun_resolver)
    utc_now = now.astimezone(UTC)
    active = next((window for window in windows if window.start <= utc_now < window.end), None)
    next_start = next((window.start for window in windows if window.start > utc_now), None)
    return active, next_start


def _resolve_endpoint(
    day: date,
    value: str,
    reference: datetime,
    sun_resolver: SunResolver | None,
) -> datetime | None:
    """Resolve one endpoint and normalize nonexistent wall times through UTC."""
    if match := _SUN_ENDPOINT.fullmatch(value):
        if sun_resolver is None:
            raise ValueError("Sun watering windows require a sun resolver")
        resolved = sun_resolver(match.group(1), day)
        if resolved is None:
            return None
        sign = -1 if match.group("sign") == "-" else 1
        offset = timedelta(
            hours=int(match.group("hours") or 0), minutes=int(match.group("minutes") or 0)
        )
        return (resolved + sign * offset).astimezone(UTC)
    local = datetime.combine(day, time.fromisoformat(value), tzinfo=reference.tzinfo)
    return local.astimezone(UTC)


def decide_zone_schedule(
    *,
    now: datetime,
    zone: ZonePlanningInput,
    watering_windows: Iterable[str],
    last_effective_irrigation: datetime | None,
    minimum_interval: timedelta,
    maximum_interval: timedelta,
    minimum_trigger_liters: float,
    sun_resolver: SunResolver | None = None,
) -> ZoneScheduleDecision:
    """Apply rhythm and window policy before producing one deterministic order."""
    active_window, next_window_start = active_and_next_window(
        now=now, values=watering_windows, sun_resolver=sun_resolver
    )
    age = (
        now.astimezone(UTC) - last_effective_irrigation.astimezone(UTC)
        if last_effective_irrigation is not None
        else None
    )
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
            request.requested_start_at is None
            or datetime.fromisoformat(request.requested_start_at) <= now
        )
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
