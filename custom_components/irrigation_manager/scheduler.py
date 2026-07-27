"""Small deterministic helpers used by the version-2 runtime."""

import math
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, tzinfo

from .models import ManualIrrigationRequest


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
    ready = (
        request
        for request in requests
        if request.status == "pending"
        and datetime.fromisoformat(request.operation_deadline_at or request.expires_at) > now
        and (
            request.requested_start_at is None
            or datetime.fromisoformat(request.requested_start_at) <= now
        )
    )
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
