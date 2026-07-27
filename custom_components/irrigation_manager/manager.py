"""Authoritative version-2 runtime for one irrigation installation."""

import asyncio
import json
import math
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .adapters import HomeAssistantActuators, HomeAssistantClock, HomeAssistantMeter
from .const import (
    CONF_AUTOMATION_ENABLED,
    CONF_BASE_TARGET,
    CONF_CONTROL_TYPE,
    CONF_EXPECTED_FLOW_L_MIN,
    CONF_LITERS_PER_COUNT,
    CONF_LITERS_PER_PULSE,
    CONF_MAIN_VALVE,
    CONF_MAX_DELIVERY_RUNTIME,
    CONF_MAX_OPERATION_LIFETIME,
    CONF_METER_ENTITY,
    CONF_METER_TYPE,
    CONF_NEEDS_RECONFIGURATION,
    CONF_OPERATION_ENABLED,
    CONF_VOLUME_MAX_RUNTIME,
    CONF_WEEKLY_SCHEDULE,
    CONF_ZONE_VALVE,
    CONTROL_TYPE_VOLUME,
    METER_TYPE_CUMULATIVE,
    METER_TYPE_PULSE,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
)
from .coordinator import IrrigationCoordinator
from .executor import (
    CLEANUP_FEEDBACK_BUDGET_SECONDS,
    ExecutionRequest,
    ExecutionResult,
    IrrigationExecutor,
)
from .meter import CumulativeMeter
from .models import (
    ActiveExecutionState,
    CalibrationProposal,
    InstallationSnapshot,
    IrrigationExecutionState,
    ManualIrrigationRequest,
    MeterCorrectionRecord,
    StoredInstallationState,
    WaterConsumptionRecord,
)
from .scheduler import (
    planned_volume_duration_seconds,
    request_priority,
    resolve_local_wall_time,
    select_manual_request,
)
from .storage import IrrigationStore
from .zone_config import effective_schedule_target

_FINAL_REQUEST_STATUSES = {"completed", "cancelled", "expired"}
_OPEN_REQUEST_STATUSES = {"pending", "executing"}


@dataclass(frozen=True, slots=True)
class _ZoneConfigSnapshot:
    """Runtime-owned copy of one zone config subentry."""

    subentry_id: str
    subentry_type: str
    title: str
    unique_id: str | None
    data: dict[str, Any]

    @property
    def zone_id(self) -> str:
        """Return the stable zone identity."""
        return self.unique_id or self.subentry_id


class IrrigationManager:
    """Plan and execute the fixed-target version-2 irrigation model."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: IrrigationCoordinator,
        store: IrrigationStore,
        stored_state: StoredInstallationState,
    ) -> None:
        """Initialize one installation runtime without touching actuators."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._store = store
        self._stored_state = stored_state
        self._installation_data = dict(entry.data)
        self._zone_configs = tuple(
            _ZoneConfigSnapshot(
                subentry_id=subentry.subentry_id,
                subentry_type=subentry.subentry_type,
                title=subentry.title,
                unique_id=subentry.unique_id,
                data=dict(subentry.data),
            )
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        )
        self._zone_configs_by_subentry_id = {zone.subentry_id: zone for zone in self._zone_configs}

        meter_type = self._installation_data.get(CONF_METER_TYPE)
        meter_entity = self._installation_data.get(CONF_METER_ENTITY)
        self._has_meter = meter_type in {METER_TYPE_CUMULATIVE, METER_TYPE_PULSE} and isinstance(
            meter_entity, str
        )
        liters_per_count = (
            self._optional_float(self._installation_data, CONF_LITERS_PER_PULSE)
            or self._optional_float(self._installation_data, CONF_LITERS_PER_COUNT)
            if meter_type == METER_TYPE_PULSE
            else None
        )
        continuity = (
            CumulativeMeter(
                accumulated_liters=stored_state.meter_accumulated_liters,
                last_raw_liters=stored_state.meter_last_raw_liters,
                correction_liters=stored_state.meter_correction_liters,
                reset_count=stored_state.meter_reset_count,
            )
            if stored_state.meter_accumulated_liters is not None
            and stored_state.meter_last_raw_liters is not None
            else None
        )
        self._actuators = HomeAssistantActuators(hass)
        self._meter = HomeAssistantMeter(
            hass,
            cast(str | None, meter_entity) if self._has_meter else None,
            liters_per_count=liters_per_count,
            continuity=continuity,
        )
        self._executor = IrrigationExecutor(
            actuators=self._actuators,
            meter=self._meter,
            clock=HomeAssistantClock(),
        )

        self._command_lock = asyncio.Lock()
        self._planning_lock = asyncio.Lock()
        self._queue_event = asyncio.Event()
        self._planning_event = asyncio.Event()
        self._complete_idle_event = asyncio.Event()
        self._terminal_events: dict[str, asyncio.Event] = {}
        self._request_errors: dict[str, Exception] = {}
        self._cancel_requested: set[str] = set()
        self._active_task: asyncio.Task[ExecutionResult] | None = None
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._automatic_planner_task: asyncio.Task[None] | None = None
        self._pending_reload_task: asyncio.Task[None] | None = None
        self._config_reload_pending = False
        self._calibration_task: asyncio.Task[ExecutionResult] | None = None
        self._cancelled_calibrations: set[str] = set()
        self._automatic_planning_in_progress = False
        self._shutting_down = False
        self._watering = False
        self._refresh_complete_idle_event()

    @property
    def _installation_reconfiguration_required(self) -> bool:
        return bool(self._installation_data.get(CONF_NEEDS_RECONFIGURATION, False))

    @staticmethod
    def _zone_reconfiguration_required(data: Mapping[str, object]) -> bool:
        return bool(data.get(CONF_NEEDS_RECONFIGURATION, False))

    @property
    def _operation_enabled(self) -> bool:
        if self._installation_reconfiguration_required:
            return False
        stored = self._stored_state.operation_enabled
        return (
            stored
            if stored is not None
            else bool(self._installation_data.get(CONF_OPERATION_ENABLED, True))
        )

    @property
    def _automation_enabled(self) -> bool:
        if self._installation_reconfiguration_required:
            return False
        stored = self._stored_state.automation_enabled
        return (
            stored
            if stored is not None
            else bool(self._installation_data.get(CONF_AUTOMATION_ENABLED, True))
        )

    def _zone_operation_released(self, zone: _ZoneConfigSnapshot) -> bool:
        if self._zone_reconfiguration_required(zone.data):
            return False
        return self._stored_state.zone_operation_enabled.get(
            zone.zone_id, bool(zone.data.get(CONF_OPERATION_ENABLED, True))
        )

    def _zone_automation_released(self, zone: _ZoneConfigSnapshot) -> bool:
        if self._zone_reconfiguration_required(zone.data):
            return False
        return self._stored_state.zone_automation_enabled.get(
            zone.zone_id, bool(zone.data.get(CONF_AUTOMATION_ENABLED, False))
        )

    def _require_reconfigured(self, zone: _ZoneConfigSnapshot | None = None) -> None:
        if self._installation_reconfiguration_required or (
            zone is not None and self._zone_reconfiguration_required(zone.data)
        ):
            raise HomeAssistantError(
                "Irrigation reconfiguration must be completed before actuation"
            )

    def snapshot(self) -> InstallationSnapshot:
        """Return the current entity presentation contract."""
        return self._coordinator.data

    async def async_initialize(self) -> None:
        """Initialize persistence and recover only a durably active execution."""
        await self._async_initialize_releases()
        await self._async_cancel_stale_pending_snapshots()
        active = self._stored_state.active_execution
        if active is not None:
            entities = [active.zone_valve]
            if active.main_valve is not None:
                entities.append(active.main_valve)
            try:
                await self._async_close_entities(entities)
            except Exception as err:  # noqa: BLE001
                self._stored_state = replace(
                    self._stored_state,
                    installation_safety_lock=f"Startup recovery failed: {err}",
                    installation_safety_lock_at=datetime.now(UTC).isoformat(),
                )
            await self._async_recover_interrupted_execution()
        elif self._operation_enabled:
            main_valve = self._installation_data.get(CONF_MAIN_VALVE)
            if isinstance(main_valve, str):
                with suppress(Exception):
                    await self._actuators.close(main_valve)

        if self._has_meter:
            with suppress(HomeAssistantError):
                await self._async_reconcile_meter_source()
        await self._async_expire_requests()
        await self.async_plan_automatic()
        self._publish(status="idle", active_zone_id=None)
        self._dispatcher_task = self._entry.async_create_background_task(
            self._hass,
            self._async_dispatch_requests(),
            "Irrigation Manager request dispatcher",
        )
        self._automatic_planner_task = self._entry.async_create_background_task(
            self._hass,
            self._async_automatic_planner(),
            "Irrigation Manager automatic planner",
        )

    async def _async_initialize_releases(self) -> None:
        operation = self._stored_state.operation_enabled
        automation = self._stored_state.automation_enabled
        zone_operation = dict(self._stored_state.zone_operation_enabled)
        zone_automation = dict(self._stored_state.zone_automation_enabled)
        changed = False
        if operation is None:
            operation = bool(self._installation_data.get(CONF_OPERATION_ENABLED, True))
            changed = True
        if automation is None:
            automation = bool(self._installation_data.get(CONF_AUTOMATION_ENABLED, True))
            changed = True
        for zone in self._zone_configs:
            if zone.zone_id not in zone_operation:
                zone_operation[zone.zone_id] = bool(zone.data.get(CONF_OPERATION_ENABLED, True))
                changed = True
            if zone.zone_id not in zone_automation:
                zone_automation[zone.zone_id] = bool(zone.data.get(CONF_AUTOMATION_ENABLED, False))
                changed = True
        if changed:
            self._stored_state = replace(
                self._stored_state,
                operation_enabled=operation,
                automation_enabled=automation,
                zone_operation_enabled=zone_operation,
                zone_automation_enabled=zone_automation,
            )
            await self._store.async_save(self._stored_state)

    async def _async_cancel_stale_pending_snapshots(self) -> None:
        """Cancel queued work whose immutable actuator snapshot no longer matches config."""
        changed = False
        requests: list[ManualIrrigationRequest] = []
        for request in self._stored_state.manual_requests:
            zone = self._zone_configs_by_subentry_id.get(request.zone_subentry_id)
            valid = (
                zone is not None
                and zone.zone_id == request.zone_id
                and zone.data.get(CONF_ZONE_VALVE) == request.zone_valve
                and request.main_valve == self._main_valve
            )
            if request.status == "pending" and not valid:
                request = replace(request, status="cancelled", revision=request.revision + 1)
                changed = True
            requests.append(request)
        if changed:
            self._stored_state = replace(self._stored_state, manual_requests=tuple(requests))
            await self._store.async_save(self._stored_state)

    async def async_shutdown(self) -> None:
        """Stop manager-owned tasks and safely recover an active execution."""
        self._shutting_down = True
        tasks = [
            task
            for task in (
                self._pending_reload_task,
                self._dispatcher_task,
                self._automatic_planner_task,
                self._active_task,
                self._calibration_task,
            )
            if task is not None and task is not asyncio.current_task()
        ]
        self._dispatcher_task = None
        self._automatic_planner_task = None
        self._pending_reload_task = None
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self._stored_state.active_execution is not None:
            await self._async_recover_interrupted_execution()

    async def async_request_config_reload(self) -> None:
        """Coalesce one reload and apply it when no execution owns old config."""
        if self._shutting_down or self._pending_reload_task is not None:
            return
        self._config_reload_pending = True
        self._queue_event.set()
        self._pending_reload_task = self._hass.async_create_task(
            self._async_reload_when_idle(),
            "Irrigation Manager deferred config reload",
        )

    async def _async_reload_when_idle(self) -> None:
        current = asyncio.current_task()
        try:
            while not self._shutting_down:
                self._complete_idle_event.clear()
                if self._is_complete_idle():
                    await self._hass.config_entries.async_reload(self._entry.entry_id)
                    return
                await self._complete_idle_event.wait()
        except asyncio.CancelledError:
            return
        finally:
            if self._pending_reload_task is current:
                self._pending_reload_task = None
                self._config_reload_pending = False

    def _is_complete_idle(self) -> bool:
        return (
            self._stored_state.active_execution is None
            and (self._active_task is None or self._active_task.done())
            and (self._calibration_task is None or self._calibration_task.done())
        )

    def _refresh_complete_idle_event(self) -> None:
        if self._is_complete_idle():
            self._complete_idle_event.set()
        else:
            self._complete_idle_event.clear()

    async def async_plan_automatic(
        self, *, dry_run: bool = False, now: datetime | None = None
    ) -> dict[str, object]:
        """Atomically replace pending automatic requests for a two-week horizon."""
        async with self._planning_lock:
            async with self._command_lock:
                self._automatic_planning_in_progress = True
            try:
                return await self._async_plan_automatic_locked(dry_run=dry_run, now=now)
            finally:
                async with self._command_lock:
                    self._automatic_planning_in_progress = False
                    self._queue_event.set()

    async def _async_plan_automatic_locked(
        self, *, dry_run: bool, now: datetime | None
    ) -> dict[str, object]:
        """Plan while excluding concurrent replans from the dispatch commit."""
        planning_now = (now or dt_util.now()).astimezone(UTC)
        local_now = dt_util.as_local(planning_now)
        candidates: list[ManualIrrigationRequest] = []
        releases_allow = (
            self._operation_enabled
            and self._automation_enabled
            and self._stored_state.installation_safety_lock is None
            and not self._stored_state.emergency_stop
        )
        if releases_allow:
            for zone in self._zone_configs:
                schedule = zone.data.get(CONF_WEEKLY_SCHEDULE)
                if (
                    not self._zone_operation_released(zone)
                    or not self._zone_automation_released(zone)
                    or not isinstance(schedule, list)
                    or len(schedule) != 7
                ):
                    continue
                if any(
                    not isinstance(row, Mapping) or row.get("weekday") != WEEKDAYS[index]
                    for index, row in enumerate(schedule)
                ):
                    raise HomeAssistantError(f"Invalid weekly schedule for zone {zone.title}")
                for offset in range(-1, 14):
                    day = local_now.date() + timedelta(days=offset)
                    row = schedule[day.weekday()]
                    if not isinstance(row, Mapping):
                        raise HomeAssistantError(f"Invalid weekly schedule for zone {zone.title}")
                    start_value = row.get("start")
                    end_value = row.get("end")
                    if start_value is None and end_value is None:
                        continue
                    if start_value is None or end_value is None:
                        raise HomeAssistantError(f"Incomplete weekly window for zone {zone.title}")
                    try:
                        start_time = time.fromisoformat(str(start_value))
                        end_time = time.fromisoformat(str(end_value))
                        target, uses_override = effective_schedule_target(zone.data, row)
                    except (TypeError, ValueError) as err:
                        raise HomeAssistantError(
                            f"Invalid weekly target for zone {zone.title}: {err}"
                        ) from err
                    start = resolve_local_wall_time(day, start_time, dt_util.DEFAULT_TIME_ZONE)
                    end = resolve_local_wall_time(day, end_time, dt_util.DEFAULT_TIME_ZONE)
                    if end <= start:
                        end = resolve_local_wall_time(
                            day + timedelta(days=1), end_time, dt_util.DEFAULT_TIME_ZONE
                        )
                    if end <= planning_now:
                        continue
                    control_type = str(zone.data.get(CONF_CONTROL_TYPE, "time"))
                    hard_limit = (
                        self._optional_float(zone.data, CONF_VOLUME_MAX_RUNTIME)
                        if control_type == CONTROL_TYPE_VOLUME
                        else None
                    )
                    if control_type == CONTROL_TYPE_VOLUME and (
                        not self._has_meter or hard_limit is None
                    ):
                        continue
                    expected_start = max(planning_now, start)
                    expected_flow = self._optional_float(zone.data, CONF_EXPECTED_FLOW_L_MIN)
                    required_duration = (
                        planned_volume_duration_seconds(
                            target_liters=target,
                            max_runtime_seconds=hard_limit,
                            expected_flow_l_min=expected_flow,
                        )
                        if hard_limit is not None
                        else target
                    )
                    if start + timedelta(seconds=required_duration) > end:
                        raise HomeAssistantError(
                            f"Weekly target for zone {zone.title} does not fit its window"
                        )
                    if expected_start + timedelta(seconds=required_duration) > end:
                        continue
                    candidates.append(
                        ManualIrrigationRequest(
                            request_id=f"automatic:{zone.zone_id}:{day.isoformat()}",
                            sequence=0,
                            zone_id=zone.zone_id,
                            zone_subentry_id=zone.subentry_id,
                            zone_name=zone.title,
                            zone_valve=str(zone.data[CONF_ZONE_VALVE]),
                            main_valve=self._main_valve,
                            target_type=(
                                "volume" if control_type == CONTROL_TYPE_VOLUME else "duration"
                            ),
                            target_value=target,
                            remaining_value=target,
                            created_at=planning_now.isoformat(),
                            expires_at=end.isoformat(),
                            requested_start_at=expected_start.isoformat(),
                            source="automatic",
                            automatic_window_end=end.isoformat(),
                            hard_time_limit_seconds=hard_limit,
                            delivery_runtime_limit_seconds=hard_limit or target,
                            operation_deadline_at=end.isoformat(),
                            resolved_inputs={
                                "base_target": zone.data.get(CONF_BASE_TARGET),
                                "day_target_override": row.get("target"),
                                "used_day_target_override": uses_override,
                                "effective_target": target,
                                "weekly_window_start": start.isoformat(),
                                "planned_delivery_duration_seconds": required_duration,
                                "planning_basis": (
                                    "calibrated_flow"
                                    if expected_flow is not None and expected_flow > 0
                                    else "maximum_runtime"
                                ),
                            },
                        )
                    )

        candidates = self._automatic_candidates_that_fit(candidates, planning_now)

        async with self._command_lock:
            pending = {
                request.request_id: request
                for request in self._stored_state.manual_requests
                if request.source == "automatic" and request.status == "pending"
            }
            sequence = self._stored_state.next_request_sequence
            reconciled: list[ManualIrrigationRequest] = []
            created: list[str] = []
            replaced_ids: list[str] = []
            for candidate in candidates:
                existing = pending.get(candidate.request_id)
                if existing is None:
                    reconciled.append(replace(candidate, sequence=sequence))
                    sequence += 1
                    created.append(candidate.request_id)
                    continue
                comparable = replace(
                    candidate,
                    sequence=existing.sequence,
                    created_at=existing.created_at,
                    requested_start_at=existing.requested_start_at,
                    revision=existing.revision,
                )
                if comparable == existing:
                    reconciled.append(existing)
                else:
                    reconciled.append(
                        replace(
                            candidate,
                            sequence=existing.sequence,
                            created_at=existing.created_at,
                            revision=existing.revision + 1,
                        )
                    )
                    replaced_ids.append(candidate.request_id)
            candidate_ids = {request.request_id for request in candidates}
            removed = sorted(pending.keys() - candidate_ids)
            retained = tuple(
                request
                for request in self._stored_state.manual_requests
                if not (request.source == "automatic" and request.status == "pending")
            )
            created.sort()
            replaced_ids.sort()
            changed = bool(created or replaced_ids or removed)
            if changed and not dry_run:
                next_state = replace(
                    self._stored_state,
                    manual_requests=(*retained, *reconciled),
                    next_request_sequence=sequence,
                )
                await self._store.async_save(next_state)
                self._stored_state = next_state
                self._queue_event.set()
                self._publish(status=self._coordinator.data.status, active_zone_id=None)
            return {
                "dry_run": dry_run,
                "horizon_days": 14,
                "created": len(created),
                "replaced": len(replaced_ids),
                "removed": len(removed),
                "created_request_ids": [] if dry_run else created,
                "would_create_request_ids": created if dry_run else [],
                "replaced_request_ids": replaced_ids,
                "removed_request_ids": removed,
            }

    def _automatic_candidates_that_fit(
        self,
        candidates: list[ManualIrrigationRequest],
        now: datetime,
    ) -> list[ManualIrrigationRequest]:
        """Simulate the single dispatcher and retain only whole in-window operations."""
        pending = [
            request
            for request in self._stored_state.manual_requests
            if request.status == "pending" and request.source != "automatic"
        ]
        pending.extend(candidates)
        active = self._stored_state.active_execution
        cursor = now
        if active is not None:
            request = self._request(active.request_id) if active.request_id else None
            if request is not None:
                cursor += self._request_expected_duration(request)
        retained: list[ManualIrrigationRequest] = []
        while pending:
            ready = [
                request
                for request in pending
                if datetime.fromisoformat(request.requested_start_at or request.created_at)
                <= cursor
            ]
            if not ready:
                cursor = min(
                    datetime.fromisoformat(request.requested_start_at or request.created_at)
                    for request in pending
                )
                ready = [
                    request
                    for request in pending
                    if datetime.fromisoformat(request.requested_start_at or request.created_at)
                    <= cursor
                ]
            request = min(ready, key=request_priority)
            expected_start = max(
                cursor,
                datetime.fromisoformat(request.requested_start_at or request.created_at),
            )
            expected_end = expected_start + self._request_expected_duration(request)
            pending.remove(request)
            if request.source == "automatic":
                window_end = datetime.fromisoformat(
                    request.automatic_window_end or request.expires_at
                )
                if expected_end > window_end:
                    continue
                retained.append(request)
            cursor = expected_end
        return retained

    async def _async_automatic_planner(self) -> None:
        """Replan at local-day boundaries and explicit release changes."""
        while not self._shutting_down:
            self._planning_event.clear()
            try:
                await self.async_plan_automatic()
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._planning_event.wait(), timeout=3_600)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                await asyncio.sleep(60)

    async def async_start_manual(
        self,
        *,
        zone_subentry_id: str,
        duration_seconds: float | None,
        amount_liters: float | None,
        hard_time_limit_seconds: float | None,
        expiry_seconds: float | None = None,
        requested_start_at: datetime | None = None,
        wait_for_completion: bool = True,
        conflict_policy: str | None = None,
    ) -> dict[str, object]:
        """Validate and durably queue one fixed-target manual request."""
        active_to_stop: str | None = None
        async with self._command_lock:
            self._require_reconfigured()
            if not self._operation_enabled:
                raise HomeAssistantError(
                    "The irrigation installation operation release is disabled"
                )
            if self._stored_state.installation_safety_lock is not None:
                raise HomeAssistantError("The irrigation installation safety lock is active")
            if self._stored_state.emergency_stop:
                raise HomeAssistantError("The irrigation installation emergency stop is active")
            zone = self._zone_for_subentry(zone_subentry_id)
            self._require_reconfigured(zone)
            if not self._zone_operation_released(zone):
                raise HomeAssistantError("The irrigation zone operation release is disabled")
            active = self._stored_state.active_execution
            if conflict_policy == "start_now" and active is not None:
                raise HomeAssistantError("Another irrigation execution is active")
            if conflict_policy in {"stop_active", "priority_next"} and active is None:
                raise HomeAssistantError("No conflicting irrigation execution is active")
            if conflict_policy == "stop_active" and active is not None:
                active_to_stop = active.request_id
            if (duration_seconds is None) == (amount_liters is None):
                raise HomeAssistantError("Exactly one irrigation target is required")
            if amount_liters is not None and not self._has_meter:
                raise HomeAssistantError("Volume irrigation requires a configured water meter")
            if amount_liters is not None and hard_time_limit_seconds is None:
                raise HomeAssistantError("Volume irrigation requires a hard time limit")
            target_type = "volume" if amount_liters is not None else "duration"
            target_value = amount_liters if amount_liters is not None else duration_seconds
            runtime = hard_time_limit_seconds if amount_liters is not None else duration_seconds
            assert target_value is not None
            assert runtime is not None
            runtime_limit = self._validated_runtime(
                zone.data, runtime, volume=amount_liters is not None
            )
            now = datetime.now(UTC)
            start = max((requested_start_at or now).astimezone(UTC), now)
            expires = start + timedelta(
                seconds=(
                    expiry_seconds if expiry_seconds is not None else max(3_600.0, runtime_limit)
                )
            )
            operation_deadline = min(
                expires,
                start
                + timedelta(
                    seconds=max(
                        runtime_limit,
                        self._number(
                            zone.data,
                            CONF_MAX_OPERATION_LIFETIME,
                            max(14_400.0, runtime_limit),
                        ),
                    )
                ),
            )
            request = ManualIrrigationRequest(
                request_id=uuid4().hex,
                sequence=self._stored_state.next_request_sequence,
                zone_id=zone.zone_id,
                zone_subentry_id=zone.subentry_id,
                zone_name=zone.title,
                zone_valve=str(zone.data[CONF_ZONE_VALVE]),
                main_valve=self._main_valve,
                target_type=target_type,
                target_value=target_value,
                remaining_value=target_value,
                created_at=now.isoformat(),
                expires_at=expires.isoformat(),
                requested_start_at=start.isoformat(),
                hard_time_limit_seconds=(runtime_limit if amount_liters is not None else None),
                delivery_runtime_limit_seconds=runtime_limit,
                operation_deadline_at=operation_deadline.isoformat(),
            )
            next_state = replace(
                self._stored_state,
                manual_requests=(*self._stored_state.manual_requests, request),
                next_request_sequence=self._stored_state.next_request_sequence + 1,
            )
            await self._store.async_save(next_state)
            self._stored_state = next_state
            terminal = self._terminal_events.setdefault(request.request_id, asyncio.Event())
            self._queue_event.set()
            self._publish(status=self._coordinator.data.status, active_zone_id=None)
        if active_to_stop is not None:
            await self.async_stop(request_id=active_to_stop)
        if wait_for_completion:
            await terminal.wait()
            if error := self._request_errors.pop(request.request_id, None):
                raise error
        return {"request_id": request.request_id, "warnings": []}

    async def _async_dispatch_requests(self) -> None:
        """Execute ready requests strictly one at a time."""
        while not self._shutting_down:
            self._queue_event.clear()
            selected: ManualIrrigationRequest | None = None
            try:
                async with self._command_lock:
                    await self._async_expire_requests()
                    selected = select_manual_request(
                        now=datetime.now(UTC),
                        requests=self._stored_state.manual_requests,
                    )
                    if self._automatic_planning_in_progress or self._config_reload_pending:
                        selected = None
                    if selected is not None and not self._request_released(selected):
                        selected = None
                    if selected is not None:
                        task = await self._async_prepare_execution(selected)
                if selected is None:
                    timeout = self._seconds_until_next_request_change()
                    with suppress(TimeoutError):
                        await asyncio.wait_for(self._queue_event.wait(), timeout=timeout)
                    continue
                result = await asyncio.shield(task)
                async with self._command_lock:
                    await self._async_finish_execution(selected.request_id, result)
            except asyncio.CancelledError:
                return
            except Exception as err:  # noqa: BLE001
                if selected is not None:
                    async with self._command_lock:
                        await self._async_fail_request(selected.request_id, err)
            finally:
                self._watering = False
                if self._active_task is not None and self._active_task.done():
                    self._active_task = None
                self._publish(status="idle", active_zone_id=None)

    def _request_released(self, request: ManualIrrigationRequest) -> bool:
        if (
            not self._operation_enabled
            or self._stored_state.installation_safety_lock is not None
            or self._stored_state.emergency_stop
        ):
            return False
        zone = self._zone_configs_by_subentry_id.get(request.zone_subentry_id)
        if (
            zone is None
            or not self._zone_operation_released(zone)
            or zone.zone_id != request.zone_id
            or zone.data.get(CONF_ZONE_VALVE) != request.zone_valve
            or request.main_valve != self._main_valve
        ):
            return False
        if (
            request.source == "automatic"
            and request.automatic_window_end is not None
            and datetime.now(UTC) + self._request_expected_duration(request)
            > datetime.fromisoformat(request.automatic_window_end)
        ):
            return False
        return request.source != "automatic" or (
            self._automation_enabled and self._zone_automation_released(zone)
        )

    async def _async_prepare_execution(
        self, request: ManualIrrigationRequest
    ) -> asyncio.Task[ExecutionResult]:
        """Claim a selected request durably before opening hardware."""
        current = self._request(request.request_id)
        if current != request or current is None:
            raise HomeAssistantError("The irrigation request changed before execution")
        self._require_reconfigured(self._zone_for_subentry(request.zone_subentry_id))
        if self._stored_state.emergency_stop:
            raise HomeAssistantError("The irrigation installation emergency stop is active")
        if self._stored_state.active_execution is not None:
            raise HomeAssistantError("The irrigation installation is busy")
        if request.operation_deadline_at is not None and datetime.fromisoformat(
            request.operation_deadline_at
        ) <= datetime.now(UTC):
            raise HomeAssistantError("The irrigation request expired")
        execution_id = uuid4().hex
        now = datetime.now(UTC)
        execution = IrrigationExecutionState(
            execution_id=execution_id,
            request_id=request.request_id,
            zone_id=request.zone_id,
            target_type=request.target_type,
            target_value=request.target_value,
            remaining_value=request.remaining_value,
            status="watering",
            created_at=now.isoformat(),
            operation_deadline_at=request.operation_deadline_at,
            delivery_runtime_limit_seconds=request.delivery_runtime_limit_seconds,
        )
        claimed = replace(
            request,
            execution_id=execution_id,
            status="executing",
            revision=request.revision + 1,
        )
        duration = request.remaining_value if request.target_type == "duration" else None
        amount = request.remaining_value if request.target_type == "volume" else None
        runtime_limit = request.delivery_runtime_limit_seconds or request.hard_time_limit_seconds
        if duration is None and runtime_limit is None:
            raise HomeAssistantError("Volume irrigation requires a hard time limit")
        meter_baseline: float | None = None
        if self._has_meter:
            try:
                meter_baseline = await self._meter.read_liters()
            except Exception as err:
                if amount is not None:
                    raise HomeAssistantError(
                        "Volume irrigation water meter is unavailable"
                    ) from err
        active = ActiveExecutionState(
            zone_id=request.zone_id,
            zone_valve=request.zone_valve,
            main_valve=request.main_valve,
            meter_raw_baseline_liters=meter_baseline,
            prepared_at=now.isoformat(),
            watering_started_at=None,
            requested_duration_seconds=duration or cast(float, runtime_limit),
            requested_amount_liters=amount,
            hard_time_limit_seconds=runtime_limit if amount is not None else None,
            delivery_deadline_at=(
                now + timedelta(seconds=duration or cast(float, runtime_limit))
            ).isoformat(),
            operation_deadline_at=request.operation_deadline_at,
            request_id=request.request_id,
            execution_id=execution_id,
        )
        next_state = replace(
            self._stored_state,
            manual_requests=self._with_request(claimed),
            irrigation_executions=(*self._stored_state.irrigation_executions, execution),
            active_execution=active,
        )
        await self._store.async_save(next_state)
        self._stored_state = next_state
        self._watering = True
        task = self._hass.async_create_task(
            self._async_execute(
                ExecutionRequest(
                    zone_id=request.zone_id,
                    zone_valve=request.zone_valve,
                    main_valve=request.main_valve,
                    duration_seconds=duration,
                    amount_liters=amount,
                    hard_time_limit_seconds=(runtime_limit if amount is not None else None),
                    monitor_interval_seconds=(
                        min(1.0, cast(float, runtime_limit)) if amount else 0
                    ),
                    require_meter_progress=amount is not None,
                    on_zone_opening=self._async_mark_zone_opening,
                    on_zone_opened=self._async_mark_zone_opened,
                    on_progress=self._async_update_progress,
                    on_actuator_command=self._async_authorize_actuator_command,
                )
            ),
            f"Irrigation Manager execution for {request.zone_name}",
        )
        self._active_task = task
        self._publish(status="watering", active_zone_id=request.zone_id)
        return task

    async def _async_execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = await self._executor.execute(request)
        if request.amount_liters is None and not self._has_meter:
            return replace(result, delivered_liters=0.0, measurement_quality="unavailable")
        return result

    async def _async_authorize_actuator_command(self, entity_id: str, open_: bool) -> None:
        """Fail every opening command after emergency stop becomes durable."""
        del entity_id
        if open_ and self._stored_state.emergency_stop:
            raise HomeAssistantError("The irrigation installation emergency stop is active")

    async def _async_mark_zone_opening(self) -> None:
        active = self._stored_state.active_execution
        if active is None:
            raise HomeAssistantError("The durable irrigation execution is missing")
        self._stored_state = replace(
            self._stored_state,
            active_execution=replace(active, zone_opening_at=datetime.now(UTC).isoformat()),
        )
        await self._store.async_save(self._stored_state)

    async def _async_mark_zone_opened(self) -> None:
        active = self._stored_state.active_execution
        if active is None:
            raise HomeAssistantError("The durable irrigation execution is missing")
        self._stored_state = replace(
            self._stored_state,
            active_execution=replace(active, watering_started_at=datetime.now(UTC).isoformat()),
        )
        await self._store.async_save(self._stored_state)

    async def _async_update_progress(self, remaining: float, quality: str) -> None:
        del remaining, quality
        self._publish(status="watering", active_zone_id=self._active_zone_id)

    async def _async_finish_execution(self, request_id: str, result: ExecutionResult) -> None:
        request = self._request(request_id)
        if request is None or request.execution_id is None:
            return
        execution = self._execution(request.execution_id)
        active = self._stored_state.active_execution
        if (
            execution is None
            or request.status != "executing"
            or execution.status != "watering"
            or active is None
            or active.request_id != request_id
            or active.execution_id != execution.execution_id
        ):
            return
        now = datetime.now(UTC)
        delivered_target = (
            result.delivered_liters if request.target_type == "volume" else result.duration_seconds
        )
        remaining = max(0.0, request.remaining_value - delivered_target)
        cancelled = request_id in self._cancel_requested
        failed = result.safety_violation is not None or (
            request.target_type == "volume" and not result.target_reached
        )
        if cancelled:
            request_status, execution_status, completion = "cancelled", "cancelled", "stopped"
        elif failed:
            request_status, execution_status = "cancelled", "failed"
            completion = result.safety_violation or "volume_target_not_reached"
        else:
            request_status = "completed"
            execution_status = "completed"
            completion = "target_reached"
            remaining = 0.0
        request = replace(
            request,
            remaining_value=remaining,
            status=request_status,
            revision=request.revision + 1,
        )
        execution = replace(
            execution,
            remaining_value=remaining,
            status=execution_status,
            delivered_liters=execution.delivered_liters + result.delivered_liters,
            delivered_duration_seconds=(
                execution.delivered_duration_seconds + result.duration_seconds
            ),
            ended_at=now.isoformat(),
            result=completion,
            measurement_quality=result.measurement_quality,
            measurement_origin=(
                "meter" if result.measurement_quality == "measured" else "unavailable"
            ),
            warnings=((result.safety_violation,) if result.safety_violation is not None else ()),
        )
        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[request.zone_id] = (
            zone_totals.get(request.zone_id, 0.0) + result.delivered_liters
        )
        qualities = dict(self._stored_state.zone_measurement_quality)
        qualities[request.zone_id] = result.measurement_quality
        last_liters = dict(self._stored_state.zone_last_delivered_liters)
        last_liters[request.zone_id] = result.delivered_liters
        last_duration = dict(self._stored_state.zone_last_duration_seconds)
        last_duration[request.zone_id] = result.duration_seconds
        installation_lock = self._stored_state.installation_safety_lock
        installation_lock_at = self._stored_state.installation_safety_lock_at
        if failed:
            installation_lock = completion
            installation_lock_at = now.isoformat()
            self._request_errors[request_id] = HomeAssistantError(str(completion))
        history = self._stored_state.water_consumption_history
        if result.delivered_liters > 0:
            history = (
                *history,
                WaterConsumptionRecord(
                    recorded_at=now.isoformat(),
                    amount_liters=result.delivered_liters,
                    zone_id=request.zone_id,
                    source=request.source,
                    quality=result.measurement_quality,
                    request_id=request.request_id,
                    execution_id=execution.execution_id,
                ),
            )[-50_000:]
        next_state = replace(
            self._stored_state,
            installation_total_liters=(
                self._stored_state.installation_total_liters + result.delivered_liters
            ),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=qualities,
            zone_last_delivered_liters=last_liters,
            zone_last_duration_seconds=last_duration,
            installation_safety_lock=installation_lock,
            installation_safety_lock_at=installation_lock_at,
            manual_requests=self._with_request(request),
            irrigation_executions=self._with_execution(execution),
            active_execution=None,
            water_consumption_history=history,
        )
        self._stored_state = self._with_meter_continuity(next_state)
        await self._store.async_save(self._stored_state)
        self._cancel_requested.discard(request_id)
        self._signal_terminal(request_id)
        self._planning_event.set()
        self._refresh_complete_idle_event()

    async def _async_fail_request(self, request_id: str, error: Exception) -> None:
        request = self._request(request_id)
        if request is None or request.status in _FINAL_REQUEST_STATUSES:
            return
        now = datetime.now(UTC).isoformat()
        failed = replace(request, status="cancelled", revision=request.revision + 1)
        execution = self._execution(request.execution_id)
        executions = (
            self._with_execution(
                replace(execution, status="failed", ended_at=now, result=str(error))
            )
            if execution is not None
            else self._stored_state.irrigation_executions
        )
        self._stored_state = replace(
            self._stored_state,
            manual_requests=self._with_request(failed),
            irrigation_executions=executions,
            active_execution=None,
            installation_safety_lock=str(error),
            installation_safety_lock_at=now,
        )
        self._stored_state = self._with_meter_continuity(self._stored_state)
        await self._store.async_save(self._stored_state)
        self._request_errors[request_id] = error
        self._signal_terminal(request_id)
        self._refresh_complete_idle_event()

    async def _async_recover_interrupted_execution(self) -> None:
        active = self._stored_state.active_execution
        if active is None:
            return
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        delivered_duration = 0.0
        if active.watering_started_at is not None:
            try:
                delivered_duration = min(
                    active.requested_duration_seconds,
                    max(
                        0.0,
                        (
                            now_dt - datetime.fromisoformat(active.watering_started_at)
                        ).total_seconds(),
                    ),
                )
            except ValueError:
                delivered_duration = 0.0
        delivered_liters = 0.0
        quality = "unavailable"
        warnings: tuple[str, ...] = ("Startup recovery could not reconstruct measured water",)
        if self._has_meter and active.meter_raw_baseline_liters is not None:
            try:
                current = await self._meter.read_liters()
                if current < active.meter_raw_baseline_liters:
                    raise ValueError("Water meter regressed during startup recovery")
                delivered_liters = current - active.meter_raw_baseline_liters
                quality = "measured"
                warnings = ()
            except Exception:  # noqa: BLE001
                pass
        request = self._request(active.request_id) if active.request_id else None
        delivered_target = (
            delivered_liters
            if request is not None and request.target_type == "volume"
            else delivered_duration
        )
        requests = tuple(
            replace(
                item,
                status="cancelled",
                remaining_value=max(0.0, item.remaining_value - delivered_target),
                revision=item.revision + 1,
            )
            if item.request_id == active.request_id and item.status not in _FINAL_REQUEST_STATUSES
            else item
            for item in self._stored_state.manual_requests
        )
        executions = tuple(
            replace(
                item,
                status="interrupted",
                remaining_value=max(0.0, item.remaining_value - delivered_target),
                delivered_liters=item.delivered_liters + delivered_liters,
                delivered_duration_seconds=(item.delivered_duration_seconds + delivered_duration),
                ended_at=now,
                result="restart_recovered" if quality == "measured" else "restart_degraded",
                measurement_quality=quality,
                measurement_origin="meter" if quality == "measured" else "unavailable",
                warnings=(*item.warnings, *warnings),
            )
            if item.execution_id == active.execution_id
            else item
            for item in self._stored_state.irrigation_executions
        )
        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[active.zone_id] = zone_totals.get(active.zone_id, 0.0) + delivered_liters
        history = self._stored_state.water_consumption_history
        if delivered_liters > 0:
            history = (
                *history,
                WaterConsumptionRecord(
                    recorded_at=now,
                    amount_liters=delivered_liters,
                    zone_id=active.zone_id,
                    source=request.source if request is not None else "manual",
                    quality=quality,
                    request_id=active.request_id,
                    execution_id=active.execution_id,
                    warnings=warnings,
                ),
            )[-50_000:]
        self._stored_state = replace(
            self._stored_state,
            active_execution=None,
            manual_requests=requests,
            irrigation_executions=executions,
            installation_total_liters=(
                self._stored_state.installation_total_liters + delivered_liters
            ),
            zone_totals_liters=zone_totals,
            zone_measurement_quality={
                **self._stored_state.zone_measurement_quality,
                active.zone_id: quality,
            },
            zone_last_delivered_liters={
                **self._stored_state.zone_last_delivered_liters,
                active.zone_id: delivered_liters,
            },
            zone_last_duration_seconds={
                **self._stored_state.zone_last_duration_seconds,
                active.zone_id: delivered_duration,
            },
            water_consumption_history=history,
            water_history_incomplete=(
                self._stored_state.water_history_incomplete or quality != "measured"
            ),
        )
        self._stored_state = self._with_meter_continuity(self._stored_state)
        await self._store.async_save(self._stored_state)
        if active.request_id is not None:
            self._signal_terminal(active.request_id)
        self._refresh_complete_idle_event()

    async def _async_expire_requests(self, *, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        changed = False
        expired_ids: list[str] = []
        requests: list[ManualIrrigationRequest] = []
        for request in self._stored_state.manual_requests:
            if (
                request.status == "pending"
                and datetime.fromisoformat(request.operation_deadline_at or request.expires_at)
                <= current
            ):
                request = replace(request, status="expired", revision=request.revision + 1)
                changed = True
                expired_ids.append(request.request_id)
            requests.append(request)
        if changed:
            self._stored_state = replace(self._stored_state, manual_requests=tuple(requests))
            await self._store.async_save(self._stored_state)
            for request_id in expired_ids:
                self._signal_terminal(request_id)

    async def async_set_installation_operation(self, *, enabled: bool) -> dict[str, object]:
        """Persist the installation operation release and stop active water."""
        if enabled:
            self._require_reconfigured()
            if any(self._zone_reconfiguration_required(zone.data) for zone in self._zone_configs):
                raise HomeAssistantError("Irrigation reconfiguration must be completed first")
        if not enabled:
            await self.async_stop_calibration(require_active=False)
        active_request_id: str | None
        async with self._command_lock:
            active = self._stored_state.active_execution
            active_request_id = active.request_id if active is not None else None
            next_state = replace(self._stored_state, operation_enabled=enabled)
            await self._store.async_save(next_state)
            self._stored_state = next_state
            self._publish(status="idle", active_zone_id=None)
            self._queue_event.set()
        if not enabled and active_request_id is not None:
            await self.async_stop(request_id=active_request_id)
        return {"operation_enabled": enabled}

    async def async_set_installation_automation(
        self, *, enabled: bool, stop_active: bool
    ) -> dict[str, object]:
        """Persist the installation automation release independently."""
        if enabled:
            self._require_reconfigured()
            if any(self._zone_reconfiguration_required(zone.data) for zone in self._zone_configs):
                raise HomeAssistantError("Irrigation reconfiguration must be completed first")
        active_request: ManualIrrigationRequest | None = None
        async with self._command_lock:
            active = self._stored_state.active_execution
            active_request = (
                self._request(active.request_id) if active and active.request_id else None
            )
            requests = tuple(
                replace(request, status="cancelled", revision=request.revision + 1)
                if not enabled and request.source == "automatic" and request.status == "pending"
                else request
                for request in self._stored_state.manual_requests
            )
            next_state = replace(
                self._stored_state,
                automation_enabled=enabled,
                manual_requests=requests,
            )
            await self._store.async_save(next_state)
            self._stored_state = next_state
            self._publish(status="idle", active_zone_id=None)
        if (
            not enabled
            and stop_active
            and active_request is not None
            and active_request.source == "automatic"
        ):
            await self.async_stop(request_id=active_request.request_id)
        replan = await self.async_plan_automatic() if enabled else None
        return {"automation_enabled": enabled, "replan": replan}

    async def async_set_zone_operation(
        self, *, zone_subentry_id: str, enabled: bool
    ) -> dict[str, object]:
        """Persist one zone operation release."""
        zone = self._zone_for_subentry(zone_subentry_id)
        if enabled:
            self._require_reconfigured(zone)
        active = self._stored_state.active_execution
        if not enabled and active is not None and active.zone_id == zone.zone_id:
            await self.async_stop_calibration(require_active=False)
        active_request_id: str | None = None
        async with self._command_lock:
            releases = dict(self._stored_state.zone_operation_enabled)
            releases[zone.zone_id] = enabled
            active = self._stored_state.active_execution
            if active is not None and active.zone_id == zone.zone_id:
                active_request_id = active.request_id
            next_state = replace(self._stored_state, zone_operation_enabled=releases)
            await self._store.async_save(next_state)
            self._stored_state = next_state
            self._publish(status="idle", active_zone_id=None)
            self._queue_event.set()
        if not enabled and active_request_id is not None:
            await self.async_stop(request_id=active_request_id)
        return {"zone_id": zone.zone_id, "operation_enabled": enabled}

    async def async_set_zone_automation(
        self, *, zone_subentry_id: str, enabled: bool, stop_active: bool
    ) -> dict[str, object]:
        """Persist one zone automation release independently."""
        zone = self._zone_for_subentry(zone_subentry_id)
        if enabled:
            self._require_reconfigured(zone)
        active_request: ManualIrrigationRequest | None = None
        async with self._command_lock:
            releases = dict(self._stored_state.zone_automation_enabled)
            releases[zone.zone_id] = enabled
            active = self._stored_state.active_execution
            active_request = (
                self._request(active.request_id) if active and active.request_id else None
            )
            requests = tuple(
                replace(request, status="cancelled", revision=request.revision + 1)
                if not enabled
                and request.zone_id == zone.zone_id
                and request.source == "automatic"
                and request.status == "pending"
                else request
                for request in self._stored_state.manual_requests
            )
            next_state = replace(
                self._stored_state,
                zone_automation_enabled=releases,
                manual_requests=requests,
            )
            await self._store.async_save(next_state)
            self._stored_state = next_state
            self._publish(status="idle", active_zone_id=None)
        if (
            not enabled
            and stop_active
            and active_request is not None
            and active_request.zone_id == zone.zone_id
            and active_request.source == "automatic"
        ):
            await self.async_stop(request_id=active_request.request_id)
        replan = await self.async_plan_automatic() if enabled else None
        return {"zone_id": zone.zone_id, "automation_enabled": enabled, "replan": replan}

    def automatic_execution_active(self, *, zone_subentry_id: str | None = None) -> bool:
        """Return whether an automatic execution matching the scope is active."""
        active = self._stored_state.active_execution
        request = self._request(active.request_id) if active and active.request_id else None
        return bool(
            request is not None
            and request.source == "automatic"
            and (zone_subentry_id is None or request.zone_subentry_id == zone_subentry_id)
        )

    async def async_emergency_stop(self) -> None:
        """Immediately close active hardware and persist the installation lock."""
        async with self._command_lock:
            now = datetime.now(UTC).isoformat()
            self._stored_state = replace(
                self._stored_state,
                emergency_stop=True,
                installation_safety_lock="Emergency stop activated",
                installation_safety_lock_at=now,
            )
            await self._store.async_save(self._stored_state)
            active = self._stored_state.active_execution
        await self.async_stop_calibration(require_active=False)
        active = self._stored_state.active_execution
        if active is not None:
            if active.request_id is not None and self._request(active.request_id) is not None:
                await self.async_cancel_request(active.request_id)
            await self._async_close_entities(
                [entity for entity in (active.zone_valve, active.main_valve) if entity]
            )
            if self._stored_state.active_execution is not None:
                await self._async_recover_interrupted_execution()
        self._publish(status="emergency_stop", active_zone_id=None)

    async def async_reset_safety_lock(self) -> None:
        """Clear the installation lock only while no execution is active."""
        async with self._command_lock:
            if not self._is_complete_idle():
                raise HomeAssistantError("The irrigation installation is busy")
            self._stored_state = replace(
                self._stored_state,
                emergency_stop=False,
                installation_safety_lock=None,
                installation_safety_lock_at=None,
            )
            await self._store.async_save(self._stored_state)
            self._publish(status="idle", active_zone_id=None)

    async def async_stop(
        self,
        *,
        request_id: str | None = None,
        execution_id: str | None = None,
    ) -> None:
        """Cancel one request, or all open requests when no target is supplied."""
        if execution_id is not None:
            execution = self._execution(execution_id)
            if execution is None:
                raise HomeAssistantError("The irrigation execution does not exist")
            request_id = execution.request_id
        if request_id is not None:
            request = self._request(request_id)
            if request is not None and request.source == "calibration":
                await self.async_stop_calibration()
                return
            await self.async_cancel_request(request_id)
            return
        for request in tuple(self._stored_state.manual_requests):
            if request.status not in _FINAL_REQUEST_STATUSES:
                with suppress(HomeAssistantError):
                    await self.async_cancel_request(request.request_id)

    async def async_cancel_request(self, request_id: str) -> None:
        """Cancel a pending or executing request."""
        task: asyncio.Task[ExecutionResult] | None = None
        async with self._command_lock:
            request = self._request(request_id)
            if request is None:
                raise HomeAssistantError("The irrigation request does not exist")
            if request.status in _FINAL_REQUEST_STATUSES:
                raise HomeAssistantError("The irrigation request is already final")
            if request.status == "executing":
                self._cancel_requested.add(request_id)
                task = self._active_task
                if task is not None:
                    task.cancel()
            else:
                cancelled = replace(
                    request,
                    status="cancelled",
                    revision=request.revision + 1,
                )
                self._stored_state = replace(
                    self._stored_state, manual_requests=self._with_request(cancelled)
                )
                await self._store.async_save(self._stored_state)
                self._signal_terminal(request_id)
                self._queue_event.set()
        if task is not None:
            await self._terminal_events.setdefault(request_id, asyncio.Event()).wait()

    def list_manual_requests(self) -> list[dict[str, object]]:
        """Return durable requests in stable sequence order."""
        return [
            request.as_dict()
            for request in sorted(
                self._stored_state.manual_requests,
                key=lambda item: (item.sequence, item.request_id),
            )
        ]

    def list_irrigation_executions(self) -> list[dict[str, object]]:
        """Return persisted executions in creation order."""
        return [execution.as_dict() for execution in self._stored_state.irrigation_executions]

    def card_open_orders(self, *, now: datetime | None = None) -> list[dict[str, object]]:
        """Return serial-queue orders with production-derived expected starts."""
        cursor = now or datetime.now(UTC)
        pending = [
            request
            for request in self._stored_state.manual_requests
            if request.status == "pending" and datetime.fromisoformat(request.expires_at) > cursor
        ]
        orders: list[dict[str, object]] = []
        while pending:
            ready = [
                request
                for request in pending
                if datetime.fromisoformat(request.requested_start_at or request.created_at)
                <= cursor
            ]
            if not ready:
                cursor = min(
                    datetime.fromisoformat(request.requested_start_at or request.created_at)
                    for request in pending
                )
                ready = [
                    request
                    for request in pending
                    if datetime.fromisoformat(request.requested_start_at or request.created_at)
                    <= cursor
                ]
            request = min(ready, key=request_priority)
            desired = datetime.fromisoformat(request.requested_start_at or request.created_at)
            expected_start = max(cursor, desired)
            cursor = expected_start + self._request_expected_duration(request)
            pending.remove(request)
            orders.append(
                {
                    "request_id": request.request_id,
                    "zone_subentry_id": request.zone_subentry_id,
                    "zone": request.zone_name,
                    "source": request.source,
                    "target_type": request.target_type,
                    "target_value": request.target_value,
                    "expected_start": expected_start.isoformat(),
                    "status": request.status,
                }
            )
        return orders

    def zone_history_page(
        self,
        *,
        zone_subentry_id: str,
        offset: int,
        limit: int,
        source: str | None = None,
        result: str | None = None,
    ) -> dict[str, object]:
        """Return one newest-first page of a zone's execution history."""
        zone = self._zone_for_subentry(zone_subentry_id)
        requests = {request.request_id: request for request in self._stored_state.manual_requests}
        items: list[dict[str, object]] = []
        for execution in reversed(self._stored_state.irrigation_executions):
            if execution.zone_id != zone.zone_id:
                continue
            request = requests.get(execution.request_id)
            item_source = request.source if request is not None else "manual"
            if source is not None and item_source != source:
                continue
            if result is not None and result not in {execution.status, execution.result}:
                continue
            items.append(
                {
                    "execution_id": execution.execution_id,
                    "started_at": execution.created_at,
                    "ended_at": execution.ended_at,
                    "source": item_source,
                    "target_type": execution.target_type,
                    "target_value": execution.target_value,
                    "result": execution.status,
                    "actual_duration": execution.delivered_duration_seconds,
                    "actual_water": (
                        execution.delivered_liters
                        if execution.measurement_quality == "measured"
                        else None
                    ),
                    "completion_reason": execution.result,
                }
            )
        page = items[offset : offset + limit]
        return {
            "items": page,
            "offset": offset,
            "limit": limit,
            "total": len(items),
            "has_more": offset + len(page) < len(items),
        }

    def manual_control_entity_ids(
        self,
        *,
        zone_subentry_ids: Iterable[str] = (),
        request_ids: Iterable[str] = (),
        execution_ids: Iterable[str] = (),
        all_open_requests: bool = False,
    ) -> tuple[str, ...]:
        """Resolve actuators affected by one manual runtime action."""
        selected_zone_ids = {
            zone.zone_id
            for subentry_id in zone_subentry_ids
            if (zone := self._zone_configs_by_subentry_id.get(subentry_id)) is not None
        }
        selected_requests = set(request_ids)
        selected_executions = set(execution_ids)
        for execution in self._stored_state.irrigation_executions:
            if execution.execution_id in selected_executions:
                selected_requests.add(execution.request_id)
        entities: set[str] = set()
        for request in self._stored_state.manual_requests:
            if request.request_id in selected_requests or (
                all_open_requests and request.status not in _FINAL_REQUEST_STATUSES
            ):
                entities.add(request.zone_valve)
                if request.main_valve is not None:
                    entities.add(request.main_valve)
        entities.update(
            {
                str(zone.data[CONF_ZONE_VALVE])
                for zone in self._zone_configs
                if zone.zone_id in selected_zone_ids
            }
        )
        if selected_zone_ids and self._main_valve is not None:
            entities.add(self._main_valve)
        return tuple(sorted(entities))

    def emergency_control_entity_ids(self) -> tuple[str, ...]:
        """Return every configured or snapshotted actuator emergency stop may affect."""
        entities = {
            str(zone.data[CONF_ZONE_VALVE])
            for zone in self._zone_configs
            if isinstance(zone.data.get(CONF_ZONE_VALVE), str)
        }
        if self._main_valve is not None:
            entities.add(self._main_valve)
        for request in self._stored_state.manual_requests:
            if request.status not in _FINAL_REQUEST_STATUSES:
                entities.add(request.zone_valve)
                if request.main_valve is not None:
                    entities.add(request.main_valve)
        active = self._stored_state.active_execution
        if active is not None:
            entities.add(active.zone_valve)
            if active.main_valve is not None:
                entities.add(active.main_valve)
        return tuple(sorted(entities))

    async def async_start_calibration(
        self,
        *,
        zone_subentry_id: str,
        duration_seconds: float,
    ) -> dict[str, object]:
        """Run a bounded flow-profile calibration."""
        self._require_reconfigured()
        zone = self._zone_for_subentry(zone_subentry_id)
        self._require_reconfigured(zone)
        if not self._operation_enabled or not self._zone_operation_released(zone):
            raise HomeAssistantError("The irrigation operation release is disabled")
        if self._stored_state.installation_safety_lock is not None:
            raise HomeAssistantError("The irrigation installation safety lock is active")
        if self._stored_state.emergency_stop:
            raise HomeAssistantError("The irrigation installation emergency stop is active")
        if not self._has_meter:
            raise HomeAssistantError("Calibration requires a cumulative water meter")
        if not self._is_complete_idle():
            raise HomeAssistantError("The irrigation installation is busy")
        if duration_seconds <= 0 or duration_seconds > 300:
            raise HomeAssistantError("Calibration duration must be between 0 and 300 seconds")
        test_id = uuid4().hex
        request_id = f"calibration:{test_id}"
        now = datetime.now(UTC)
        try:
            meter_baseline = await self._meter.read_liters()
        except Exception as err:
            raise HomeAssistantError("Calibration water meter is unavailable") from err
        request = ManualIrrigationRequest(
            request_id=request_id,
            sequence=self._stored_state.next_request_sequence,
            zone_id=zone.zone_id,
            zone_subentry_id=zone.subentry_id,
            zone_name=zone.title,
            zone_valve=str(zone.data[CONF_ZONE_VALVE]),
            main_valve=self._main_valve,
            target_type="duration",
            target_value=duration_seconds,
            remaining_value=duration_seconds,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=duration_seconds)).isoformat(),
            requested_start_at=now.isoformat(),
            status="executing",
            source="calibration",
            execution_id=test_id,
            delivery_runtime_limit_seconds=duration_seconds,
            operation_deadline_at=(now + timedelta(seconds=duration_seconds)).isoformat(),
        )
        execution = IrrigationExecutionState(
            execution_id=test_id,
            request_id=request_id,
            zone_id=zone.zone_id,
            target_type="duration",
            target_value=duration_seconds,
            remaining_value=duration_seconds,
            status="watering",
            created_at=now.isoformat(),
            delivery_runtime_limit_seconds=duration_seconds,
            operation_deadline_at=request.operation_deadline_at,
        )
        active = ActiveExecutionState(
            zone_id=zone.zone_id,
            zone_valve=str(zone.data[CONF_ZONE_VALVE]),
            main_valve=self._main_valve,
            meter_raw_baseline_liters=meter_baseline,
            prepared_at=now.isoformat(),
            watering_started_at=None,
            requested_duration_seconds=duration_seconds,
            delivery_deadline_at=(now + timedelta(seconds=duration_seconds)).isoformat(),
            request_id=request_id,
            execution_id=test_id,
        )
        async with self._command_lock:
            self._stored_state = replace(
                self._stored_state,
                active_execution=active,
                manual_requests=(*self._stored_state.manual_requests, request),
                irrigation_executions=(
                    *self._stored_state.irrigation_executions,
                    execution,
                ),
                next_request_sequence=self._stored_state.next_request_sequence + 1,
            )
            await self._store.async_save(self._stored_state)
            task = self._hass.async_create_task(
                self._async_run_calibration(test_id, zone, duration_seconds),
                "Irrigation Manager flow calibration",
            )
            self._calibration_task = task
            self._watering = True
            self._publish(status="watering", active_zone_id=zone.zone_id)
        return {"test_id": test_id, "expires_at": active.delivery_deadline_at}

    async def _async_run_calibration(
        self, test_id: str, zone: _ZoneConfigSnapshot, duration_seconds: float
    ) -> ExecutionResult:
        try:
            result = await self._executor.execute(
                ExecutionRequest(
                    zone_id=zone.zone_id,
                    zone_valve=str(zone.data[CONF_ZONE_VALVE]),
                    main_valve=self._main_valve,
                    duration_seconds=duration_seconds,
                    require_meter_progress=True,
                    on_zone_opening=self._async_mark_zone_opening,
                    on_zone_opened=self._async_mark_zone_opened,
                    on_actuator_command=self._async_authorize_actuator_command,
                )
            )
        except asyncio.CancelledError:
            result = ExecutionResult(
                zone_id=zone.zone_id,
                delivered_liters=0,
                duration_seconds=0,
                stopped=True,
                target_reached=False,
                measurement_quality="unknown",
            )
        if test_id in self._cancelled_calibrations:
            return result
        async with self._command_lock:
            if test_id in self._cancelled_calibrations:
                return result
            now = datetime.now(UTC)
            average = (
                result.delivered_liters * 60 / result.duration_seconds
                if result.delivered_liters > 0 and result.duration_seconds > 0
                else 0.0
            )
            proposal = (
                CalibrationProposal(
                    proposal_id=uuid4().hex,
                    zone_id=zone.zone_id,
                    zone_subentry_id=zone.subentry_id,
                    zone_valve=str(zone.data[CONF_ZONE_VALVE]),
                    zone_config_hash=self._calibration_zone_config_hash(zone),
                    created_at=datetime.now(UTC).isoformat(),
                    delivered_liters=result.delivered_liters,
                    duration_seconds=result.duration_seconds,
                    average_flow_l_min=average,
                    opening_latency_seconds=result.opening_latency_seconds,
                    post_run_liters=result.post_run_liters,
                    proposed_min_flow_l_min=average * 0.8,
                    proposed_max_flow_l_min=average * 1.2,
                )
                if average > 0 and result.safety_violation is None
                else self._stored_state.calibration_proposal
            )
            zone_totals = dict(self._stored_state.zone_totals_liters)
            zone_totals[zone.zone_id] = zone_totals.get(zone.zone_id, 0) + result.delivered_liters
            request = self._request(f"calibration:{test_id}")
            execution = self._execution(test_id)
            successful = (
                not result.stopped and result.safety_violation is None and result.target_reached
            )
            requests = (
                self._with_request(
                    replace(
                        request,
                        remaining_value=0.0 if successful else request.remaining_value,
                        status="completed" if successful else "cancelled",
                        revision=request.revision + 1,
                    )
                )
                if request is not None
                else self._stored_state.manual_requests
            )
            executions = (
                self._with_execution(
                    replace(
                        execution,
                        remaining_value=0.0 if successful else execution.remaining_value,
                        status="completed" if successful else "failed",
                        delivered_liters=result.delivered_liters,
                        delivered_duration_seconds=result.duration_seconds,
                        ended_at=now.isoformat(),
                        result=(
                            "target_reached"
                            if successful
                            else result.safety_violation or "calibration_stopped"
                        ),
                        measurement_quality=result.measurement_quality,
                        measurement_origin="meter",
                    )
                )
                if execution is not None
                else self._stored_state.irrigation_executions
            )
            self._stored_state = replace(
                self._stored_state,
                active_execution=None,
                calibration_proposal=proposal,
                installation_total_liters=(
                    self._stored_state.installation_total_liters + result.delivered_liters
                ),
                zone_totals_liters=zone_totals,
                manual_requests=requests,
                irrigation_executions=executions,
                installation_safety_lock=(
                    result.safety_violation
                    if result.safety_violation is not None
                    else self._stored_state.installation_safety_lock
                ),
                installation_safety_lock_at=(
                    now.isoformat()
                    if result.safety_violation is not None
                    else self._stored_state.installation_safety_lock_at
                ),
            )
            self._stored_state = self._with_meter_continuity(self._stored_state)
            await self._store.async_save(self._stored_state)
            self._watering = False
            self._calibration_task = None
            self._publish(status="idle", active_zone_id=None)
            self._refresh_complete_idle_event()
        del test_id
        return result

    def is_calibration_active(self, test_id: str) -> bool:
        """Return whether a calibration owns the active execution identity."""
        active = self._stored_state.active_execution
        return active is not None and active.execution_id == test_id

    async def async_confirm_calibration(self, *, test_id: str) -> dict[str, object]:
        """Calibration has a fixed bound and needs no dead-man extension."""
        if not self.is_calibration_active(test_id):
            raise HomeAssistantError("The calibration is not active")
        active = cast(ActiveExecutionState, self._stored_state.active_execution)
        return {"test_id": test_id, "confirmation_deadline": active.delivery_deadline_at}

    async def async_stop_calibration(self, *, require_active: bool = True) -> None:
        """Stop an active calibration operation."""
        task = self._calibration_task
        if task is None or task.done():
            if require_active:
                raise HomeAssistantError("No calibration is active")
            return
        active = self._stored_state.active_execution
        if active is None or active.execution_id is None:
            if require_active:
                raise HomeAssistantError("No calibration is active")
            return
        test_id = active.execution_id
        self._cancelled_calibrations.add(test_id)
        task.cancel()
        result_or_error = await asyncio.gather(task, return_exceptions=True)
        result = result_or_error[0]
        if not isinstance(result, ExecutionResult):
            result = ExecutionResult(
                zone_id=active.zone_id,
                delivered_liters=0.0,
                duration_seconds=0.0,
                stopped=True,
                target_reached=False,
                measurement_quality="unknown",
            )
        async with self._command_lock:
            current = self._stored_state.active_execution
            if current is not None and current.execution_id == test_id:
                request = self._request(current.request_id) if current.request_id else None
                execution = self._execution(test_id)
                now = datetime.now(UTC).isoformat()
                if request is not None:
                    request = replace(
                        request,
                        status="cancelled",
                        revision=request.revision + 1,
                    )
                if execution is not None:
                    execution = replace(
                        execution,
                        status="cancelled",
                        delivered_liters=execution.delivered_liters + result.delivered_liters,
                        delivered_duration_seconds=(
                            execution.delivered_duration_seconds + result.duration_seconds
                        ),
                        ended_at=now,
                        result="calibration_stopped",
                        measurement_quality=result.measurement_quality,
                        measurement_origin=(
                            "meter" if result.measurement_quality == "measured" else "unavailable"
                        ),
                    )
                zone_totals = dict(self._stored_state.zone_totals_liters)
                zone_totals[current.zone_id] = (
                    zone_totals.get(current.zone_id, 0.0) + result.delivered_liters
                )
                self._stored_state = replace(
                    self._stored_state,
                    active_execution=None,
                    manual_requests=(
                        self._with_request(request)
                        if request is not None
                        else self._stored_state.manual_requests
                    ),
                    irrigation_executions=(
                        self._with_execution(execution)
                        if execution is not None
                        else self._stored_state.irrigation_executions
                    ),
                    installation_total_liters=(
                        self._stored_state.installation_total_liters + result.delivered_liters
                    ),
                    zone_totals_liters=zone_totals,
                )
                self._stored_state = self._with_meter_continuity(self._stored_state)
                await self._store.async_save(self._stored_state)
            self._calibration_task = None
            self._watering = False
            self._publish(status="idle", active_zone_id=None)
        self._cancelled_calibrations.discard(test_id)

    def calibration_proposal(self) -> dict[str, object] | None:
        """Return the latest review-only calibration proposal."""
        proposal = self._stored_state.calibration_proposal
        return proposal.as_dict() if proposal is not None else None

    async def async_resolve_calibration(
        self, *, proposal_id: str, resolution: str
    ) -> dict[str, object]:
        """Accept or discard a measured flow profile explicitly."""
        proposal = self._stored_state.calibration_proposal
        if proposal is None or proposal.proposal_id != proposal_id or proposal.status != "pending":
            raise HomeAssistantError("The calibration proposal is not pending")
        if resolution not in {"accept", "discard"}:
            raise HomeAssistantError("Unsupported calibration resolution")
        live = self._entry.subentries.get(proposal.zone_subentry_id)
        if resolution == "accept":
            if live is None:
                raise HomeAssistantError("The calibration zone no longer exists")
            zone = _ZoneConfigSnapshot(
                live.subentry_id,
                live.subentry_type,
                live.title,
                live.unique_id,
                dict(live.data),
            )
            if self._calibration_zone_config_hash(zone) != proposal.zone_config_hash:
                raise HomeAssistantError("The irrigation zone changed after calibration")
            self._hass.config_entries.async_update_subentry(
                self._entry,
                live,
                data={
                    **live.data,
                    "expected_flow_l_min": proposal.average_flow_l_min,
                    "min_flow": proposal.proposed_min_flow_l_min,
                    "max_flow": proposal.proposed_max_flow_l_min,
                    "flow_calibrated_at": proposal.created_at,
                },
            )
        proposal = replace(proposal, status="accepted" if resolution == "accept" else "discarded")
        self._stored_state = replace(self._stored_state, calibration_proposal=proposal)
        await self._store.async_save(self._stored_state)
        return proposal.as_dict()

    @staticmethod
    def _calibration_zone_config_hash(zone: _ZoneConfigSnapshot) -> str:
        payload = {
            "zone_id": zone.zone_id,
            "zone_valve": zone.data.get(CONF_ZONE_VALVE),
        }
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    async def async_correct_physical_meter(
        self, *, physical_total_liters: float, reason: str | None = None
    ) -> dict[str, object]:
        """Correct the displayed physical meter without changing consumption."""
        if not self._has_meter:
            raise HomeAssistantError("No water meter is configured")
        current = self._meter.continuity
        if current is None:
            raise HomeAssistantError("The water meter has no accepted reading")
        previous_total = current.total_liters
        corrected_at = datetime.now(UTC).isoformat()
        continuity = self._meter.correct(physical_total_liters=physical_total_liters)
        record = MeterCorrectionRecord(
            previous_total_liters=previous_total,
            new_total_liters=continuity.total_liters,
            difference_liters=continuity.total_liters - previous_total,
            corrected_at=corrected_at,
            reason=reason.strip() if reason and reason.strip() else None,
        )
        self._stored_state = self._with_meter_continuity(
            replace(
                self._stored_state,
                meter_correction_history=(
                    *self._stored_state.meter_correction_history,
                    record,
                )[-500:],
            )
        )
        await self._store.async_save(self._stored_state)
        self._publish(status=self._coordinator.data.status, active_zone_id=self._active_zone_id)
        return record.as_dict()

    def _publish(self, *, status: str, active_zone_id: str | None) -> None:
        """Publish the compact v2 state derived from durable records."""
        if self._stored_state.emergency_stop:
            status = "emergency_stop"
        elif self._stored_state.installation_safety_lock is not None:
            status = "safety_lock"
        elif self._installation_reconfiguration_required:
            status = "needs_reconfiguration"
        elif status == "idle" and not self._operation_enabled:
            status = "disabled"
        elif status == "idle" and not self._automation_enabled:
            status = "automatic_disabled"
        zone_status: dict[str, str] = {}
        for zone in self._zone_configs:
            zone_status[zone.zone_id] = (
                "needs_reconfiguration"
                if self._installation_reconfiguration_required
                or self._zone_reconfiguration_required(zone.data)
                else "safety_lock"
                if self._stored_state.installation_safety_lock is not None
                else "installation_disabled"
                if not self._operation_enabled
                else "disabled"
                if not self._zone_operation_released(zone)
                else "watering"
                if active_zone_id == zone.zone_id
                else "automatic_disabled"
                if not self._automation_enabled or not self._zone_automation_released(zone)
                else "idle"
            )
        local_now = dt_util.as_local(dt_util.now())
        timezone = local_now.tzinfo
        day_start = datetime.combine(local_now.date(), time.min, tzinfo=timezone)
        day_end = day_start + timedelta(days=1)
        month_start = datetime.combine(local_now.date().replace(day=1), time.min, tzinfo=timezone)
        next_month = (
            date(local_now.year + 1, 1, 1)
            if local_now.month == 12
            else date(local_now.year, local_now.month + 1, 1)
        )
        month_end = datetime.combine(next_month, time.min, tzinfo=timezone)
        runtime_today = 0.0
        runtime_month = 0.0
        zone_runtime_today: dict[str, float] = {}
        zone_runtime_month: dict[str, float] = {}
        for execution in self._stored_state.irrigation_executions:
            today = self._execution_runtime_in_period(execution, day_start, day_end)
            month = self._execution_runtime_in_period(execution, month_start, month_end)
            runtime_today += today
            runtime_month += month
            zone_runtime_today[execution.zone_id] = (
                zone_runtime_today.get(execution.zone_id, 0) + today
            )
            zone_runtime_month[execution.zone_id] = (
                zone_runtime_month.get(execution.zone_id, 0) + month
            )
        for zone in self._zone_configs:
            zone_runtime_today.setdefault(zone.zone_id, 0.0)
            zone_runtime_month.setdefault(zone.zone_id, 0.0)
        orders = self.card_open_orders()
        continuity = self._meter.continuity
        self._coordinator.set_snapshot(
            InstallationSnapshot(
                installation_total_liters=self._stored_state.installation_total_liters,
                zone_totals_liters=dict(self._stored_state.zone_totals_liters),
                zone_measurement_quality=dict(self._stored_state.zone_measurement_quality),
                zone_last_delivered_liters=dict(self._stored_state.zone_last_delivered_liters),
                zone_last_duration_seconds=dict(self._stored_state.zone_last_duration_seconds),
                unassigned_total_liters=self._stored_state.unassigned_total_liters,
                water_period_liters=self._water_period_totals(dt_util.now()),
                zone_water_period_liters={
                    zone.zone_id: self._water_period_totals(dt_util.now(), zone_id=zone.zone_id)
                    for zone in self._zone_configs
                },
                physical_meter_liters=continuity.total_liters if continuity else None,
                meter_measurement_quality="measured" if continuity else "unknown",
                status=status,
                active_zone_id=active_zone_id,
                emergency_stop=self._stored_state.emergency_stop,
                installation_safety_lock=self._stored_state.installation_safety_lock,
                installation_safety_lock_at=self._stored_state.installation_safety_lock_at,
                pending_request_count=sum(
                    request.status in _OPEN_REQUEST_STATUSES
                    for request in self._stored_state.manual_requests
                ),
                active_request_id=(
                    self._stored_state.active_execution.request_id
                    if self._stored_state.active_execution
                    else None
                ),
                active_execution_id=(
                    self._stored_state.active_execution.execution_id
                    if self._stored_state.active_execution
                    else None
                ),
                automation_enabled=self._automation_enabled,
                operation_enabled=self._operation_enabled,
                zone_operation_enabled={
                    zone.zone_id: self._zone_operation_released(zone) for zone in self._zone_configs
                },
                zone_automation_enabled={
                    zone.zone_id: self._zone_automation_released(zone)
                    for zone in self._zone_configs
                },
                next_zone_id=(
                    next(
                        (
                            request.zone_id
                            for request in self._stored_state.manual_requests
                            if request.request_id == orders[0]["request_id"]
                        ),
                        None,
                    )
                    if orders
                    else None
                ),
                next_start_at=cast(str, orders[0]["expected_start"]) if orders else None,
                zone_next_irrigation={
                    zone.zone_id: cast(str, order["expected_start"])
                    for zone in self._zone_configs
                    if (
                        order := next(
                            (
                                item
                                for item in orders
                                if item["zone_subentry_id"] == zone.subentry_id
                            ),
                            None,
                        )
                    )
                },
                zone_status=zone_status,
                recent_history=tuple(
                    execution.as_dict()
                    for execution in self._stored_state.irrigation_executions[-10:]
                ),
                runtime_today_seconds=runtime_today,
                runtime_month_seconds=runtime_month,
                zone_runtime_today_seconds=zone_runtime_today,
                zone_runtime_month_seconds=zone_runtime_month,
            )
        )
        self._refresh_complete_idle_event()

    @staticmethod
    def _execution_runtime_in_period(
        execution: IrrigationExecutionState,
        period_start: datetime,
        period_end: datetime,
    ) -> float:
        if execution.ended_at is None:
            return 0.0
        ended_at = datetime.fromisoformat(execution.ended_at)
        duration = max(0.0, execution.delivered_duration_seconds)
        start_utc = period_start.astimezone(UTC)
        end_utc = period_end.astimezone(UTC)
        return max(
            0.0,
            (
                min(ended_at.astimezone(UTC), end_utc)
                - max(
                    ended_at.astimezone(UTC) - timedelta(seconds=duration),
                    start_utc,
                )
            ).total_seconds(),
        )

    def _water_period_totals(
        self, now: datetime, *, zone_id: str | None = None
    ) -> dict[str, float]:
        local = dt_util.as_local(now)
        day = local.date()
        month = day.replace(day=1)
        totals = {"today": 0.0, "month": 0.0}
        for record in self._stored_state.water_consumption_history:
            if zone_id is not None and record.zone_id != zone_id:
                continue
            recorded = dt_util.as_local(datetime.fromisoformat(record.recorded_at)).date()
            if recorded == day:
                totals["today"] += record.amount_liters
            if recorded >= month and recorded.month == month.month and recorded.year == month.year:
                totals["month"] += record.amount_liters
        return totals

    def diagnostics_state_decisions(self) -> dict[str, object]:
        """Return only v2 state needed to explain current decisions."""
        snapshot = self.snapshot()
        return {
            "status": snapshot.status,
            "operation_enabled": snapshot.operation_enabled,
            "automation_enabled": snapshot.automation_enabled,
            "installation_safety_lock": snapshot.installation_safety_lock,
            "zone_status": snapshot.zone_status,
            "pending_request_count": snapshot.pending_request_count,
            "active_request_id": snapshot.active_request_id,
        }

    def _request(self, request_id: str) -> ManualIrrigationRequest | None:
        return next(
            (
                request
                for request in self._stored_state.manual_requests
                if request.request_id == request_id
            ),
            None,
        )

    def _execution(self, execution_id: str | None) -> IrrigationExecutionState | None:
        return next(
            (
                execution
                for execution in self._stored_state.irrigation_executions
                if execution.execution_id == execution_id
            ),
            None,
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

    def _with_meter_continuity(self, state: StoredInstallationState) -> StoredInstallationState:
        continuity = self._meter.continuity
        if continuity is None:
            return state
        return replace(
            state,
            meter_accumulated_liters=continuity.accumulated_liters,
            meter_last_raw_liters=continuity.last_raw_liters,
            meter_correction_liters=continuity.correction_liters,
            meter_reset_count=continuity.reset_count,
            meter_source_entity_id=cast(str | None, self._installation_data.get(CONF_METER_ENTITY)),
            meter_source_liters_per_count=(
                self._optional_float(self._installation_data, CONF_LITERS_PER_PULSE)
                if self._installation_data.get(CONF_METER_TYPE) == METER_TYPE_PULSE
                else None
            ),
        )

    async def _async_reconcile_meter_source(self) -> None:
        entity_id = cast(str | None, self._installation_data.get(CONF_METER_ENTITY))
        factor = (
            self._optional_float(self._installation_data, CONF_LITERS_PER_PULSE)
            if self._installation_data.get(CONF_METER_TYPE) == METER_TYPE_PULSE
            else None
        )
        if (
            self._stored_state.meter_source_entity_id != entity_id
            or self._stored_state.meter_source_liters_per_count != factor
            or self._meter.continuity is None
        ):
            await self._meter.rebase_source()
            self._stored_state = self._with_meter_continuity(self._stored_state)
            await self._store.async_save(self._stored_state)

    @property
    def _main_valve(self) -> str | None:
        value = self._installation_data.get(CONF_MAIN_VALVE)
        return value if isinstance(value, str) else None

    @property
    def _active_zone_id(self) -> str | None:
        active = self._stored_state.active_execution
        return active.zone_id if active is not None else None

    def _zone_for_subentry(self, zone_subentry_id: str) -> _ZoneConfigSnapshot:
        zone = self._zone_configs_by_subentry_id.get(zone_subentry_id)
        if zone is None or zone.subentry_type != SUBENTRY_TYPE_ZONE:
            raise HomeAssistantError("The irrigation zone does not exist")
        return zone

    def _validated_runtime(
        self, data: Mapping[str, object], runtime: float, *, volume: bool
    ) -> float:
        if not math.isfinite(runtime) or runtime <= 0:
            raise HomeAssistantError("The irrigation runtime must be positive")
        configured = self._optional_float(
            data, CONF_VOLUME_MAX_RUNTIME if volume else CONF_MAX_DELIVERY_RUNTIME
        )
        if configured is not None and runtime > configured:
            raise HomeAssistantError(
                f"The irrigation runtime must not exceed {configured:g} seconds"
            )
        return runtime

    @staticmethod
    def _optional_float(data: Mapping[str, object], key: str) -> float | None:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    @classmethod
    def _number(cls, data: Mapping[str, object], key: str, default: float) -> float:
        return cls._optional_float(data, key) or default

    def _request_expected_duration(self, request: ManualIrrigationRequest) -> timedelta:
        planned_delivery_duration = self._optional_float(
            request.resolved_inputs, "planned_delivery_duration_seconds"
        )
        seconds = (
            request.remaining_value
            if request.target_type == "duration"
            else planned_delivery_duration or request.delivery_runtime_limit_seconds or 1
        )
        close_budget = CLEANUP_FEEDBACK_BUDGET_SECONDS * (
            2 if request.main_valve is not None else 1
        )
        return timedelta(seconds=max(1.0, seconds) + close_budget)

    def _seconds_until_next_request_change(self) -> float | None:
        now = datetime.now(UTC)
        moments = []
        for request in self._stored_state.manual_requests:
            if request.status != "pending":
                continue
            moments.append(
                datetime.fromisoformat(request.operation_deadline_at or request.expires_at)
            )
            moments.append(datetime.fromisoformat(request.requested_start_at or request.created_at))
        return (
            max(0.0, min((moment - now).total_seconds() for moment in moments)) if moments else None
        )

    async def _async_close_entities(self, entity_ids: Iterable[str]) -> None:
        errors: list[Exception] = []
        for entity_id in dict.fromkeys(entity_ids):
            try:
                await self._actuators.close(entity_id)
            except Exception as err:  # noqa: BLE001
                errors.append(err)
        if errors:
            raise ExceptionGroup("Irrigation valve closure failed", errors)

    def _signal_terminal(self, request_id: str) -> None:
        self._terminal_events.setdefault(request_id, asyncio.Event()).set()
