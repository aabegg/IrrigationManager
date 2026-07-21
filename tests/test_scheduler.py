"""Behavior tests for deterministic irrigation scheduling."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from custom_components.irrigation_manager.models import (
    IrrigationExecutionState,
    ManualIrrigationRequest,
)
from custom_components.irrigation_manager.scheduler import (
    WateringMode,
    ZonePlanningInput,
    dose_target,
    plan_orders,
    select_manual_request,
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
