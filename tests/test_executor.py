"""Behavior tests for safe irrigation execution."""

import asyncio
from collections.abc import Sequence

import pytest

from custom_components.irrigation_manager.executor import (
    ExecutionRequest,
    IrrigationExecutor,
    ValveDidNotOpenError,
)


class FakeActuators:
    """Record actuator operations and expose deterministic feedback."""

    def __init__(
        self,
        *,
        failing_valve: str | None = None,
        failing_close: str | None = None,
    ) -> None:
        self.failing_valve = failing_valve
        self.failing_close = failing_close
        self.open_valves: set[str] = set()
        self.operations: list[tuple[str, str]] = []

    async def open(self, entity_id: str) -> None:
        self.operations.append(("open", entity_id))
        if entity_id != self.failing_valve:
            self.open_valves.add(entity_id)

    async def close(self, entity_id: str) -> None:
        self.operations.append(("close", entity_id))
        if entity_id == self.failing_close:
            raise RuntimeError(f"Could not close {entity_id}")
        self.open_valves.discard(entity_id)

    async def is_open(self, entity_id: str) -> bool:
        return entity_id in self.open_valves


class FakeMeter:
    """Return a known start and end total."""

    def __init__(self, readings: Sequence[float]) -> None:
        self.readings = iter(readings)

    async def read_liters(self) -> float:
        return next(self.readings)


class FakeFlow:
    """Return deterministic instantaneous flow readings."""

    def __init__(self, readings: Sequence[float]) -> None:
        self.readings = iter(readings)

    async def read_l_min(self) -> float:
        return next(self.readings)


class FakeClock:
    """Record requested waits without delaying the test."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []
        self.elapsed = 0.0

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.elapsed += seconds

    def monotonic(self) -> float:
        return self.elapsed


class BlockingClock:
    """Hold an active dose until its task is cancelled."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.elapsed = 0.0

    async def sleep(self, seconds: float) -> None:
        if seconds == 0:
            return
        self.started.set()
        await asyncio.Event().wait()

    def monotonic(self) -> float:
        return self.elapsed


async def test_execute_timed_waters_one_zone_and_attributes_meter_delta() -> None:
    """Open main then zone, close safely, and assign measured consumption."""
    actuators = FakeActuators()
    clock = FakeClock()
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([1_000.0, 1_025.0]),
        clock=clock,
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve="switch.main",
            duration_seconds=60,
            settle_seconds=5,
        )
    )

    assert actuators.operations == [
        ("open", "switch.main"),
        ("open", "switch.zone_lawn"),
        ("close", "switch.zone_lawn"),
        ("close", "switch.main"),
    ]
    assert clock.sleeps == [60, 5]
    assert result.zone_id == "lawn"
    assert result.delivered_liters == 25.0
    assert actuators.open_valves == set()


async def test_execute_closes_main_when_zone_does_not_open() -> None:
    """Return to a closed installation if valve feedback rejects opening."""
    actuators = FakeActuators(failing_valve="switch.zone_lawn")
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([1_000.0]),
        clock=FakeClock(),
    )

    with pytest.raises(ValveDidNotOpenError):
        await executor.execute(
            ExecutionRequest(
                zone_id="lawn",
                zone_valve="switch.zone_lawn",
                main_valve="switch.main",
                duration_seconds=60,
                settle_seconds=5,
            )
        )

    assert actuators.operations == [
        ("open", "switch.main"),
        ("open", "switch.zone_lawn"),
        ("close", "switch.zone_lawn"),
        ("close", "switch.main"),
    ]
    assert actuators.open_valves == set()


async def test_stop_reports_actual_water_time_for_estimated_consumption() -> None:
    """Do not account the requested duration after an early stop."""
    clock = BlockingClock()
    actuators = FakeActuators()
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([0, 0]),
        clock=clock,
    )
    task = asyncio.create_task(
        executor.execute(
            ExecutionRequest(
                zone_id="lawn",
                zone_valve="switch.zone_lawn",
                main_valve="switch.main",
                duration_seconds=600,
            )
        )
    )
    await clock.started.wait()
    clock.elapsed = 12

    task.cancel()
    result = await task

    assert result.stopped
    assert result.duration_seconds == 12
    assert actuators.open_valves == set()


async def test_cleanup_attempts_main_close_when_zone_close_fails() -> None:
    """Always depower the installation even if zone cleanup reports an error."""
    actuators = FakeActuators(failing_close="switch.zone_lawn")
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([0, 10]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve="switch.main",
            duration_seconds=60,
        )
    )

    assert ("close", "switch.main") in actuators.operations
    assert "switch.main" not in actuators.open_valves
    assert result.delivered_liters == 10
    assert "switch.zone_lawn" in result.safety_violation


async def test_monitor_closes_a_second_zone_that_opens_during_watering() -> None:
    """End the dose and close a foreign zone as soon as exclusivity is lost."""
    actuators = FakeActuators()
    actuators.open_valves.add("switch.zone_beds")
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([0, 5]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve="switch.main",
            duration_seconds=60,
            managed_zone_valves=("switch.zone_lawn", "switch.zone_beds"),
            monitor_interval_seconds=1,
        )
    )

    assert result.duration_seconds == 1
    assert result.delivered_liters == 5
    assert "switch.zone_beds opened unexpectedly" in result.safety_violation
    assert actuators.open_valves == set()


@pytest.mark.parametrize(
    ("flow", "minimum", "maximum", "scope"),
    [
        (5.0, 10.0, 20.0, "zone"),
        (25.0, 10.0, 20.0, "installation"),
    ],
)
async def test_flow_outside_profile_stops_with_correct_safety_scope(
    flow: float,
    minimum: float,
    maximum: float,
    scope: str,
) -> None:
    """Low flow locks one zone while high flow locks the installation."""
    actuators = FakeActuators()
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([0, 1]),
        flow=FakeFlow([flow]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve="switch.main",
            duration_seconds=60,
            monitor_interval_seconds=1,
            minimum_flow_l_min=minimum,
            maximum_flow_l_min=maximum,
        )
    )

    assert result.duration_seconds == 1
    assert result.safety_scope == scope
    assert "flow" in result.safety_violation.lower()
    assert actuators.open_valves == set()
