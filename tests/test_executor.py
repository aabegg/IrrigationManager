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

    async def open(self, entity_id: str, *, verify: bool = True) -> None:
        self.operations.append(("open", entity_id))
        if entity_id != self.failing_valve:
            self.open_valves.add(entity_id)

    async def close(self, entity_id: str, *, verify: bool = True) -> None:
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


class FailingMeter:
    """Return readings until a deterministic meter failure occurs."""

    def __init__(self, readings: Sequence[float | Exception]) -> None:
        self.readings = iter(readings)

    async def read_liters(self) -> float:
        reading = next(self.readings)
        if isinstance(reading, Exception):
            raise reading
        return reading


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
    """Hold an active irrigation operation until its task is cancelled."""

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


class RealClock:
    """Use the event loop clock for absolute-deadline tests."""

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    def monotonic(self) -> float:
        return asyncio.get_running_loop().time()


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


async def test_volume_target_closes_when_cumulative_meter_reaches_target() -> None:
    """Poll the cumulative meter and close immediately after observing the target."""
    actuators = FakeActuators()
    clock = FakeClock()
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([100, 104, 110, 112]),
        clock=clock,
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=10,
            hard_time_limit_seconds=60,
            monitor_interval_seconds=1,
        )
    )

    assert clock.sleeps == [1, 1, 0]
    assert result.target_reached
    assert result.delivered_liters == 12
    assert result.duration_seconds == 2
    assert result.measurement_quality == "measured"
    assert actuators.open_valves == set()


async def test_volume_target_hard_timeout_closes_and_reports_partial_amount() -> None:
    """Never keep watering beyond the configured volume safety timeout."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FakeMeter([100, 102, 104, 104]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=10,
            hard_time_limit_seconds=2,
            monitor_interval_seconds=1,
        )
    )

    assert not result.target_reached
    assert result.delivered_liters == 4
    assert result.duration_seconds == 2
    assert result.safety_violation == "Hard time limit reached before volume target"


async def test_volume_meter_failure_aborts_without_losing_partial_measurement() -> None:
    """Close on meter loss and retain the last valid cumulative delta."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([100, 104, RuntimeError("offline"), RuntimeError("offline")]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=10,
            hard_time_limit_seconds=60,
            monitor_interval_seconds=1,
        )
    )

    assert result.delivered_liters == 4
    assert result.duration_seconds == 2
    assert "Water meter failed" in (result.safety_violation or "")
    assert result.measurement_quality == "measured"


async def test_timed_irrigation_runs_when_optional_meter_is_unavailable() -> None:
    """Treat a timed operation's meter as observational rather than an actuation gate."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([RuntimeError("offline"), RuntimeError("offline")]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            duration_seconds=5,
        )
    )

    assert result.target_reached
    assert result.duration_seconds == 5
    assert result.delivered_liters == 0
    assert result.measurement_quality == "unavailable"
    assert result.safety_violation is None


async def test_required_meter_failure_commands_zone_then_main_close() -> None:
    """Fail closed in hydraulic order even when the initial meter baseline is unavailable."""
    actuators = FakeActuators()
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FailingMeter([RuntimeError("offline")]),
        clock=FakeClock(),
    )

    with pytest.raises(RuntimeError, match="Water meter is unavailable"):
        await executor.execute(
            ExecutionRequest(
                zone_id="lawn",
                zone_valve="switch.zone_lawn",
                main_valve="switch.main",
                amount_liters=10,
                hard_time_limit_seconds=60,
            )
        )

    assert actuators.operations == [
        ("close", "switch.zone_lawn"),
        ("close", "switch.main"),
    ]


async def test_required_meter_progress_rejects_zero_delivery() -> None:
    """Treat a missing cumulative response as a zone fault for calibration."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FakeMeter([100, 100, 100]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            duration_seconds=5,
            monitor_interval_seconds=1,
            require_meter_progress=True,
        )
    )

    assert not result.target_reached
    assert result.safety_scope == "zone"
    assert "No cumulative meter progress" in (result.safety_violation or "")


async def test_explicit_stop_does_not_turn_missing_meter_progress_into_lock() -> None:
    """Let a user stop before the next meter increment without creating a safety fault."""
    clock = BlockingClock()
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FakeMeter([100, 100]),
        clock=clock,
    )
    task = asyncio.create_task(
        executor.execute(
            ExecutionRequest(
                zone_id="lawn",
                zone_valve="switch.zone_lawn",
                main_valve=None,
                duration_seconds=60,
                monitor_interval_seconds=1,
                require_meter_progress=True,
            )
        )
    )
    await clock.started.wait()

    task.cancel()
    result = await task

    assert result.stopped
    assert result.safety_violation is None
    assert result.safety_scope is None


async def test_volume_deadline_includes_progress_persistence_overhead() -> None:
    """Bound valve checks, meter reads, and progress writes by one deadline."""

    class DelayedActuators(FakeActuators):
        async def is_open(self, entity_id: str) -> bool:
            await asyncio.sleep(0.005)
            return await super().is_open(entity_id)

    class DelayedMeter(FakeMeter):
        async def read_liters(self) -> float:
            await asyncio.sleep(0.005)
            return await super().read_liters()

    actuators = DelayedActuators()
    clock = RealClock()
    progress_started = asyncio.Event()
    progress_completed = False

    async def persist_progress(_remaining: float, _quality: str) -> None:
        nonlocal progress_completed
        progress_started.set()
        await asyncio.sleep(0.2)
        progress_completed = True

    executor = IrrigationExecutor(
        actuators=actuators,
        meter=DelayedMeter([100, 101, 101]),
        clock=clock,
    )
    started_at = clock.monotonic()

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=100,
            hard_time_limit_seconds=0.03,
            monitor_interval_seconds=0.001,
            on_progress=persist_progress,
        )
    )
    elapsed = clock.monotonic() - started_at

    assert progress_started.is_set()
    assert not progress_completed
    assert elapsed < 0.1
    assert result.duration_seconds == pytest.approx(0.03, abs=0.02)
    assert result.delivered_liters == 1
    assert result.safety_violation == "Hard time limit reached before volume target"
    assert actuators.open_valves == set()


async def test_volume_deadline_closes_zone_when_open_feedback_never_confirms() -> None:
    """Start the hard deadline before open confirmation can block indefinitely."""

    class UnconfirmedActuators(FakeActuators):
        async def is_open(self, entity_id: str) -> bool:
            if entity_id == "switch.zone_lawn":
                await asyncio.sleep(0.2)
            return await super().is_open(entity_id)

    actuators = UnconfirmedActuators()
    clock = RealClock()
    confirmed = False

    async def mark_confirmed() -> None:
        nonlocal confirmed
        confirmed = True

    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([100, 102]),
        clock=clock,
    )
    started_at = clock.monotonic()

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=10,
            hard_time_limit_seconds=0.03,
            monitor_interval_seconds=0.001,
            on_zone_opened=mark_confirmed,
        )
    )
    elapsed = clock.monotonic() - started_at

    assert not confirmed
    assert elapsed < 0.1
    assert result.duration_seconds == pytest.approx(0.03, abs=0.02)
    assert result.delivered_liters == 2
    assert result.safety_violation == "Hard time limit reached before volume target"
    assert actuators.operations == [
        ("open", "switch.zone_lawn"),
        ("close", "switch.zone_lawn"),
    ]
    assert actuators.open_valves == set()


async def test_volume_deadline_starts_before_main_feedback_confirmation() -> None:
    """Bound main-valve confirmation and still attempt cleanup for every valve."""

    class UnconfirmedMainActuators(FakeActuators):
        async def is_open(self, entity_id: str) -> bool:
            if entity_id == "switch.main":
                await asyncio.sleep(0.2)
            return await super().is_open(entity_id)

    actuators = UnconfirmedMainActuators()
    clock = RealClock()
    zone_opening_marked = False

    async def mark_zone_opening() -> None:
        nonlocal zone_opening_marked
        zone_opening_marked = True

    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([100, 100]),
        clock=clock,
    )
    started_at = clock.monotonic()

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve="switch.main",
            amount_liters=10,
            hard_time_limit_seconds=0.03,
            monitor_interval_seconds=0.001,
            on_zone_opening=mark_zone_opening,
        )
    )
    elapsed = clock.monotonic() - started_at

    assert not zone_opening_marked
    assert elapsed < 0.1
    assert result.delivered_liters == 0
    assert result.safety_violation == "Hard time limit reached before volume target"
    assert actuators.operations == [
        ("open", "switch.main"),
        ("close", "switch.zone_lawn"),
        ("close", "switch.main"),
    ]
    assert actuators.open_valves == set()


async def test_volume_cleanup_is_bounded_separately_and_preserves_close_order() -> None:
    """Keep target timing separate while closing zone before main within bounded waits."""

    class HangingCloseActuators(FakeActuators):
        def __init__(self) -> None:
            super().__init__()
            self.completed_closes: list[str] = []

        async def close(self, entity_id: str, *, verify: bool = True) -> None:
            self.operations.append(("close", entity_id))
            self.open_valves.discard(entity_id)
            await asyncio.sleep(0.2)
            self.completed_closes.append(entity_id)

    actuators = HangingCloseActuators()
    clock = RealClock()
    executor = IrrigationExecutor(
        actuators=actuators,
        meter=FakeMeter([100, 110, 110]),
        clock=clock,
    )
    started_at = clock.monotonic()

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve="switch.main",
            amount_liters=10,
            hard_time_limit_seconds=0.05,
            monitor_interval_seconds=0.001,
        )
    )
    elapsed = clock.monotonic() - started_at

    assert 0.4 < elapsed < 0.6
    assert result.delivered_liters == 10
    assert result.safety_violation is None
    assert actuators.operations == [
        ("open", "switch.main"),
        ("open", "switch.zone_lawn"),
        ("close", "switch.zone_lawn"),
        ("close", "switch.main"),
    ]
    assert actuators.completed_closes == ["switch.zone_lawn", "switch.main"]
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


async def test_stop_reports_actual_irrigation_duration() -> None:
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
    """End the operation and close a foreign zone as soon as exclusivity is lost."""
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
