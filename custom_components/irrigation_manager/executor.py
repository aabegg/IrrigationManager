"""Safe, serialized execution of irrigation requests."""

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

CLEANUP_FEEDBACK_BUDGET_SECONDS = 5.0


class ActuatorPort(Protocol):
    """Control and observe logical irrigation valves."""

    async def open(self, entity_id: str, *, verify: bool = True) -> None:
        """Open one logical valve."""

    async def close(self, entity_id: str, *, verify: bool = True) -> None:
        """Close one logical valve."""

    async def is_open(self, entity_id: str) -> bool:
        """Return whether feedback reports the valve open."""


class MeterPort(Protocol):
    """Read a normalized cumulative water total."""

    async def read_liters(self) -> float:
        """Return the current cumulative total in liters."""


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
    """One exclusive irrigation operation with exactly one target."""

    zone_id: str
    zone_valve: str
    main_valve: str | None
    duration_seconds: float | None = None
    amount_liters: float | None = None
    hard_time_limit_seconds: float | None = None
    settle_seconds: float = 0.0
    managed_zone_valves: tuple[str, ...] = ()
    monitor_interval_seconds: float = 0.0
    on_zone_opening: Callable[[], Awaitable[None]] | None = None
    on_zone_opened: Callable[[], Awaitable[None]] | None = None
    on_zone_closed: Callable[[], Awaitable[None]] | None = None
    on_progress: Callable[[float, str], Awaitable[None]] | None = None
    require_meter_progress: bool = False
    on_actuator_command: Callable[[str, bool], Awaitable[None]] | None = None
    feedback_bypass_entities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject ambiguous targets and volume requests without a hard limit."""
        if (self.duration_seconds is None) == (self.amount_liters is None):
            raise ValueError("Exactly one irrigation target is required")
        if self.amount_liters is not None and self.hard_time_limit_seconds is None:
            raise ValueError("Volume irrigation requires a hard time limit")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Measured result of one irrigation operation."""

    zone_id: str
    delivered_liters: float
    duration_seconds: float
    stopped: bool = False
    safety_violation: str | None = None
    safety_scope: str | None = None
    measurement_quality: str = "measured"
    target_reached: bool = True
    opening_latency_seconds: float = 0.0
    post_run_liters: float = 0.0


@dataclass(slots=True)
class _ExecutionProgress:
    """Latest cumulative-meter progress retained on interruption."""

    delivered_liters: float = 0.0
    target_reached: bool = False
    watering_started_at: float | None = None
    opening_latency_seconds: float = 0.0
    zone_open_confirmed: bool = False


class IrrigationExecutor:
    """Execute one hydraulic operation at a time and always close its valves."""

    def __init__(
        self,
        *,
        actuators: ActuatorPort,
        meter: MeterPort,
        clock: ClockPort,
    ) -> None:
        """Initialize the executor with hardware and timing ports."""
        self._actuators = actuators
        self._meter = meter
        self._clock = clock
        self._lock = asyncio.Lock()

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a request and attribute only cumulative-meter water."""
        async with self._lock:
            time_limit = request.duration_seconds or request.hard_time_limit_seconds
            if time_limit is None:
                raise ValueError("An execution time limit is required")

            operation_started_at = (
                self._clock.monotonic() if request.amount_liters is not None else None
            )
            deadline = (
                operation_started_at + time_limit if operation_started_at is not None else None
            )
            meter_start_liters: float | None = None
            try:
                if deadline is not None:
                    async with asyncio.timeout(max(0.0, deadline - self._clock.monotonic())):
                        meter_start_liters = await self._meter.read_liters()
                else:
                    meter_start_liters = await self._meter.read_liters()
                self._validate_meter_reading(meter_start_liters)
            except (Exception, TimeoutError) as err:
                if request.amount_liters is not None or request.require_meter_progress:
                    await self._close_in_order(
                        [
                            entity_id
                            for entity_id in (request.zone_valve, request.main_valve)
                            if entity_id is not None
                        ],
                        budget_seconds=CLEANUP_FEEDBACK_BUDGET_SECONDS,
                        on_command=request.on_actuator_command,
                        feedback_bypass_entities=request.feedback_bypass_entities,
                    )
                    raise RuntimeError(f"Water meter is unavailable: {err}") from err
            progress = _ExecutionProgress(target_reached=request.duration_seconds is not None)
            violations: list[str] = []
            safety_scope: str | None = None
            execution_error: Exception | None = None
            stopped = False
            deadline_expired = False
            try:
                try:
                    if request.amount_liters is not None:
                        if deadline is None:
                            raise RuntimeError("Volume irrigation deadline is missing")
                        async with asyncio.timeout(max(0.0, deadline - self._clock.monotonic())):
                            safety_scope = await self._open_and_water(
                                request,
                                deadline=deadline,
                                meter_start_liters=meter_start_liters,
                                progress=progress,
                                violations=violations,
                            )
                    else:
                        await self._open_valves(request, progress)
                        if progress.watering_started_at is None:
                            raise RuntimeError("Irrigation start checkpoint is missing")
                        deadline = progress.watering_started_at + time_limit
                        safety_scope = await self._water_and_monitor(
                            request,
                            deadline=deadline,
                            meter_start_liters=meter_start_liters,
                            progress=progress,
                            violations=violations,
                        )
                except TimeoutError:
                    deadline_expired = True
                    self._record_hard_timeout(request, violations, progress)

            except asyncio.CancelledError:
                stopped = True
            except Exception as err:  # noqa: BLE001
                execution_error = err
            finally:
                cleanup_entities = [request.zone_valve]
                if request.main_valve is not None:
                    cleanup_entities.append(request.main_valve)
                cleanup_errors = await self._close_in_order(
                    cleanup_entities,
                    budget_seconds=CLEANUP_FEEDBACK_BUDGET_SECONDS,
                    on_command=request.on_actuator_command,
                    feedback_bypass_entities=request.feedback_bypass_entities,
                    zone_valve=request.zone_valve,
                    on_zone_closed=request.on_zone_closed,
                )
                for entity_id, cleanup_error in cleanup_errors.items():
                    violations.append(f"Could not close {entity_id}: {cleanup_error}")
                    safety_scope = (
                        "installation"
                        if entity_id != request.zone_valve
                        else safety_scope or "zone"
                    )

            if not progress.zone_open_confirmed and execution_error is not None:
                raise execution_error
            if progress.watering_started_at is None:
                if execution_error is not None:
                    raise execution_error
                if violations and not deadline_expired:
                    raise RuntimeError("; ".join(violations))

            ended_at = self._clock.monotonic()
            elapsed_started_at = (
                progress.watering_started_at
                if progress.watering_started_at is not None
                else operation_started_at
            )
            delivered_duration_seconds = min(
                time_limit,
                0.0 if elapsed_started_at is None else max(0.0, ended_at - elapsed_started_at),
            )
            if not stopped:
                await self._clock.sleep(request.settle_seconds)
            try:
                meter_end_liters = await self._meter.read_liters()
                if meter_start_liters is None:
                    raise RuntimeError("Water meter start reading was unavailable")
                progress.delivered_liters = self._meter_delta(
                    start_liters=meter_start_liters,
                    current_liters=meter_end_liters,
                )
            except Exception as err:  # noqa: BLE001
                if request.amount_liters is not None or request.require_meter_progress:
                    violations.append(f"Water meter failed during irrigation: {err}")
                    progress.target_reached = False
                    safety_scope = safety_scope or "installation"
                else:
                    progress.delivered_liters = 0.0

            meter_progress_required = (
                request.amount_liters is not None or request.require_meter_progress
            )
            if (
                not stopped
                and progress.zone_open_confirmed
                and meter_progress_required
                and progress.delivered_liters <= 0
            ):
                violations.append("No cumulative meter progress during irrigation")
                progress.target_reached = False
                safety_scope = safety_scope or "zone"
            if execution_error is not None:
                violations.append(str(execution_error))

            return ExecutionResult(
                zone_id=request.zone_id,
                delivered_liters=progress.delivered_liters,
                duration_seconds=delivered_duration_seconds,
                stopped=stopped,
                safety_violation="; ".join(dict.fromkeys(violations)) or None,
                safety_scope=safety_scope,
                measurement_quality=(
                    "measured" if meter_start_liters is not None else "unavailable"
                ),
                target_reached=progress.target_reached,
                opening_latency_seconds=progress.opening_latency_seconds,
            )

    async def _open_and_water(
        self,
        request: ExecutionRequest,
        *,
        deadline: float,
        meter_start_liters: float | None,
        progress: _ExecutionProgress,
        violations: list[str],
    ) -> str | None:
        """Open valves and deliver water within one absolute volume deadline."""
        await self._open_valves(request, progress)
        return await self._water_and_monitor(
            request,
            deadline=deadline,
            meter_start_liters=meter_start_liters,
            progress=progress,
            violations=violations,
        )

    async def _open_valves(self, request: ExecutionRequest, progress: _ExecutionProgress) -> None:
        """Open the main valve before issuing the zone-valve command."""
        if request.main_valve is not None:
            await self._open_and_confirm(request, request.main_valve)
        if request.on_zone_opening is not None:
            await request.on_zone_opening()
        progress.watering_started_at = self._clock.monotonic()
        await self._open_and_confirm(request, request.zone_valve)
        progress.opening_latency_seconds = self._clock.monotonic() - progress.watering_started_at
        progress.zone_open_confirmed = True
        if request.on_zone_opened is not None:
            await request.on_zone_opened()

    async def _water_and_monitor(
        self,
        request: ExecutionRequest,
        *,
        deadline: float,
        meter_start_liters: float | None,
        progress: _ExecutionProgress,
        violations: list[str],
    ) -> str | None:
        """Deliver irrigation while enforcing exclusivity and meter targets."""
        if request.amount_liters is None and request.monitor_interval_seconds <= 0:
            await self._clock.sleep(max(0.0, deadline - self._clock.monotonic()))
            return None

        while self._clock.monotonic() < deadline:
            interval = request.monitor_interval_seconds or 1.0
            await self._clock.sleep(min(interval, max(0.0, deadline - self._clock.monotonic())))
            if request.amount_liters is not None and self._clock.monotonic() >= deadline:
                self._record_hard_timeout(request, violations, progress)
                return None
            if (
                request.zone_valve not in request.feedback_bypass_entities
                and not await self._actuators.is_open(request.zone_valve)
            ):
                violations.append(f"{request.zone_valve} closed unexpectedly")
                progress.target_reached = False
                return "zone"
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

            if request.amount_liters is None:
                continue
            if meter_start_liters is None:
                raise RuntimeError("Volume irrigation meter baseline is unavailable")
            try:
                current_liters = await self._meter.read_liters()
                progress.delivered_liters = self._meter_delta(
                    start_liters=meter_start_liters,
                    current_liters=current_liters,
                )
            except Exception as err:  # noqa: BLE001
                violations.append(f"Water meter failed during irrigation: {err}")
                progress.target_reached = False
                return "installation"
            if request.on_progress is not None:
                await request.on_progress(
                    max(0.0, request.amount_liters - progress.delivered_liters),
                    "measured",
                )
            if progress.delivered_liters >= request.amount_liters:
                progress.target_reached = True
                return None

        if request.amount_liters is not None:
            self._record_hard_timeout(request, violations, progress)
        return None

    @staticmethod
    def _record_hard_timeout(
        request: ExecutionRequest,
        violations: list[str],
        progress: _ExecutionProgress,
    ) -> None:
        """Mark an unreached volume target at its absolute deadline."""
        progress.target_reached = False
        if request.amount_liters is not None:
            violations.append("Hard time limit reached before volume target")

    @staticmethod
    def _validate_meter_reading(reading_liters: float) -> None:
        """Reject values that cannot represent a cumulative physical meter."""
        if not math.isfinite(reading_liters) or reading_liters < 0:
            raise ValueError("Water meter reading is not plausible")

    @classmethod
    def _meter_delta(cls, *, start_liters: float, current_liters: float) -> float:
        """Return measured irrigation water without accepting meter regression."""
        cls._validate_meter_reading(start_liters)
        cls._validate_meter_reading(current_liters)
        if current_liters < start_liters:
            raise ValueError("Water meter regressed during irrigation")
        return current_liters - start_liters

    async def _open_and_confirm(self, request: ExecutionRequest, entity_id: str) -> None:
        """Open one actuator and reject missing feedback."""
        await self._notify_actuator_command(request, entity_id, True)
        bypass = entity_id in request.feedback_bypass_entities
        await self._actuators.open(entity_id, verify=not bypass)
        if not bypass and not await self._actuators.is_open(entity_id):
            raise ValveDidNotOpenError(entity_id)

    async def _close_zone(self, request: ExecutionRequest) -> None:
        """Close the active zone before the main-valve cleanup phase."""
        await self._notify_actuator_command(request, request.zone_valve, False)
        await self._actuators.close(
            request.zone_valve,
            verify=request.zone_valve not in request.feedback_bypass_entities,
        )

    async def _close_in_order(
        self,
        entity_ids: list[str],
        *,
        budget_seconds: float,
        on_command: Callable[[str, bool], Awaitable[None]] | None = None,
        feedback_bypass_entities: tuple[str, ...] = (),
        zone_valve: str | None = None,
        on_zone_closed: Callable[[], Awaitable[None]] | None = None,
    ) -> dict[str, BaseException]:
        """Command zone then main closure, each with a cleanup-only bound."""
        errors: dict[str, BaseException] = {}
        for entity_id in dict.fromkeys(entity_ids):
            try:
                async with asyncio.timeout(budget_seconds):
                    if on_command is not None:
                        await on_command(entity_id, False)
                    await self._actuators.close(
                        entity_id,
                        verify=entity_id not in feedback_bypass_entities,
                    )
                    if entity_id == zone_valve and on_zone_closed is not None:
                        await on_zone_closed()
            except BaseException as err:  # noqa: BLE001
                errors[entity_id] = err
        return errors

    @staticmethod
    async def _notify_actuator_command(
        request: ExecutionRequest, entity_id: str, open_: bool
    ) -> None:
        """Publish command intent before feedback can race the service response."""
        if request.on_actuator_command is not None:
            await request.on_actuator_command(entity_id, open_)
