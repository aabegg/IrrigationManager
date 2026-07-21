"""Safe, serialized execution of irrigation requests."""

import asyncio
from dataclasses import dataclass
from typing import Protocol


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
    """One timed, exclusive irrigation dose."""

    zone_id: str
    zone_valve: str
    main_valve: str | None
    duration_seconds: float
    settle_seconds: float = 0.0
    managed_zone_valves: tuple[str, ...] = ()
    monitor_interval_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Measured result of one irrigation dose."""

    zone_id: str
    delivered_liters: float
    duration_seconds: float
    stopped: bool = False
    safety_violation: str | None = None


class IrrigationExecutor:
    """Execute one hydraulic dose at a time and always close its valves."""

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
        """Execute a timed request and attribute its cumulative meter delta."""
        async with self._lock:
            meter_start_liters = await self._meter.read_liters()
            zone_closed = False
            stopped = False
            watering_started_at: float | None = None
            delivered_duration_seconds = request.duration_seconds
            violations: list[str] = []
            execution_error: Exception | None = None
            try:
                if request.main_valve is not None:
                    await self._open_and_confirm(request.main_valve)
                await self._open_and_confirm(request.zone_valve)
                watering_started_at = self._clock.monotonic()
                await self._water_and_monitor(request, violations)
                if violations:
                    delivered_duration_seconds = min(
                        request.duration_seconds,
                        max(0.0, self._clock.monotonic() - watering_started_at),
                    )
                try:
                    await self._actuators.close(request.zone_valve)
                    zone_closed = True
                except Exception as err:  # noqa: BLE001
                    violations.append(f"Could not close {request.zone_valve}: {err}")
            except asyncio.CancelledError:
                stopped = True
                delivered_duration_seconds = (
                    0.0
                    if watering_started_at is None
                    else min(
                        request.duration_seconds,
                        max(0.0, self._clock.monotonic() - watering_started_at),
                    )
                )
            except Exception as err:  # noqa: BLE001
                execution_error = err
            finally:
                if not zone_closed:
                    try:
                        await self._actuators.close(request.zone_valve)
                    except Exception as err:  # noqa: BLE001
                        violations.append(f"Could not close {request.zone_valve}: {err}")
                if request.main_valve is not None:
                    try:
                        await self._actuators.close(request.main_valve)
                    except Exception as err:  # noqa: BLE001
                        violations.append(f"Could not close {request.main_valve}: {err}")

            if watering_started_at is None:
                if execution_error is not None:
                    raise execution_error
                if violations:
                    raise RuntimeError("; ".join(violations))

            await self._clock.sleep(request.settle_seconds)
            meter_end_liters = await self._meter.read_liters()
            if execution_error is not None:
                violations.append(str(execution_error))

            return ExecutionResult(
                zone_id=request.zone_id,
                delivered_liters=max(0.0, meter_end_liters - meter_start_liters),
                duration_seconds=delivered_duration_seconds,
                stopped=stopped,
                safety_violation="; ".join(dict.fromkeys(violations)) or None,
            )

    async def _water_and_monitor(self, request: ExecutionRequest, violations: list[str]) -> None:
        """Water for the requested duration while enforcing valve exclusivity."""
        if request.monitor_interval_seconds <= 0:
            await self._clock.sleep(request.duration_seconds)
            return

        remaining = request.duration_seconds
        while remaining > 0:
            step = min(request.monitor_interval_seconds, remaining)
            await self._clock.sleep(step)
            remaining -= step
            if not await self._actuators.is_open(request.zone_valve):
                violations.append(f"{request.zone_valve} closed unexpectedly")
                return
            for entity_id in request.managed_zone_valves:
                if entity_id == request.zone_valve:
                    continue
                if await self._actuators.is_open(entity_id):
                    violations.append(f"{entity_id} opened unexpectedly")
                    try:
                        await self._actuators.close(entity_id)
                    except Exception as err:  # noqa: BLE001
                        violations.append(f"Could not close {entity_id}: {err}")
                    return

    async def _open_and_confirm(self, entity_id: str) -> None:
        """Open one actuator and reject missing feedback."""
        await self._actuators.open(entity_id)
        if not await self._actuators.is_open(entity_id):
            raise ValveDidNotOpenError(entity_id)
