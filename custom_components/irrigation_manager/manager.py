"""Runtime orchestration for one irrigation installation."""

import asyncio
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event

from .adapters import (
    HomeAssistantActuators,
    HomeAssistantClock,
    HomeAssistantFlow,
    HomeAssistantMeter,
)
from .const import (
    CONF_FLOW_GRACE_SECONDS,
    CONF_FLOW_MAX_AGE_SECONDS,
    CONF_FLOW_SENSOR,
    CONF_LEAK_DURATION_SECONDS,
    CONF_LEAK_FLOW_THRESHOLD,
    CONF_LEAK_MONITORING,
    CONF_MAIN_VALVE,
    CONF_MAX_DOSE_AMOUNT,
    CONF_MAX_DOSE_DURATION,
    CONF_MAX_FLOW,
    CONF_METER_FAILURE_STRATEGY,
    CONF_MIN_FLOW,
    CONF_SOAK_DURATION,
    CONF_WATER_METER,
    CONF_ZONE_VALVE,
    METER_FAILURE_ABORT,
    METER_FAILURE_ESTIMATED_TIME_FALLBACK,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import IrrigationCoordinator
from .executor import ExecutionRequest, ExecutionResult, IrrigationExecutor
from .leak_monitor import LeakObservation
from .models import (
    ActiveExecutionState,
    InstallationSnapshot,
    IrrigationExecutionState,
    ManualIrrigationRequest,
    StoredInstallationState,
)
from .scheduler import dose_target, select_manual_request
from .storage import IrrigationStore


class _StaleRequestClaimError(HomeAssistantError):
    """Raised when a selected request changed before its durable claim."""


class IrrigationManager:
    """Coordinate manual execution, persistence, and published state."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: IrrigationCoordinator,
        store: IrrigationStore,
        stored_state: StoredInstallationState,
    ) -> None:
        """Initialize one installation runtime."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._store = store
        self._stored_state = stored_state
        self._has_meter = bool(entry.data.get(CONF_WATER_METER))
        self._actuators = HomeAssistantActuators(hass)
        self._meter = HomeAssistantMeter(hass, entry.data.get(CONF_WATER_METER))
        flow_entity_id = entry.data.get(CONF_FLOW_SENSOR)
        self._flow = (
            HomeAssistantFlow(
                hass,
                flow_entity_id,
                self._optional_float(entry.data, CONF_FLOW_MAX_AGE_SECONDS) or 30.0,
            )
            if isinstance(flow_entity_id, str)
            else None
        )
        self._executor = IrrigationExecutor(
            actuators=self._actuators,
            meter=self._meter,
            flow=self._flow,
            clock=HomeAssistantClock(),
        )
        self._active_task: asyncio.Task[ExecutionResult] | None = None
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._queue_event = asyncio.Event()
        self._terminal_events: dict[str, asyncio.Event] = {}
        self._request_errors: dict[str, Exception] = {}
        self._cancel_requested: set[str] = set()
        self._pause_requested: set[str] = set()
        self._watering = False
        self._command_lock = asyncio.Lock()
        self._leak_threshold_l_min = (
            self._optional_float(entry.data, CONF_LEAK_FLOW_THRESHOLD) or 0.5
        )
        self._leak_duration_seconds = (
            self._optional_float(entry.data, CONF_LEAK_DURATION_SECONDS) or 30.0
        )
        self._leak_monitoring = (
            self._flow is not None and entry.data.get(CONF_LEAK_MONITORING, True) is not False
        )
        self._leak_observation: LeakObservation | None = None
        self._leak_confirmation_task: asyncio.Task[None] | None = None
        self._leak_application_task: asyncio.Task[None] | None = None
        self._flow_event_tasks: set[asyncio.Task[None]] = set()
        self._unsubscribe_flow: Callable[[], None] | None = None
        self._shutting_down = False
        self._active_target_type: str | None = None
        self._active_target_value: float | None = None
        self._active_remaining_value: float | None = None
        self._active_measurement_quality: str | None = None

    async def async_initialize(self) -> None:
        """Close configured valves left open across a restart."""
        entity_ids = self._zone_valves()
        active_could_have_flowed = False
        if active := self._stored_state.active_execution:
            zone_state = self._hass.states.get(active.zone_valve)
            main_state = (
                self._hass.states.get(active.main_valve) if active.main_valve is not None else None
            )
            active_could_have_flowed = (
                zone_state is not None
                and zone_state.state in {"on", "open"}
                and (
                    active.main_valve is None
                    or (main_state is not None and main_state.state in {"on", "open"})
                )
            )
            entity_ids.append(active.zone_valve)
            if active.main_valve is not None:
                entity_ids.append(active.main_valve)
        if main_valve := self._entry.data.get(CONF_MAIN_VALVE):
            entity_ids.append(main_valve)
        await self._async_close_entities(list(dict.fromkeys(entity_ids)))
        await self._async_recover_interrupted_execution(could_have_flowed=active_could_have_flowed)
        await self._async_expire_requests()
        await self._async_ensure_idle_meter_baseline()
        if self._leak_monitoring and self._flow is not None:
            flow_entity_id = self._entry.data[CONF_FLOW_SENSOR]
            self._unsubscribe_flow = async_track_state_change_event(
                self._hass,
                flow_entity_id,
                self._flow_state_changed,
            )
            await self._async_consider_current_flow()
        self._publish(status="idle", active_zone_id=None)
        self._dispatcher_task = self._entry.async_create_background_task(
            self._hass,
            self._async_dispatch_requests(),
            "Irrigation Manager manual request dispatcher",
        )

    async def async_shutdown(self) -> None:
        """Stop runtime work and remove all Home Assistant listeners."""
        self._shutting_down = True
        dispatcher_task = self._dispatcher_task
        self._dispatcher_task = None
        if dispatcher_task is not None:
            dispatcher_task.cancel()
        if self._unsubscribe_flow is not None:
            self._unsubscribe_flow()
            self._unsubscribe_flow = None
        confirmation_task = self._leak_confirmation_task
        application_task = self._leak_application_task
        self._cancel_leak_observation()
        if application_task is not None:
            await asyncio.gather(application_task, return_exceptions=True)
        if confirmation_task is not None:
            await asyncio.gather(confirmation_task, return_exceptions=True)
        if dispatcher_task is not None:
            await asyncio.gather(dispatcher_task, return_exceptions=True)
        active_task = self._active_task
        if active_task is not None and not active_task.done():
            active_task.cancel()
            await asyncio.gather(active_task, return_exceptions=True)
        if self._stored_state.active_execution is not None:
            await self._async_recover_interrupted_execution(could_have_flowed=False)
        tasks = tuple(self._flow_event_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @callback
    def _flow_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Schedule event-driven idle-flow evaluation."""
        if self._shutting_down:
            return
        task = self._hass.async_create_task(
            self._async_consider_flow_sample(event.data["new_state"]),
            "Irrigation Manager idle-flow observation",
        )
        self._flow_event_tasks.add(task)
        task.add_done_callback(self._flow_event_tasks.discard)

    async def _async_consider_current_flow(self) -> None:
        """Apply the current flow sample to the idle leak observer."""
        if self._flow is None or self._shutting_down:
            return
        await self._async_consider_flow_sample(
            self._hass.states.get(self._entry.data[CONF_FLOW_SENSOR])
        )

    async def _async_consider_flow_sample(self, state: State | None) -> None:
        """Apply one specific event sample without collapsing intervening states."""
        if self._flow is None or self._shutting_down:
            return
        try:
            flow_l_min = self._flow.read_state_l_min(state)
        except HomeAssistantError:
            async with self._command_lock:
                self._cancel_leak_observation()
            return
        async with self._command_lock:
            if not self._is_idle_for_leak_monitoring():
                self._cancel_leak_observation()
                return
            now = asyncio.get_running_loop().time()
            if flow_l_min <= self._leak_threshold_l_min:
                self._cancel_leak_observation()
                return
            if self._stored_state.installation_safety_lock is not None:
                return
            if self._leak_observation is None:
                self._leak_observation = LeakObservation.start(
                    at=now,
                    flow_l_min=flow_l_min,
                )
                self._leak_confirmation_task = self._hass.async_create_task(
                    self._async_confirm_idle_flow_after_delay(),
                    "Irrigation Manager leak confirmation",
                )
            else:
                self._leak_observation = self._leak_observation.observe(
                    at=now,
                    flow_l_min=flow_l_min,
                )

    async def _async_confirm_idle_flow_after_delay(self) -> None:
        """Confirm a continuous idle-flow observation after its minimum duration."""
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(self._leak_duration_seconds)
            if self._flow is None:
                return
            try:
                flow_l_min = await self._flow.read_l_min()
            except HomeAssistantError:
                return
            async with self._command_lock:
                if (
                    self._leak_confirmation_task is not current_task
                    or not self._is_idle_for_leak_monitoring()
                    or flow_l_min <= self._leak_threshold_l_min
                    or self._leak_observation is None
                ):
                    return
                now = asyncio.get_running_loop().time()
                observation = self._leak_observation.observe(
                    at=now,
                    flow_l_min=flow_l_min,
                )
                confirmed = observation.confirm(
                    at=now,
                    minimum_duration_seconds=self._leak_duration_seconds,
                )
                if confirmed is not None:
                    application_task = self._hass.async_create_task(
                        self._async_apply_idle_flow_lock(
                            flow_l_min=flow_l_min,
                            integrated_liters=confirmed.integrated_liters,
                        ),
                        "Irrigation Manager confirmed leak safety application",
                    )
                    self._leak_application_task = application_task
                    try:
                        await asyncio.shield(application_task)
                    except asyncio.CancelledError:
                        await application_task
                        raise
        except asyncio.CancelledError:
            return
        finally:
            if self._leak_confirmation_task is current_task:
                self._leak_confirmation_task = None
                self._leak_observation = None
            if self._leak_application_task is not None and self._leak_application_task.done():
                self._leak_application_task = None

    async def _async_apply_idle_flow_lock(
        self, *, flow_l_min: float, integrated_liters: float
    ) -> None:
        """Close every known valve, account water, and persist the safety lock."""
        reason = (
            f"Leak detected: idle flow {flow_l_min:g} L/min exceeded "
            f"{self._leak_threshold_l_min:g} L/min for "
            f"{self._leak_duration_seconds:g} seconds"
        )
        self._stored_state = replace(
            self._stored_state,
            installation_safety_lock=reason,
        )
        persistence_errors: list[Exception] = []
        try:
            await self._store.async_save(self._stored_state)
        except Exception as err:  # noqa: BLE001
            persistence_errors.append(err)
        self._publish(status="safety_lock", active_zone_id=None)

        close_error: Exception | None = None
        try:
            await self._async_close_entities(self._all_known_valves())
        except Exception as err:  # noqa: BLE001
            close_error = err

        amount_liters = integrated_liters
        quality = "integrated"
        origin = "flow_sensor"
        new_baseline = self._stored_state.idle_meter_raw_baseline_liters
        if self._has_meter and new_baseline is not None:
            try:
                current_raw_liters = await self._meter.read_raw_liters()
            except HomeAssistantError:
                pass
            else:
                amount_liters = (
                    current_raw_liters - new_baseline
                    if current_raw_liters >= new_baseline
                    else current_raw_liters
                )
                new_baseline = current_raw_liters
                quality = "measured"
                origin = "cumulative_meter"

        if close_error is not None:
            reason = f"{reason}; not all valves could be closed: {close_error}"
        self._stored_state = replace(
            self._stored_state,
            installation_total_liters=(
                self._stored_state.installation_total_liters + amount_liters
            ),
            unassigned_total_liters=(self._stored_state.unassigned_total_liters + amount_liters),
            unassigned_measurement_quality=quality,
            unassigned_measurement_origin=origin,
            idle_meter_raw_baseline_liters=new_baseline,
            installation_safety_lock=reason,
        )
        try:
            await self._store.async_save(self._stored_state)
        except Exception as err:  # noqa: BLE001
            persistence_errors.append(err)
        self._publish(status="safety_lock", active_zone_id=None)
        if len(persistence_errors) == 1:
            raise persistence_errors[0]
        if persistence_errors:
            raise ExceptionGroup(
                "Could not persist confirmed leak safety state", persistence_errors
            )

    def _is_idle_for_leak_monitoring(self) -> bool:
        """Return whether flow cannot belong to an active or settling dose."""
        return (
            not self._watering
            and self._stored_state.active_execution is None
            and (self._active_task is None or self._active_task.done())
        )

    def _cancel_leak_observation(self) -> None:
        """Discard a short artifact or an observation claimed by watering."""
        task = self._leak_confirmation_task
        if (
            self._leak_application_task is None
            and task is not None
            and task is not asyncio.current_task()
        ):
            task.cancel()
            self._leak_confirmation_task = None
        self._leak_observation = None

    def _all_known_valves(self) -> list[str]:
        """Return configured valves plus any valve persisted by an execution."""
        entity_ids = self._zone_valves()
        if main_valve := self._entry.data.get(CONF_MAIN_VALVE):
            entity_ids.append(main_valve)
        if active := self._stored_state.active_execution:
            entity_ids.append(active.zone_valve)
            if active.main_valve is not None:
                entity_ids.append(active.main_valve)
        return list(dict.fromkeys(entity_ids))

    async def _async_ensure_idle_meter_baseline(self) -> None:
        """Persist a raw idle baseline without treating an existing total as use."""
        if not self._has_meter or self._stored_state.idle_meter_raw_baseline_liters is not None:
            return
        try:
            baseline = await self._meter.read_raw_liters()
        except HomeAssistantError:
            return
        self._stored_state = replace(
            self._stored_state,
            idle_meter_raw_baseline_liters=baseline,
        )
        await self._store.async_save(self._stored_state)

    async def _async_refresh_idle_meter_baseline(self) -> None:
        """Exclude the just-finished watering and its settling water from idle use."""
        if not self._has_meter:
            return
        try:
            baseline = await self._meter.read_raw_liters()
        except HomeAssistantError:
            return
        self._stored_state = replace(
            self._stored_state,
            idle_meter_raw_baseline_liters=baseline,
        )
        await self._store.async_save(self._stored_state)

    async def _async_recover_interrupted_execution(self, *, could_have_flowed: bool = True) -> None:
        """Account for a durable active dose after all valves are closed."""
        active = self._stored_state.active_execution
        if active is None:
            return

        delivered_liters = 0.0
        delivered_duration_seconds = 0.0
        quality = "unknown"
        recovery_started_at = active.watering_started_at
        if recovery_started_at is None and active.zone_opening_at is not None and could_have_flowed:
            recovery_started_at = active.zone_opening_at
        if recovery_started_at is not None:
            started_at = datetime.fromisoformat(recovery_started_at)
            delivered_duration_seconds = max(0.0, (datetime.now(UTC) - started_at).total_seconds())
            if not could_have_flowed:
                delivered_duration_seconds = min(
                    delivered_duration_seconds,
                    active.requested_duration_seconds,
                )
        if (
            active.watering_started_at is not None
            and active.fallback_started_at is not None
            and active.estimated_flow_l_min is not None
        ):
            delivered_liters = active.delivered_liters_at_fallback
            if could_have_flowed:
                checkpoint_at = datetime.fromisoformat(
                    active.fallback_checkpoint_at or active.fallback_started_at
                )
                hard_runtime_started_at = datetime.fromisoformat(active.prepared_at)
                elapsed_before_checkpoint = max(
                    0.0,
                    (checkpoint_at - hard_runtime_started_at).total_seconds(),
                )
                hard_limit = active.hard_time_limit_seconds or active.requested_duration_seconds
                fallback_duration_limit = max(0.0, hard_limit - elapsed_before_checkpoint)
                if active.requested_amount_liters is not None:
                    remaining_liters = max(
                        0.0,
                        active.requested_amount_liters - active.delivered_liters_at_fallback,
                    )
                    fallback_duration_limit = min(
                        fallback_duration_limit,
                        remaining_liters * 60 / active.estimated_flow_l_min,
                    )
                fallback_duration = min(
                    max(0.0, (datetime.now(UTC) - checkpoint_at).total_seconds()),
                    fallback_duration_limit,
                )
                delivered_liters += fallback_duration * active.estimated_flow_l_min / 60
            quality = "estimated"
        if (
            quality == "unknown"
            and active.fallback_started_at is None
            and recovery_started_at is not None
            and active.meter_raw_baseline_liters is not None
            and self._has_meter
        ):
            try:
                current_liters = await self._meter.read_raw_liters()
            except HomeAssistantError:
                pass
            else:
                delivered_liters = (
                    current_liters - active.meter_raw_baseline_liters
                    if current_liters >= active.meter_raw_baseline_liters
                    else current_liters
                )
                quality = "measured"
        if (
            quality == "unknown"
            and active.watering_started_at is not None
            and active.estimated_flow_l_min is not None
        ):
            delivered_liters = delivered_duration_seconds * active.estimated_flow_l_min / 60
            quality = "estimated"

        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[active.zone_id] = zone_totals.get(active.zone_id, 0.0) + delivered_liters
        measurement_quality = dict(self._stored_state.zone_measurement_quality)
        last_delivered = dict(self._stored_state.zone_last_delivered_liters)
        last_duration = dict(self._stored_state.zone_last_duration_seconds)
        if recovery_started_at is not None:
            measurement_quality[active.zone_id] = quality
            last_delivered[active.zone_id] = delivered_liters
            last_duration[active.zone_id] = delivered_duration_seconds
        requests = self._stored_state.manual_requests
        executions = self._stored_state.irrigation_executions
        terminal_request_id: str | None = None
        if (
            active.request_id is not None
            and (request := self._request(active.request_id)) is not None
        ):
            delivered_target = (
                delivered_liters if request.target_type == "volume" else delivered_duration_seconds
            )
            remaining = max(0.0, request.remaining_value - delivered_target)
            completed = remaining <= 1e-6
            expired = datetime.fromisoformat(request.expires_at) <= datetime.now(UTC)
            request = replace(
                request,
                remaining_value=0.0 if completed else remaining,
                status="completed" if completed else "expired" if expired else "pending",
                soak_until=None,
                execution_id=request.execution_id if completed else None,
                revision=request.revision + 1,
            )
            requests = self._with_request(request)
            if (
                active.execution_id is not None
                and (execution := self._execution(active.execution_id)) is not None
            ):
                execution = replace(
                    execution,
                    remaining_value=0.0 if completed else remaining,
                    delivered_liters=execution.delivered_liters + delivered_liters,
                    delivered_duration_seconds=(
                        execution.delivered_duration_seconds + delivered_duration_seconds
                    ),
                    status="completed" if completed else "interrupted",
                    ended_at=datetime.now(UTC).isoformat(),
                    result=(
                        "target_reached_during_recovery"
                        if completed
                        else "expired"
                        if expired
                        else "restart"
                    ),
                )
                executions = self._with_execution(execution)
            if completed or expired:
                terminal_request_id = request.request_id
        self._stored_state = replace(
            self._stored_state,
            installation_total_liters=(
                self._stored_state.installation_total_liters + delivered_liters
            ),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=measurement_quality,
            zone_last_delivered_liters=last_delivered,
            zone_last_duration_seconds=last_duration,
            active_execution=None,
            manual_requests=requests,
            irrigation_executions=executions,
        )
        await self._store.async_save(self._stored_state)
        if terminal_request_id is not None:
            self._signal_terminal(terminal_request_id)
        await self._async_refresh_idle_meter_baseline()
        self._publish(status="idle", active_zone_id=None)

    async def _async_close_entities(self, entity_ids: list[str]) -> None:
        """Attempt every requested closure before reporting any failures."""
        errors: list[Exception] = []
        for entity_id in dict.fromkeys(entity_ids):
            try:
                await self._actuators.close(entity_id)
            except Exception as err:  # noqa: BLE001
                errors.append(err)
        if errors:
            raise ExceptionGroup("Could not close all irrigation valves", errors)

    def _zone_valves(self) -> list[str]:
        """Return all logical zone valves configured for this installation."""
        return [
            subentry.data[CONF_ZONE_VALVE]
            for subentry in self._entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        ]

    async def _async_preflight(
        self,
        *,
        target_zone_id: str | None = None,
        ignore_installation_lock: bool = False,
    ) -> None:
        """Prove all managed valves are available and hydraulically closed."""
        if self._stored_state.installation_safety_lock is not None and not ignore_installation_lock:
            raise HomeAssistantError("The irrigation installation has a safety lock")
        if target_zone_id in self._stored_state.zone_safety_locks:
            raise HomeAssistantError("The irrigation zone has a safety lock")
        entity_ids = self._zone_valves()
        if main_valve := self._entry.data.get(CONF_MAIN_VALVE):
            entity_ids.append(main_valve)
        unavailable: list[str] = []
        unexpectedly_open: list[str] = []
        for entity_id in entity_ids:
            state = self._hass.states.get(entity_id)
            if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
                unavailable.append(entity_id)
            elif state.state not in {STATE_OFF, "closed"}:
                unexpectedly_open.append(entity_id)
        if unavailable:
            raise HomeAssistantError(
                f"Irrigation valve state is unavailable: {', '.join(unavailable)}"
            )
        if not unexpectedly_open:
            return

        close_error: Exception | None = None
        try:
            await self._async_close_entities(unexpectedly_open)
        except Exception as err:  # noqa: BLE001
            close_error = err
        self._stored_state = replace(
            self._stored_state,
            emergency_stop=True,
            active_execution=None,
        )
        await self._store.async_save(self._stored_state)
        self._publish(status="emergency_stop", active_zone_id=None)
        error = HomeAssistantError(
            "Unexpectedly open irrigation valve activated the emergency stop"
        )
        if close_error is not None:
            raise error from close_error
        raise error

    async def async_start_manual(
        self,
        *,
        zone_subentry_id: str,
        duration_seconds: float | None,
        amount_liters: float | None,
        hard_time_limit_seconds: float | None,
        expiry_seconds: float = 3600,
        wait_for_completion: bool = True,
    ) -> dict[str, object]:
        """Persist a manual order, dispatch it immediately when possible, and return its ID."""
        async with self._command_lock:
            if self._stored_state.emergency_stop:
                raise HomeAssistantError("The emergency stop is active")
            subentry = self._entry.subentries.get(zone_subentry_id)
            if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
                raise HomeAssistantError("The irrigation zone does not exist")
            if amount_liters is not None and not self._has_meter:
                raise HomeAssistantError("Volume irrigation requires a configured cumulative meter")
            target_type = "volume" if amount_liters is not None else "duration"
            target_value = amount_liters if amount_liters is not None else duration_seconds
            if target_value is None:
                raise HomeAssistantError("An irrigation target is required")
            now = datetime.now(UTC)
            request_id = uuid4().hex
            zone_id = subentry.unique_id or subentry.subentry_id
            max_dose_key = (
                CONF_MAX_DOSE_AMOUNT if target_type == "volume" else CONF_MAX_DOSE_DURATION
            )
            request = ManualIrrigationRequest(
                request_id=request_id,
                sequence=self._stored_state.next_request_sequence,
                zone_id=zone_id,
                zone_subentry_id=zone_subentry_id,
                zone_name=subentry.title,
                zone_valve=subentry.data[CONF_ZONE_VALVE],
                main_valve=self._entry.data.get(CONF_MAIN_VALVE),
                target_type=target_type,
                target_value=target_value,
                remaining_value=target_value,
                created_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=expiry_seconds)).isoformat(),
                hard_time_limit_seconds=hard_time_limit_seconds,
                max_dose_value=self._optional_float(subentry.data, max_dose_key),
                soak_duration_seconds=(
                    self._optional_float(subentry.data, CONF_SOAK_DURATION) or 0.0
                ),
                meter_failure_strategy=str(
                    subentry.data.get(CONF_METER_FAILURE_STRATEGY, METER_FAILURE_ABORT)
                ),
                estimated_flow_l_min=self._estimated_flow(subentry.data),
                minimum_flow_l_min=self._optional_float(subentry.data, CONF_MIN_FLOW),
                maximum_flow_l_min=self._optional_float(subentry.data, CONF_MAX_FLOW),
                flow_grace_seconds=(
                    flow_grace
                    if (flow_grace := self._optional_float(subentry.data, CONF_FLOW_GRACE_SECONDS))
                    is not None
                    else 5.0
                ),
            )
            self._stored_state = replace(
                self._stored_state,
                manual_requests=(*self._stored_state.manual_requests, request),
                next_request_sequence=self._stored_state.next_request_sequence + 1,
            )
            await self._store.async_save(self._stored_state)
            terminal_event = self._terminal_events.setdefault(request_id, asyncio.Event())
            self._queue_event.set()
            self._publish(status=self._coordinator.data.status, active_zone_id=None)

        if wait_for_completion:
            await terminal_event.wait()
            if error := self._request_errors.pop(request_id, None):
                raise error
        return {"request_id": request_id}

    async def _async_dispatch_requests(self) -> None:
        """Run ready manual orders one dose at a time, yielding during soak pauses."""
        while not self._shutting_down:
            self._queue_event.clear()
            request: ManualIrrigationRequest | None = None
            try:
                async with self._command_lock:
                    await self._async_expire_requests()
                    request = select_manual_request(
                        now=datetime.now(UTC),
                        requests=self._stored_state.manual_requests,
                        executions=self._stored_state.irrigation_executions,
                    )
                if request is None:
                    delay = self._seconds_until_next_request_change()
                    with suppress(TimeoutError):
                        await asyncio.wait_for(self._queue_event.wait(), timeout=delay)
                    continue

                dose_value = dose_target(request)
                duration_seconds = dose_value if request.target_type == "duration" else None
                amount_liters = dose_value if request.target_type == "volume" else None
                execution = self._execution(request.execution_id)
                dose_number = execution.dose_number + 1 if execution is not None else 1
                remaining_runtime = (
                    None
                    if request.hard_time_limit_seconds is None
                    else max(
                        0.0,
                        request.hard_time_limit_seconds
                        - self._consumed_watering_seconds(request.request_id),
                    )
                )
                if remaining_runtime is not None and remaining_runtime <= 0:
                    async with self._command_lock:
                        await self._async_fail_request(
                            request.request_id,
                            HomeAssistantError("Irrigation execution hard runtime exhausted"),
                        )
                    continue
                if datetime.fromisoformat(request.expires_at) <= datetime.now(UTC):
                    async with self._command_lock:
                        await self._async_expire_requests()
                    continue
                prepare_seconds = max(
                    0.0,
                    (
                        datetime.fromisoformat(request.expires_at) - datetime.now(UTC)
                    ).total_seconds(),
                )
                try:
                    async with asyncio.timeout(prepare_seconds):
                        async with self._command_lock:
                            task = await self._async_prepare_manual(
                                manual_request=request,
                                dose_value=dose_value,
                                duration_seconds=duration_seconds,
                                amount_liters=amount_liters,
                                hard_time_limit_seconds=remaining_runtime,
                                dose_number=dose_number,
                            )
                except TimeoutError:
                    async with self._command_lock:
                        active = self._stored_state.active_execution
                        if active is not None and active.request_id == request.request_id:
                            await self._async_recover_interrupted_execution(could_have_flowed=False)
                        await self._async_expire_requests()
                    continue
                expiry_seconds = max(
                    0.0,
                    (
                        datetime.fromisoformat(request.expires_at) - datetime.now(UTC)
                    ).total_seconds(),
                )
                done, _ = await asyncio.wait((task,), timeout=expiry_seconds)
                expired_during_dose = task not in done
                if expired_during_dose:
                    task.cancel()
                try:
                    result = await asyncio.shield(task)
                except asyncio.CancelledError:
                    if not expired_during_dose:
                        raise
                    async with self._command_lock:
                        await self._async_recover_interrupted_execution(could_have_flowed=False)
                        await self._async_expire_requests()
                    continue
                async with self._command_lock:
                    await self._async_finish_dose(
                        request.request_id,
                        result,
                        expired=expired_during_dose,
                    )
            except _StaleRequestClaimError:
                pass
            except asyncio.CancelledError:
                return
            except Exception as err:  # noqa: BLE001
                if request is not None:
                    async with self._command_lock:
                        await self._async_fail_request(request.request_id, err)
            finally:
                self._watering = False
                if self._active_task is not None and self._active_task.done():
                    self._active_task = None
                self._clear_active_target()
                self._publish(status=self._coordinator.data.status, active_zone_id=None)
                if not self._shutting_down:
                    await self._async_consider_current_flow()

    async def _async_finish_dose(
        self,
        request_id: str,
        result: ExecutionResult,
        *,
        expired: bool = False,
    ) -> None:
        """Account dose progress and persist completion, pause, cancellation, or soak."""
        request = self._request(request_id)
        if request is None or request.execution_id is None:
            return
        execution = self._execution(request.execution_id)
        if execution is None:
            return
        delivered_target = (
            result.delivered_liters if request.target_type == "volume" else result.duration_seconds
        )
        remaining = max(0.0, request.remaining_value - delivered_target)
        execution = replace(
            execution,
            remaining_value=remaining,
            delivered_liters=execution.delivered_liters + result.delivered_liters,
            delivered_duration_seconds=(
                execution.delivered_duration_seconds + result.duration_seconds
            ),
        )
        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[request.zone_id] = (
            zone_totals.get(request.zone_id, 0.0) + result.delivered_liters
        )
        measurement_quality = dict(self._stored_state.zone_measurement_quality)
        measurement_quality[request.zone_id] = result.measurement_quality
        last_delivered = dict(self._stored_state.zone_last_delivered_liters)
        last_delivered[request.zone_id] = result.delivered_liters
        last_duration = dict(self._stored_state.zone_last_duration_seconds)
        last_duration[request.zone_id] = result.duration_seconds
        zone_locks = dict(self._stored_state.zone_safety_locks)
        if result.safety_scope == "zone" and result.safety_violation:
            zone_locks[request.zone_id] = result.safety_violation
        installation_lock = self._stored_state.installation_safety_lock
        if result.safety_scope == "installation" and result.safety_violation:
            installation_lock = result.safety_violation
        idle_meter_baseline = self._stored_state.idle_meter_raw_baseline_liters
        if self._has_meter:
            with suppress(HomeAssistantError):
                idle_meter_baseline = await self._meter.read_raw_liters()
        now = datetime.now(UTC)
        terminal = False
        if request_id in self._cancel_requested:
            self._cancel_requested.discard(request_id)
            request = replace(
                request,
                remaining_value=remaining,
                status="cancelled",
                revision=request.revision + 1,
            )
            execution = replace(
                execution, status="cancelled", ended_at=now.isoformat(), result="stopped"
            )
            terminal = True
        elif expired or datetime.fromisoformat(request.expires_at) <= now:
            self._pause_requested.discard(request_id)
            request = replace(
                request,
                remaining_value=remaining,
                status="expired",
                soak_until=None,
                revision=request.revision + 1,
            )
            execution = replace(
                execution,
                remaining_value=remaining,
                status="interrupted",
                ended_at=now.isoformat(),
                result="expired",
            )
            terminal = True
        elif request_id in self._pause_requested:
            self._pause_requested.discard(request_id)
            request = replace(
                request,
                remaining_value=remaining,
                status="paused",
                revision=request.revision + 1,
            )
            execution = replace(execution, remaining_value=remaining, status="paused")
        elif result.stopped:
            request = replace(
                request,
                remaining_value=remaining,
                status="pending",
                execution_id=None,
                revision=request.revision + 1,
            )
            execution = replace(
                execution,
                remaining_value=remaining,
                status="interrupted",
                ended_at=now.isoformat(),
                result="interrupted",
            )
        elif result.safety_violation is not None:
            request = replace(
                request,
                remaining_value=remaining,
                status="cancelled",
                revision=request.revision + 1,
            )
            execution = replace(
                execution,
                status="failed",
                ended_at=now.isoformat(),
                result=result.safety_violation,
            )
            self._request_errors[request_id] = HomeAssistantError(result.safety_violation)
            terminal = True
        elif remaining <= 1e-6:
            request = replace(
                request,
                remaining_value=0.0,
                status="completed",
                revision=request.revision + 1,
            )
            execution = replace(
                execution,
                remaining_value=0.0,
                status="completed",
                ended_at=now.isoformat(),
                result="target_reached",
            )
            terminal = True
        else:
            soak_until = now + timedelta(seconds=request.soak_duration_seconds)
            request = replace(
                request,
                remaining_value=remaining,
                status="soaking",
                soak_until=soak_until.isoformat(),
                revision=request.revision + 1,
            )
            execution = replace(execution, remaining_value=remaining, status="soaking")
        self._stored_state = replace(
            self._stored_state,
            installation_total_liters=(
                self._stored_state.installation_total_liters + result.delivered_liters
            ),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=measurement_quality,
            zone_last_delivered_liters=last_delivered,
            zone_last_duration_seconds=last_duration,
            zone_safety_locks=zone_locks,
            installation_safety_lock=installation_lock,
            idle_meter_raw_baseline_liters=idle_meter_baseline,
            active_execution=None,
            manual_requests=self._with_request(request),
            irrigation_executions=self._with_execution(execution),
        )
        await self._store.async_save(self._stored_state)
        if terminal:
            self._signal_terminal(request_id)
        self._queue_event.set()

    async def _async_fail_request(self, request_id: str, error: Exception) -> None:
        """Finalize an order that could not safely execute."""
        request = self._request(request_id)
        if request is None:
            return
        request = replace(request, status="cancelled", revision=request.revision + 1)
        executions = self._stored_state.irrigation_executions
        if request.execution_id is not None and (
            execution := self._execution(request.execution_id)
        ):
            execution = replace(
                execution,
                status="failed",
                ended_at=datetime.now(UTC).isoformat(),
                result=str(error),
            )
            executions = self._with_execution(execution)
        self._stored_state = replace(
            self._stored_state,
            manual_requests=self._with_request(request),
            irrigation_executions=executions,
            active_execution=None,
        )
        await self._store.async_save(self._stored_state)
        self._request_errors[request_id] = error
        self._signal_terminal(request_id)

    async def _async_expire_requests(self) -> None:
        """Expire durable orders that have not completed before their deadline."""
        now = datetime.now(UTC)
        changed = False
        expired_request_ids: list[str] = []
        requests: list[ManualIrrigationRequest] = []
        executions = self._stored_state.irrigation_executions
        for request in self._stored_state.manual_requests:
            if (
                request.status in {"pending", "executing", "soaking", "paused"}
                and datetime.fromisoformat(request.expires_at) <= now
            ):
                request = replace(
                    request,
                    status="expired",
                    soak_until=None,
                    revision=request.revision + 1,
                )
                changed = True
                if request.execution_id is not None and (
                    execution := self._execution(request.execution_id)
                ):
                    executions = tuple(
                        replace(
                            execution,
                            status="interrupted",
                            ended_at=now.isoformat(),
                            result="expired",
                        )
                        if item.execution_id == execution.execution_id
                        else item
                        for item in executions
                    )
                expired_request_ids.append(request.request_id)
            requests.append(request)
        if changed:
            self._stored_state = replace(
                self._stored_state,
                manual_requests=tuple(requests),
                irrigation_executions=executions,
            )
            await self._store.async_save(self._stored_state)
            for request_id in expired_request_ids:
                self._signal_terminal(request_id)

    def _seconds_until_next_request_change(self) -> float | None:
        """Return the bounded delay until a soak or expiry needs reevaluation."""
        now = datetime.now(UTC)
        moments = [
            datetime.fromisoformat(value)
            for request in self._stored_state.manual_requests
            if request.status in {"pending", "executing", "soaking", "paused"}
            for value in (request.expires_at, request.soak_until)
            if value is not None
        ]
        return (
            max(0.0, min((moment - now).total_seconds() for moment in moments)) if moments else None
        )

    def list_manual_requests(self) -> list[dict[str, object]]:
        """Return durable manual orders in stable scheduler order."""
        return [
            request.as_dict()
            for request in sorted(
                self._stored_state.manual_requests,
                key=lambda item: (item.sequence, item.request_id),
            )
        ]

    def list_irrigation_executions(self) -> list[dict[str, object]]:
        """Return persisted irrigation executions in creation order."""
        return [execution.as_dict() for execution in self._stored_state.irrigation_executions]

    async def async_cancel_request(self, request_id: str) -> None:
        """Cancel one selected pending, soaking, paused, or active order."""
        await self._async_control_request(request_id=request_id, action="cancel")

    async def async_pause_request(self, request_id: str) -> None:
        """Pause one selected order while preserving its remaining target."""
        await self._async_control_request(request_id=request_id, action="pause")

    async def async_resume_request(self, request_id: str) -> None:
        """Resume one paused order at its original FIFO position."""
        async with self._command_lock:
            request = self._request(request_id)
            if request is None:
                raise HomeAssistantError("The irrigation request does not exist")
            if request.status != "paused":
                raise HomeAssistantError("The irrigation request is not paused")
            request = replace(request, status="pending", revision=request.revision + 1)
            execution = self._execution(request.execution_id)
            self._stored_state = replace(
                self._stored_state,
                manual_requests=self._with_request(request),
                irrigation_executions=(
                    self._with_execution(replace(execution, status="waiting"))
                    if execution is not None
                    else self._stored_state.irrigation_executions
                ),
            )
            await self._store.async_save(self._stored_state)
            self._queue_event.set()

    async def _async_control_request(self, *, request_id: str, action: str) -> None:
        """Apply cancellation or pause to exactly one durable order."""
        task: asyncio.Task[ExecutionResult] | None = None
        async with self._command_lock:
            request = self._request(request_id)
            if request is None:
                raise HomeAssistantError("The irrigation request does not exist")
            if request.status in {"completed", "cancelled", "expired"}:
                raise HomeAssistantError("The irrigation request is already final")
            if request.status == "executing":
                (self._cancel_requested if action == "cancel" else self._pause_requested).add(
                    request_id
                )
                task = self._active_task
                if task is not None:
                    task.cancel()
            else:
                status = "cancelled" if action == "cancel" else "paused"
                request = replace(
                    request,
                    status=status,
                    soak_until=None,
                    revision=request.revision + 1,
                )
                execution = self._execution(request.execution_id)
                self._stored_state = replace(
                    self._stored_state,
                    manual_requests=self._with_request(request),
                    irrigation_executions=(
                        self._with_execution(
                            replace(
                                execution,
                                status=status,
                                ended_at=(
                                    datetime.now(UTC).isoformat() if action == "cancel" else None
                                ),
                                result=("cancelled" if action == "cancel" else None),
                            )
                        )
                        if execution is not None
                        else self._stored_state.irrigation_executions
                    ),
                )
                await self._store.async_save(self._stored_state)
                if action == "cancel":
                    self._signal_terminal(request_id)
                self._queue_event.set()
        if task is not None:
            await asyncio.shield(task)

    def _request(self, request_id: str) -> ManualIrrigationRequest | None:
        return next(
            (item for item in self._stored_state.manual_requests if item.request_id == request_id),
            None,
        )

    def _execution(self, execution_id: str | None) -> IrrigationExecutionState | None:
        return next(
            (
                item
                for item in self._stored_state.irrigation_executions
                if item.execution_id == execution_id
            ),
            None,
        )

    def _consumed_watering_seconds(self, request_id: str) -> float:
        """Return persisted hydraulic runtime across every execution of one request."""
        return sum(
            execution.delivered_duration_seconds
            for execution in self._stored_state.irrigation_executions
            if execution.request_id == request_id
        )

    def _with_request(
        self, request: ManualIrrigationRequest
    ) -> tuple[ManualIrrigationRequest, ...]:
        return tuple(
            request if item.request_id == request.request_id else item
            for item in self._stored_state.manual_requests
        )

    def _with_execution(
        self, execution: IrrigationExecutionState
    ) -> tuple[IrrigationExecutionState, ...]:
        return tuple(
            execution if item.execution_id == execution.execution_id else item
            for item in self._stored_state.irrigation_executions
        )

    def _signal_terminal(self, request_id: str) -> None:
        self._terminal_events.setdefault(request_id, asyncio.Event()).set()

    async def _async_prepare_manual(
        self,
        *,
        manual_request: ManualIrrigationRequest,
        dose_value: float,
        duration_seconds: float | None,
        amount_liters: float | None,
        hard_time_limit_seconds: float | None,
        dose_number: int,
    ) -> asyncio.Task[ExecutionResult]:
        """Validate and durably claim one manual execution before opening valves."""
        current_request = self._request(manual_request.request_id)
        if (
            current_request is None
            or current_request.revision != manual_request.revision
            or current_request != manual_request
        ):
            raise _StaleRequestClaimError(
                "The irrigation request changed before it could be claimed"
            )
        selected_request = select_manual_request(
            now=datetime.now(UTC),
            requests=self._stored_state.manual_requests,
            executions=self._stored_state.irrigation_executions,
        )
        if selected_request is None or selected_request.request_id != manual_request.request_id:
            raise _StaleRequestClaimError(
                "The irrigation request is no longer eligible for execution"
            )
        manual_request = current_request
        if self._stored_state.emergency_stop:
            raise HomeAssistantError("The emergency stop is active")
        if self._stored_state.active_execution is not None:
            raise HomeAssistantError("An interrupted irrigation execution needs recovery")
        if self._active_task is not None and not self._active_task.done():
            raise HomeAssistantError("This irrigation installation is busy")
        subentry = self._entry.subentries.get(manual_request.zone_subentry_id)
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise HomeAssistantError("The irrigation zone does not exist")
        zone_id = manual_request.zone_id
        await self._async_preflight(target_zone_id=zone_id)
        self._cancel_leak_observation()

        estimated_flow_l_min = manual_request.estimated_flow_l_min
        meter_failure_strategy = manual_request.meter_failure_strategy
        minimum_flow_l_min = manual_request.minimum_flow_l_min
        maximum_flow_l_min = manual_request.maximum_flow_l_min
        if self._flow is not None and (
            minimum_flow_l_min is not None or maximum_flow_l_min is not None
        ):
            await self._flow.read_l_min()
        flow_grace_seconds = manual_request.flow_grace_seconds
        start_in_estimated_fallback = False
        meter_raw_baseline_liters: float | None = None
        if amount_liters is not None and not self._has_meter:
            raise HomeAssistantError("Volume irrigation requires a configured cumulative meter")
        if self._has_meter:
            try:
                meter_raw_baseline_liters = await self._meter.read_raw_liters()
            except HomeAssistantError:
                if amount_liters is None or meter_failure_strategy == METER_FAILURE_ABORT:
                    raise
                start_in_estimated_fallback = True
        if start_in_estimated_fallback and (
            estimated_flow_l_min is None or estimated_flow_l_min <= 0
        ):
            raise HomeAssistantError(
                "Estimated meter fallback requires a configured zone flow profile"
            )
        execution_time_limit = duration_seconds or hard_time_limit_seconds
        if execution_time_limit is None:
            raise HomeAssistantError("A hard irrigation time limit is required")
        now = datetime.now(UTC).isoformat()
        execution = self._execution(manual_request.execution_id)
        if execution is None:
            execution_id = uuid4().hex
            execution = IrrigationExecutionState(
                execution_id=execution_id,
                request_id=manual_request.request_id,
                zone_id=zone_id,
                target_type=manual_request.target_type,
                target_value=manual_request.target_value,
                remaining_value=manual_request.remaining_value,
                status="watering",
                created_at=now,
                dose_number=dose_number,
            )
            executions = (*self._stored_state.irrigation_executions, execution)
        else:
            execution_id = execution.execution_id
            execution = replace(
                execution,
                status="watering",
                dose_number=dose_number,
            )
            executions = self._with_execution(execution)
        manual_request = replace(
            manual_request,
            execution_id=execution_id,
            status="executing",
            soak_until=None,
            revision=manual_request.revision + 1,
        )
        self._stored_state = replace(
            self._stored_state,
            manual_requests=self._with_request(manual_request),
            irrigation_executions=executions,
            active_execution=ActiveExecutionState(
                zone_id=zone_id,
                zone_valve=manual_request.zone_valve,
                main_valve=manual_request.main_valve,
                meter_raw_baseline_liters=meter_raw_baseline_liters,
                prepared_at=now,
                watering_started_at=None,
                requested_duration_seconds=execution_time_limit,
                estimated_flow_l_min=estimated_flow_l_min,
                requested_amount_liters=amount_liters,
                hard_time_limit_seconds=hard_time_limit_seconds,
                meter_failure_strategy=meter_failure_strategy,
                request_id=manual_request.request_id,
                execution_id=execution_id,
                dose_number=dose_number,
                dose_target_value=dose_value,
            ),
        )
        await self._store.async_save(self._stored_state)
        self._active_target_type = manual_request.target_type
        self._active_target_value = manual_request.target_value
        self._active_remaining_value = manual_request.remaining_value
        self._active_measurement_quality = (
            "estimated"
            if start_in_estimated_fallback or (not self._has_meter and estimated_flow_l_min)
            else "unknown"
            if not self._has_meter
            else "measured"
        )
        self._watering = True
        task = self._hass.async_create_task(
            self._async_execute(
                request=ExecutionRequest(
                    zone_id=zone_id,
                    zone_valve=manual_request.zone_valve,
                    main_valve=manual_request.main_valve,
                    duration_seconds=duration_seconds,
                    amount_liters=amount_liters,
                    hard_time_limit_seconds=hard_time_limit_seconds,
                    meter_failure_strategy=meter_failure_strategy,
                    estimated_flow_l_min=estimated_flow_l_min,
                    start_in_estimated_fallback=start_in_estimated_fallback,
                    managed_zone_valves=tuple(self._zone_valves()),
                    monitor_interval_seconds=1,
                    minimum_flow_l_min=minimum_flow_l_min,
                    maximum_flow_l_min=maximum_flow_l_min,
                    flow_grace_seconds=flow_grace_seconds,
                    on_zone_opening=self._async_mark_zone_opening,
                    on_zone_opened=self._async_mark_zone_opened,
                    on_progress=self._async_update_progress,
                ),
                estimated_flow_l_min=estimated_flow_l_min,
            ),
            f"Irrigation Manager manual dose for {manual_request.zone_name}",
        )
        self._active_task = task
        return task

    async def _async_mark_zone_opening(self) -> None:
        """Durably mark that water may flow before commanding the zone."""
        active = self._stored_state.active_execution
        if active is None:
            raise HomeAssistantError("The durable irrigation execution is missing")
        self._stored_state = replace(
            self._stored_state,
            active_execution=replace(
                active,
                zone_opening_at=datetime.now(UTC).isoformat(),
            ),
        )
        await self._store.async_save(self._stored_state)

    async def _async_mark_zone_opened(self) -> None:
        """Durably mark confirmed water delivery after valve feedback succeeds."""
        active = self._stored_state.active_execution
        if active is None:
            raise HomeAssistantError("The durable irrigation execution is missing")
        now = datetime.now(UTC).isoformat()
        self._stored_state = replace(
            self._stored_state,
            active_execution=replace(
                active,
                watering_started_at=now,
                fallback_started_at=(
                    now
                    if active.requested_amount_liters is not None
                    and active.meter_raw_baseline_liters is None
                    and active.meter_failure_strategy == METER_FAILURE_ESTIMATED_TIME_FALLBACK
                    else active.fallback_started_at
                ),
                fallback_checkpoint_at=(
                    now
                    if active.requested_amount_liters is not None
                    and active.meter_raw_baseline_liters is None
                    and active.meter_failure_strategy == METER_FAILURE_ESTIMATED_TIME_FALLBACK
                    else active.fallback_checkpoint_at
                ),
            ),
        )
        await self._store.async_save(self._stored_state)

    async def _async_update_progress(self, remaining: float, quality: str) -> None:
        """Publish volume progress and durably record a meter fallback transition."""
        active = self._stored_state.active_execution
        request = (
            self._request(active.request_id) if active is not None and active.request_id else None
        )
        self._active_remaining_value = (
            max(
                0.0,
                request.remaining_value - (active.dose_target_value or 0.0) + remaining,
            )
            if request is not None and active is not None
            else remaining
        )
        self._active_measurement_quality = quality
        if active is not None and quality == "estimated":
            delivered = max(0.0, (active.requested_amount_liters or 0.0) - remaining)
            now = datetime.now(UTC).isoformat()
            self._stored_state = replace(
                self._stored_state,
                active_execution=replace(
                    active,
                    fallback_started_at=active.fallback_started_at or now,
                    fallback_checkpoint_at=now,
                    delivered_liters_at_fallback=delivered,
                ),
            )
            await self._store.async_save(self._stored_state)
        self._publish(status="watering", active_zone_id=active.zone_id if active else None)

    async def async_stop(
        self,
        *,
        request_id: str | None = None,
        execution_id: str | None = None,
    ) -> None:
        """Stop one selected order/execution, or every open and pending order."""
        if execution_id is not None:
            execution = self._execution(execution_id)
            if execution is None:
                raise HomeAssistantError("The irrigation execution does not exist")
            request_id = execution.request_id
        if request_id is not None:
            await self.async_cancel_request(request_id)
            return
        request_ids = [
            request.request_id
            for request in self._stored_state.manual_requests
            if request.status not in {"completed", "cancelled", "expired"}
        ]
        for open_request_id in request_ids:
            try:
                await self.async_cancel_request(open_request_id)
            except HomeAssistantError:
                continue

    async def async_emergency_stop(self) -> None:
        """Stop all water delivery and persist the non-overridable safety lock."""
        async with self._command_lock:
            active = self._stored_state.active_execution
            self._stored_state = replace(self._stored_state, emergency_stop=True)
            await self._store.async_save(self._stored_state)
            self._publish(status="emergency_stop", active_zone_id=None)
        await self.async_stop()
        entity_ids = self._zone_valves()
        if active is not None:
            entity_ids.append(active.zone_valve)
            if active.main_valve is not None:
                entity_ids.append(active.main_valve)
        if main_valve := self._entry.data.get(CONF_MAIN_VALVE):
            entity_ids.append(main_valve)
        await self._async_close_entities(list(dict.fromkeys(entity_ids)))
        self._publish(status="emergency_stop", active_zone_id=None)

    async def async_reset_emergency_stop(self) -> None:
        """Clear the safety lock only while idle with all valves proven closed."""
        async with self._command_lock:
            if self._active_task is not None and not self._active_task.done():
                raise HomeAssistantError("The irrigation installation is busy")
            if self._stored_state.active_execution is not None:
                raise HomeAssistantError("An interrupted irrigation execution needs recovery")
            await self._async_preflight()
            self._stored_state = replace(
                self._stored_state,
                emergency_stop=False,
            )
            await self._store.async_save(self._stored_state)
            self._publish(status="idle", active_zone_id=None)

    async def async_reset_zone_safety(self, *, zone_subentry_id: str) -> None:
        """Clear one zone lock only while the installation is safely idle."""
        async with self._command_lock:
            if self._active_task is not None and not self._active_task.done():
                raise HomeAssistantError("The irrigation installation is busy")
            subentry = self._entry.subentries.get(zone_subentry_id)
            if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
                raise HomeAssistantError("The irrigation zone does not exist")
            await self._async_preflight()
            zone_id = subentry.unique_id or subentry.subentry_id
            zone_locks = dict(self._stored_state.zone_safety_locks)
            zone_locks.pop(zone_id, None)
            self._stored_state = replace(
                self._stored_state,
                zone_safety_locks=zone_locks,
            )
            await self._store.async_save(self._stored_state)
            self._publish(status="idle", active_zone_id=None)

    async def async_reset_installation_safety(self) -> None:
        """Clear the installation lock only after excessive flow has ended."""
        async with self._command_lock:
            if self._active_task is not None and not self._active_task.done():
                raise HomeAssistantError("The irrigation installation is busy")
            await self._async_preflight(ignore_installation_lock=True)
            if self._flow is not None:
                flow_l_min = await self._flow.read_l_min()
                if flow_l_min > self._leak_threshold_l_min:
                    raise HomeAssistantError("Hazardous idle flow is still present")
                maximums = [
                    value
                    for subentry in self._entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
                    if (value := self._optional_float(subentry.data, CONF_MAX_FLOW)) is not None
                ]
                if maximums and flow_l_min > min(maximums):
                    raise HomeAssistantError("Excessive flow is still present")
            self._stored_state = replace(
                self._stored_state,
                installation_safety_lock=None,
            )
            await self._store.async_save(self._stored_state)
            await self._async_refresh_idle_meter_baseline()
            self._publish(status="idle", active_zone_id=None)

    async def async_assign_water(self, *, zone_subentry_id: str, amount_liters: float) -> None:
        """Move measured unassigned consumption to one irrigation zone."""
        async with self._command_lock:
            await self._async_assign_water(
                zone_subentry_id=zone_subentry_id,
                amount_liters=amount_liters,
            )

    async def _async_assign_water(self, *, zone_subentry_id: str, amount_liters: float) -> None:
        """Validate and persist one consumption assignment."""
        if self._active_task is not None and not self._active_task.done():
            raise HomeAssistantError("Consumption cannot be assigned while watering")
        if self._stored_state.active_execution is not None:
            raise HomeAssistantError("An interrupted irrigation execution needs recovery")
        subentry = self._entry.subentries.get(zone_subentry_id)
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise HomeAssistantError("The irrigation zone does not exist")
        if amount_liters > self._stored_state.unassigned_total_liters:
            raise HomeAssistantError("The amount exceeds unassigned consumption")

        zone_id = subentry.unique_id or subentry.subentry_id
        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[zone_id] = zone_totals.get(zone_id, 0.0) + amount_liters
        self._stored_state = replace(
            self._stored_state,
            zone_totals_liters=zone_totals,
            unassigned_total_liters=(self._stored_state.unassigned_total_liters - amount_liters),
        )
        await self._store.async_save(self._stored_state)
        self._publish(status="idle", active_zone_id=None)

    async def _async_execute(
        self, *, request: ExecutionRequest, estimated_flow_l_min: float | None
    ) -> ExecutionResult:
        """Execute one dose while retaining its durable recovery checkpoint."""
        self._publish(status="watering", active_zone_id=request.zone_id)
        final_status = "idle"
        try:
            try:
                result = await self._executor.execute(request)
            finally:
                self._watering = False
            delivered_liters = result.delivered_liters
            measurement_result_quality = result.measurement_quality
            if request.amount_liters is None and not self._has_meter:
                if estimated_flow_l_min is not None:
                    delivered_liters = result.duration_seconds * estimated_flow_l_min / 60
                    measurement_result_quality = "estimated"
                else:
                    measurement_result_quality = "unknown"
            return replace(
                result,
                delivered_liters=delivered_liters,
                measurement_quality=measurement_result_quality,
            )
        except Exception:
            final_status = "error"
            await self._async_recover_interrupted_execution()
            raise
        finally:
            self._publish(status=final_status, active_zone_id=None)

    def _publish(self, *, status: str, active_zone_id: str | None) -> None:
        """Publish one consistent snapshot from persisted runtime state."""
        if self._stored_state.emergency_stop:
            status = "emergency_stop"
        elif self._stored_state.installation_safety_lock is not None:
            status = "safety_lock"
        elif status == "idle" and any(
            request.status == "soaking" for request in self._stored_state.manual_requests
        ):
            status = "soaking"
        active = self._stored_state.active_execution
        selected_request = (
            self._request(active.request_id)
            if active is not None and active.request_id is not None
            else min(
                (
                    request
                    for request in self._stored_state.manual_requests
                    if request.status in {"pending", "executing", "soaking", "paused"}
                ),
                key=lambda request: (request.sequence, request.request_id),
                default=None,
            )
        )
        selected_execution = (
            self._execution(selected_request.execution_id) if selected_request is not None else None
        )
        self._coordinator.set_snapshot(
            InstallationSnapshot(
                installation_total_liters=(self._stored_state.installation_total_liters),
                zone_totals_liters=dict(self._stored_state.zone_totals_liters),
                zone_measurement_quality=dict(self._stored_state.zone_measurement_quality),
                zone_last_delivered_liters=dict(self._stored_state.zone_last_delivered_liters),
                zone_last_duration_seconds=dict(self._stored_state.zone_last_duration_seconds),
                zone_safety_locks=dict(self._stored_state.zone_safety_locks),
                unassigned_total_liters=self._stored_state.unassigned_total_liters,
                unassigned_measurement_quality=(self._stored_state.unassigned_measurement_quality),
                unassigned_measurement_origin=(self._stored_state.unassigned_measurement_origin),
                status=status,
                active_zone_id=active_zone_id,
                emergency_stop=self._stored_state.emergency_stop,
                installation_safety_lock=(self._stored_state.installation_safety_lock),
                active_target_type=(
                    self._active_target_type
                    or (selected_request.target_type if selected_request is not None else None)
                ),
                active_target_value=(
                    self._active_target_value
                    if self._active_target_value is not None
                    else selected_request.target_value
                    if selected_request is not None
                    else None
                ),
                active_remaining_value=(
                    self._active_remaining_value
                    if self._active_remaining_value is not None
                    else selected_request.remaining_value
                    if selected_request is not None
                    else None
                ),
                active_measurement_quality=self._active_measurement_quality,
                pending_request_count=sum(
                    request.status in {"pending", "executing", "soaking", "paused"}
                    for request in self._stored_state.manual_requests
                ),
                current_dose_number=(
                    active.dose_number
                    if active is not None
                    else selected_execution.dose_number
                    if selected_execution is not None
                    else None
                ),
                active_request_id=(selected_request.request_id if selected_request else None),
                active_execution_id=(
                    selected_execution.execution_id if selected_execution else None
                ),
            )
        )

    def _clear_active_target(self) -> None:
        """Clear transient target progress after an execution finishes."""
        self._active_target_type = None
        self._active_target_value = None
        self._active_remaining_value = None
        self._active_measurement_quality = None

    @staticmethod
    def _estimated_flow(data: Mapping[str, object]) -> float | None:
        """Use the configured flow profile midpoint for meterless accounting."""
        values = [
            float(value)
            for key in (CONF_MIN_FLOW, CONF_MAX_FLOW)
            if isinstance((value := data.get(key)), int | float)
        ]
        return sum(values) / len(values) if values else None

    @staticmethod
    def _optional_float(data: Mapping[str, object], key: str) -> float | None:
        """Return one optional numeric config value as a float."""
        value = data.get(key)
        return float(value) if isinstance(value, int | float) else None
