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


class FakeFlow:
    """Return deterministic instantaneous flow readings."""

    def __init__(self, readings: Sequence[float]) -> None:
        self.readings = iter(readings)

    async def read_l_min(self) -> float:
        return next(self.readings)


class FailingFlow:
    """Return direct-flow samples until a deterministic failure."""

    def __init__(self, readings: Sequence[float | Exception]) -> None:
        self.readings = iter(readings)

    async def read_l_min(self) -> float:
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


class FallbackBlockingClock:
    """Advance through meter fallback, then block for cancellation."""

    def __init__(self) -> None:
        self.sleeps = 0
        self.elapsed = 0.0
        self.blocked = asyncio.Event()

    async def sleep(self, seconds: float) -> None:
        if seconds == 0:
            return
        self.sleeps += 1
        if self.sleeps <= 2:
            self.elapsed += seconds
            return
        self.blocked.set()
        await asyncio.Event().wait()

    def monotonic(self) -> float:
        return self.elapsed


class FlowFinalBlockingClock:
    """Allow one flow sample, then stop inside the following interval."""

    def __init__(self) -> None:
        self.sleeps = 0
        self.elapsed = 0.0
        self.blocked = asyncio.Event()

    async def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        if self.sleeps == 1:
            self.elapsed += seconds
            return
        self.blocked.set()
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


async def test_volume_meter_failure_can_finish_with_explicit_estimated_fallback() -> None:
    """Preserve measured water and estimate only the remainder from the flow profile."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([100, 104, RuntimeError("offline")]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=10,
            hard_time_limit_seconds=20,
            monitor_interval_seconds=1,
            meter_failure_strategy="estimated_time_fallback",
            estimated_flow_l_min=60,
        )
    )

    assert result.target_reached
    assert result.delivered_liters == 10
    assert result.duration_seconds == 7
    assert result.measurement_quality == "estimated"


async def test_volume_meter_failure_integrates_configured_direct_flow() -> None:
    """Use direct flow samples without ever labelling them cumulative-meter measured."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([100, RuntimeError("offline")]),
        flow=FakeFlow([60, 60]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=2,
            hard_time_limit_seconds=5,
            monitor_interval_seconds=1,
            meter_failure_strategy="estimated_time_fallback",
            estimated_flow_l_min=30,
            observe_flow=True,
        )
    )

    assert result.target_reached
    assert result.delivered_liters == 2
    assert result.measurement_quality == "integrated"


async def test_cancellation_integrates_final_fresh_flow_interval_once() -> None:
    """Account water between the last valid sample and cancellation exactly once."""
    clock = FlowFinalBlockingClock()
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FakeMeter([0]),
        flow=FakeFlow([60]),
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
                observe_flow=True,
                use_flow_consumption=True,
                flow_freshness_seconds=30,
            )
        )
    )
    await clock.blocked.wait()
    clock.elapsed = 1.5

    task.cancel()
    result = await task

    assert result.stopped
    assert result.delivered_liters == 1.5
    assert result.measurement_quality == "integrated"


async def test_flow_failure_integrates_only_fresh_final_interval() -> None:
    """Bound the final interval by freshness when the next flow read fails."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FakeMeter([0]),
        flow=FailingFlow([60, RuntimeError("offline")]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            duration_seconds=10,
            monitor_interval_seconds=1,
            observe_flow=True,
            use_flow_consumption=True,
            flow_freshness_seconds=0.25,
        )
    )

    assert result.delivered_liters == 0.5
    assert result.measurement_quality == "integrated"
    assert "Flow safety unavailable" in (result.safety_violation or "")


async def test_final_meter_failure_uses_integrated_flow_consumption() -> None:
    """Keep valid integrated consumption when the cumulative final read fails."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([0, RuntimeError("offline"), RuntimeError("offline")]),
        flow=FakeFlow([60]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            duration_seconds=1,
            monitor_interval_seconds=1,
            observe_flow=True,
            use_flow_consumption=True,
            flow_freshness_seconds=30,
        )
    )

    assert result.delivered_liters == 1
    assert result.measurement_quality == "integrated"
    assert result.safety_violation is None


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


async def test_required_meter_progress_does_not_accept_direct_flow_fallback() -> None:
    """Require cumulative evidence even when direct flow can account consumption."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([100, RuntimeError("offline")]),
        flow=FakeFlow([60]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            duration_seconds=1,
            monitor_interval_seconds=1,
            observe_flow=True,
            require_meter_progress=True,
        )
    )

    assert result.measurement_quality == "integrated"
    assert not result.target_reached
    assert result.safety_scope == "zone"
    assert "No cumulative meter progress" in (result.safety_violation or "")


@pytest.mark.parametrize(
    ("meter_end", "minimum", "maximum", "scope", "message"),
    [
        (0.1, 10, 20, "zone", "below minimum"),
        (1.0, 10, 20, "installation", "plausible execution maximum"),
    ],
)
async def test_required_meter_progress_checks_average_flow(
    meter_end: float,
    minimum: float,
    maximum: float,
    scope: str,
    message: str,
) -> None:
    """Use cumulative delivery for authoritative end-of-operation flow safety."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FakeMeter([0, meter_end]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            duration_seconds=1,
            monitor_interval_seconds=1,
            minimum_flow_l_min=minimum,
            maximum_flow_l_min=maximum,
            require_meter_progress=True,
        )
    )

    assert not result.target_reached
    assert result.safety_scope == scope
    assert message in (result.safety_violation or "")


async def test_initial_meter_read_can_enter_explicit_estimated_fallback() -> None:
    """Handle meter loss between manager preflight and executor baseline read."""
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([RuntimeError("offline")]),
        clock=FakeClock(),
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=None,
            amount_liters=2,
            hard_time_limit_seconds=3,
            monitor_interval_seconds=1,
            meter_failure_strategy="estimated_time_fallback",
            estimated_flow_l_min=60,
        )
    )

    assert result.target_reached
    assert result.delivered_liters == 2
    assert result.duration_seconds == 2
    assert result.measurement_quality == "estimated"


async def test_cancellation_preserves_measured_and_estimated_fallback_progress() -> None:
    """Return the latest mixed-quality amount when cancellation interrupts a wait."""
    clock = FallbackBlockingClock()
    executor = IrrigationExecutor(
        actuators=FakeActuators(),
        meter=FailingMeter([100, 104, RuntimeError("offline")]),
        clock=clock,
    )
    task = asyncio.create_task(
        executor.execute(
            ExecutionRequest(
                zone_id="lawn",
                zone_valve="switch.zone_lawn",
                main_valve=None,
                amount_liters=100,
                hard_time_limit_seconds=60,
                monitor_interval_seconds=1,
                meter_failure_strategy="estimated_time_fallback",
                estimated_flow_l_min=60,
            )
        )
    )
    await clock.blocked.wait()
    clock.elapsed = 5

    task.cancel()
    result = await task

    assert result.stopped
    assert result.delivered_liters == 8
    assert result.duration_seconds == 5
    assert result.measurement_quality == "estimated"
    assert not result.target_reached


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


async def test_volume_deadline_bounds_hanging_close_feedback_and_retries_cleanup() -> None:
    """Do not hang when closure succeeds physically but feedback never returns."""

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

    assert 0.2 < elapsed < 0.4
    assert result.delivered_liters == 10
    assert "Hard time limit" in (result.safety_violation or "")
    assert actuators.operations == [
        ("open", "switch.main"),
        ("open", "switch.zone_lawn"),
        ("close", "switch.zone_lawn"),
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
