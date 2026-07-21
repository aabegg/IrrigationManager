"""Runtime orchestration for one irrigation installation."""

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .adapters import HomeAssistantActuators, HomeAssistantClock, HomeAssistantMeter
from .const import (
    CONF_MAIN_VALVE,
    CONF_MAX_FLOW,
    CONF_MIN_FLOW,
    CONF_WATER_METER,
    CONF_ZONE_VALVE,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import IrrigationCoordinator
from .executor import ExecutionRequest, IrrigationExecutor
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
        self._executor = IrrigationExecutor(
            actuators=self._actuators,
            meter=self._meter,
            clock=HomeAssistantClock(),
        )
        self._active_task: asyncio.Task[None] | None = None
        self._watering = False
        self._command_lock = asyncio.Lock()

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

    async def _async_recover_interrupted_execution(self, *, could_have_flowed: bool = True) -> None:
        """Account for a durable active dose after all valves are closed."""
        active = self._stored_state.active_execution
        if active is None:
            return

        delivered_liters = 0.0
        quality = "unknown"
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
            started_at = datetime.fromisoformat(active.watering_started_at)
            elapsed_seconds = max(0.0, (datetime.now(UTC) - started_at).total_seconds())
            if not could_have_flowed:
                elapsed_seconds = min(elapsed_seconds, active.requested_duration_seconds)
            delivered_liters = elapsed_seconds * active.estimated_flow_l_min / 60
            quality = "estimated"

        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[active.zone_id] = zone_totals.get(active.zone_id, 0.0) + delivered_liters
        measurement_quality = dict(self._stored_state.zone_measurement_quality)
        measurement_quality[active.zone_id] = quality
        self._stored_state = replace(
            self._stored_state,
            installation_total_liters=(
                self._stored_state.installation_total_liters + delivered_liters
            ),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=measurement_quality,
            active_execution=None,
        )
        await self._store.async_save(self._stored_state)
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

    async def _async_preflight(self) -> None:
        """Prove all managed valves are available and hydraulically closed."""
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
        self._stored_state = StoredInstallationState(
            installation_total_liters=self._stored_state.installation_total_liters,
            zone_totals_liters=dict(self._stored_state.zone_totals_liters),
            zone_measurement_quality=dict(self._stored_state.zone_measurement_quality),
            unassigned_total_liters=self._stored_state.unassigned_total_liters,
            emergency_stop=True,
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
        await self._async_preflight()

        zone_id = subentry.unique_id or subentry.subentry_id
        estimated_flow_l_min = self._estimated_flow(subentry.data)
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
        measurement_quality = dict(self._stored_state.zone_measurement_quality)
        measurement_quality[zone_id] = "measured"
        self._stored_state = StoredInstallationState(
            installation_total_liters=self._stored_state.installation_total_liters,
            zone_totals_liters=zone_totals,
            zone_measurement_quality=measurement_quality,
            unassigned_total_liters=(self._stored_state.unassigned_total_liters - amount_liters),
            emergency_stop=self._stored_state.emergency_stop,
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
            self._stored_state = StoredInstallationState(
                installation_total_liters=(
                    self._stored_state.installation_total_liters + delivered_liters
                ),
                zone_totals_liters=zone_totals,
                zone_measurement_quality=measurement_quality,
                unassigned_total_liters=self._stored_state.unassigned_total_liters,
                emergency_stop=(
                    self._stored_state.emergency_stop or result.safety_violation is not None
                ),
            )
            await self._store.async_save(self._stored_state)
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
        if self._stored_state.emergency_stop and status == "idle":
            status = "emergency_stop"
        self._coordinator.set_snapshot(
            InstallationSnapshot(
                installation_total_liters=(self._stored_state.installation_total_liters),
                zone_totals_liters=dict(self._stored_state.zone_totals_liters),
                zone_measurement_quality=dict(self._stored_state.zone_measurement_quality),
                unassigned_total_liters=self._stored_state.unassigned_total_liters,
                status=status,
                active_zone_id=active_zone_id,
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
