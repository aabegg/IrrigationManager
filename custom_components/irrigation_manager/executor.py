"""Safe, serialized execution of irrigation requests."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

CLEANUP_FEEDBACK_BUDGET_SECONDS = 5.0


class ActuatorPort(Protocol):
    """Control and observe logical irrigation valves."""

    async def open(self, entity_id: str) -> None:
        """Open one logical valve."""

    async def close(self, entity_id: str) -> None:
        """Close one logical valve."""

    async def is_open(self, entity_id: str) -> bool:
        """Return whether feedback reports the valve open."""


class MeterPort(Protocol):
    """Read a normalized cumulative water total."""

    async def read_liters(self) -> float:
        """Return the current cumulative total in liters."""


class FlowPort(Protocol):
    """Read normalized instantaneous irrigation flow."""

    async def read_l_min(self) -> float:
        """Return the current flow in liters per minute."""


class ClockPort(Protocol):
    """Provide elapsed-time waits without coupling domain logic to HA."""

    async def sleep(self, seconds: float) -> None:
        """Wait for elapsed seconds."""

    def monotonic(self) -> float:
        """Return a monotonic timestamp for delivered-duration accounting."""


class ValveDidNotOpenError(RuntimeError):
    """Raised when actuator feedback does not confirm an open command."""


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """One exclusive irrigation dose with exactly one target."""

    zone_id: str
    zone_valve: str
    main_valve: str | None
    duration_seconds: float | None = None
    amount_liters: float | None = None
    hard_time_limit_seconds: float | None = None
    meter_failure_strategy: str = "abort"
    estimated_flow_l_min: float | None = None
    start_in_estimated_fallback: bool = False
    settle_seconds: float = 0.0
    managed_zone_valves: tuple[str, ...] = ()
    monitor_interval_seconds: float = 0.0
    minimum_flow_l_min: float | None = None
    maximum_flow_l_min: float | None = None
    flow_grace_seconds: float = 0.0
    on_zone_opening: Callable[[], Awaitable[None]] | None = None
    on_zone_opened: Callable[[], Awaitable[None]] | None = None
    on_progress: Callable[[float, str], Awaitable[None]] | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous targets and volume requests without a hard limit."""
        if (self.duration_seconds is None) == (self.amount_liters is None):
            raise ValueError("Exactly one irrigation target is required")
        if self.amount_liters is not None and self.hard_time_limit_seconds is None:
            raise ValueError("Volume irrigation requires a hard time limit")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Measured result of one irrigation dose."""

    zone_id: str
    delivered_liters: float
    duration_seconds: float
    stopped: bool = False
    safety_violation: str | None = None
    safety_scope: str | None = None
    measurement_quality: str = "measured"
    target_reached: bool = True


@dataclass(slots=True)
class _ExecutionProgress:
    """Latest accounting state, retained when monitoring is interrupted."""

    delivered_liters: float
    measurement_quality: str
    target_reached: bool
    accounted_at: float | None = None


class IrrigationExecutor:
    """Execute one hydraulic dose at a time and always close its valves."""

    def __init__(
        self,
        *,
        actuators: ActuatorPort,
        meter: MeterPort,
        flow: FlowPort | None = None,
        clock: ClockPort,
    ) -> None:
        """Initialize the executor with hardware and timing ports."""
        self._actuators = actuators
        self._meter = meter
        self._flow = flow
        self._clock = clock
        self._lock = asyncio.Lock()

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a request and attribute measured or explicitly estimated water."""
        async with self._lock:
            time_limit = request.duration_seconds or request.hard_time_limit_seconds
            if time_limit is None:
                raise ValueError("An execution time limit is required")
            using_estimated_fallback = request.start_in_estimated_fallback
            meter_start_liters: float | None = None
            if not using_estimated_fallback:
                try:
                    meter_start_liters = await self._meter.read_liters()
                except Exception:
                    if (
                        request.amount_liters is None
                        or request.meter_failure_strategy != "estimated_time_fallback"
                        or request.estimated_flow_l_min is None
                        or request.estimated_flow_l_min <= 0
                    ):
                        raise
                    using_estimated_fallback = True
            zone_closed = False
            zone_open_confirmed = False
            stopped = False
            watering_started_at: float | None = None
            delivered_duration_seconds = time_limit
            progress = _ExecutionProgress(
                delivered_liters=0.0,
                measurement_quality=("estimated" if using_estimated_fallback else "measured"),
                target_reached=request.duration_seconds is not None,
            )
            violations: list[str] = []
            safety_scope: str | None = None
            execution_error: Exception | None = None
            deadline_expired = False
            operation_started_at = (
                self._clock.monotonic() if request.amount_liters is not None else None
            )
            deadline = (
                operation_started_at + time_limit if operation_started_at is not None else None
            )
            try:
                try:
                    if request.amount_liters is not None:
                        if deadline is None:
                            raise RuntimeError("Volume irrigation deadline is missing")
                        async with asyncio.timeout(max(0.0, deadline - self._clock.monotonic())):
                            if request.main_valve is not None:
                                await self._open_and_confirm(request.main_valve)
                            if request.on_zone_opening is not None:
                                await request.on_zone_opening()
                            watering_started_at = self._clock.monotonic()
                            progress.accounted_at = watering_started_at
                            await self._open_and_confirm(request.zone_valve)
                            zone_open_confirmed = True
                            if request.on_zone_opened is not None:
                                await request.on_zone_opened()
                            safety_scope = await self._water_and_monitor(
                                request,
                                violations,
                                deadline,
                                meter_start_liters,
                                progress,
                            )
                    else:
                        if request.main_valve is not None:
                            await self._open_and_confirm(request.main_valve)
                        if request.on_zone_opening is not None:
                            await request.on_zone_opening()
                        watering_started_at = self._clock.monotonic()
                        progress.accounted_at = watering_started_at
                        deadline = watering_started_at + time_limit
                        await self._open_and_confirm(request.zone_valve)
                        zone_open_confirmed = True
                        if request.on_zone_opened is not None:
                            await request.on_zone_opened()
                        safety_scope = await self._water_and_monitor(
                            request,
                            violations,
                            deadline,
                            meter_start_liters,
                            progress,
                        )
                except TimeoutError:
                    deadline_expired = True
                    self._record_hard_timeout(request, violations, progress)
                if request.amount_liters is not None or violations:
                    elapsed_started_at = (
                        watering_started_at
                        if watering_started_at is not None
                        else operation_started_at
                    )
                    delivered_duration_seconds = min(
                        time_limit,
                        0.0
                        if elapsed_started_at is None
                        else max(0.0, self._clock.monotonic() - elapsed_started_at),
                    )
                try:
                    if request.amount_liters is not None and deadline is not None:
                        async with asyncio.timeout(max(0.0, deadline - self._clock.monotonic())):
                            await self._actuators.close(request.zone_valve)
                    else:
                        await self._actuators.close(request.zone_valve)
                    zone_closed = True
                except TimeoutError:
                    deadline_expired = True
                    self._record_hard_timeout(request, violations, progress)
                except Exception as err:  # noqa: BLE001
                    violations.append(f"Could not close {request.zone_valve}: {err}")
                    safety_scope = safety_scope or "zone"
            except asyncio.CancelledError:
                stopped = True
                self._capture_estimated_progress(request, progress)
                elapsed_started_at = (
                    watering_started_at if watering_started_at is not None else operation_started_at
                )
                delivered_duration_seconds = (
                    0.0
                    if elapsed_started_at is None
                    else min(
                        time_limit,
                        max(0.0, self._clock.monotonic() - elapsed_started_at),
                    )
                )
            except Exception as err:  # noqa: BLE001
                execution_error = err
                elapsed_started_at = (
                    watering_started_at if watering_started_at is not None else operation_started_at
                )
                if elapsed_started_at is not None:
                    delivered_duration_seconds = min(
                        time_limit,
                        max(0.0, self._clock.monotonic() - elapsed_started_at),
                    )
            finally:
                cleanup_entities = [] if zone_closed else [request.zone_valve]
                if request.main_valve is not None:
                    cleanup_entities.append(request.main_valve)
                cleanup_errors = await self._close_with_shared_feedback_budget(
                    cleanup_entities,
                    budget_seconds=CLEANUP_FEEDBACK_BUDGET_SECONDS,
                )
                for entity_id, cleanup_error in cleanup_errors.items():
                    if entity_id == request.zone_valve:
                        violations.append(f"Could not close {request.zone_valve}: {cleanup_error}")
                        safety_scope = safety_scope or "zone"
                    else:
                        violations.append(f"Could not close {entity_id}: {cleanup_error}")
                        safety_scope = "installation"

            if not zone_open_confirmed and execution_error is not None:
                raise execution_error
            if watering_started_at is None:
                if execution_error is not None:
                    raise execution_error
                if violations and not deadline_expired:
                    raise RuntimeError("; ".join(violations))

            await self._clock.sleep(request.settle_seconds)
            if progress.measurement_quality == "measured" and meter_start_liters is not None:
                try:
                    meter_end_liters = await self._meter.read_liters()
                except Exception as err:  # noqa: BLE001
                    if request.amount_liters is None:
                        execution_error = execution_error or err
                else:
                    progress.delivered_liters = max(0.0, meter_end_liters - meter_start_liters)
            if execution_error is not None:
                violations.append(str(execution_error))

            return ExecutionResult(
                zone_id=request.zone_id,
                delivered_liters=progress.delivered_liters,
                duration_seconds=delivered_duration_seconds,
                stopped=stopped,
                safety_violation="; ".join(dict.fromkeys(violations)) or None,
                safety_scope=safety_scope,
                measurement_quality=progress.measurement_quality,
                target_reached=progress.target_reached,
            )

    async def _water_and_monitor(
        self,
        request: ExecutionRequest,
        violations: list[str],
        deadline: float,
        meter_start_liters: float | None,
        progress: _ExecutionProgress,
    ) -> str | None:
        """Water for the requested duration while enforcing valve exclusivity."""
        if request.amount_liters is None and request.monitor_interval_seconds <= 0:
            await self._clock.sleep(max(0.0, deadline - self._clock.monotonic()))
            return None

        watering_started_at = self._clock.monotonic()
        while self._clock.monotonic() < deadline:
            interval = request.monitor_interval_seconds or 1.0
            step = min(interval, max(0.0, deadline - self._clock.monotonic()))
            if (
                request.amount_liters is not None
                and progress.measurement_quality == "estimated"
                and request.estimated_flow_l_min
            ):
                estimated_seconds_to_target = (
                    max(0.0, request.amount_liters - progress.delivered_liters)
                    * 60
                    / request.estimated_flow_l_min
                )
                step = min(step, estimated_seconds_to_target)
            await self._clock.sleep(step)
            if request.amount_liters is not None and self._clock.monotonic() >= deadline:
                self._record_hard_timeout(request, violations, progress)
                return None
            if not await self._actuators.is_open(request.zone_valve):
                violations.append(f"{request.zone_valve} closed unexpectedly")
                progress.target_reached = False
                return "zone"
            if request.amount_liters is not None and self._clock.monotonic() >= deadline:
                self._record_hard_timeout(request, violations, progress)
                return None
            for entity_id in request.managed_zone_valves:
                if entity_id == request.zone_valve:
                    continue
                if await self._actuators.is_open(entity_id):
                    violations.append(f"{entity_id} opened unexpectedly")
                    try:
                        await self._actuators.close(entity_id)
                    except Exception as err:  # noqa: BLE001
                        violations.append(f"Could not close {entity_id}: {err}")
                    progress.target_reached = False
                    return "installation"
                if request.amount_liters is not None and self._clock.monotonic() >= deadline:
                    self._record_hard_timeout(request, violations, progress)
                    return None
            if self._flow is not None and (
                request.minimum_flow_l_min is not None or request.maximum_flow_l_min is not None
            ):
                elapsed = self._clock.monotonic() - watering_started_at
                if elapsed >= request.flow_grace_seconds:
                    try:
                        flow_l_min = await self._flow.read_l_min()
                    except Exception as err:  # noqa: BLE001
                        violations.append(f"Flow safety unavailable: {err}")
                        progress.target_reached = False
                        return "installation"
                    if request.amount_liters is not None and self._clock.monotonic() >= deadline:
                        self._record_hard_timeout(request, violations, progress)
                        return None
                    if (
                        request.maximum_flow_l_min is not None
                        and flow_l_min > request.maximum_flow_l_min
                    ):
                        violations.append(
                            f"Flow {flow_l_min} L/min exceeds maximum "
                            f"{request.maximum_flow_l_min} L/min"
                        )
                        progress.target_reached = False
                        return "installation"
                    if (
                        request.minimum_flow_l_min is not None
                        and flow_l_min < request.minimum_flow_l_min
                    ):
                        violations.append(
                            f"Flow {flow_l_min} L/min is below minimum "
                            f"{request.minimum_flow_l_min} L/min"
                        )
                        progress.target_reached = False
                        return "zone"

            if request.amount_liters is not None:
                if progress.measurement_quality == "measured":
                    try:
                        current_liters = await self._meter.read_liters()
                    except Exception as err:  # noqa: BLE001
                        if request.meter_failure_strategy != "estimated_time_fallback":
                            violations.append(f"Water meter failed during irrigation: {err}")
                            progress.target_reached = False
                            return None
                        if (
                            request.estimated_flow_l_min is None
                            or request.estimated_flow_l_min <= 0
                        ):
                            violations.append(
                                "Water meter failed and no flow profile is configured"
                            )
                            progress.target_reached = False
                            return None
                        progress.measurement_quality = "estimated"
                        self._capture_estimated_progress(request, progress)
                    else:
                        if meter_start_liters is None:
                            raise RuntimeError("Volume irrigation meter baseline is missing")
                        progress.delivered_liters = max(0.0, current_liters - meter_start_liters)
                        progress.accounted_at = self._clock.monotonic()
                else:
                    if request.estimated_flow_l_min is None or request.estimated_flow_l_min <= 0:
                        raise RuntimeError("Estimated fallback flow is missing")
                    self._capture_estimated_progress(request, progress)
                if self._clock.monotonic() >= deadline:
                    self._record_hard_timeout(request, violations, progress)
                    return None
                if request.on_progress is not None:
                    await request.on_progress(
                        max(0.0, request.amount_liters - progress.delivered_liters),
                        progress.measurement_quality,
                    )
                if self._clock.monotonic() >= deadline:
                    self._record_hard_timeout(request, violations, progress)
                    return None
                if progress.delivered_liters >= request.amount_liters:
                    progress.target_reached = True
                    return None
        if request.amount_liters is not None:
            self._record_hard_timeout(request, violations, progress)
        return None

    def _record_hard_timeout(
        self,
        request: ExecutionRequest,
        violations: list[str],
        progress: _ExecutionProgress,
    ) -> None:
        """Mark an unreached volume target at its absolute deadline."""
        self._capture_estimated_progress(request, progress)
        progress.target_reached = False
        if request.amount_liters is not None:
            violations.append("Hard time limit reached before volume target")

    def _capture_estimated_progress(
        self,
        request: ExecutionRequest,
        progress: _ExecutionProgress,
    ) -> None:
        """Account estimated water elapsed since the latest durable observation."""
        if (
            progress.measurement_quality != "estimated"
            or request.estimated_flow_l_min is None
            or request.estimated_flow_l_min <= 0
            or progress.accounted_at is None
        ):
            return
        now = self._clock.monotonic()
        progress.delivered_liters += (
            max(0.0, now - progress.accounted_at) * request.estimated_flow_l_min / 60
        )
        progress.accounted_at = now

    async def _open_and_confirm(self, entity_id: str) -> None:
        """Open one actuator and reject missing feedback."""
        await self._actuators.open(entity_id)
        if not await self._actuators.is_open(entity_id):
            raise ValveDidNotOpenError(entity_id)

    async def _close_with_shared_feedback_budget(
        self,
        entity_ids: list[str],
        *,
        budget_seconds: float,
    ) -> dict[str, BaseException]:
        """Start every fail-safe close and share one bounded feedback budget.

        The water-runtime deadline determines when closure starts. This separate
        budget only bounds confirmation that all close commands took effect.
        """
        tasks = {
            entity_id: asyncio.create_task(self._actuators.close(entity_id))
            for entity_id in dict.fromkeys(entity_ids)
        }
        if not tasks:
            return {}
        done, pending = await asyncio.wait(tasks.values(), timeout=budget_seconds)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        errors: dict[str, BaseException] = {}
        for entity_id, task in tasks.items():
            if task in pending:
                errors[entity_id] = TimeoutError(
                    "close feedback exceeded the shared cleanup budget"
                )
            elif task in done and (error := task.exception()) is not None:
                errors[entity_id] = error
        return errors
