"""Runtime orchestration for one irrigation installation."""

import asyncio
from collections.abc import Mapping

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
from .models import InstallationSnapshot, StoredInstallationState
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
        self._executor = IrrigationExecutor(
            actuators=self._actuators,
            meter=HomeAssistantMeter(hass, entry.data.get(CONF_WATER_METER)),
            clock=HomeAssistantClock(),
        )
        self._active_task: asyncio.Task[None] | None = None
        self._watering = False

    async def async_initialize(self) -> None:
        """Close configured valves left open across a restart."""
        entity_ids = self._zone_valves()
        if main_valve := self._entry.data.get(CONF_MAIN_VALVE):
            entity_ids.append(main_valve)
        await self._async_close_entities(
            [
                entity_id
                for entity_id in entity_ids
                if (state := self._hass.states.get(entity_id)) is not None
                and state.state not in {STATE_OFF, "closed"}
            ]
        )

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
        if self._stored_state.emergency_stop:
            raise HomeAssistantError("The emergency stop is active")
        if self._active_task is not None and not self._active_task.done():
            raise HomeAssistantError("This irrigation installation is busy")
        subentry = self._entry.subentries.get(zone_subentry_id)
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise HomeAssistantError("The irrigation zone does not exist")
        await self._async_preflight()

        zone_id = subentry.unique_id or subentry.subentry_id
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
                ),
                estimated_flow_l_min=self._estimated_flow(subentry.data),
            ),
            f"Irrigation Manager manual dose for {subentry.title}",
        )
        self._active_task = task
        try:
            await task
        finally:
            self._watering = False
            if self._active_task is task:
                self._active_task = None

    async def async_stop(self) -> None:
        """Stop the active dose; the executor closes and meters it safely."""
        task = self._active_task
        if task is None or task.done():
            return
        if self._watering:
            task.cancel()
            await task
        else:
            await asyncio.shield(task)

    async def async_assign_water(self, *, zone_subentry_id: str, amount_liters: float) -> None:
        """Move measured unassigned consumption to one irrigation zone."""
        if self._active_task is not None and not self._active_task.done():
            raise HomeAssistantError("Consumption cannot be assigned while watering")
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
