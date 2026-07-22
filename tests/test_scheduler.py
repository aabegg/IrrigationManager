"""Behavior tests for deterministic irrigation scheduling."""

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from custom_components.irrigation_manager.models import (
    IrrigationExecutionState,
    ManualIrrigationRequest,
)
from custom_components.irrigation_manager.scheduler import (
    WateringMode,
    ZonePlanningInput,
    active_and_next_window,
    decide_zone_schedule,
    dose_target,
    plan_orders,
    resolve_daily_windows,
    select_manual_request,
)


def test_weekday_and_date_overrides_replace_default_windows() -> None:
    """Apply exact-date closure ahead of weekday and default rules."""
    berlin = ZoneInfo("Europe/Berlin")
    monday = datetime(2026, 7, 20, 4, 30, tzinfo=berlin)
    tuesday = datetime(2026, 7, 21, 4, 30, tzinfo=berlin)
    values = ["04:00-06:00", "mon@05:00-07:00", "2026-07-21@closed"]

    monday_window, _ = active_and_next_window(now=monday, values=values)
    tuesday_window, next_start = active_and_next_window(now=tuesday, values=values)

    assert monday_window is None
    assert next_start is not None
    assert tuesday_window is None


def test_sun_offset_window_uses_resolver_and_stable_local_date() -> None:
    """Resolve sun offsets through the supplied HA-compatible helper seam."""
    berlin = ZoneInfo("Europe/Berlin")
    now = datetime(2026, 7, 20, 5, 0, tzinfo=berlin)

    def sun(event: str, day: date) -> datetime:
        hour = 5 if event == "sunrise" else 21
        return datetime.combine(day, time(hour), tzinfo=berlin)

    active, _ = active_and_next_window(
        now=now,
        values=["mon@sunrise-00:30..sunrise+01:00"],
        sun_resolver=sun,
    )

    assert active is not None
    assert active.start == datetime(2026, 7, 20, 2, 30, tzinfo=UTC)
    assert active.end == datetime(2026, 7, 20, 4, 0, tzinfo=UTC)


def test_dst_window_range_uses_elapsed_time_not_wall_clock_time() -> None:
    """A spring-forward window loses the nonexistent local hour."""
    berlin = ZoneInfo("Europe/Berlin")
    windows = resolve_daily_windows(
        now=datetime(2026, 3, 29, 1, 45, tzinfo=berlin),
        values=["sun@01:30-03:30"],
    )

    instant = datetime(2026, 3, 29, 0, 45, tzinfo=UTC)
    active = next(window for window in windows if window.start <= instant < window.end)
    assert active.end - active.start == timedelta(hours=1)


def test_plan_orders_prioritizes_window_then_need_then_zone_priority() -> None:
    """Sort due zones by deadline, relative need, and configured priority."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    zones = [
        ZonePlanningInput(
            zone_id="hedge",
            mode=WateringMode.DEMAND,
            calculated_target_liters=80,
            minimum_target_liters=0,
            maximum_target_liters=120,
            minimum_effective_liters=10,
            flow_liters_per_minute=10,
            relative_need=0.9,
            priority=10,
            window_end=now + timedelta(hours=3),
        ),
        ZonePlanningInput(
            zone_id="lawn",
            mode=WateringMode.DEMAND,
            calculated_target_liters=60,
            minimum_target_liters=0,
            maximum_target_liters=100,
            minimum_effective_liters=10,
            flow_liters_per_minute=10,
            relative_need=0.7,
            priority=1,
            window_end=now + timedelta(hours=1),
        ),
        ZonePlanningInput(
            zone_id="raised_bed",
            mode=WateringMode.MINIMUM,
            calculated_target_liters=20,
            minimum_target_liters=40,
            maximum_target_liters=80,
            minimum_effective_liters=10,
            flow_liters_per_minute=10,
            relative_need=0.4,
            priority=5,
            window_end=now + timedelta(hours=3),
        ),
    ]

    orders = plan_orders(now=now, zones=zones)

    assert [order.zone_id for order in orders] == ["lawn", "hedge", "raised_bed"]
    assert orders[2].target_liters == 40


def test_plan_orders_creates_partial_only_when_minimum_effective_dose_fits() -> None:
    """Fit a useful partial dose into the remaining watering window."""
    now = datetime(2026, 7, 21, 5, 55, tzinfo=UTC)
    fitting = ZonePlanningInput(
        zone_id="pots",
        mode=WateringMode.DEMAND,
        calculated_target_liters=30,
        minimum_target_liters=0,
        maximum_target_liters=50,
        minimum_effective_liters=4,
        flow_liters_per_minute=2,
        relative_need=0.8,
        priority=1,
        window_end=now + timedelta(minutes=5),
    )
    too_small = ZonePlanningInput(
        zone_id="lawn",
        mode=WateringMode.DEMAND,
        calculated_target_liters=100,
        minimum_target_liters=0,
        maximum_target_liters=100,
        minimum_effective_liters=20,
        flow_liters_per_minute=2,
        relative_need=1.0,
        priority=1,
        window_end=now + timedelta(minutes=5),
    )

    orders = plan_orders(now=now, zones=[fitting, too_small])

    assert len(orders) == 1
    assert orders[0].zone_id == "pots"
    assert orders[0].target_liters == 10
    assert orders[0].is_partial is True


def _automatic_zone(*, mode: WateringMode, target: float) -> ZonePlanningInput:
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    return ZonePlanningInput(
        zone_id="lawn",
        mode=mode,
        calculated_target_liters=target,
        minimum_target_liters=20,
        maximum_target_liters=100,
        minimum_effective_liters=1,
        flow_liters_per_minute=10,
        relative_need=target / 100,
        priority=1,
        window_end=now + timedelta(hours=2),
    )


def test_demand_mode_skips_below_trigger_even_after_maximum_interval() -> None:
    """A maximum interval does not manufacture demand in demand mode."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    decision = decide_zone_schedule(
        now=now,
        zone=_automatic_zone(mode=WateringMode.DEMAND, target=4),
        watering_windows=["03:00-05:00"],
        last_effective_irrigation=now - timedelta(days=10),
        minimum_interval=timedelta(days=1),
        maximum_interval=timedelta(days=7),
        minimum_trigger_liters=5,
    )

    assert decision.order is None
    assert decision.reason == "demand_below_trigger"


def test_demand_mode_waits_until_readily_available_water_is_depleted() -> None:
    """Do not release a large refill target before the physical RAW threshold."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    decision = decide_zone_schedule(
        now=now,
        zone=replace(
            _automatic_zone(mode=WateringMode.DEMAND, target=50),
            demand_threshold_reached=False,
        ),
        watering_windows=["03:00-05:00"],
        last_effective_irrigation=now - timedelta(days=2),
        minimum_interval=timedelta(days=1),
        maximum_interval=timedelta(days=7),
        minimum_trigger_liters=5,
    )

    assert decision.order is None
    assert decision.reason == "readily_available_water_not_depleted"


def test_minimum_mode_releases_mandatory_amount_at_maximum_interval() -> None:
    """Guarantee the configured minimum only when the maximum interval is due."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    decision = decide_zone_schedule(
        now=now,
        zone=_automatic_zone(mode=WateringMode.MINIMUM, target=0),
        watering_windows=["03:00-05:00"],
        last_effective_irrigation=now - timedelta(days=7),
        minimum_interval=timedelta(days=1),
        maximum_interval=timedelta(days=7),
        minimum_trigger_liters=5,
    )

    assert decision.order is not None
    assert decision.order.target_liters == 20


def test_minimum_interval_blocks_an_otherwise_needed_zone() -> None:
    """Never create an automatic target before the effective minimum interval."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    decision = decide_zone_schedule(
        now=now,
        zone=_automatic_zone(mode=WateringMode.DEMAND, target=50),
        watering_windows=["03:00-05:00"],
        last_effective_irrigation=now - timedelta(hours=12),
        minimum_interval=timedelta(days=1),
        maximum_interval=timedelta(days=7),
        minimum_trigger_liters=5,
    )

    assert decision.order is None
    assert decision.reason == "minimum_interval"


def test_cross_midnight_window_resolves_to_one_stable_opportunity() -> None:
    """Keep both sides of midnight in the opportunity that began the prior day."""
    before_midnight = datetime(2026, 7, 21, 23, 30, tzinfo=UTC)
    after_midnight = datetime(2026, 7, 22, 1, 0, tzinfo=UTC)

    first, _ = active_and_next_window(now=before_midnight, values=["22:00-02:00"])
    second, _ = active_and_next_window(now=after_midnight, values=["22:00-02:00"])

    assert first is not None
    assert second is not None
    assert first.opportunity_id == second.opportunity_id
    assert first.end == datetime(2026, 7, 22, 2, 0, tzinfo=UTC)


def _manual_request(
    *, sequence: int, status: str = "pending", soak_until: datetime | None = None
) -> ManualIrrigationRequest:
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    return ManualIrrigationRequest(
        request_id=f"request-{sequence}",
        sequence=sequence,
        zone_id=f"zone-{sequence}",
        zone_subentry_id=f"subentry-{sequence}",
        zone_name=f"Zone {sequence}",
        zone_valve=f"switch.zone_{sequence}",
        main_valve=None,
        target_type="duration",
        target_value=30,
        remaining_value=25,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        status=status,
        max_dose_value=10,
        soak_until=soak_until.isoformat() if soak_until else None,
    )


def test_manual_scheduler_splits_target_and_skips_a_soaking_fifo_head() -> None:
    """Keep FIFO stable while allowing another zone to use a hydraulic gap."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    soaking = _manual_request(
        sequence=1,
        status="soaking",
        soak_until=now + timedelta(minutes=5),
    )
    ready = _manual_request(sequence=2)

    assert dose_target(soaking) == 10
    assert select_manual_request(now=now, requests=[ready, soaking]) == ready


def test_manual_scheduler_blocks_every_request_for_a_zone_that_is_still_soaking() -> None:
    """Never start a second execution for a zone during its first execution's soak."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    soaking = _manual_request(
        sequence=1,
        status="soaking",
        soak_until=now + timedelta(minutes=5),
    )
    same_zone = replace(_manual_request(sequence=2), zone_id=soaking.zone_id)
    other_zone = _manual_request(sequence=3)
    soaking_execution = IrrigationExecutionState(
        execution_id="execution-soaking",
        request_id=soaking.request_id,
        zone_id=soaking.zone_id,
        target_type="duration",
        target_value=30,
        remaining_value=25,
        status="soaking",
        created_at=soaking.created_at,
    )

    assert (
        select_manual_request(
            now=now,
            requests=[replace(soaking, status="pending"), same_zone],
            executions=[soaking_execution],
        )
        is None
    )
    assert (
        select_manual_request(
            now=now,
            requests=[soaking, same_zone, other_zone],
            executions=[soaking_execution],
        )
        == other_zone
    )


def test_manual_request_has_priority_over_an_older_automatic_request() -> None:
    """Let explicit user intent pass every not-yet-started automatic order."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    automatic = replace(_manual_request(sequence=1), source="automatic")
    manual = _manual_request(sequence=2)

    assert select_manual_request(now=now, requests=[automatic, manual]) == manual


def test_automatic_requests_use_window_need_and_priority_not_creation_sequence() -> None:
    """Preserve scheduler priority when requests were created by different replans."""
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    later = replace(
        _manual_request(sequence=1),
        source="automatic",
        automatic_window_end=(now + timedelta(hours=2)).isoformat(),
        automatic_relative_need=1.0,
        automatic_priority=10,
    )
    urgent = replace(
        _manual_request(sequence=2),
        source="automatic",
        automatic_window_end=(now + timedelta(hours=1)).isoformat(),
        automatic_relative_need=0.1,
        automatic_priority=0,
    )

    assert select_manual_request(now=now, requests=[later, urgent]) == urgent
