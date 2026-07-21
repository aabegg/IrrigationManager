"""Runtime orchestration for one irrigation installation."""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime

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
    CONF_MAX_FLOW,
    CONF_MIN_FLOW,
    CONF_WATER_METER,
    CONF_ZONE_VALVE,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import IrrigationCoordinator
from .executor import ExecutionRequest, IrrigationExecutor
from .leak_monitor import LeakObservation
from .models import (
    ActiveExecutionState,
    InstallationSnapshot,
    StoredInstallationState,
)
from .storage import IrrigationStore


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
        self._active_task: asyncio.Task[None] | None = None
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

    async def async_shutdown(self) -> None:
        """Stop runtime work and remove all Home Assistant listeners."""
        self._shutting_down = True
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
        await self.async_stop()
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
        if active.watering_started_at is not None:
            started_at = datetime.fromisoformat(active.watering_started_at)
            delivered_duration_seconds = max(0.0, (datetime.now(UTC) - started_at).total_seconds())
            if not could_have_flowed:
                delivered_duration_seconds = min(
                    delivered_duration_seconds,
                    active.requested_duration_seconds,
                )
        if (
            active.watering_started_at is not None
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
        if active.watering_started_at is not None:
            measurement_quality[active.zone_id] = quality
            last_delivered[active.zone_id] = delivered_liters
            last_duration[active.zone_id] = delivered_duration_seconds
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
        )
        await self._store.async_save(self._stored_state)
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

    async def async_start_manual(self, *, zone_subentry_id: str, duration_seconds: float) -> None:
        """Run one manually requested, time-controlled irrigation dose."""
        try:
            async with self._command_lock:
                task = await self._async_prepare_manual(
                    zone_subentry_id=zone_subentry_id,
                    duration_seconds=duration_seconds,
                )
        except asyncio.CancelledError:
            await self._async_recover_interrupted_execution(could_have_flowed=False)
            return
        try:
            await task
        except asyncio.CancelledError:
            await self._async_recover_interrupted_execution(could_have_flowed=False)
        finally:
            self._watering = False
            if self._active_task is task:
                self._active_task = None
            if not self._shutting_down:
                await self._async_consider_current_flow()

    async def _async_prepare_manual(
        self, *, zone_subentry_id: str, duration_seconds: float
    ) -> asyncio.Task[None]:
        """Validate and durably claim one manual execution before opening valves."""
        if self._stored_state.emergency_stop:
            raise HomeAssistantError("The emergency stop is active")
        if self._stored_state.active_execution is not None:
            raise HomeAssistantError("An interrupted irrigation execution needs recovery")
        if self._active_task is not None and not self._active_task.done():
            raise HomeAssistantError("This irrigation installation is busy")
        subentry = self._entry.subentries.get(zone_subentry_id)
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise HomeAssistantError("The irrigation zone does not exist")
        zone_id = subentry.unique_id or subentry.subentry_id
        await self._async_preflight(target_zone_id=zone_id)
        self._cancel_leak_observation()

        estimated_flow_l_min = self._estimated_flow(subentry.data)
        minimum_flow_l_min = self._optional_float(subentry.data, CONF_MIN_FLOW)
        maximum_flow_l_min = self._optional_float(subentry.data, CONF_MAX_FLOW)
        if self._flow is not None and (
            minimum_flow_l_min is not None or maximum_flow_l_min is not None
        ):
            await self._flow.read_l_min()
        flow_grace_seconds = self._optional_float(subentry.data, CONF_FLOW_GRACE_SECONDS)
        if flow_grace_seconds is None:
            flow_grace_seconds = 5.0
        meter_raw_baseline_liters = await self._meter.read_raw_liters() if self._has_meter else None
        self._stored_state = replace(
            self._stored_state,
            active_execution=ActiveExecutionState(
                zone_id=zone_id,
                zone_valve=subentry.data[CONF_ZONE_VALVE],
                main_valve=self._entry.data.get(CONF_MAIN_VALVE),
                meter_raw_baseline_liters=meter_raw_baseline_liters,
                prepared_at=datetime.now(UTC).isoformat(),
                watering_started_at=None,
                requested_duration_seconds=duration_seconds,
                estimated_flow_l_min=estimated_flow_l_min,
            ),
        )
        await self._store.async_save(self._stored_state)
        self._watering = True
        task = self._hass.async_create_task(
            self._async_execute(
                request=ExecutionRequest(
                    zone_id=zone_id,
                    zone_valve=subentry.data[CONF_ZONE_VALVE],
                    main_valve=self._entry.data.get(CONF_MAIN_VALVE),
                    duration_seconds=duration_seconds,
                    managed_zone_valves=tuple(self._zone_valves()),
                    monitor_interval_seconds=1,
                    minimum_flow_l_min=minimum_flow_l_min,
                    maximum_flow_l_min=maximum_flow_l_min,
                    flow_grace_seconds=flow_grace_seconds,
                    on_zone_opening=self._async_mark_zone_opening,
                ),
                estimated_flow_l_min=estimated_flow_l_min,
            ),
            f"Irrigation Manager manual dose for {subentry.title}",
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
                watering_started_at=datetime.now(UTC).isoformat(),
            ),
        )
        await self._store.async_save(self._stored_state)

    async def async_stop(self) -> None:
        """Stop the active dose; the executor closes and meters it safely."""
        async with self._command_lock:
            task = self._active_task
            if task is None or task.done():
                return
            should_cancel = self._watering
            if should_cancel:
                task.cancel()
        try:
            await task if should_cancel else asyncio.shield(task)
        except asyncio.CancelledError:
            await self._async_recover_interrupted_execution(could_have_flowed=False)

    async def async_emergency_stop(self) -> None:
        """Stop all water delivery and persist the non-overridable safety lock."""
        async with self._command_lock:
            active = self._stored_state.active_execution
            self._stored_state = replace(self._stored_state, emergency_stop=True)
            await self._store.async_save(self._stored_state)
            self._publish(status="emergency_stop", active_zone_id=None)
            task = self._active_task
            if task is not None and not task.done():
                task.cancel()
            try:
                if task is not None:
                    await task
            except asyncio.CancelledError:
                await self._async_recover_interrupted_execution(could_have_flowed=False)
            finally:
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
    ) -> None:
        """Execute and atomically account for one dose."""
        self._publish(status="watering", active_zone_id=request.zone_id)
        final_status = "idle"
        try:
            try:
                result = await self._executor.execute(request)
            finally:
                self._watering = False
            delivered_liters = result.delivered_liters
            if not self._has_meter and estimated_flow_l_min is not None:
                delivered_liters = result.duration_seconds * estimated_flow_l_min / 60
            zone_totals = dict(self._stored_state.zone_totals_liters)
            zone_totals[request.zone_id] = zone_totals.get(request.zone_id, 0.0) + delivered_liters
            measurement_quality = dict(self._stored_state.zone_measurement_quality)
            measurement_quality[request.zone_id] = (
                "measured"
                if self._has_meter
                else "estimated"
                if estimated_flow_l_min is not None
                else "unknown"
            )
            last_delivered = dict(self._stored_state.zone_last_delivered_liters)
            last_delivered[request.zone_id] = delivered_liters
            last_duration = dict(self._stored_state.zone_last_duration_seconds)
            last_duration[request.zone_id] = result.duration_seconds
            zone_locks = dict(self._stored_state.zone_safety_locks)
            if result.safety_scope == "zone" and result.safety_violation:
                zone_locks[request.zone_id] = result.safety_violation
            installation_lock = self._stored_state.installation_safety_lock
            if result.safety_scope == "installation" and result.safety_violation:
                installation_lock = result.safety_violation
            self._stored_state = replace(
                self._stored_state,
                installation_total_liters=(
                    self._stored_state.installation_total_liters + delivered_liters
                ),
                zone_totals_liters=zone_totals,
                zone_measurement_quality=measurement_quality,
                zone_last_delivered_liters=last_delivered,
                zone_last_duration_seconds=last_duration,
                zone_safety_locks=zone_locks,
                installation_safety_lock=installation_lock,
                active_execution=None,
            )
            await self._store.async_save(self._stored_state)
            await self._async_refresh_idle_meter_baseline()
            if result.safety_violation is not None:
                raise HomeAssistantError(result.safety_violation)
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
            )
        )

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
