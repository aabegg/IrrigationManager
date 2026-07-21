"""Behavior tests for deterministic irrigation scheduling."""

from datetime import UTC, datetime, timedelta

from custom_components.irrigation_manager.scheduler import (
    WateringMode,
    ZonePlanningInput,
    plan_orders,
)


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
