"""Runtime orchestration for one irrigation installation."""

import asyncio
import csv
import io
import json
import math
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .adapters import (
    HomeAssistantActuators,
    HomeAssistantClock,
    HomeAssistantFlow,
    HomeAssistantMeter,
)
from .const import (
    CONF_ACTUATOR_TRANSITION_GRACE_SECONDS,
    CONF_AGRONOMIC_VALUES_CONFIRMED,
    CONF_APPLICATION_EFFICIENCY,
    CONF_AREA_M2,
    CONF_AUTOMATIC_MAX_DURATION,
    CONF_AUTOMATION_ENABLED,
    CONF_CALIBRATION_SETTLE_SECONDS,
    CONF_CROP_FACTOR,
    CONF_CUSTOM_PROFILES,
    CONF_ET0_SENSORS,
    CONF_EXPOSURE_PROFILE,
    CONF_FLOW_GRACE_SECONDS,
    CONF_FLOW_MAX_AGE_SECONDS,
    CONF_FLOW_SENSOR,
    CONF_FORECAST_DEFERRAL_HOURS,
    CONF_FORECAST_RAIN_PROBABILITY,
    CONF_FORECAST_RAIN_THRESHOLD_MM,
    CONF_FROST_ENTITY,
    CONF_FROST_THRESHOLD,
    CONF_HARDWARE_BATTERY_MINIMUM,
    CONF_HARDWARE_BATTERY_SENSOR,
    CONF_HARDWARE_CONNECTIVITY_SENSOR,
    CONF_HARDWARE_FAULT_SENSOR,
    CONF_HARDWARE_HEALTH_MAX_AGE_SECONDS,
    CONF_HUMIDITY_SENSORS,
    CONF_INSTALLATION_DAILY_BUDGET_LITERS,
    CONF_INSTALLATION_MAX_DELIVERY_RUNTIME,
    CONF_INSTALLATION_MAX_OPERATION_LIFETIME,
    CONF_INSTALLATION_WEEKLY_BUDGET_LITERS,
    CONF_IRRIGATION_PROFILE,
    CONF_LEAK_DURATION_SECONDS,
    CONF_LEAK_FLOW_THRESHOLD,
    CONF_LEAK_MONITORING,
    CONF_LITERS_PER_COUNT,
    CONF_MAIN_VALVE,
    CONF_MAINTENANCE_CONFIRMATION_INTERVAL,
    CONF_MAINTENANCE_MAX_DURATION,
    CONF_MANDATORY_AMOUNT_LITERS,
    CONF_MAX_DELIVERY_RUNTIME,
    CONF_MAX_DOSE_AMOUNT,
    CONF_MAX_DOSE_DURATION,
    CONF_MAX_EFFECTIVE_RAIN_MM,
    CONF_MAX_FLOW,
    CONF_MAX_OPERATION_LIFETIME,
    CONF_MAXIMUM_DEFICIT_MM,
    CONF_MAXIMUM_INTERVAL_DAYS,
    CONF_MAXIMUM_TARGET_LITERS,
    CONF_METER_FAILURE_STRATEGY,
    CONF_METER_MAX_AGE_SECONDS,
    CONF_METER_RESOLUTION_LITERS,
    CONF_MIN_FLOW,
    CONF_MINIMUM_EFFECTIVE_LITERS,
    CONF_MINIMUM_INTERVAL_DAYS,
    CONF_MINIMUM_TRIGGER_LITERS,
    CONF_NOTIFY_ENTITIES,
    CONF_OPEN_METEO_ENABLED,
    CONF_PAUSE_TIMEOUT_SECONDS,
    CONF_PLANT_PROFILE,
    CONF_PRESSURE_SENSORS,
    CONF_PROFILE_OVERRIDES,
    CONF_RAIN_FACTOR,
    CONF_RAIN_SENSORS,
    CONF_RAIN_STOP_ENTITY,
    CONF_RAIN_STOP_THRESHOLD,
    CONF_RAW_METER,
    CONF_SEASONAL_CROP_FACTORS,
    CONF_SOAK_DURATION,
    CONF_SOIL_MOISTURE_AGGREGATION,
    CONF_SOIL_MOISTURE_CORRECTION_LIMIT_MM,
    CONF_SOIL_MOISTURE_MAX_AGE_SECONDS,
    CONF_SOIL_MOISTURE_ROLE,
    CONF_SOIL_MOISTURE_SENSORS,
    CONF_SOIL_MOISTURE_WET_THRESHOLD,
    CONF_SOIL_PROFILE,
    CONF_SOLAR_RADIATION_SENSORS,
    CONF_SUBAREAS,
    CONF_SUNSHINE_DURATION_SENSORS,
    CONF_TEMPERATURE_SENSORS,
    CONF_WATER_METER,
    CONF_WATERING_MODE,
    CONF_WATERING_WINDOWS,
    CONF_WEATHER_BACKFILL_DAYS,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_FAILURE_POLICY,
    CONF_WEATHER_FALLBACK_DAYS,
    CONF_WEATHER_FINALIZATION_TIME,
    CONF_WEATHER_MAX_AGE_SECONDS,
    CONF_WEATHER_PREVIEW_INTERVAL_HOURS,
    CONF_WIND_SPEED_SENSORS,
    CONF_ZONE_DAILY_BUDGET_LITERS,
    CONF_ZONE_PRIORITY,
    CONF_ZONE_VALVE,
    CONF_ZONE_WEEKLY_BUDGET_LITERS,
    EXPORT_SCHEMA_VERSION,
    METER_FAILURE_ABORT,
    METER_FAILURE_ESTIMATED_TIME_FALLBACK,
    SOIL_MOISTURE_ROLE_INHIBIT,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import IrrigationCoordinator
from .events import IrrigationEventPublisher
from .executor import ExecutionRequest, ExecutionResult, IrrigationExecutor
from .leak_monitor import LeakObservation
from .meter import CumulativeMeter, round_target_to_resolution
from .models import (
    ActiveExecutionState,
    CalibrationProposal,
    InstallationSnapshot,
    IrrigationExecutionState,
    MaintenanceTestState,
    ManualIrrigationRequest,
    StoredInstallationState,
    UncreditedBalanceDelivery,
    WaterConsumptionRecord,
)
from .profiles import (
    EffectiveZoneProfile,
    builtin_profiles,
    copy_profile,
    dependent_profile_ids,
    profile_impacted_zones,
    resolve_effective_zone_profile,
    validate_custom_profiles,
)
from .scheduler import (
    WateringMode,
    ZonePlanningInput,
    ZoneScheduleDecision,
    active_and_next_window,
    decide_zone_schedule,
    dose_target,
    parse_window_rule,
    select_manual_request,
)
from .soil_moisture import SoilMoistureAssessment, assess_soil_moisture
from .storage import IrrigationStore
from .water_balance import (
    WaterBalancePeriod,
    ZoneWaterBalance,
    apply_water_balance,
    calculate_effective_irrigation_mm,
    calculate_effective_rain,
    calculate_irrigation_target_liters,
)
from .weather import (
    Et0Result,
    RainForecast,
    WeatherOrchestrator,
    calculate_seasonal_value,
    seasonal_et0,
)


class _StaleRequestClaimError(HomeAssistantError):
    """Raised when a selected request changed before its durable claim."""


class _DurableTransitionError(HomeAssistantError):
    """Raised when an actuator-safe transition could not be persisted."""


WATER_HISTORY_MAX_RECORDS = 50_000
WATER_HISTORY_SAFETY_MARGIN_DAYS = 45


@dataclass(frozen=True, slots=True)
class _ZoneConfigSnapshot:
    """Immutable runtime view of one config subentry."""

    subentry_id: str
    subentry_type: str
    title: str
    unique_id: str | None
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _WeatherSafety:
    """Current fail-safe interpretation of configured weather interlocks."""

    frost_blocked: bool
    rain_stop_active: bool
    status: str


def _event_result_reason(result: str | None, status: str) -> str:
    """Keep event reasons stable and free of raw entity/error text."""
    stable_results = {
        "cancelled",
        "expired",
        "interrupted",
        "restart",
        "stopped",
        "target_reached",
        "target_reached_during_recovery",
    }
    return result if result in stable_results else status


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
        self._coordinator = coordinator
        self._store = store
        self._stored_state = stored_state
        self._events = IrrigationEventPublisher(
            hass,
            installation_id=entry.unique_id or entry.entry_id,
            installation_name=entry.title,
            config=self._installation_data,
        )
        self._weather = WeatherOrchestrator(hass, self._installation_data)
        self._weather_schedule_unsubscribers: list[Callable[[], None]] = []
        self._weather_model_quality = "unavailable"
        self._weather_model_method = "unavailable"
        self._weather_automation_available = not self._weather_model_configured
        self._reference_evapotranspiration_mm: float | None = None
        self._measured_rain_mm: float | None = None
        self._weather_period_id: str | None = None
        self._weather_last_finalized_at: str | None = None
        self._rain_forecast: RainForecast | None = None
        self._zone_provisional_deficit_mm: dict[str, float] = {}
        self._zone_crop_evapotranspiration_mm: dict[str, float] = {}
        self._zone_effective_rain_mm: dict[str, float] = {}
        self._zone_calculation_explanations: dict[str, dict[str, object]] = {}
        self._zone_effective_profiles: dict[str, dict[str, object]] = {}
        self._zone_soil_moisture: dict[str, dict[str, object]] = {}
        self._zone_hardware_health: dict[str, dict[str, object]] = {}
        self._provisional_period_id: str | None = None
        self._last_weather_preview_at: datetime | None = None
        self._restore_latest_weather_snapshot()
        meter_entity = self._installation_data.get(CONF_WATER_METER)
        raw_meter_entity = self._installation_data.get(CONF_RAW_METER)
        self._has_meter = bool(meter_entity or raw_meter_entity)
        self._actuators = HomeAssistantActuators(
            hass,
            self._number(
                self._installation_data,
                CONF_ACTUATOR_TRANSITION_GRACE_SECONDS,
                5.0,
            ),
        )
        self._meter = HomeAssistantMeter(
            hass,
            cast(str | None, meter_entity or raw_meter_entity),
            self._optional_float(self._installation_data, CONF_METER_MAX_AGE_SECONDS) or 300.0,
            liters_per_count=(
                self._optional_float(self._installation_data, CONF_LITERS_PER_COUNT)
                if raw_meter_entity
                else None
            ),
            continuity=(
                CumulativeMeter(
                    accumulated_liters=stored_state.meter_accumulated_liters,
                    last_raw_liters=stored_state.meter_last_raw_liters,
                    correction_liters=stored_state.meter_correction_liters,
                    reset_count=stored_state.meter_reset_count,
                )
                if stored_state.meter_accumulated_liters is not None
                and stored_state.meter_last_raw_liters is not None
                else None
            ),
        )
        flow_entity_id = self._installation_data.get(CONF_FLOW_SENSOR)
        self._flow = (
            HomeAssistantFlow(
                hass,
                flow_entity_id,
                self._optional_float(self._installation_data, CONF_FLOW_MAX_AGE_SECONDS) or 30.0,
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
        self._automatic_planner_task: asyncio.Task[None] | None = None
        self._queue_event = asyncio.Event()
        self._planning_event = asyncio.Event()
        self._terminal_events: dict[str, asyncio.Event] = {}
        self._request_errors: dict[str, Exception] = {}
        self._cancel_requested: set[str] = set()
        self._skip_requested: dict[str, str] = {}
        self._pause_requested: set[str] = set()
        self._watering = False
        self._command_lock = asyncio.Lock()
        self._leak_threshold_l_min = (
            self._optional_float(self._installation_data, CONF_LEAK_FLOW_THRESHOLD) or 0.5
        )
        self._leak_duration_seconds = (
            self._optional_float(self._installation_data, CONF_LEAK_DURATION_SECONDS) or 30.0
        )
        self._leak_monitoring = (
            self._flow is not None
            and self._installation_data.get(CONF_LEAK_MONITORING, True) is not False
        )
        self._leak_observation: LeakObservation | None = None
        self._leak_confirmation_task: asyncio.Task[None] | None = None
        self._leak_application_task: asyncio.Task[None] | None = None
        self._flow_event_tasks: set[asyncio.Task[None]] = set()
        self._unsubscribe_flow: Callable[[], None] | None = None
        self._state_event_tasks: set[asyncio.Task[None]] = set()
        self._state_unsubscribers: list[Callable[[], None]] = []
        self._active_external_violation: tuple[str, str, str | None] | None = None
        self._expected_actuator_states: dict[str, tuple[bool, float]] = {}
        self._commanded_actuator_states: dict[str, bool] = {}
        self._feedback_watchdog_tasks: dict[str, asyncio.Task[None]] = {}
        self._weather_watchdog_event = asyncio.Event()
        self._weather_watchdog_task: asyncio.Task[None] | None = None
        self._shutting_down = False
        self._active_target_type: str | None = None
        self._active_target_value: float | None = None
        self._active_remaining_value: float | None = None
        self._active_measurement_quality: str | None = None
        self._current_flow_l_min: float | None = None
        self._complete_idle_event = asyncio.Event()
        self._pending_reload_task: asyncio.Task[None] | None = None
        self._maintenance_task: asyncio.Task[ExecutionResult] | None = None
        self._maintenance_watchdog_task: asyncio.Task[None] | None = None
        self._maintenance_stop_reason: str | None = None
        self._maintenance_flow_samples: list[float] = []
        self._refresh_complete_idle_event()

    @property
    def _weather_model_configured(self) -> bool:
        """Return whether automatic water modeling has an explicit source."""
        has_rain_source = bool(
            self._installation_data.get(CONF_RAIN_SENSORS)
            or self._installation_data.get(CONF_OPEN_METEO_ENABLED)
        )
        has_et_source = bool(
            self._installation_data.get(CONF_WEATHER_ENTITY)
            or self._installation_data.get(CONF_TEMPERATURE_SENSORS)
            or self._installation_data.get(CONF_ET0_SENSORS)
            or self._installation_data.get(CONF_OPEN_METEO_ENABLED)
        )
        return has_rain_source and has_et_source

    def _restore_latest_weather_snapshot(self) -> None:
        """Restore published model metadata without recomputing historical periods."""
        snapshots = self._stored_state.weather_calculation_snapshots
        if not snapshots:
            return
        period_id = max(snapshots)
        snapshot = snapshots[period_id]
        et0 = snapshot.get("et0")
        if not isinstance(et0, dict):
            return
        value = et0.get("value_mm")
        self._reference_evapotranspiration_mm = (
            float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
        )
        rain = snapshot.get("rain_mm")
        self._measured_rain_mm = (
            float(rain) if isinstance(rain, int | float) and not isinstance(rain, bool) else None
        )
        self._weather_model_quality = str(et0.get("quality", "unavailable"))
        self._weather_model_method = str(et0.get("method", "unavailable"))
        self._weather_period_id = period_id
        finalized_at = snapshot.get("finalized_at")
        self._weather_last_finalized_at = finalized_at if isinstance(finalized_at, str) else None
        self._weather_automation_available = self._reference_evapotranspiration_mm is not None
        zones = snapshot.get("zones")
        if isinstance(zones, dict):
            self._zone_calculation_explanations = {
                str(key): dict(value) for key, value in zones.items() if isinstance(value, dict)
            }
            self._zone_crop_evapotranspiration_mm = self._numeric_zone_snapshot_values(
                cast(dict[str, dict[str, object]], zones), "crop_evapotranspiration_mm"
            )
            self._zone_effective_rain_mm = self._numeric_zone_snapshot_values(
                cast(dict[str, dict[str, object]], zones), "effective_rain_mm"
            )

    @staticmethod
    def _numeric_zone_snapshot_values(
        zones: Mapping[str, dict[str, object]], key: str
    ) -> dict[str, float]:
        """Extract finite per-zone numbers from a persisted explanation snapshot."""
        result: dict[str, float] = {}
        for zone_id, raw in zones.items():
            value = raw.get(key)
            if isinstance(value, int | float) and not isinstance(value, bool):
                numeric = float(value)
                if math.isfinite(numeric):
                    result[str(zone_id)] = numeric
        return result

    async def async_request_config_reload(self) -> None:
        """Coalesce a persisted config update and apply it only at complete idle."""
        if self._shutting_down or self._pending_reload_task is not None:
            return
        self._pending_reload_task = self._hass.async_create_task(
            self._async_reload_when_complete_idle(),
            "Irrigation Manager deferred config reload",
        )

    async def _async_reload_when_complete_idle(self) -> None:
        """Wait without blocking the Options Flow, then reload this config entry once."""
        current_task = asyncio.current_task()
        try:
            while not self._shutting_down:
                self._complete_idle_event.clear()
                if self._is_complete_idle():
                    async with self._command_lock:
                        if self._is_complete_idle():
                            await self._hass.config_entries.async_reload(self._entry.entry_id)
                            return
                await self._complete_idle_event.wait()
        except asyncio.CancelledError:
            return
        finally:
            if self._pending_reload_task is current_task:
                self._pending_reload_task = None

    def _is_complete_idle(self) -> bool:
        """Return whether no request can still execute using the current snapshot."""
        return (
            not self._watering
            and self._stored_state.active_execution is None
            and (self._active_task is None or self._active_task.done())
            and not any(
                request.status in {"pending", "executing", "soaking", "paused"}
                for request in self._stored_state.manual_requests
            )
        )

    def _refresh_complete_idle_event(self) -> None:
        """Wake a deferred reload when the manager reaches complete idle."""
        if self._is_complete_idle():
            self._complete_idle_event.set()
        else:
            self._complete_idle_event.clear()

    def _setup_weather_schedule(self) -> None:
        """Check local-day work on an elapsed interval that cannot be skipped by DST."""
        self._weather_schedule_unsubscribers.append(
            async_track_time_interval(
                self._hass,
                self._async_scheduled_weather_tick,
                timedelta(minutes=15),
                name="Irrigation Manager weather due check",
            )
        )

    async def _async_weather_startup(self) -> None:
        """Backfill every retained missing day and publish today's provisional balance."""
        now = dt_util.now()
        await self._async_backfill_weather_days(now, through_yesterday=True)
        await self.async_update_weather_preview(now=now)
        await self.async_plan_automatic(now=now)

    async def _async_scheduled_weather_tick(self, now: datetime) -> None:
        """Run idempotent due work without depending on one local wall-clock minute."""
        if not self._weather_model_configured:
            return
        finalized = await self._async_backfill_weather_days(now)
        preview_interval = timedelta(
            hours=max(
                1,
                min(
                    12,
                    int(
                        self._number(
                            self._installation_data,
                            CONF_WEATHER_PREVIEW_INTERVAL_HOURS,
                            1,
                        )
                    ),
                ),
            )
        )
        preview_due = (
            self._last_weather_preview_at is None
            or now.astimezone(UTC) - self._last_weather_preview_at >= preview_interval
        )
        if preview_due:
            await self.async_update_weather_preview(now=now)
        if finalized or preview_due:
            await self.async_plan_automatic(now=now)

    async def _async_backfill_weather_days(
        self, now: datetime, *, through_yesterday: bool = False
    ) -> list[str]:
        """Finalize every missing retained local day in chronological order."""
        local_now = dt_util.as_local(now)
        raw_finalization = str(
            self._installation_data.get(CONF_WEATHER_FINALIZATION_TIME, "00:10:00")
        )
        try:
            finalization = time.fromisoformat(raw_finalization)
        except ValueError:
            finalization = time(0, 10)
        due_day = local_now.date() - timedelta(
            days=(
                1
                if through_yesterday or local_now.time().replace(tzinfo=None) >= finalization
                else 2
            )
        )
        finalized_dates = [
            date.fromisoformat(period_id)
            for period_id in self._stored_state.finalized_weather_periods
            if self._is_iso_date(period_id)
        ]
        retention_days = int(self._number(self._installation_data, CONF_WEATHER_BACKFILL_DAYS, 14))
        retention_start = due_day - timedelta(days=max(1, retention_days) - 1)
        start = (
            max(max(finalized_dates) + timedelta(days=1), retention_start)
            if finalized_dates
            else retention_start
        )
        finalized: list[str] = []
        current = start
        while current <= due_day:
            period_id = current.isoformat()
            if period_id not in self._stored_state.finalized_weather_periods:
                await self.async_finalize_weather_day(current)
                finalized.append(period_id)
            current += timedelta(days=1)
        return finalized

    @staticmethod
    def _is_iso_date(value: str) -> bool:
        """Return whether a persisted period identifier is a calendar date."""
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True

    async def async_initialize(self) -> None:
        """Close configured valves left open across a restart."""
        await self._async_derive_migrated_runtime_limits()
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
        if main_valve := self._installation_data.get(CONF_MAIN_VALVE):
            entity_ids.append(main_valve)
        await self._async_close_entities(list(dict.fromkeys(entity_ids)))
        await self._async_recover_interrupted_execution(could_have_flowed=active_could_have_flowed)
        with suppress(HomeAssistantError):
            await self._async_reconcile_meter_source()
        if self._stored_state.maintenance_test is not None:
            interrupted_test = self._stored_state.maintenance_test
            self._stored_state = replace(self._stored_state, maintenance_test=None)
            await self._store.async_save(self._stored_state)
            self._events.fire(
                "maintenance_ended",
                reason="restart",
                target=self._events.zone_target(interrupted_test.zone_id),
                context={"test_id": interrupted_test.test_id, "kind": interrupted_test.kind},
            )
            await self._events.async_critical(
                "maintenance_interrupted",
                title="Irrigation maintenance test interrupted",
                message=(
                    f"{self._events.installation_name} closed all valves after a restart "
                    "interrupted a supervised test. Inspect the installation before retrying."
                ),
            )
        await self._async_recover_inactive_open_executions()
        await self._async_expire_requests()
        await self._async_initialize_zone_balances()
        await self._async_ensure_idle_meter_baseline()
        for entity_id in self._all_known_valves():
            self._state_unsubscribers.append(
                async_track_state_change_event(self._hass, entity_id, self._actuator_state_changed)
            )
        weather_entities: set[str] = set()
        for key in (CONF_FROST_ENTITY, CONF_RAIN_STOP_ENTITY):
            value = self._installation_data.get(key)
            if isinstance(value, str):
                weather_entities.add(value)
        for entity_id in weather_entities:
            self._state_unsubscribers.append(
                async_track_state_change_event(self._hass, entity_id, self._weather_state_changed)
            )
        await self._async_verify_supervised_valves_after_startup()
        self._weather_watchdog_task = self._entry.async_create_background_task(
            self._hass,
            self._async_weather_freshness_watchdog(),
            "Irrigation Manager weather freshness watchdog",
        )
        self._setup_weather_schedule()
        if self._weather_model_configured:
            self._entry.async_create_background_task(
                self._hass,
                self._async_weather_startup(),
                "Irrigation Manager weather startup reconciliation",
            )
        if self._leak_monitoring and self._flow is not None:
            flow_entity_id = self._installation_data[CONF_FLOW_SENSOR]
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
        self._automatic_planner_task = self._entry.async_create_background_task(
            self._hass,
            self._async_automatic_planner(),
            "Irrigation Manager automatic planner",
        )

    async def _async_verify_supervised_valves_after_startup(self) -> None:
        """Close and lock any valve opened in the startup listener-registration gap."""
        for entity_id in self._all_known_valves():
            state = self._hass.states.get(entity_id)
            if state is not None and state.state in {"on", "open"}:
                await self._async_apply_actuator_violation(
                    entity_id,
                    reason=f"{entity_id} opened unexpectedly during startup",
                    opening=True,
                )

    async def _async_derive_migrated_runtime_limits(self) -> None:
        """Replace conservative storage placeholders with current config-derived limits."""
        changed = False
        requests: list[ManualIrrigationRequest] = []
        for request in self._stored_state.manual_requests:
            if (
                request.runtime_limits_need_config_derivation
                or request.delivery_runtime_limit_seconds is None
                or request.operation_deadline_at is None
            ):
                zone = self._zone_configs_by_subentry_id.get(request.zone_subentry_id)
                zone_data = zone.data if zone is not None else {}
                delivery_limit = self._delivery_runtime_limit(
                    zone_data, request.hard_time_limit_seconds
                )
                operation_deadline = min(
                    datetime.fromisoformat(request.expires_at),
                    datetime.fromisoformat(request.created_at)
                    + timedelta(seconds=self._operation_lifetime_limit(zone_data)),
                )
                request = replace(
                    request,
                    delivery_runtime_limit_seconds=delivery_limit,
                    operation_deadline_at=operation_deadline.isoformat(),
                    runtime_limits_need_config_derivation=False,
                )
                changed = True
            requests.append(request)

        request_by_id = {request.request_id: request for request in requests}
        executions: list[IrrigationExecutionState] = []
        for execution in self._stored_state.irrigation_executions:
            if (
                execution.runtime_limits_need_config_derivation
                or execution.delivery_runtime_limit_seconds is None
                or execution.operation_deadline_at is None
            ):
                linked_request = request_by_id.get(execution.request_id)
                zone = next(
                    (
                        item
                        for item in self._zone_configs
                        if (item.unique_id or item.subentry_id) == execution.zone_id
                    ),
                    None,
                )
                zone_data = zone.data if zone is not None else {}
                execution_delivery_limit = (
                    linked_request.delivery_runtime_limit_seconds
                    if linked_request is not None
                    and linked_request.delivery_runtime_limit_seconds is not None
                    else self._delivery_runtime_limit(zone_data, None)
                )
                execution_deadline = (
                    linked_request.operation_deadline_at
                    if linked_request is not None
                    and linked_request.operation_deadline_at is not None
                    else (
                        datetime.fromisoformat(execution.created_at)
                        + timedelta(seconds=self._operation_lifetime_limit(zone_data))
                    ).isoformat()
                )
                execution = replace(
                    execution,
                    delivery_runtime_limit_seconds=execution_delivery_limit,
                    operation_deadline_at=execution_deadline,
                    runtime_limits_need_config_derivation=False,
                )
                changed = True
            executions.append(execution)
        if changed:
            self._stored_state = replace(
                self._stored_state,
                manual_requests=tuple(requests),
                irrigation_executions=tuple(executions),
            )
            await self._store.async_save(self._stored_state)

    async def async_shutdown(self) -> None:
        """Stop runtime work and remove all Home Assistant listeners."""
        self._shutting_down = True
        reload_task = self._pending_reload_task
        if reload_task is not None and reload_task is not asyncio.current_task():
            reload_task.cancel()
            await asyncio.gather(reload_task, return_exceptions=True)
            self._pending_reload_task = None
        dispatcher_task = self._dispatcher_task
        self._dispatcher_task = None
        planner_task = self._automatic_planner_task
        self._automatic_planner_task = None
        if dispatcher_task is not None:
            dispatcher_task.cancel()
        if planner_task is not None:
            planner_task.cancel()
        if self._unsubscribe_flow is not None:
            self._unsubscribe_flow()
            self._unsubscribe_flow = None
        for unsubscribe in self._state_unsubscribers:
            unsubscribe()
        self._state_unsubscribers.clear()
        for unsubscribe in self._weather_schedule_unsubscribers:
            unsubscribe()
        self._weather_schedule_unsubscribers.clear()
        for task in self._feedback_watchdog_tasks.values():
            task.cancel()
        if self._feedback_watchdog_tasks:
            await asyncio.gather(*self._feedback_watchdog_tasks.values(), return_exceptions=True)
        self._feedback_watchdog_tasks.clear()
        weather_watchdog_task = self._weather_watchdog_task
        self._weather_watchdog_task = None
        if weather_watchdog_task is not None:
            weather_watchdog_task.cancel()
            await asyncio.gather(weather_watchdog_task, return_exceptions=True)
        confirmation_task = self._leak_confirmation_task
        application_task = self._leak_application_task
        self._cancel_leak_observation()
        if application_task is not None:
            await asyncio.gather(application_task, return_exceptions=True)
        if confirmation_task is not None:
            await asyncio.gather(confirmation_task, return_exceptions=True)
        if dispatcher_task is not None:
            await asyncio.gather(dispatcher_task, return_exceptions=True)
        if planner_task is not None:
            await asyncio.gather(planner_task, return_exceptions=True)
        active_task = self._active_task
        if active_task is not None and not active_task.done():
            active_task.cancel()
            await asyncio.gather(active_task, return_exceptions=True)
        maintenance_task = self._maintenance_task
        if maintenance_task is not None and not maintenance_task.done():
            maintenance_task.cancel()
            await asyncio.gather(maintenance_task, return_exceptions=True)
        watchdog_task = self._maintenance_watchdog_task
        if watchdog_task is not None and watchdog_task is not asyncio.current_task():
            watchdog_task.cancel()
            await asyncio.gather(watchdog_task, return_exceptions=True)
        if self._stored_state.active_execution is not None:
            await self._async_recover_interrupted_execution(could_have_flowed=False)
        tasks = tuple(self._flow_event_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        state_tasks = tuple(self._state_event_tasks)
        for task in state_tasks:
            task.cancel()
        if state_tasks:
            await asyncio.gather(*state_tasks, return_exceptions=True)

    @callback
    def _actuator_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Continuously supervise managed actuator feedback."""
        new_state = event.data["new_state"]
        if self._shutting_down or new_state is None:
            return
        open_ = new_state.state in {"on", "open"}
        closed = new_state.state in {STATE_OFF, "closed"}
        entity_id = new_state.entity_id
        active = self._stored_state.active_execution
        if not open_ and not closed:
            if active is not None:
                expected = self._expected_actuator_states.get(entity_id)
                self._schedule_feedback_watchdog(
                    entity_id,
                    check_at=expected[1] if expected is not None else None,
                )
            return
        if self._actuator_transition_expected(entity_id, open_=open_):
            return
        if self._commanded_actuator_states.get(entity_id) == open_:
            self._cancel_feedback_watchdog(entity_id)
            return
        if active is not None and open_ == self._active_expected_open(entity_id, active):
            self._cancel_feedback_watchdog(entity_id)
            return
        task = self._hass.async_create_task(
            self._async_handle_unexpected_actuator_state(entity_id, open_=open_),
            "Irrigation Manager actuator safety supervision",
        )
        self._state_event_tasks.add(task)
        task.add_done_callback(self._state_event_tasks.discard)

    def _actuator_transition_expected(self, entity_id: str, *, open_: bool) -> bool:
        """Consume command intent within its bounded feedback window."""
        expected = self._expected_actuator_states.get(entity_id)
        if expected is not None:
            expected_open, expires_at = expected
            if asyncio.get_running_loop().time() <= expires_at and expected_open == open_:
                self._expected_actuator_states.pop(entity_id, None)
                self._cancel_feedback_watchdog(entity_id)
                return True
            if asyncio.get_running_loop().time() > expires_at:
                self._expected_actuator_states.pop(entity_id, None)
        return False

    async def _async_expect_actuator_state(self, entity_id: str, open_: bool) -> None:
        """Record executor command intent before the actuator service is called."""
        expires_at = asyncio.get_running_loop().time() + self._actuator_transition_grace_seconds
        self._commanded_actuator_states[entity_id] = open_
        self._expected_actuator_states[entity_id] = (open_, expires_at)
        self._schedule_feedback_watchdog(entity_id, check_at=expires_at)

    @property
    def _actuator_transition_grace_seconds(self) -> float:
        """Return the configured bounded actuator feedback transition grace."""
        return self._number(
            self._installation_data,
            CONF_ACTUATOR_TRANSITION_GRACE_SECONDS,
            5.0,
        )

    def _active_run_identity(self) -> str | None:
        """Return the identity owning the current external-violation lifecycle."""
        active = self._stored_state.active_execution
        if active is None:
            return None
        if self._stored_state.maintenance_test is not None:
            return f"maintenance:{self._stored_state.maintenance_test.test_id}"
        return active.execution_id or active.request_id or f"prepared:{active.prepared_at}"

    @staticmethod
    def _active_expected_open(entity_id: str, active: ActiveExecutionState) -> bool:
        """Return the steady state expected for a managed actuator during delivery."""
        return active.zone_opening_at is not None and (
            entity_id == active.zone_valve or entity_id == active.main_valve
        )

    def _schedule_feedback_watchdog(self, entity_id: str, *, check_at: float | None = None) -> None:
        """Check unresolved feedback once after the configured grace."""
        identity = self._active_run_identity()
        if identity is None:
            return
        self._cancel_feedback_watchdog(entity_id)
        deadline = check_at or (
            asyncio.get_running_loop().time() + self._actuator_transition_grace_seconds
        )
        task = self._hass.async_create_task(
            self._async_check_actuator_feedback(entity_id, identity, deadline),
            "Irrigation Manager actuator feedback watchdog",
        )
        self._feedback_watchdog_tasks[entity_id] = task

    def _cancel_feedback_watchdog(self, entity_id: str) -> None:
        """Cancel one resolved actuator feedback check."""
        task = self._feedback_watchdog_tasks.pop(entity_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    async def _async_check_actuator_feedback(
        self, entity_id: str, identity: str, deadline: float
    ) -> None:
        """Fail closed if feedback remains unavailable or contradictory."""
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(max(0.0, deadline - asyncio.get_running_loop().time()))
            if self._active_run_identity() != identity:
                return
            active = self._stored_state.active_execution
            if active is None:
                return
            state = self._hass.states.get(entity_id)
            expected = self._expected_actuator_states.get(entity_id)
            expected_open = (
                expected[0]
                if expected is not None
                else self._commanded_actuator_states.get(
                    entity_id, self._active_expected_open(entity_id, active)
                )
            )
            actual_open = state is not None and state.state in {"on", "open"}
            actual_closed = state is not None and state.state in {STATE_OFF, "closed"}
            if (actual_open and expected_open) or (actual_closed and not expected_open):
                self._expected_actuator_states.pop(entity_id, None)
                return
            reason = (
                f"{entity_id} feedback unavailable after transition grace"
                if not actual_open and not actual_closed
                else f"{entity_id} did not reach its commanded state"
            )
            await self._async_apply_actuator_violation(entity_id, reason=reason)
        except asyncio.CancelledError:
            return
        finally:
            if self._feedback_watchdog_tasks.get(entity_id) is current_task:
                self._feedback_watchdog_tasks.pop(entity_id, None)

    async def _async_handle_unexpected_actuator_state(self, entity_id: str, *, open_: bool) -> None:
        """Fail closed for unsolicited openings and active valve closures."""
        active = self._stored_state.active_execution
        if not open_ and active is None:
            return
        reason = (
            f"{entity_id} opened unexpectedly"
            if open_
            else f"{entity_id} closed unexpectedly during irrigation"
        )
        await self._async_apply_actuator_violation(entity_id, reason=reason, opening=open_)

    async def _async_apply_actuator_violation(
        self, entity_id: str, *, reason: str, opening: bool = False
    ) -> None:
        """Persist the correct lock, cancel the owning run, and close all valves."""
        async with self._command_lock:
            active = self._stored_state.active_execution
            if active is None and not opening:
                return
            identity = self._active_run_identity()
            if opening or active is None or entity_id != active.zone_valve:
                scope = "installation"
                self._stored_state = replace(self._stored_state, installation_safety_lock=reason)
            else:
                assert active is not None
                scope = "zone"
                zone_locks = dict(self._stored_state.zone_safety_locks)
                zone_locks[active.zone_id] = reason
                self._stored_state = replace(self._stored_state, zone_safety_locks=zone_locks)
            close_entities = self._all_known_valves()
            if identity is not None:
                self._active_external_violation = (identity, reason, scope)
            await self._store.async_save(self._stored_state)
            self._publish(status="safety_lock", active_zone_id=active.zone_id if active else None)
            for task in (self._active_task, self._maintenance_task):
                if task is not None and not task.done():
                    task.cancel()
            event_target = self._events.installation_target()
            if scope == "zone":
                assert active is not None
                event_target = self._events.zone_target(active.zone_id)
        with suppress(Exception):
            await self._async_close_entities(close_entities)
        self._events.fire(
            "safety_lock_activated",
            reason="unexpected_actuator_state",
            target=event_target,
            context={"safety_scope": scope, "lock_active": True},
        )

    @callback
    def _weather_state_changed(self, _event: Event[EventStateChangedData]) -> None:
        """Re-evaluate weather interlocks and stop affected active watering."""
        if self._shutting_down:
            return
        self._weather_watchdog_event.set()
        task = self._hass.async_create_task(
            self._async_apply_weather_interlocks(),
            "Irrigation Manager weather safety supervision",
        )
        self._state_event_tasks.add(task)
        task.add_done_callback(self._state_event_tasks.discard)

    async def _async_apply_weather_interlocks(self) -> None:
        """Stop active watering when a hard frost or automatic rain stop applies."""
        weather = self._weather_safety()
        async with self._command_lock:
            active = self._stored_state.active_execution
            if active is None:
                self._planning_event.set()
                self._publish(status=self._coordinator.data.status, active_zone_id=None)
                return
            request = self._request(active.request_id) if active.request_id else None
            maintenance = self._stored_state.maintenance_test
            reason = None
            if weather.frost_blocked:
                reason = "Frost safety interlock activated"
            elif weather.rain_stop_active and (
                maintenance is not None or (request is not None and request.source == "automatic")
            ):
                reason = "Rain stop threshold reached"
            if reason is None:
                return
            identity = self._active_run_identity()
            if identity is not None:
                self._active_external_violation = (identity, reason, None)
            for task in (self._active_task, self._maintenance_task):
                if task is not None and not task.done():
                    task.cancel()
        self._events.fire(
            "weather_interlock_activated",
            reason="frost" if weather.frost_blocked else "rain_stop",
            target=self._events.installation_target(),
            quality=weather.status,
        )

    def _weather_safety(self) -> _WeatherSafety:
        """Validate freshness and plausibility, failing safe for configured sources."""
        max_age = self._number(self._installation_data, CONF_WEATHER_MAX_AGE_SECONDS, 900)
        frost_entity = self._installation_data.get(CONF_FROST_ENTITY)
        rain_entity = self._installation_data.get(CONF_RAIN_STOP_ENTITY)
        frost_blocked = False
        rain_stop = False
        failures: list[str] = []
        if isinstance(frost_entity, str):
            try:
                value = self._numeric_weather_value(frost_entity, max_age=max_age)
                state = self._hass.states.get(frost_entity)
                unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
                if unit in TemperatureConverter.VALID_UNITS:
                    value = TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
                if not -100 <= value <= 80:
                    raise ValueError("implausible frost temperature")
                frost_blocked = value <= self._number(
                    self._installation_data, CONF_FROST_THRESHOLD, 2
                )
            except HomeAssistantError, ValueError:
                frost_blocked = True
                failures.append("frost_source_invalid")
        if isinstance(rain_entity, str):
            try:
                value = self._numeric_weather_value(rain_entity, max_age=max_age)
                if not 0 <= value <= 1_000:
                    raise ValueError("implausible rain value")
                rain_stop = value >= self._number(
                    self._installation_data, CONF_RAIN_STOP_THRESHOLD, 0.1
                )
            except HomeAssistantError, ValueError:
                rain_stop = True
                failures.append("rain_source_invalid")
        configured = isinstance(frost_entity, str) or isinstance(rain_entity, str)
        return _WeatherSafety(
            frost_blocked=frost_blocked,
            rain_stop_active=rain_stop,
            status=",".join(failures) if failures else "valid" if configured else "not_configured",
        )

    def _numeric_weather_value(self, entity_id: str, *, max_age: float) -> float:
        """Read one finite, fresh native numeric entity value."""
        state = self._hass.states.get(entity_id)
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            raise HomeAssistantError(f"Weather safety entity {entity_id} is unavailable")
        if (datetime.now(UTC) - state.last_reported).total_seconds() > max_age:
            raise HomeAssistantError(f"Weather safety entity {entity_id} is stale")
        try:
            value = float(state.state)
        except ValueError as err:
            raise HomeAssistantError(f"Weather safety entity {entity_id} is not numeric") from err
        if not math.isfinite(value):
            raise HomeAssistantError(f"Weather safety entity {entity_id} is not plausible")
        return value

    def _seconds_until_weather_expiry(self) -> float | None:
        """Return time until the oldest configured sample becomes stale while active."""
        if self._stored_state.active_execution is None:
            return None
        max_age = self._number(self._installation_data, CONF_WEATHER_MAX_AGE_SECONDS, 900)
        expiries = []
        for key in (CONF_FROST_ENTITY, CONF_RAIN_STOP_ENTITY):
            entity_id = self._installation_data.get(key)
            if not isinstance(entity_id, str):
                continue
            state = self._hass.states.get(entity_id)
            if state is None:
                return 0.0
            expiries.append(state.last_reported + timedelta(seconds=max_age))
        if not expiries:
            return None
        return max(0.0, (min(expiries) - datetime.now(UTC)).total_seconds())

    async def _async_weather_freshness_watchdog(self) -> None:
        """Enforce weather expiry during active runs without needing a state event."""
        try:
            while not self._shutting_down:
                self._weather_watchdog_event.clear()
                delay = self._seconds_until_weather_expiry()
                if delay is None:
                    await self._weather_watchdog_event.wait()
                    continue
                try:
                    await asyncio.wait_for(
                        self._weather_watchdog_event.wait(),
                        timeout=max(0.01, delay),
                    )
                except TimeoutError:
                    await self._async_apply_weather_interlocks()
        except asyncio.CancelledError:
            return

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
            self._hass.states.get(self._installation_data[CONF_FLOW_SENSOR])
        )

    async def _async_consider_flow_sample(self, state: State | None) -> None:
        """Apply one specific event sample without collapsing intervening states."""
        if self._flow is None or self._shutting_down:
            return
        try:
            flow_l_min = self._flow.read_state_l_min(state)
        except HomeAssistantError:
            async with self._command_lock:
                self._current_flow_l_min = None
                self._cancel_leak_observation()
                self._publish(status=self._coordinator.data.status, active_zone_id=None)
            return
        async with self._command_lock:
            self._current_flow_l_min = flow_l_min
            self._publish(
                status=self._coordinator.data.status,
                active_zone_id=self._coordinator.data.active_zone_id,
            )
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
            unassigned_available_liters=(
                self._stored_state.unassigned_available_liters + amount_liters
            ),
            unassigned_measurement_quality=quality,
            unassigned_measurement_origin=origin,
            idle_meter_raw_baseline_liters=new_baseline,
            installation_safety_lock=reason,
        )
        self._stored_state = self._with_consumption_record(
            self._with_meter_continuity(self._stored_state),
            amount_liters=amount_liters,
            zone_id=None,
            source=origin,
            quality=quality,
        )
        try:
            await self._store.async_save(self._stored_state)
        except Exception as err:  # noqa: BLE001
            persistence_errors.append(err)
        self._publish(status="safety_lock", active_zone_id=None)
        self._events.fire(
            "leak_detected",
            reason="idle_flow_confirmed",
            target=self._events.installation_target(),
            measurements={
                "flow_l_min": flow_l_min,
                "threshold_l_min": self._leak_threshold_l_min,
                "duration_seconds": self._leak_duration_seconds,
                "delivered_liters": amount_liters,
            },
            quality=quality,
            context={"safety_scope": "installation", "lock_active": True},
        )
        self._events.fire(
            "safety_lock_activated",
            reason="idle_leak",
            target=self._events.installation_target(),
            measurements={"flow_l_min": flow_l_min},
            quality=quality,
            context={"safety_scope": "installation", "lock_active": True},
        )
        await self._events.async_critical(
            "installation_leak",
            title="Irrigation leak detected",
            message=(
                f"{self._events.installation_name} was locked after persistent flow "
                "was detected while idle. Check the water supply and valves before resetting "
                "the safety lock."
            ),
        )
        if close_error is not None:
            await self._events.async_critical(
                "valve_closure_failed",
                title="Irrigation valve closure failed",
                message=(
                    f"{self._events.installation_name} could not confirm that every valve "
                    "closed after a leak. Isolate the water supply and inspect the valves."
                ),
            )
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
        if main_valve := self._installation_data.get(CONF_MAIN_VALVE):
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
        recovered_at = datetime.now(UTC)

        delivered_liters = 0.0
        delivered_duration_seconds = 0.0
        quality = "unknown"
        recovery_started_at = active.watering_started_at
        if recovery_started_at is None and active.zone_opening_at is not None and could_have_flowed:
            recovery_started_at = active.zone_opening_at
        if recovery_started_at is not None:
            started_at = datetime.fromisoformat(recovery_started_at)
            delivered_duration_seconds = max(0.0, (recovered_at - started_at).total_seconds())
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
                    max(0.0, (recovered_at - checkpoint_at).total_seconds()),
                    fallback_duration_limit,
                )
                delivered_liters += fallback_duration * active.estimated_flow_l_min / 60
            quality = active.fallback_quality
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
        request = self._request(active.request_id) if active.request_id is not None else None
        execution = (
            self._execution(active.execution_id) if active.execution_id is not None else None
        )
        balance_snapshot = self._resolve_balance_snapshot(active, execution, request)
        if balance_snapshot is not None:
            active = replace(
                active,
                balance_area_m2=balance_snapshot[0],
                balance_application_efficiency=balance_snapshot[1],
                balance_maximum_deficit_mm=balance_snapshot[2],
                balance_minimum_effective_liters=balance_snapshot[3],
            )
            if request is not None:
                request = replace(
                    request,
                    balance_area_m2=balance_snapshot[0],
                    balance_application_efficiency=balance_snapshot[1],
                    balance_maximum_deficit_mm=balance_snapshot[2],
                    balance_minimum_effective_liters=balance_snapshot[3],
                )
                requests = self._replace_request_in(requests, request)
            if execution is not None:
                execution = replace(
                    execution,
                    balance_area_m2=balance_snapshot[0],
                    balance_application_efficiency=balance_snapshot[1],
                    balance_maximum_deficit_mm=balance_snapshot[2],
                    balance_minimum_effective_liters=balance_snapshot[3],
                )
                executions = self._replace_execution_in(executions, execution)
        effective_delivery = self._crosses_effective_threshold(
            previous_liters=0.0,
            delivered_liters=delivered_liters,
            minimum_effective_liters=active.balance_minimum_effective_liters,
        )
        terminal_request_id: str | None = None
        if request is not None:
            delivered_target = (
                delivered_liters if request.target_type == "volume" else delivered_duration_seconds
            )
            remaining = max(0.0, request.remaining_value - delivered_target)
            completed = remaining <= 1e-6
            expired = datetime.fromisoformat(request.expires_at) <= recovered_at
            request = replace(
                request,
                remaining_value=0.0 if completed else remaining,
                status="completed" if completed else "expired" if expired else "pending",
                soak_until=None,
                execution_id=request.execution_id if completed else None,
                revision=request.revision + 1,
            )
            requests = self._replace_request_in(requests, request)
            if execution is not None:
                prior_execution_liters = execution.delivered_liters
                execution = replace(
                    execution,
                    remaining_value=0.0 if completed else remaining,
                    delivered_liters=execution.delivered_liters + delivered_liters,
                    delivered_duration_seconds=(
                        execution.delivered_duration_seconds + delivered_duration_seconds
                    ),
                    status="completed" if completed else "interrupted",
                    ended_at=recovered_at.isoformat(),
                    result=(
                        "target_reached_during_recovery"
                        if completed
                        else "expired"
                        if expired
                        else "restart"
                    ),
                )
                executions = self._replace_execution_in(executions, execution)
                effective_delivery = self._crosses_effective_threshold(
                    previous_liters=prior_execution_liters,
                    delivered_liters=delivered_liters,
                    minimum_effective_liters=(execution.balance_minimum_effective_liters),
                )
            if completed or expired:
                terminal_request_id = request.request_id
        deficits, last_effective = self._balance_after_delivery(
            zone_id=active.zone_id,
            delivered_liters=delivered_liters,
            effective_delivery=effective_delivery,
            delivered_at=recovered_at,
            area_m2=active.balance_area_m2,
            application_efficiency=active.balance_application_efficiency,
            maximum_deficit_mm=active.balance_maximum_deficit_mm,
        )
        uncredited_deliveries = self._stored_state.uncredited_balance_deliveries
        if delivered_liters > 0 and balance_snapshot is None:
            uncredited_deliveries = (
                *uncredited_deliveries,
                self._uncredited_balance_delivery(
                    zone_id=active.zone_id,
                    delivered_liters=delivered_liters,
                    delivered_at=recovered_at,
                    request_id=active.request_id,
                    execution_id=active.execution_id,
                ),
            )
        recovered_state = replace(
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
            zone_deficit_mm=deficits,
            zone_last_effective_irrigation=last_effective,
            uncredited_balance_deliveries=uncredited_deliveries,
            budget_usage_liters=self._budget_usage_after_delivery(
                self._stored_state.budget_usage_liters,
                zone_id=active.zone_id,
                delivered_liters=delivered_liters,
                delivered_at=recovered_at,
            ),
        )
        recovered_state = self._with_consumption_record(
            self._with_meter_continuity(recovered_state),
            amount_liters=delivered_liters,
            zone_id=active.zone_id,
            source="restart_recovery",
            quality=quality,
            request_id=active.request_id,
            execution_id=active.execution_id,
            dose_number=active.dose_number,
        )
        await self._store.async_save(recovered_state)
        self._stored_state = recovered_state
        if active.execution_id is not None:
            recovered_execution = self._execution(active.execution_id)
            self._events.fire(
                "dose_ended",
                reason="restart_recovery",
                target=self._events.zone_target(active.zone_id),
                measurements={
                    "delivered_liters": delivered_liters,
                    "duration_seconds": delivered_duration_seconds,
                },
                quality=quality,
                context={
                    "request_id": active.request_id,
                    "execution_id": active.execution_id,
                    "dose_number": active.dose_number,
                    "recovered": True,
                },
            )
            if recovered_execution is not None and recovered_execution.ended_at is not None:
                self._events.fire(
                    "execution_ended",
                    reason=_event_result_reason(
                        recovered_execution.result, recovered_execution.status
                    ),
                    target=self._events.zone_target(active.zone_id),
                    measurements={
                        "delivered_liters": recovered_execution.delivered_liters,
                        "duration_seconds": recovered_execution.delivered_duration_seconds,
                    },
                    quality=quality,
                    context={
                        "request_id": active.request_id,
                        "execution_id": active.execution_id,
                        "status": recovered_execution.status,
                        "recovered": True,
                    },
                )
        if terminal_request_id is not None:
            self._signal_terminal(terminal_request_id)
        await self._async_refresh_idle_meter_baseline()
        self._publish(status="idle", active_zone_id=None)
        self._planning_event.set()

    async def _async_recover_inactive_open_executions(self) -> None:
        """Interrupt persisted waits, pauses, and soaks without losing request remainder."""
        open_statuses = {"waiting", "watering", "soaking", "paused"}
        open_executions = {
            execution.execution_id: execution
            for execution in self._stored_state.irrigation_executions
            if execution.status in open_statuses
        }
        if not open_executions:
            return
        now = datetime.now(UTC).isoformat()
        requests = tuple(
            replace(
                request,
                status="paused" if request.status == "paused" else "pending",
                execution_id=None,
                soak_until=None,
                revision=request.revision + 1,
            )
            if request.execution_id in open_executions
            and request.status not in {"completed", "cancelled", "expired"}
            else request
            for request in self._stored_state.manual_requests
        )
        executions = tuple(
            replace(
                execution,
                status="interrupted",
                ended_at=now,
                result="restart",
            )
            if execution.execution_id in open_executions
            else execution
            for execution in self._stored_state.irrigation_executions
        )
        self._stored_state = replace(
            self._stored_state,
            manual_requests=requests,
            irrigation_executions=executions,
        )
        await self._store.async_save(self._stored_state)
        for execution in open_executions.values():
            self._events.fire(
                "execution_ended",
                reason="restart",
                target=self._events.zone_target(execution.zone_id),
                measurements={
                    "delivered_liters": execution.delivered_liters,
                    "duration_seconds": execution.delivered_duration_seconds,
                },
                quality="unknown",
                context={
                    "request_id": execution.request_id,
                    "execution_id": execution.execution_id,
                    "status": "interrupted",
                    "recovered": True,
                },
            )

    async def _async_close_entities(
        self, entity_ids: list[str], *, report_failure: bool = True
    ) -> None:
        """Attempt every requested closure before reporting any failures."""
        errors: list[Exception] = []
        for entity_id in dict.fromkeys(entity_ids):
            try:
                await self._async_expect_actuator_state(entity_id, False)
                await self._actuators.close(entity_id)
            except Exception as err:  # noqa: BLE001
                errors.append(err)
        if errors and report_failure:
            self._events.fire(
                "safety_lock_activated",
                reason="valve_closure_failed",
                target=self._events.installation_target(),
                context={"failed_valve_count": len(errors)},
            )
            await self._events.async_critical(
                "valve_closure_failed",
                title="Irrigation valve closure failed",
                message=(
                    f"{self._events.installation_name} could not confirm that every valve "
                    "closed. Isolate the water supply and inspect the irrigation valves."
                ),
            )
        if errors:
            raise ExceptionGroup("Could not close all irrigation valves", errors)

    def _zone_valves(self) -> list[str]:
        """Return all logical zone valves configured for this installation."""
        return [subentry.data[CONF_ZONE_VALVE] for subentry in self._zone_configs]

    async def _async_preflight(
        self,
        *,
        target_zone_id: str | None = None,
        source: str = "manual",
        ignore_weather: bool = True,
        ignore_installation_lock: bool = False,
        ignore_winter_lock: bool = False,
        ignore_emergency_stop: bool = False,
    ) -> None:
        """Prove all managed valves are available and hydraulically closed."""
        if self._stored_state.emergency_stop and not ignore_emergency_stop:
            raise HomeAssistantError("The emergency stop is active")
        if self._stored_state.winter_lock and not ignore_winter_lock:
            raise HomeAssistantError("The winter lock is active")
        if self._stored_state.installation_safety_lock is not None and not ignore_installation_lock:
            raise HomeAssistantError("The irrigation installation has a safety lock")
        if target_zone_id in self._stored_state.zone_safety_locks:
            raise HomeAssistantError("The irrigation zone has a safety lock")
        if not ignore_weather:
            weather = self._weather_safety()
            if weather.frost_blocked:
                raise HomeAssistantError(f"Frost safety blocks irrigation ({weather.status})")
            if source == "automatic" and weather.rain_stop_active:
                raise HomeAssistantError(
                    f"Rain safety blocks automatic irrigation ({weather.status})"
                )
        target_zone = next(
            (
                item
                for item in self._zone_configs
                if (item.unique_id or item.subentry_id) == target_zone_id
            ),
            None,
        )
        if target_zone is not None:
            now = datetime.now(UTC)
            hardware = self._hardware_health(target_zone.data, now=now)
            self._zone_hardware_health[target_zone_id or ""] = hardware
            if hardware["status"] == "blocked":
                raise HomeAssistantError("Valve hardware health preflight failed")
            moisture = self._soil_moisture_assessment(target_zone.data, now=now)
            if moisture is not None:
                self._zone_soil_moisture[target_zone_id or ""] = moisture.as_dict()
                if (
                    str(target_zone.data.get(CONF_SOIL_MOISTURE_ROLE)) == SOIL_MOISTURE_ROLE_INHIBIT
                    and moisture.safety_blocked
                ):
                    raise HomeAssistantError("Soil-moisture safety preflight is wet or incomplete")
        entity_ids = self._zone_valves()
        if main_valve := self._installation_data.get(CONF_MAIN_VALVE):
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

    async def _async_initialize_zone_balances(self) -> None:
        """Treat newly automated zones as freshly watered and persist that baseline."""
        last_effective = dict(self._stored_state.zone_last_effective_irrigation)
        now = dt_util.now().isoformat()
        changed = False
        for subentry in self._zone_configs:
            zone_id = subentry.unique_id or subentry.subentry_id
            if subentry.data.get(CONF_AUTOMATION_ENABLED, False) and zone_id not in last_effective:
                last_effective[zone_id] = now
                changed = True
        if changed:
            self._stored_state = replace(
                self._stored_state,
                zone_last_effective_irrigation=last_effective,
            )
            await self._store.async_save(self._stored_state)

    def _effective_zone_profile(self, data: Mapping[str, Any], day: date) -> EffectiveZoneProfile:
        """Resolve one immutable effective profile from current config."""
        return resolve_effective_zone_profile(
            data,
            self._installation_data.get(CONF_CUSTOM_PROFILES, {}),
            day,
        )

    def _soil_moisture_assessment(
        self, data: Mapping[str, Any], *, now: datetime
    ) -> SoilMoistureAssessment | None:
        """Read explicitly configured soil sensors without mutating the ET balance."""
        raw_entities = data.get(CONF_SOIL_MOISTURE_SENSORS, [])
        entities = list(raw_entities) if isinstance(raw_entities, list | tuple) else []
        raw_subareas = data.get(CONF_SUBAREAS, [])
        if isinstance(raw_subareas, list | tuple):
            for subarea in raw_subareas:
                if not isinstance(subarea, Mapping):
                    continue
                subarea_entities = subarea.get(CONF_SOIL_MOISTURE_SENSORS, [])
                if isinstance(subarea_entities, list | tuple):
                    entities.extend(subarea_entities)
        entity_ids = list(dict.fromkeys(str(value) for value in entities))
        if not entity_ids:
            return None
        return assess_soil_moisture(
            self._hass,
            entity_ids=entity_ids,
            aggregation=str(data.get(CONF_SOIL_MOISTURE_AGGREGATION, "median")),
            role=str(data.get(CONF_SOIL_MOISTURE_ROLE, "plausibility")),
            max_age_seconds=self._number(data, CONF_SOIL_MOISTURE_MAX_AGE_SECONDS, 3_600),
            wet_threshold=self._number(data, CONF_SOIL_MOISTURE_WET_THRESHOLD, 80),
            correction_limit_mm=self._number(data, CONF_SOIL_MOISTURE_CORRECTION_LIMIT_MM, 0),
            now=now,
        )

    def _hardware_health(self, data: Mapping[str, Any], *, now: datetime) -> dict[str, object]:
        """Validate optional valve battery, connectivity, and fault observations."""
        max_age = self._number(data, CONF_HARDWARE_HEALTH_MAX_AGE_SECONDS, 300)
        result: dict[str, object] = {"status": "not_configured", "checks": {}}
        checks: dict[str, object] = {}
        failures: list[str] = []
        for kind, key in (
            ("battery", CONF_HARDWARE_BATTERY_SENSOR),
            ("connectivity", CONF_HARDWARE_CONNECTIVITY_SENSOR),
            ("fault", CONF_HARDWARE_FAULT_SENSOR),
        ):
            entity_id = data.get(key)
            if not isinstance(entity_id, str):
                continue
            state = self._hass.states.get(entity_id)
            reason: str | None = None
            value: object = None
            if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
                reason = "unavailable"
            elif (
                now.astimezone(UTC) - state.last_reported.astimezone(UTC)
            ).total_seconds() > max_age:
                reason = "stale"
            elif kind == "battery":
                try:
                    battery = float(state.state)
                except ValueError:
                    battery = math.nan
                value = battery
                if (
                    state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) != PERCENTAGE
                    or not math.isfinite(battery)
                    or not 0 <= battery <= 100
                ):
                    reason = "invalid_unit_or_value"
                elif battery < self._number(data, CONF_HARDWARE_BATTERY_MINIMUM, 20):
                    reason = "battery_low"
            elif kind == "connectivity":
                value = state.state
                if state.state.lower() not in {"on", "connected", "home", "online", "ok"}:
                    reason = "disconnected"
            else:
                value = state.state
                if state.state.lower() not in {"off", "clear", "none", "normal", "ok"}:
                    reason = "fault_active"
            checks[kind] = {"valid": reason is None, "reason": reason, "value": value}
            if reason is not None:
                failures.append(f"{kind}:{reason}")
        if checks:
            result = {
                "status": "blocked" if failures else "healthy",
                "checks": checks,
                "failures": failures,
            }
        return result

    def _zone_schedule_decisions(
        self, *, now: datetime
    ) -> list[tuple[_ZoneConfigSnapshot, ZonePlanningInput, ZoneScheduleDecision]]:
        """Build reproducible per-zone decisions from config and durable balance."""
        decisions: list[tuple[_ZoneConfigSnapshot, ZonePlanningInput, ZoneScheduleDecision]] = []
        weather = self._weather_safety()
        provisional_current = (
            self._provisional_period_id
            == now.astimezone(dt_util.DEFAULT_TIME_ZONE).date().isoformat()
        )
        for subentry in self._zone_configs:
            zone_id = subentry.unique_id or subentry.subentry_id
            data = subentry.data
            profile = self._effective_zone_profile(data, now.date())
            maximum_deficit = profile.maximum_deficit_mm
            final_deficit = self._stored_state.zone_deficit_mm.get(zone_id, 0.0)
            planning_deficit = (
                self._zone_provisional_deficit_mm.get(zone_id, final_deficit)
                if provisional_current
                else final_deficit
            )
            moisture = self._soil_moisture_assessment(data, now=now)
            hardware = self._hardware_health(data, now=now)
            deficit = min(
                maximum_deficit,
                max(0.0, planning_deficit),
            )
            if moisture is not None:
                deficit = max(0.0, deficit - moisture.correction_mm)
                self._zone_soil_moisture[zone_id] = moisture.as_dict()
            self._zone_hardware_health[zone_id] = hardware
            self._zone_effective_profiles[zone_id] = dict(profile.resolved_inputs)
            area = profile.area_m2
            efficiency = profile.application_efficiency
            target = calculate_irrigation_target_liters(
                deficit_mm=deficit,
                area_m2=area,
                application_efficiency=efficiency,
            )
            flow = self._estimated_flow(data) or 0.0
            maximum_target = self._number(data, CONF_MAXIMUM_TARGET_LITERS, 1_000.0)
            if flow > 0:
                maximum_target = min(
                    maximum_target,
                    flow * self._number(data, CONF_AUTOMATIC_MAX_DURATION, 3_600.0) / 60,
                )
            budget_remaining = self._automatic_budget_remaining_liters(
                zone_id=zone_id, data=data, now=now
            )
            if budget_remaining is not None:
                maximum_target = min(maximum_target, budget_remaining)
            planning_input = ZonePlanningInput(
                zone_id=zone_id,
                mode=WateringMode(str(data.get(CONF_WATERING_MODE, WateringMode.DEMAND))),
                calculated_target_liters=target,
                minimum_target_liters=self._number(data, CONF_MANDATORY_AMOUNT_LITERS, 1.0),
                maximum_target_liters=maximum_target,
                minimum_effective_liters=self._number(data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1),
                flow_liters_per_minute=flow,
                relative_need=deficit / maximum_deficit if maximum_deficit > 0 else 0.0,
                priority=int(self._number(data, CONF_ZONE_PRIORITY, 0.0)),
                window_end=now,
                enabled=bool(data.get(CONF_AUTOMATION_ENABLED, False)),
                blocked=(
                    self._stored_state.emergency_stop
                    or self._stored_state.winter_lock
                    or self._stored_state.maintenance_test is not None
                    or self._stored_state.installation_safety_lock is not None
                    or zone_id in self._stored_state.zone_safety_locks
                    or weather.frost_blocked
                    or weather.rain_stop_active
                    or (self._weather_model_configured and not self._weather_automation_available)
                    or hardware["status"] == "blocked"
                    or (
                        moisture is not None
                        and str(data.get(CONF_SOIL_MOISTURE_ROLE)) == SOIL_MOISTURE_ROLE_INHIBIT
                        and moisture.safety_blocked
                    )
                ),
            )
            last_value = self._stored_state.zone_last_effective_irrigation.get(zone_id)
            last_effective = datetime.fromisoformat(last_value) if last_value else None
            raw_windows = data.get(CONF_WATERING_WINDOWS, ["04:00-06:00"])
            windows = (
                [str(value) for value in raw_windows]
                if isinstance(raw_windows, list | tuple)
                else [str(raw_windows)]
            )
            decision = decide_zone_schedule(
                now=now,
                zone=planning_input,
                watering_windows=windows,
                last_effective_irrigation=last_effective,
                minimum_interval=timedelta(
                    days=self._number(data, CONF_MINIMUM_INTERVAL_DAYS, 1.0)
                ),
                maximum_interval=timedelta(
                    days=self._number(data, CONF_MAXIMUM_INTERVAL_DAYS, 7.0)
                ),
                minimum_trigger_liters=self._number(data, CONF_MINIMUM_TRIGGER_LITERS, 1.0),
                sun_resolver=self._sun_event,
            )
            if (
                budget_remaining is not None
                and budget_remaining < self._number(data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1)
                and target >= self._number(data, CONF_MINIMUM_TRIGGER_LITERS, 1.0)
            ):
                decision = replace(decision, order=None, reason="budget_exhausted")
            if decision.order is not None and self._forecast_defers_zone(
                zone_id=zone_id, data=data, now=now
            ):
                decision = replace(decision, order=None, reason="forecast_rain_deferred")
            if (
                decision.active_window is not None
                and self._automatic_request_id(zone_id, decision.active_window.opportunity_id)
                in self._stored_state.suppressed_automatic_opportunities
            ):
                decision = replace(
                    decision,
                    order=None,
                    reason="opportunity_suppressed",
                )
            decisions.append((subentry, planning_input, decision))
        return decisions

    def _forecast_defers_zone(
        self, *, zone_id: str, data: Mapping[str, Any], now: datetime
    ) -> bool:
        """Apply bounded forecast deferral without changing deficit or target."""
        if zone_id in self._stored_state.cancelled_forecast_deferrals:
            return False
        deadline_value = self._stored_state.forecast_deferral_deadlines.get(zone_id)
        if deadline_value is not None:
            return now < datetime.fromisoformat(deadline_value)
        if not self._forecast_qualifies(data, now=now, zone_id=zone_id):
            return False
        maximum_hours = self._number(data, CONF_FORECAST_DEFERRAL_HOURS, 24)
        return now < now + timedelta(hours=maximum_hours)

    def _forecast_qualifies(self, data: Mapping[str, Any], *, now: datetime, zone_id: str) -> bool:
        """Return whether the current forecast meets one zone's explicit thresholds."""
        forecast = self._rain_forecast
        probability = forecast.probability_percent if forecast is not None else None
        provisional_current = (
            self._provisional_period_id
            == now.astimezone(dt_util.DEFAULT_TIME_ZONE).date().isoformat()
        )
        available_storage = (
            self._zone_provisional_deficit_mm.get(
                zone_id, self._stored_state.zone_deficit_mm.get(zone_id, 0)
            )
            if provisional_current
            else self._stored_state.zone_deficit_mm.get(zone_id, 0)
        )
        expected_effective_rain = (
            calculate_effective_rain(
                measured_rain_mm=forecast.amount_mm,
                rain_factor=self._effective_zone_profile(data, now.date()).rain_factor,
                maximum_infiltration_mm=self._number(data, CONF_MAX_EFFECTIVE_RAIN_MM, 25),
                available_storage_mm=available_storage,
            ).effective_mm
            if forecast is not None
            else 0.0
        )
        return bool(
            forecast is not None
            and self._number(data, CONF_FORECAST_DEFERRAL_HOURS, 24) > 0
            and forecast.valid_at
            <= now + timedelta(hours=self._number(data, CONF_FORECAST_DEFERRAL_HOURS, 24))
            and expected_effective_rain >= self._number(data, CONF_FORECAST_RAIN_THRESHOLD_MM, 5)
            and probability is not None
            and probability >= self._number(data, CONF_FORECAST_RAIN_PROBABILITY, 70)
        )

    async def async_plan_automatic(
        self, *, dry_run: bool = False, now: datetime | None = None
    ) -> dict[str, object]:
        """Plan current automatic opportunities and optionally persist their requests."""
        planning_now = now or dt_util.now()
        if self._weather_model_configured:
            self._rain_forecast = await self._weather.async_rain_forecast(planning_now)
        async with self._command_lock:
            if not dry_run:
                await self._async_expire_requests(now=planning_now)
                deferrals = dict(self._stored_state.forecast_deferral_started)
                deadlines = dict(self._stored_state.forecast_deferral_deadlines)
                cancelled_deferrals = set(self._stored_state.cancelled_forecast_deferrals)
                changed_deferrals = False
                for subentry in self._zone_configs:
                    zone_id = subentry.unique_id or subentry.subentry_id
                    qualifies = self._forecast_qualifies(
                        subentry.data, now=planning_now, zone_id=zone_id
                    )
                    deadline_value = deadlines.get(zone_id)
                    if zone_id in deferrals and deadline_value is None:
                        deadline_value = (
                            datetime.fromisoformat(deferrals[zone_id])
                            + timedelta(
                                hours=self._number(subentry.data, CONF_FORECAST_DEFERRAL_HOURS, 24)
                            )
                        ).isoformat()
                        deadlines[zone_id] = deadline_value
                        changed_deferrals = True
                    expired = deadline_value is not None and planning_now >= datetime.fromisoformat(
                        deadline_value
                    )
                    if expired:
                        deferrals.pop(zone_id, None)
                        deadlines.pop(zone_id, None)
                        cancelled_deferrals.add(zone_id)
                        changed_deferrals = True
                    if (
                        qualifies
                        and zone_id not in deferrals
                        and zone_id not in cancelled_deferrals
                    ):
                        deferrals[zone_id] = planning_now.isoformat()
                        deadlines[zone_id] = (
                            planning_now
                            + timedelta(
                                hours=self._number(subentry.data, CONF_FORECAST_DEFERRAL_HOURS, 24)
                            )
                        ).isoformat()
                        changed_deferrals = True
                        self._events.fire(
                            "automatic_irrigation_deferred",
                            reason="forecast_rain",
                            target=self._events.zone_target(zone_id),
                            measurements={
                                "forecast_rain_mm": (
                                    self._rain_forecast.amount_mm if self._rain_forecast else 0.0
                                )
                            },
                            quality=self._rain_forecast.quality if self._rain_forecast else None,
                        )
                    elif not qualifies and zone_id in cancelled_deferrals:
                        cancelled_deferrals.discard(zone_id)
                        changed_deferrals = True
                if changed_deferrals:
                    self._stored_state = replace(
                        self._stored_state,
                        forecast_deferral_started=deferrals,
                        forecast_deferral_deadlines=deadlines,
                        cancelled_forecast_deferrals=tuple(sorted(cancelled_deferrals)),
                    )
                    await self._store.async_save(self._stored_state)
            decisions = self._zone_schedule_decisions(now=planning_now)
            ordered = sorted(
                decisions,
                key=lambda item: (
                    item[2].order is None,
                    item[2].order.window_end
                    if item[2].order
                    else datetime.max.replace(tzinfo=planning_now.tzinfo),
                    -item[1].relative_need,
                    -item[1].priority,
                    item[1].zone_id,
                ),
            )
            ordered = self._allocate_automatic_budgets(ordered, now=planning_now)
            created: list[str] = []
            updated: list[str] = []
            cancelled: list[str] = []
            recreated: list[str] = []
            requests = self._stored_state.manual_requests
            sequence = self._stored_state.next_request_sequence
            for subentry, planning_input, decision in ordered:
                if decision.active_window is None:
                    continue
                request_id = self._automatic_request_id(
                    planning_input.zone_id, decision.active_window.opportunity_id
                )
                existing = next(
                    (request for request in requests if request.request_id == request_id), None
                )
                if decision.order is None:
                    if existing is not None and existing.status == "pending":
                        requests = tuple(
                            replace(
                                request,
                                status="cancelled",
                                revision=request.revision + 1,
                            )
                            if request.request_id == request_id
                            else request
                            for request in requests
                        )
                        cancelled.append(request_id)
                    continue
                order = decision.order
                data = subentry.data
                target_type = "volume" if self._has_meter else "duration"
                target_value = (
                    order.target_liters
                    if target_type == "volume"
                    else order.expected_duration_seconds
                )
                meter_rounding: dict[str, object] | None = None
                if target_type == "volume":
                    target_value, meter_rounding = self._round_meter_target(target_value)
                remaining_window = max(
                    1.0,
                    (decision.active_window.end - planning_now).total_seconds(),
                )
                hard_limit = min(
                    remaining_window,
                    self._number(data, CONF_AUTOMATIC_MAX_DURATION, 3_600.0),
                )
                delivery_limit = self._delivery_runtime_limit(data, hard_limit)
                operation_deadline = min(
                    decision.active_window.end,
                    planning_now + timedelta(seconds=self._operation_lifetime_limit(data)),
                )
                balance_snapshot = self._balance_snapshot(data)
                resolved_inputs = dict(
                    self._effective_zone_profile(data, planning_now.date()).resolved_inputs
                )
                if meter_rounding is not None:
                    resolved_inputs["meter_target_rounding"] = meter_rounding
                if existing is not None and existing.status in {"cancelled", "expired"}:
                    requests = tuple(
                        replace(
                            request,
                            sequence=sequence,
                            target_type=target_type,
                            target_value=target_value,
                            remaining_value=target_value,
                            created_at=planning_now.isoformat(),
                            expires_at=decision.active_window.end.isoformat(),
                            status="pending",
                            execution_id=None,
                            hard_time_limit_seconds=(
                                delivery_limit if target_type == "volume" else None
                            ),
                            delivery_runtime_limit_seconds=delivery_limit,
                            operation_deadline_at=operation_deadline.isoformat(),
                            automatic_window_end=decision.active_window.end.isoformat(),
                            automatic_relative_need=planning_input.relative_need,
                            automatic_priority=planning_input.priority,
                            balance_area_m2=balance_snapshot[0],
                            balance_application_efficiency=balance_snapshot[1],
                            balance_maximum_deficit_mm=balance_snapshot[2],
                            balance_minimum_effective_liters=balance_snapshot[3],
                            resolved_inputs=resolved_inputs,
                            revision=request.revision + 1,
                        )
                        if request.request_id == request_id
                        else request
                        for request in requests
                    )
                    sequence += 1
                    recreated.append(request_id)
                    continue
                if existing is not None and existing.status != "pending":
                    continue
                if existing is not None:
                    if (
                        existing.target_type != target_type
                        or abs(existing.target_value - target_value) > 1e-6
                        or existing.automatic_window_end != decision.active_window.end.isoformat()
                        or abs(
                            (existing.automatic_relative_need or 0.0) - planning_input.relative_need
                        )
                        > 1e-6
                        or existing.automatic_priority != planning_input.priority
                    ):
                        requests = tuple(
                            replace(
                                request,
                                target_type=target_type,
                                target_value=target_value,
                                remaining_value=target_value,
                                hard_time_limit_seconds=(
                                    delivery_limit if target_type == "volume" else None
                                ),
                                delivery_runtime_limit_seconds=delivery_limit,
                                operation_deadline_at=operation_deadline.isoformat(),
                                automatic_window_end=decision.active_window.end.isoformat(),
                                automatic_relative_need=planning_input.relative_need,
                                automatic_priority=planning_input.priority,
                                balance_area_m2=balance_snapshot[0],
                                balance_application_efficiency=balance_snapshot[1],
                                balance_maximum_deficit_mm=balance_snapshot[2],
                                balance_minimum_effective_liters=balance_snapshot[3],
                                resolved_inputs=resolved_inputs,
                                revision=request.revision + 1,
                            )
                            if request.request_id == request_id
                            else request
                            for request in requests
                        )
                        updated.append(request_id)
                    continue
                request = ManualIrrigationRequest(
                    request_id=request_id,
                    sequence=sequence,
                    zone_id=planning_input.zone_id,
                    zone_subentry_id=subentry.subentry_id,
                    zone_name=subentry.title,
                    zone_valve=str(data[CONF_ZONE_VALVE]),
                    main_valve=self._installation_data.get(CONF_MAIN_VALVE),
                    target_type=target_type,
                    target_value=target_value,
                    remaining_value=target_value,
                    created_at=planning_now.isoformat(),
                    expires_at=decision.active_window.end.isoformat(),
                    source="automatic",
                    automatic_window_end=decision.active_window.end.isoformat(),
                    automatic_relative_need=planning_input.relative_need,
                    automatic_priority=planning_input.priority,
                    hard_time_limit_seconds=delivery_limit if target_type == "volume" else None,
                    delivery_runtime_limit_seconds=delivery_limit,
                    operation_deadline_at=operation_deadline.isoformat(),
                    max_dose_value=self._optional_float(
                        data,
                        CONF_MAX_DOSE_AMOUNT if target_type == "volume" else CONF_MAX_DOSE_DURATION,
                    ),
                    soak_duration_seconds=self._number(data, CONF_SOAK_DURATION, 0.0),
                    meter_failure_strategy=str(
                        data.get(CONF_METER_FAILURE_STRATEGY, METER_FAILURE_ABORT)
                    ),
                    estimated_flow_l_min=self._estimated_flow(data),
                    minimum_flow_l_min=self._optional_float(data, CONF_MIN_FLOW),
                    maximum_flow_l_min=self._optional_float(data, CONF_MAX_FLOW),
                    flow_grace_seconds=self._number(data, CONF_FLOW_GRACE_SECONDS, 5.0),
                    balance_area_m2=balance_snapshot[0],
                    balance_application_efficiency=balance_snapshot[1],
                    balance_maximum_deficit_mm=balance_snapshot[2],
                    balance_minimum_effective_liters=balance_snapshot[3],
                    resolved_inputs=resolved_inputs,
                )
                requests = (*requests, request)
                sequence += 1
                created.append(request_id)
            changed = bool(created or updated or cancelled or recreated)
            if not dry_run and changed:
                self._stored_state = replace(
                    self._stored_state,
                    manual_requests=requests,
                    next_request_sequence=sequence,
                )
                await self._store.async_save(self._stored_state)
                for request_id in created:
                    request = next(item for item in requests if item.request_id == request_id)
                    self._events.fire(
                        "request_created",
                        reason="automatic_opportunity",
                        target=self._events.zone_target(request.zone_id),
                        measurements={"target_value": request.target_value},
                        context={
                            "request_id": request_id,
                            "target_type": request.target_type,
                            "source": "automatic",
                        },
                    )
                for request_id in (*updated, *recreated):
                    request = next(item for item in requests if item.request_id == request_id)
                    self._events.fire(
                        "request_changed",
                        reason=(
                            "automatic_opportunity_recreated"
                            if request_id in recreated
                            else "automatic_target_recalculated"
                        ),
                        target=self._events.zone_target(request.zone_id),
                        measurements={"target_value": request.target_value},
                        context={
                            "request_id": request_id,
                            "revision": request.revision,
                            "source": "automatic",
                        },
                    )
                for request_id in cancelled:
                    request = next(item for item in requests if item.request_id == request_id)
                    self._events.fire(
                        "request_cancelled",
                        reason="automatic_opportunity_no_longer_needed",
                        target=self._events.zone_target(request.zone_id),
                        context={"request_id": request_id, "source": "automatic"},
                    )
                self._queue_event.set()
            if not dry_run:
                self._publish(status=self._coordinator.data.status, active_zone_id=None)
            return {
                "dry_run": dry_run,
                "created_request_ids": [] if dry_run else created,
                "would_create_request_ids": created if dry_run else [],
                "updated_request_ids": [] if dry_run else updated,
                "cancelled_request_ids": [] if dry_run else cancelled,
                "recreated_request_ids": [] if dry_run else recreated,
                "weather_entity": self._weather_snapshot(),
                "rain_forecast": (
                    self._rain_forecast.as_dict() if self._rain_forecast is not None else None
                ),
                "zones": [
                    {
                        "zone_id": planning_input.zone_id,
                        "needed": decision.needed,
                        "target_liters": decision.target_liters,
                        "planned_liters": (
                            decision.order.target_liters if decision.order else None
                        ),
                        "reason": decision.reason,
                        "window_end": (
                            decision.active_window.end.isoformat()
                            if decision.active_window
                            else None
                        ),
                        "next_window": (
                            decision.next_window_start.isoformat()
                            if decision.next_window_start
                            else None
                        ),
                    }
                    for _, planning_input, decision in ordered
                ],
            }

    def _allocate_automatic_budgets(
        self,
        ordered: list[tuple[_ZoneConfigSnapshot, ZonePlanningInput, ZoneScheduleDecision]],
        *,
        now: datetime,
    ) -> list[tuple[_ZoneConfigSnapshot, ZonePlanningInput, ZoneScheduleDecision]]:
        """Allocate shared budget remainder once in final scheduler priority order."""
        usage = dict(self._stored_state.budget_usage_liters)
        allocated: list[tuple[_ZoneConfigSnapshot, ZonePlanningInput, ZoneScheduleDecision]] = []
        for subentry, planning, decision in ordered:
            order = decision.order
            if order is None:
                allocated.append((subentry, planning, decision))
                continue
            keys = self._budget_keys(planning.zone_id, now)
            limits = (
                self._optional_float(
                    self._installation_data, CONF_INSTALLATION_DAILY_BUDGET_LITERS
                ),
                self._optional_float(
                    self._installation_data, CONF_INSTALLATION_WEEKLY_BUDGET_LITERS
                ),
                self._optional_float(subentry.data, CONF_ZONE_DAILY_BUDGET_LITERS),
                self._optional_float(subentry.data, CONF_ZONE_WEEKLY_BUDGET_LITERS),
            )
            remainders = [
                max(0.0, limit - usage.get(key, 0.0))
                for key, limit in zip(keys, limits, strict=True)
                if limit is not None
            ]
            target = min(order.target_liters, *remainders) if remainders else order.target_liters
            minimum = self._number(subentry.data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1)
            if target < minimum:
                decision = replace(decision, order=None, reason="budget_exhausted")
            else:
                for key in keys:
                    usage[key] = usage.get(key, 0.0) + target
                decision = replace(
                    decision,
                    order=replace(
                        order,
                        target_liters=target,
                        expected_duration_seconds=(target / planning.flow_liters_per_minute * 60),
                        is_partial=order.is_partial or target < order.target_liters,
                    ),
                )
            allocated.append((subentry, planning, decision))
        return allocated

    async def async_skip_automatic(
        self, *, zone_subentry_id: str, now: datetime | None = None
    ) -> dict[str, object]:
        """Suppress exactly the current automatic watering opportunity."""
        planning_now = now or dt_util.now()
        request_id: str
        should_cancel = False
        async with self._command_lock:
            subentry = self._zone_configs_by_subentry_id.get(zone_subentry_id)
            if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
                raise HomeAssistantError("The irrigation zone does not exist")
            raw_windows = subentry.data.get(CONF_WATERING_WINDOWS, ["04:00-06:00"])
            windows = (
                [str(value) for value in raw_windows]
                if isinstance(raw_windows, list | tuple)
                else [str(raw_windows)]
            )
            active_window, _ = active_and_next_window(
                now=planning_now, values=windows, sun_resolver=self._sun_event
            )
            if active_window is None:
                raise HomeAssistantError("The irrigation zone has no active watering window")
            zone_id = subentry.unique_id or subentry.subentry_id
            request_id = self._automatic_request_id(zone_id, active_window.opportunity_id)
            suppressions = self._stored_state.suppressed_automatic_opportunities
            if request_id not in suppressions:
                self._stored_state = replace(
                    self._stored_state,
                    suppressed_automatic_opportunities=(*suppressions, request_id),
                )
                await self._store.async_save(self._stored_state)
            request = self._request(request_id)
            should_cancel = request is not None and request.status not in {
                "completed",
                "cancelled",
                "expired",
            }
            self._publish(status=self._coordinator.data.status, active_zone_id=None)
        if should_cancel:
            await self.async_cancel_request(request_id)
        self._planning_event.set()
        return {"opportunity_id": request_id, "suppressed": True}

    async def async_clear_forecast_deferral(self, *, zone_subentry_id: str) -> dict[str, object]:
        """Explicitly cancel one zone's persisted forecast delay."""
        async with self._command_lock:
            subentry = self._zone_configs_by_subentry_id.get(zone_subentry_id)
            if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
                raise HomeAssistantError("The irrigation zone does not exist")
            zone_id = subentry.unique_id or subentry.subentry_id
            existed = zone_id in self._stored_state.forecast_deferral_started
            if existed:
                self._stored_state = replace(
                    self._stored_state,
                    forecast_deferral_started={
                        key: value
                        for key, value in self._stored_state.forecast_deferral_started.items()
                        if key != zone_id
                    },
                    forecast_deferral_deadlines={
                        key: value
                        for key, value in self._stored_state.forecast_deferral_deadlines.items()
                        if key != zone_id
                    },
                    cancelled_forecast_deferrals=tuple(
                        sorted({*self._stored_state.cancelled_forecast_deferrals, zone_id})
                    ),
                )
                await self._store.async_save(self._stored_state)
                self._planning_event.set()
                self._publish(status=self._coordinator.data.status, active_zone_id=None)
                self._events.fire(
                    "automatic_irrigation_deferral_cancelled",
                    reason="user_cancelled",
                    target=self._events.zone_target(zone_id),
                )
            return {"zone_id": zone_id, "cancelled": existed}

    async def async_finalize_daily_weather(
        self,
        *,
        period_id: str,
        reference_evapotranspiration_mm: float,
        rain_mm: float,
        calculation: Et0Result | None = None,
        weather_inputs: Mapping[str, object] | None = None,
        finalized_at: datetime | None = None,
    ) -> dict[str, object]:
        """Apply one finalized daily weather contribution exactly once."""
        if not all(
            math.isfinite(value) and value >= 0
            for value in (reference_evapotranspiration_mm, rain_mm)
        ):
            raise HomeAssistantError("Finalized weather values must be finite and non-negative")
        signature = json.dumps([reference_evapotranspiration_mm, rain_mm], separators=(",", ":"))
        async with self._command_lock:
            previous = self._stored_state.finalized_weather_periods.get(period_id)
            if previous is not None:
                if previous != signature:
                    raise HomeAssistantError(
                        "This weather period was already finalized with different values"
                    )
                return {"applied": False, "period_id": period_id}
            deficits = dict(self._stored_state.zone_deficit_mm)
            zone_snapshots: dict[str, dict[str, object]] = {}
            period_day = date.fromisoformat(period_id)
            for subentry in self._zone_configs:
                zone_id = subentry.unique_id or subentry.subentry_id
                data = subentry.data
                profile = self._effective_zone_profile(data, period_day)
                maximum = profile.maximum_deficit_mm
                previous_deficit = deficits.get(zone_id, 0.0)
                crop_factor = profile.crop_and_location_factor
                crop_et = reference_evapotranspiration_mm * crop_factor
                effective_rain = calculate_effective_rain(
                    measured_rain_mm=rain_mm,
                    rain_factor=profile.rain_factor,
                    maximum_infiltration_mm=self._number(data, CONF_MAX_EFFECTIVE_RAIN_MM, 25.0),
                    available_storage_mm=previous_deficit + crop_et,
                )
                updated = apply_water_balance(
                    ZoneWaterBalance(previous_deficit, maximum),
                    WaterBalancePeriod(
                        crop_evapotranspiration_mm=crop_et,
                        effective_rain_mm=effective_rain.effective_mm,
                        effective_irrigation_mm=0.0,
                    ),
                )
                deficits[zone_id] = updated.deficit_mm
                area = profile.area_m2
                efficiency = profile.application_efficiency
                gross_target = calculate_irrigation_target_liters(
                    deficit_mm=updated.deficit_mm,
                    area_m2=area,
                    application_efficiency=efficiency,
                )
                zone_snapshots[zone_id] = {
                    "previous_deficit_mm": previous_deficit,
                    "reference_evapotranspiration_mm": reference_evapotranspiration_mm,
                    "seasonal_crop_and_location_factor": crop_factor,
                    "crop_evapotranspiration_mm": crop_et,
                    "measured_rain_mm": rain_mm,
                    "rain_factor": profile.rain_factor,
                    "maximum_effective_rain_mm": self._number(
                        data, CONF_MAX_EFFECTIVE_RAIN_MM, 25.0
                    ),
                    "effective_rain_mm": effective_rain.effective_mm,
                    "runoff_mm": effective_rain.runoff_mm,
                    "drainage_mm": effective_rain.drainage_mm,
                    "final_deficit_mm": updated.deficit_mm,
                    "maximum_deficit_mm": maximum,
                    "resolved_profile": profile.resolved_inputs,
                    "target": {
                        "net_depth_mm": updated.deficit_mm,
                        "area_m2": area,
                        "application_efficiency": efficiency,
                        "gross_liters_before_limits": gross_target,
                        "maximum_target_liters": self._number(
                            data, CONF_MAXIMUM_TARGET_LITERS, 1_000.0
                        ),
                        "minimum_trigger_liters": self._number(
                            data, CONF_MINIMUM_TRIGGER_LITERS, 1.0
                        ),
                        "watering_mode": str(data.get(CONF_WATERING_MODE, WateringMode.DEMAND)),
                    },
                }
            periods = dict(self._stored_state.finalized_weather_periods)
            periods[period_id] = signature
            at = finalized_at or dt_util.now()
            et0_snapshot = calculation or Et0Result(
                reference_evapotranspiration_mm,
                "manual",
                "provided",
                dict(weather_inputs or {}),
                {},
            )
            snapshots = dict(self._stored_state.weather_calculation_snapshots)
            snapshots[period_id] = {
                "period_id": period_id,
                "period_start": period_id,
                "finalized_at": at.isoformat(),
                "et0": et0_snapshot.as_dict(),
                "rain_mm": rain_mm,
                "weather_inputs": dict(weather_inputs or {}),
                "zones": zone_snapshots,
            }
            snapshots = dict(sorted(snapshots.items())[-90:])
            self._stored_state = replace(
                self._stored_state,
                zone_deficit_mm=deficits,
                finalized_weather_periods=periods,
                weather_calculation_snapshots=snapshots,
                weather_failure_since=(
                    self._stored_state.weather_failure_since or at.isoformat()
                    if et0_snapshot.method.endswith("_fallback")
                    else None
                ),
            )
            self._reference_evapotranspiration_mm = reference_evapotranspiration_mm
            self._measured_rain_mm = rain_mm
            self._weather_model_quality = et0_snapshot.quality
            self._weather_model_method = et0_snapshot.method
            self._weather_period_id = period_id
            self._weather_last_finalized_at = at.isoformat()
            self._weather_automation_available = True
            self._zone_calculation_explanations = zone_snapshots
            self._zone_crop_evapotranspiration_mm = self._numeric_zone_snapshot_values(
                zone_snapshots, "crop_evapotranspiration_mm"
            )
            self._zone_effective_rain_mm = self._numeric_zone_snapshot_values(
                zone_snapshots, "effective_rain_mm"
            )
            await self._store.async_save(self._stored_state)
            self._planning_event.set()
            self._publish(status=self._coordinator.data.status, active_zone_id=None)
            self._events.fire(
                "weather_correction_applied",
                reason="daily_weather_finalized",
                target=self._events.installation_target(),
                measurements={
                    "reference_evapotranspiration_mm": reference_evapotranspiration_mm,
                    "rain_mm": rain_mm,
                },
                quality="final",
                context={
                    "period_id": period_id,
                    "zone_deficit_mm": deficits,
                    "model": et0_snapshot.method,
                },
            )
            return {
                "applied": True,
                "period_id": period_id,
                "zone_deficit_mm": deficits,
                "calculation": et0_snapshot.as_dict(),
            }

    async def async_finalize_weather_day(self, day: date) -> dict[str, object]:
        """Acquire, calculate, and durably finalize one completed local day."""
        if day.isoformat() in self._stored_state.finalized_weather_periods:
            return {"applied": False, "period_id": day.isoformat()}
        weather = await self._weather.async_daily_weather(day)
        calculation = self._weather.calculate_et0(weather)
        now = dt_util.now()
        failure_since = self._stored_state.weather_failure_since
        if calculation.value_mm is None or weather.rain_mm is None:
            failure_start = datetime.fromisoformat(failure_since) if failure_since else now
            fallback_days = self._number(self._installation_data, CONF_WEATHER_FALLBACK_DAYS, 3)
            within_fallback = now <= failure_start + timedelta(days=fallback_days)
            fallback_value: float | None = None
            fallback_method = "unavailable"
            if within_fallback:
                latest = self._latest_final_weather_snapshot()
                latest_period = (
                    max(self._stored_state.weather_calculation_snapshots)
                    if self._stored_state.weather_calculation_snapshots
                    else None
                )
                if (
                    latest is not None
                    and latest_period is not None
                    and abs((day - date.fromisoformat(latest_period)).days) <= fallback_days
                ):
                    et0 = latest.get("et0")
                    candidate = et0.get("value_mm") if isinstance(et0, dict) else None
                    if isinstance(candidate, int | float) and not isinstance(candidate, bool):
                        fallback_value = float(candidate)
                        fallback_method = "historical_fallback"
                if fallback_value is None:
                    fallback_value = seasonal_et0(self._installation_data, day)
                    fallback_method = "seasonal_fallback"
            if fallback_value is not None and weather.rain_mm is not None:
                calculation = Et0Result(
                    fallback_value,
                    fallback_method,
                    "degraded",
                    weather.inputs(),
                    calculation.comparisons,
                    (*calculation.warnings, "weather_fallback_active"),
                )
            else:
                self._weather_automation_available = False
                self._weather_model_quality = "unknown"
                self._weather_model_method = "unavailable"
                reason = (
                    "fallback_duration_exhausted"
                    if not within_fallback
                    else "required_observation_missing"
                )
                return await self._async_record_unknown_weather_day(
                    day=day,
                    calculation=calculation,
                    weather_inputs=weather.inputs(),
                    failure_start=failure_start,
                    reason=reason,
                )
        assert calculation.value_mm is not None
        assert weather.rain_mm is not None
        return await self.async_finalize_daily_weather(
            period_id=day.isoformat(),
            reference_evapotranspiration_mm=calculation.value_mm,
            rain_mm=weather.rain_mm.value,
            calculation=calculation,
            weather_inputs=weather.inputs(),
            finalized_at=now,
        )

    async def _async_record_unknown_weather_day(
        self,
        *,
        day: date,
        calculation: Et0Result,
        weather_inputs: Mapping[str, object],
        failure_start: datetime,
        reason: str,
    ) -> dict[str, object]:
        """Account for one unavailable day without inventing balance contributions."""
        period_id = day.isoformat()
        finalized_at = dt_util.now()
        async with self._command_lock:
            if period_id in self._stored_state.finalized_weather_periods:
                return {"applied": False, "period_id": period_id}
            periods = dict(self._stored_state.finalized_weather_periods)
            periods[period_id] = json.dumps([None, None, reason], separators=(",", ":"))
            snapshots = dict(self._stored_state.weather_calculation_snapshots)
            zones = {
                (subentry.unique_id or subentry.subentry_id): {
                    "accounting_applied": False,
                    "quality": "unknown",
                    "reason": reason,
                    "final_deficit_mm": self._stored_state.zone_deficit_mm.get(
                        subentry.unique_id or subentry.subentry_id, 0.0
                    ),
                }
                for subentry in self._zone_configs
            }
            snapshots[period_id] = {
                "period_id": period_id,
                "period_start": period_id,
                "finalized_at": finalized_at.isoformat(),
                "et0": {
                    **calculation.as_dict(),
                    "method": "unavailable",
                    "quality": "unknown",
                    "value_mm": None,
                },
                "rain_mm": None,
                "weather_inputs": dict(weather_inputs),
                "zones": zones,
                "accounting_applied": False,
                "reason": reason,
            }
            snapshots = dict(sorted(snapshots.items())[-90:])
            self._stored_state = replace(
                self._stored_state,
                finalized_weather_periods=periods,
                weather_calculation_snapshots=snapshots,
                weather_failure_since=(
                    self._stored_state.weather_failure_since or failure_start.isoformat()
                ),
            )
            self._weather_model_quality = "unknown"
            self._weather_model_method = "unavailable"
            self._weather_period_id = period_id
            self._weather_last_finalized_at = finalized_at.isoformat()
            self._weather_automation_available = False
            self._zone_calculation_explanations = zones
            await self._store.async_save(self._stored_state)
            self._publish(status=self._coordinator.data.status, active_zone_id=None)
        self._events.fire(
            "weather_model_unavailable",
            reason=reason,
            target=self._events.installation_target(),
            quality="unknown",
            context={"period_id": period_id, "accounting_applied": False},
        )
        return {
            "applied": True,
            "accounting_applied": False,
            "period_id": period_id,
            "quality": "unknown",
            "reason": reason,
        }

    async def async_update_weather_preview(
        self, *, now: datetime | None = None
    ) -> dict[str, object]:
        """Publish a current-day estimate without mutating the durable balance."""
        current = now or dt_util.now()
        local_day = current.astimezone(dt_util.DEFAULT_TIME_ZONE).date()
        weather = await self._weather.async_daily_weather(local_day, end=current)
        calculation = self._weather.calculate_et0(weather)
        provisional: dict[str, float] = {}
        crop_values: dict[str, float] = {}
        rain_values: dict[str, float] = {}
        explanations: dict[str, dict[str, object]] = {}
        if calculation.value_mm is not None and weather.rain_mm is not None:
            for subentry in self._zone_configs:
                zone_id = subentry.unique_id or subentry.subentry_id
                data = subentry.data
                previous = self._stored_state.zone_deficit_mm.get(zone_id, 0.0)
                profile = self._effective_zone_profile(data, local_day)
                maximum = profile.maximum_deficit_mm
                factor = profile.crop_and_location_factor
                crop_et = calculation.value_mm * factor
                rain = calculate_effective_rain(
                    measured_rain_mm=weather.rain_mm.value,
                    rain_factor=profile.rain_factor,
                    maximum_infiltration_mm=self._number(data, CONF_MAX_EFFECTIVE_RAIN_MM, 25),
                    available_storage_mm=previous + crop_et,
                )
                updated = apply_water_balance(
                    ZoneWaterBalance(previous, maximum),
                    WaterBalancePeriod(crop_et, rain.effective_mm, 0),
                )
                provisional[zone_id] = updated.deficit_mm
                crop_values[zone_id] = crop_et
                rain_values[zone_id] = rain.effective_mm
                explanations[zone_id] = {
                    "provisional": True,
                    "period_id": local_day.isoformat(),
                    "previous_final_deficit_mm": previous,
                    "crop_evapotranspiration_mm": crop_et,
                    "effective_rain_mm": rain.effective_mm,
                    "provisional_deficit_mm": updated.deficit_mm,
                    "model": calculation.as_dict(),
                    "resolved_profile": profile.resolved_inputs,
                }
        self._zone_provisional_deficit_mm = provisional
        self._provisional_period_id = (
            current.astimezone(dt_util.DEFAULT_TIME_ZONE).date().isoformat()
        )
        self._last_weather_preview_at = current.astimezone(UTC)
        self._zone_crop_evapotranspiration_mm = crop_values
        self._zone_effective_rain_mm = rain_values
        if explanations:
            self._zone_calculation_explanations = explanations
        self._publish(status=self._coordinator.data.status, active_zone_id=None)
        return {
            "period_id": local_day.isoformat(),
            "calculation": calculation.as_dict(),
            "zone_provisional_deficit_mm": provisional,
        }

    def _seasonal_crop_factor(self, data: Mapping[str, Any], day: date) -> float:
        """Return the configured base factor adjusted by its annual monthly curve."""
        base = self._number(data, CONF_CROP_FACTOR, 1.0)
        raw = data.get(CONF_SEASONAL_CROP_FACTORS)
        if raw is None:
            return base
        try:
            return base * calculate_seasonal_value(cast(str, raw), day)
        except TypeError, ValueError:
            return base

    def _latest_final_weather_snapshot(self) -> dict[str, object] | None:
        """Return the newest immutable weather snapshot, if any."""
        snapshots = self._stored_state.weather_calculation_snapshots
        return snapshots[max(snapshots)] if snapshots else None

    async def _async_automatic_planner(self) -> None:
        """Replan at window boundaries and after water-balance changes."""
        while not self._shutting_down:
            self._planning_event.clear()
            try:
                await self.async_plan_automatic()
                delay = self._seconds_until_next_automatic_change()
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._planning_event.wait(), timeout=delay)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                await asyncio.sleep(60)

    def _seconds_until_next_automatic_change(self) -> float:
        """Return a bounded delay to the next start or end of a configured window."""
        now = dt_util.now()
        boundaries: list[datetime] = []
        for subentry in self._zone_configs:
            raw = subentry.data.get(CONF_WATERING_WINDOWS, ["04:00-06:00"])
            values = [str(value) for value in raw] if isinstance(raw, list | tuple) else [str(raw)]
            active, next_start = active_and_next_window(
                now=now, values=values, sun_resolver=self._sun_event
            )
            if active is not None:
                boundaries.append(active.end)
            if next_start is not None:
                boundaries.append(next_start)
        if not boundaries:
            return 3_600.0
        return max(0.1, min((boundary - now).total_seconds() for boundary in boundaries))

    def _weather_snapshot(self) -> dict[str, object] | None:
        """Expose configured native weather state as planning context without templates."""
        entity_id = self._installation_data.get(CONF_WEATHER_ENTITY)
        state = self._hass.states.get(entity_id) if isinstance(entity_id, str) else None
        if state is None:
            return None
        return {
            "entity_id": entity_id,
            "state": state.state,
            "attributes": {
                key: state.attributes[key]
                for key in ("temperature", "humidity", "wind_speed", "pressure")
                if key in state.attributes
            },
        }

    async def async_start_manual(
        self,
        *,
        zone_subentry_id: str,
        duration_seconds: float | None,
        amount_liters: float | None,
        hard_time_limit_seconds: float | None,
        expiry_seconds: float = 3600,
        requested_start_at: datetime | None = None,
        wait_for_completion: bool = True,
    ) -> dict[str, object]:
        """Persist a manual order, dispatch it immediately when possible, and return its ID."""
        async with self._command_lock:
            if self._stored_state.emergency_stop:
                raise HomeAssistantError("The emergency stop is active")
            if self._stored_state.winter_lock:
                raise HomeAssistantError("The winter lock is active")
            if self._stored_state.maintenance_test is not None:
                raise HomeAssistantError("A supervised maintenance test is active")
            subentry = self._zone_configs_by_subentry_id.get(zone_subentry_id)
            if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
                raise HomeAssistantError("The irrigation zone does not exist")
            if amount_liters is not None and not self._has_meter:
                raise HomeAssistantError("Volume irrigation requires a configured cumulative meter")
            meter_rounding: dict[str, object] | None = None
            if amount_liters is not None:
                amount_liters, meter_rounding = self._round_meter_target(amount_liters)
            target_type = "volume" if amount_liters is not None else "duration"
            target_value = amount_liters if amount_liters is not None else duration_seconds
            if target_value is None:
                raise HomeAssistantError("An irrigation target is required")
            now = datetime.now(UTC)
            requested_start = (requested_start_at or now).astimezone(UTC)
            if requested_start < now:
                requested_start = now
            request_id = uuid4().hex
            zone_id = subentry.unique_id or subentry.subentry_id
            max_dose_key = (
                CONF_MAX_DOSE_AMOUNT if target_type == "volume" else CONF_MAX_DOSE_DURATION
            )
            balance_snapshot = self._balance_snapshot(subentry.data)
            delivery_limit = self._delivery_runtime_limit(subentry.data, hard_time_limit_seconds)
            expires_at = requested_start + timedelta(seconds=expiry_seconds)
            operation_deadline = min(
                expires_at,
                requested_start + timedelta(seconds=self._operation_lifetime_limit(subentry.data)),
            )
            weather = self._weather_safety()
            if weather.frost_blocked:
                raise HomeAssistantError(f"Frost safety blocks irrigation ({weather.status})")
            if weather.rain_stop_active:
                self._events.fire(
                    "weather_interlock_warning",
                    reason="manual_rain_override",
                    target=self._events.zone_target(zone_id),
                    quality=weather.status,
                )
            request = ManualIrrigationRequest(
                request_id=request_id,
                sequence=self._stored_state.next_request_sequence,
                zone_id=zone_id,
                zone_subentry_id=zone_subentry_id,
                zone_name=subentry.title,
                zone_valve=subentry.data[CONF_ZONE_VALVE],
                main_valve=self._installation_data.get(CONF_MAIN_VALVE),
                target_type=target_type,
                target_value=target_value,
                remaining_value=target_value,
                created_at=now.isoformat(),
                expires_at=expires_at.isoformat(),
                requested_start_at=requested_start.isoformat(),
                hard_time_limit_seconds=(delivery_limit if target_type == "volume" else None),
                delivery_runtime_limit_seconds=delivery_limit,
                operation_deadline_at=operation_deadline.isoformat(),
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
                balance_area_m2=balance_snapshot[0],
                balance_application_efficiency=balance_snapshot[1],
                balance_maximum_deficit_mm=balance_snapshot[2],
                balance_minimum_effective_liters=balance_snapshot[3],
                resolved_inputs=dict(
                    self._effective_zone_profile(subentry.data, now.date()).resolved_inputs
                    | ({"meter_target_rounding": meter_rounding} if meter_rounding else {})
                ),
            )
            budget_warnings = self._manual_budget_warnings(request, now=requested_start)
            if meter_rounding and meter_rounding["direction"] != "exact":
                budget_warnings.append("meter_target_rounded_up")
            if meter_rounding and meter_rounding.get("coarse_resolution") is True:
                budget_warnings.append("coarse_meter_resolution")
            self._stored_state = replace(
                self._stored_state,
                manual_requests=(*self._stored_state.manual_requests, request),
                next_request_sequence=self._stored_state.next_request_sequence + 1,
            )
            await self._store.async_save(self._stored_state)
            self._events.fire(
                "request_created",
                reason="manual_request",
                target=self._events.zone_target(zone_id),
                measurements={"target_value": target_value},
                context={
                    "request_id": request_id,
                    "target_type": target_type,
                    "source": "manual",
                },
            )
            for warning in budget_warnings:
                self._events.fire(
                    "manual_budget_overrun_warning",
                    reason=warning,
                    target=self._events.zone_target(zone_id),
                    measurements={"target_liters": self._request_target_liters(request)},
                    context={"request_id": request_id},
                )
            if budget_warnings:
                await self._events.async_critical(
                    f"manual_budget_overrun_{request_id}",
                    title="Manual irrigation exceeds a water budget",
                    message=(
                        f"{request.zone_name} was queued by explicit request despite exceeding: "
                        f"{', '.join(budget_warnings)}."
                    ),
                )
            terminal_event = self._terminal_events.setdefault(request_id, asyncio.Event())
            self._queue_event.set()
            self._publish(status=self._coordinator.data.status, active_zone_id=None)

        if wait_for_completion:
            await terminal_event.wait()
            if error := self._request_errors.pop(request_id, None):
                raise error
        return {"request_id": request_id, "warnings": budget_warnings}

    async def async_create_manual_plan(
        self,
        *,
        items: tuple[Mapping[str, object], ...],
        requested_start_at: datetime | None,
        expiry_seconds: float,
        plan_id: str | None = None,
    ) -> dict[str, object]:
        """Validate and persist a stable ordered multi-zone plan in one write."""
        if not items:
            raise HomeAssistantError("A manual plan requires at least one irrigation zone")
        async with self._command_lock:
            existing = sorted(
                (
                    request
                    for request in self._stored_state.manual_requests
                    if plan_id is not None and request.plan_id == plan_id
                ),
                key=lambda request: (request.sequence, request.request_id),
            )
            if existing and len(existing) != len(items):
                raise HomeAssistantError("The manual plan ID already has different items")
            if self._stored_state.emergency_stop or self._stored_state.winter_lock:
                raise HomeAssistantError("The irrigation installation is locked")
            if self._stored_state.maintenance_test is not None:
                raise HomeAssistantError("A supervised maintenance test is active")
            now = datetime.now(UTC)
            requested_start = (
                requested_start_at.astimezone(UTC)
                if existing and requested_start_at is not None
                else datetime.fromisoformat(
                    existing[0].requested_start_at or existing[0].created_at
                )
                if existing
                else max((requested_start_at or now).astimezone(UTC), now)
            )
            plan_id = plan_id or uuid4().hex
            sequence = self._stored_state.next_request_sequence
            requests: list[ManualIrrigationRequest] = []
            for index, item in enumerate(items):
                zone_subentry_id = item.get("zone_subentry_id")
                if not isinstance(zone_subentry_id, str):
                    raise HomeAssistantError("Every plan item requires an irrigation zone")
                duration = self._finite_positive(item.get("duration"))
                amount = self._finite_positive(item.get("amount"))
                hard_limit = self._finite_positive(item.get("hard_time_limit"))
                if (duration is None) == (amount is None):
                    raise HomeAssistantError("Every plan item requires exactly one target")
                if amount is not None and hard_limit is None:
                    raise HomeAssistantError("Amount targets require a hard time limit")
                subentry = self._zone_configs_by_subentry_id.get(zone_subentry_id)
                if subentry is None:
                    raise HomeAssistantError("A plan irrigation zone does not exist")
                if amount is not None and not self._has_meter:
                    raise HomeAssistantError("Volume irrigation requires a cumulative meter")
                meter_rounding: dict[str, object] | None = None
                if amount is not None:
                    amount, meter_rounding = self._round_meter_target(amount)
                target_type = "volume" if amount is not None else "duration"
                target_value = amount if amount is not None else duration
                assert target_value is not None
                delivery_limit = self._delivery_runtime_limit(subentry.data, hard_limit)
                expires_at = requested_start + timedelta(seconds=expiry_seconds)
                balance = self._balance_snapshot(subentry.data)
                request = ManualIrrigationRequest(
                    request_id=(existing[index].request_id if existing else uuid4().hex),
                    sequence=(existing[index].sequence if existing else sequence),
                    zone_id=subentry.unique_id or subentry.subentry_id,
                    zone_subentry_id=subentry.subentry_id,
                    zone_name=subentry.title,
                    zone_valve=str(subentry.data[CONF_ZONE_VALVE]),
                    main_valve=self._installation_data.get(CONF_MAIN_VALVE),
                    target_type=target_type,
                    target_value=target_value,
                    remaining_value=target_value,
                    created_at=now.isoformat(),
                    expires_at=expires_at.isoformat(),
                    requested_start_at=requested_start.isoformat(),
                    plan_id=plan_id,
                    hard_time_limit_seconds=delivery_limit if target_type == "volume" else None,
                    delivery_runtime_limit_seconds=delivery_limit,
                    operation_deadline_at=min(
                        expires_at,
                        requested_start
                        + timedelta(seconds=self._operation_lifetime_limit(subentry.data)),
                    ).isoformat(),
                    max_dose_value=self._optional_float(
                        subentry.data,
                        CONF_MAX_DOSE_AMOUNT if target_type == "volume" else CONF_MAX_DOSE_DURATION,
                    ),
                    soak_duration_seconds=self._number(subentry.data, CONF_SOAK_DURATION, 0),
                    meter_failure_strategy=str(
                        subentry.data.get(CONF_METER_FAILURE_STRATEGY, METER_FAILURE_ABORT)
                    ),
                    estimated_flow_l_min=self._estimated_flow(subentry.data),
                    minimum_flow_l_min=self._optional_float(subentry.data, CONF_MIN_FLOW),
                    maximum_flow_l_min=self._optional_float(subentry.data, CONF_MAX_FLOW),
                    flow_grace_seconds=self._number(subentry.data, CONF_FLOW_GRACE_SECONDS, 5),
                    balance_area_m2=balance[0],
                    balance_application_efficiency=balance[1],
                    balance_maximum_deficit_mm=balance[2],
                    balance_minimum_effective_liters=balance[3],
                    resolved_inputs=dict(
                        self._effective_zone_profile(subentry.data, now.date()).resolved_inputs
                        | ({"meter_target_rounding": meter_rounding} if meter_rounding else {})
                    ),
                )
                requests.append(request)
                sequence += 1
            if existing:
                if any(
                    self._canonical_plan_request(current) != self._canonical_plan_request(candidate)
                    for current, candidate in zip(existing, requests, strict=True)
                ):
                    raise HomeAssistantError(
                        "The manual plan ID was reused with a different immutable request"
                    )
                return {
                    "plan_id": plan_id,
                    "request_ids": [request.request_id for request in existing],
                    "warnings": {},
                    "created": False,
                }
            next_state = replace(
                self._stored_state,
                manual_requests=(*self._stored_state.manual_requests, *requests),
                next_request_sequence=sequence,
            )
            await self._store.async_save(next_state)
            self._stored_state = next_state
            warnings = {
                request.request_id: self._manual_budget_warnings(request, now=requested_start)
                for request in requests
            }
            for request in requests:
                self._events.fire(
                    "request_created",
                    reason="manual_plan",
                    target=self._events.zone_target(request.zone_id),
                    measurements={"target_value": request.target_value},
                    context={"request_id": request.request_id, "plan_id": plan_id},
                )
                if request_warnings := warnings[request.request_id]:
                    await self._events.async_critical(
                        f"manual_budget_overrun_{request.request_id}",
                        title="Manual irrigation exceeds a water budget",
                        message=(
                            f"{request.zone_name} was queued by explicit request despite "
                            f"exceeding: {', '.join(request_warnings)}."
                        ),
                    )
            self._queue_event.set()
            self._publish(status=self._coordinator.data.status, active_zone_id=None)
            return {
                "plan_id": plan_id,
                "request_ids": [request.request_id for request in requests],
                "warnings": warnings,
                "created": True,
            }

    @staticmethod
    def _canonical_plan_request(request: ManualIrrigationRequest) -> dict[str, object]:
        """Return every immutable execution input represented by one plan request."""
        mutable_or_generated = {
            "request_id",
            "sequence",
            "remaining_value",
            "created_at",
            "status",
            "execution_id",
            "soak_until",
            "pause_until",
            "revision",
        }
        return {
            key: value
            for key, value in request.as_dict().items()
            if key not in mutable_or_generated
        }

    async def async_edit_request(
        self,
        *,
        request_id: str,
        duration_seconds: float | None,
        amount_liters: float | None,
        hard_time_limit_seconds: float | None,
        requested_start_at: datetime | None,
        expires_at: datetime | None,
    ) -> dict[str, object]:
        """Edit a manual request target and opportunity before execution starts."""
        async with self._command_lock:
            request = self._request(request_id)
            if request is None or request.source != "manual":
                raise HomeAssistantError("The manual irrigation request does not exist")
            if request.status != "pending" or request.execution_id is not None:
                raise HomeAssistantError("Only an unstarted request can be edited")
            if duration_seconds is not None and amount_liters is not None:
                raise HomeAssistantError("Exactly one edited target may be provided")
            subentry = self._zone_configs_by_subentry_id.get(request.zone_subentry_id)
            if subentry is None:
                raise HomeAssistantError("The irrigation zone no longer exists")
            target_type = request.target_type
            target_value = request.target_value
            if duration_seconds is not None:
                target_type, target_value = "duration", duration_seconds
            elif amount_liters is not None:
                if not self._has_meter:
                    raise HomeAssistantError("Volume irrigation requires a cumulative meter")
                target_type = "volume"
                target_value, meter_rounding = self._round_meter_target(amount_liters)
            if target_type == "volume" and hard_time_limit_seconds is None:
                hard_time_limit_seconds = request.hard_time_limit_seconds
            delivery_limit = self._delivery_runtime_limit(
                subentry.data, hard_time_limit_seconds if target_type == "volume" else None
            )
            start = (
                requested_start_at.astimezone(UTC)
                if requested_start_at is not None
                else datetime.fromisoformat(request.requested_start_at or request.created_at)
            )
            expiry = (
                expires_at.astimezone(UTC)
                if expires_at is not None
                else datetime.fromisoformat(request.expires_at)
            )
            if expiry <= start:
                raise HomeAssistantError("Request expiry must be after its desired start")
            updated = replace(
                request,
                target_type=target_type,
                target_value=target_value,
                remaining_value=target_value,
                requested_start_at=start.isoformat(),
                expires_at=expiry.isoformat(),
                hard_time_limit_seconds=delivery_limit if target_type == "volume" else None,
                delivery_runtime_limit_seconds=delivery_limit,
                operation_deadline_at=min(
                    expiry,
                    start + timedelta(seconds=self._operation_lifetime_limit(subentry.data)),
                ).isoformat(),
                max_dose_value=self._optional_float(
                    subentry.data,
                    CONF_MAX_DOSE_AMOUNT if target_type == "volume" else CONF_MAX_DOSE_DURATION,
                ),
                resolved_inputs={
                    **request.resolved_inputs,
                    **(
                        {"meter_target_rounding": meter_rounding}
                        if amount_liters is not None
                        else {}
                    ),
                },
                revision=request.revision + 1,
            )
            self._stored_state = replace(
                self._stored_state, manual_requests=self._with_request(updated)
            )
            await self._store.async_save(self._stored_state)
            self._queue_event.set()
            self._events.fire(
                "request_changed",
                reason="user_edit",
                target=self._events.zone_target(updated.zone_id),
                measurements={"target_value": updated.target_value},
                context={"request_id": request_id, "revision": updated.revision},
            )
            warnings = self._manual_budget_warnings(updated, now=start)
            if warnings:
                await self._events.async_critical(
                    f"manual_budget_overrun_{request_id}",
                    title="Manual irrigation exceeds a water budget",
                    message=(
                        f"{updated.zone_name} was changed by explicit request despite "
                        f"exceeding: {', '.join(warnings)}."
                    ),
                )
            return {**updated.as_dict(), "warnings": warnings}

    async def async_reorder_requests(self, request_ids: tuple[str, ...]) -> list[str]:
        """Assign an explicit stable priority order to unstarted manual requests."""
        if len(request_ids) != len(set(request_ids)):
            raise HomeAssistantError("Request IDs in a reorder action must be unique")
        async with self._command_lock:
            open_requests = sorted(
                (
                    request
                    for request in self._stored_state.manual_requests
                    if request.source == "manual"
                    and request.status in {"pending", "paused", "executing", "soaking"}
                ),
                key=lambda request: (request.sequence, request.request_id),
            )
            pending = [
                request
                for request in open_requests
                if request.status == "pending" and request.execution_id is None
            ]
            by_id = {request.request_id: request for request in pending}
            if any(request_id not in by_id for request_id in request_ids):
                raise HomeAssistantError("Only unstarted manual requests can be reordered")
            selected = [by_id[request_id] for request_id in request_ids]
            selected_ids = set(request_ids)
            ordered_pending = selected + [
                request for request in pending if request.request_id not in selected_ids
            ]
            pending_iterator = iter(ordered_pending)
            ordered = [
                next(pending_iterator) if request in pending else request
                for request in open_requests
            ]
            next_sequence = self._stored_state.next_request_sequence
            sequence_by_id = {
                request.request_id: index
                for index, request in enumerate(ordered, start=next_sequence)
            }
            requests = tuple(
                replace(
                    request,
                    sequence=sequence_by_id[request.request_id],
                    revision=request.revision + 1,
                )
                if request.request_id in sequence_by_id
                and request.sequence != sequence_by_id[request.request_id]
                else request
                for request in self._stored_state.manual_requests
            )
            next_state = replace(
                self._stored_state,
                manual_requests=requests,
                next_request_sequence=next_sequence + len(ordered),
            )
            await self._store.async_save(next_state)
            self._stored_state = next_state
            self._queue_event.set()
            return [request.request_id for request in ordered_pending]

    async def _async_dispatch_requests(self) -> None:
        """Run ready manual orders one dose at a time, yielding during soak pauses."""
        while not self._shutting_down:
            self._queue_event.clear()
            request: ManualIrrigationRequest | None = None
            run_identity: str | None = None
            try:
                async with self._command_lock:
                    await self._async_expire_requests()
                    request = select_manual_request(
                        now=datetime.now(UTC),
                        requests=self._stored_state.manual_requests,
                        executions=self._stored_state.irrigation_executions,
                    )
                    if request is not None and request.source == "automatic":
                        request = await self._async_apply_dispatch_budget(request)
                if request is None:
                    delay = self._seconds_until_next_request_change()
                    with suppress(TimeoutError):
                        await asyncio.wait_for(self._queue_event.wait(), timeout=delay)
                    continue

                dose_value = dose_target(request)
                execution = self._execution(request.execution_id)
                dose_number = execution.dose_number + 1 if execution is not None else 1
                runtime_limit = (
                    request.delivery_runtime_limit_seconds
                    if request.delivery_runtime_limit_seconds is not None
                    else request.hard_time_limit_seconds
                )
                remaining_runtime = (
                    None
                    if runtime_limit is None
                    else max(
                        0.0,
                        runtime_limit - self._consumed_watering_seconds(request.request_id),
                    )
                )
                if remaining_runtime is not None and remaining_runtime <= 0:
                    async with self._command_lock:
                        await self._async_fail_request(
                            request.request_id,
                            HomeAssistantError("Irrigation execution hard runtime exhausted"),
                        )
                    continue
                duration_seconds = (
                    min(dose_value, remaining_runtime)
                    if request.target_type == "duration" and remaining_runtime is not None
                    else dose_value
                    if request.target_type == "duration"
                    else None
                )
                amount_liters = dose_value if request.target_type == "volume" else None
                operation_deadline = datetime.fromisoformat(
                    request.operation_deadline_at or request.expires_at
                )
                if operation_deadline <= datetime.now(UTC):
                    async with self._command_lock:
                        await self._async_expire_requests()
                    continue
                prepare_seconds = max(
                    0.0,
                    (operation_deadline - datetime.now(UTC)).total_seconds(),
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
                            run_identity = self._active_run_identity()
                except TimeoutError:
                    async with self._command_lock:
                        active = self._stored_state.active_execution
                        if active is not None and active.request_id == request.request_id:
                            await self._async_recover_interrupted_execution(could_have_flowed=False)
                        await self._async_expire_requests()
                    continue
                expiry_seconds = max(
                    0.0,
                    (operation_deadline - datetime.now(UTC)).total_seconds(),
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
                if run_identity is not None:
                    result = self._consume_external_violation(run_identity, result)
                async with self._command_lock:
                    await self._async_finish_dose(
                        request.request_id,
                        result,
                        expired=expired_during_dose,
                    )
            except _StaleRequestClaimError:
                pass
            except _DurableTransitionError:
                pass
            except asyncio.CancelledError:
                return
            except Exception as err:  # noqa: BLE001
                if request is not None:
                    async with self._command_lock:
                        await self._async_fail_request(request.request_id, err)
            finally:
                if run_identity is not None:
                    self._clear_external_violation(run_identity)
                self._watering = False
                if self._active_task is not None and self._active_task.done():
                    self._active_task = None
                self._clear_active_target()
                self._publish(status=self._coordinator.data.status, active_zone_id=None)
                if not self._shutting_down:
                    await self._async_consider_current_flow()

    async def _async_apply_dispatch_budget(
        self, request: ManualIrrigationRequest
    ) -> ManualIrrigationRequest | None:
        """Revalidate an automatic target atomically immediately before its claim."""
        subentry = self._zone_configs_by_subentry_id.get(request.zone_subentry_id)
        if subentry is None:
            return request
        remaining_liters = self._automatic_budget_remaining_liters(
            zone_id=request.zone_id,
            data=subentry.data,
            now=dt_util.now(),
        )
        if remaining_liters is None:
            return request
        minimum_liters = self._number(subentry.data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1)
        if remaining_liters < minimum_liters:
            cancelled = replace(
                request,
                status="cancelled",
                revision=request.revision + 1,
            )
            self._stored_state = replace(
                self._stored_state,
                manual_requests=self._with_request(cancelled),
            )
            await self._store.async_save(self._stored_state)
            self._events.fire(
                "automatic_irrigation_deferred",
                reason="budget_exhausted",
                target=self._events.zone_target(request.zone_id),
                measurements={"budget_remaining_liters": remaining_liters},
                context={"request_id": request.request_id},
            )
            self._planning_event.set()
            return None
        allowed_value = (
            remaining_liters
            if request.target_type == "volume"
            else remaining_liters * 60 / request.estimated_flow_l_min
            if request.estimated_flow_l_min
            else request.remaining_value
        )
        if allowed_value >= request.remaining_value:
            return request
        limited = replace(
            request,
            remaining_value=allowed_value,
            revision=request.revision + 1,
        )
        self._stored_state = replace(
            self._stored_state,
            manual_requests=self._with_request(limited),
        )
        await self._store.async_save(self._stored_state)
        return limited

    async def _async_finish_dose(
        self,
        request_id: str,
        result: ExecutionResult,
        *,
        expired: bool = False,
    ) -> None:
        """Account dose progress and persist completion, pause, cancellation, or soak."""
        request = self._request(request_id)
        if request is None or request.execution_id is None or request.status != "executing":
            return
        execution = self._execution(request.execution_id)
        if execution is None:
            return
        delivered_target = (
            result.delivered_liters if request.target_type == "volume" else result.duration_seconds
        )
        remaining = max(0.0, request.remaining_value - delivered_target)
        prior_execution_liters = execution.delivered_liters
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
        deficits, last_effective = self._balance_after_delivery(
            zone_id=request.zone_id,
            delivered_liters=result.delivered_liters,
            effective_delivery=self._crosses_effective_threshold(
                previous_liters=prior_execution_liters,
                delivered_liters=result.delivered_liters,
                minimum_effective_liters=execution.balance_minimum_effective_liters,
            ),
            delivered_at=now,
            area_m2=execution.balance_area_m2,
            application_efficiency=execution.balance_application_efficiency,
            maximum_deficit_mm=execution.balance_maximum_deficit_mm,
        )
        uncredited_deliveries = self._stored_state.uncredited_balance_deliveries
        if result.delivered_liters > 0 and any(
            value is None
            for value in (
                execution.balance_area_m2,
                execution.balance_application_efficiency,
                execution.balance_maximum_deficit_mm,
                execution.balance_minimum_effective_liters,
            )
        ):
            uncredited_deliveries = (
                *uncredited_deliveries,
                self._uncredited_balance_delivery(
                    zone_id=request.zone_id,
                    delivered_liters=result.delivered_liters,
                    delivered_at=now,
                    request_id=request.request_id,
                    execution_id=execution.execution_id,
                ),
            )
        terminal = False
        cancel_requested = request_id in self._cancel_requested
        pause_requested = request_id in self._pause_requested
        skip_opportunity = self._skip_requested.get(request_id)
        if cancel_requested:
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
        elif expired or self._request_deadline(request) <= now:
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
        elif pause_requested:
            request = replace(
                request,
                remaining_value=remaining,
                status="paused",
                pause_until=self._pause_deadline(request, now).isoformat(),
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
        suppressions = self._stored_state.suppressed_automatic_opportunities
        if skip_opportunity is not None and skip_opportunity not in suppressions:
            suppressions = (*suppressions, skip_opportunity)
        dose_record = {
            "dose_number": execution.dose_number,
            "ended_at": now.isoformat(),
            "delivered_liters": result.delivered_liters,
            "duration_seconds": result.duration_seconds,
            "measurement_quality": result.measurement_quality,
            "measurement_origin": self._measurement_origin(result.measurement_quality),
            "warning": result.safety_violation,
        }
        execution = replace(
            execution,
            measurement_quality=result.measurement_quality,
            measurement_origin=self._measurement_origin(result.measurement_quality),
            warnings=(
                (*execution.warnings, result.safety_violation)
                if result.safety_violation is not None
                else execution.warnings
            ),
            doses=(*execution.doses, dose_record),
        )
        next_state = replace(
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
            zone_deficit_mm=deficits,
            zone_last_effective_irrigation=last_effective,
            uncredited_balance_deliveries=uncredited_deliveries,
            budget_usage_liters=self._budget_usage_after_delivery(
                self._stored_state.budget_usage_liters,
                zone_id=request.zone_id,
                delivered_liters=result.delivered_liters,
                delivered_at=now,
            ),
            suppressed_automatic_opportunities=suppressions,
        )
        next_state = self._with_consumption_record(
            self._with_meter_continuity(next_state),
            amount_liters=result.delivered_liters,
            zone_id=request.zone_id,
            source=request.source,
            quality=result.measurement_quality,
            request_id=request.request_id,
            execution_id=execution.execution_id,
            dose_number=execution.dose_number,
            warnings=(() if result.safety_violation is None else (result.safety_violation,)),
        )
        try:
            await self._store.async_save(next_state)
        except Exception as err:
            raise _DurableTransitionError(
                "The stopped irrigation state could not be persisted"
            ) from err
        self._stored_state = next_state
        if cancel_requested:
            self._cancel_requested.discard(request_id)
        if pause_requested:
            self._pause_requested.discard(request_id)
        self._skip_requested.pop(request_id, None)
        self._events.fire(
            "dose_ended",
            reason=_event_result_reason(execution.result, execution.status),
            target=self._events.zone_target(request.zone_id),
            measurements={
                "delivered_liters": result.delivered_liters,
                "duration_seconds": result.duration_seconds,
                "remaining_value": remaining,
            },
            quality=result.measurement_quality,
            context={
                "request_id": request.request_id,
                "execution_id": execution.execution_id,
                "dose_number": execution.dose_number,
                "status": execution.status,
            },
        )
        if request.status in {"cancelled", "expired"}:
            self._events.fire(
                "request_cancelled" if request.status == "cancelled" else "request_expired",
                reason=(
                    "execution_cancelled" if request.status == "cancelled" else "expiry_reached"
                ),
                target=self._events.zone_target(request.zone_id),
                context={
                    "request_id": request.request_id,
                    "execution_id": execution.execution_id,
                    "source": request.source,
                },
            )
        elif request.status == "paused":
            self._events.fire(
                "request_changed",
                reason="user_pause",
                target=self._events.zone_target(request.zone_id),
                measurements={"remaining_value": request.remaining_value},
                context={
                    "request_id": request.request_id,
                    "execution_id": execution.execution_id,
                    "status": request.status,
                    "revision": request.revision,
                },
            )
        if terminal:
            self._events.fire(
                "execution_ended",
                reason=_event_result_reason(execution.result, execution.status),
                target=self._events.zone_target(request.zone_id),
                measurements={
                    "delivered_liters": execution.delivered_liters,
                    "duration_seconds": execution.delivered_duration_seconds,
                },
                quality=result.measurement_quality,
                context={
                    "request_id": request.request_id,
                    "execution_id": execution.execution_id,
                    "status": execution.status,
                },
            )
        if result.safety_violation is not None and result.safety_scope is not None:
            reason = (
                "flow_above_maximum"
                if "exceeds maximum" in result.safety_violation
                else "flow_below_minimum"
                if "below minimum" in result.safety_violation
                else "execution_safety_violation"
            )
            target = (
                self._events.installation_target()
                if result.safety_scope == "installation"
                else self._events.zone_target(request.zone_id)
            )
            self._events.fire(
                "safety_lock_activated",
                reason=reason,
                target=target,
                measurements={"delivered_liters": result.delivered_liters},
                quality=result.measurement_quality,
                context={
                    "request_id": request.request_id,
                    "execution_id": execution.execution_id,
                    "safety_scope": result.safety_scope,
                    "lock_active": True,
                },
            )
            if "Flow " in result.safety_violation:
                self._events.fire(
                    "flow_deviation",
                    reason=reason,
                    target=target,
                    measurements={"delivered_liters": result.delivered_liters},
                    quality=result.measurement_quality,
                    context={
                        "request_id": request.request_id,
                        "execution_id": execution.execution_id,
                        "safety_scope": result.safety_scope,
                    },
                )
            if result.safety_scope == "installation":
                await self._events.async_critical(
                    "installation_safety_lock",
                    title="Irrigation installation locked",
                    message=(
                        f"{self._events.installation_name} stopped because of a critical "
                        "flow or valve safety deviation. Inspect the installation before "
                        "resetting the lock."
                    ),
                )
            if "Could not close" in result.safety_violation:
                await self._events.async_critical(
                    "valve_closure_failed",
                    title="Irrigation valve closure failed",
                    message=(
                        f"{self._events.installation_name} could not confirm a valve closure. "
                        "Isolate the water supply and inspect the affected irrigation zone."
                    ),
                )
        if terminal:
            self._signal_terminal(request_id)
        self._queue_event.set()
        self._planning_event.set()

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

    async def _async_expire_requests(self, *, now: datetime | None = None) -> None:
        """Expire durable orders that have not completed before their deadline."""
        now = now or datetime.now(UTC)
        changed = False
        expired_request_ids: list[str] = []
        requests: list[ManualIrrigationRequest] = []
        executions = self._stored_state.irrigation_executions
        for request in self._stored_state.manual_requests:
            request_deadline = self._request_deadline(request)
            pause_timed_out = (
                request.status == "paused"
                and request.pause_until is not None
                and datetime.fromisoformat(request.pause_until) <= now
            )
            if request.status in {"pending", "executing", "soaking", "paused"} and (
                request_deadline <= now or pause_timed_out
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
                            result="pause_timeout" if pause_timed_out else "expired",
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
                expired_request = self._request(request_id)
                if expired_request is not None:
                    self._events.fire(
                        "request_expired",
                        reason="expiry_reached",
                        target=self._events.zone_target(expired_request.zone_id),
                        context={"request_id": request_id, "source": expired_request.source},
                    )
            self._refresh_complete_idle_event()
            self._planning_event.set()

    def _seconds_until_next_request_change(self) -> float | None:
        """Return the bounded delay until a soak or expiry needs reevaluation."""
        now = datetime.now(UTC)
        moments = [
            datetime.fromisoformat(value)
            for request in self._stored_state.manual_requests
            if request.status in {"pending", "executing", "soaking", "paused"}
            for value in (
                (request.operation_deadline_at or request.expires_at),
                request.soak_until,
                request.pause_until,
            )
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

    def calendar_events(self, *, start: datetime, end: datetime) -> list[dict[str, object]]:
        """Return read-only scheduled order ranges with stable request UIDs."""
        candidates = [
            request
            for request in self._stored_state.manual_requests
            if request.status in {"pending", "executing", "soaking", "paused"}
            and (
                request.source == "automatic"
                or (
                    request.source == "manual"
                    and request.requested_start_at is not None
                    and datetime.fromisoformat(request.requested_start_at)
                    > datetime.fromisoformat(request.created_at)
                )
            )
        ]
        candidates.sort(
            key=lambda request: (
                datetime.fromisoformat(request.requested_start_at or request.created_at),
                0 if request.source == "manual" else 1,
                request.sequence,
                request.request_id,
            )
        )
        cursor: datetime | None = None
        events: list[dict[str, object]] = []
        for request in candidates:
            desired = datetime.fromisoformat(request.requested_start_at or request.created_at)
            event_start = max(desired, cursor) if cursor is not None else desired
            duration = self._request_expected_duration(request)
            event_end = min(
                event_start + duration,
                datetime.fromisoformat(request.expires_at),
            )
            if event_end <= event_start:
                event_end = event_start + timedelta(seconds=1)
            cursor = event_end
            if event_start < end and event_end > start:
                events.append(
                    {
                        "uid": request.request_id,
                        "start": event_start,
                        "end": event_end,
                        "summary": request.zone_name,
                        "description": (
                            f"{request.source}; {request.target_value:g} {request.target_type}; "
                            f"request {request.request_id}"
                        ),
                    }
                )
        return events

    def _request_expected_duration(self, request: ManualIrrigationRequest) -> timedelta:
        """Estimate the complete event range, including planned soak pauses."""
        watering_seconds = (
            request.target_value
            if request.target_type == "duration"
            else request.target_value * 60 / request.estimated_flow_l_min
            if request.estimated_flow_l_min
            else request.delivery_runtime_limit_seconds or 1
        )
        dose_count = (
            max(1, math.ceil(request.target_value / request.max_dose_value))
            if request.max_dose_value is not None and request.max_dose_value > 0
            else 1
        )
        return timedelta(
            seconds=max(1.0, watering_seconds + (dose_count - 1) * request.soak_duration_seconds)
        )

    def list_uncredited_balance_deliveries(self) -> list[dict[str, object]]:
        """Return deliveries requiring explicit water-balance reconciliation."""
        return [delivery.as_dict() for delivery in self._stored_state.uncredited_balance_deliveries]

    def list_profiles(self) -> dict[str, object]:
        """Return immutable built-ins and detached user-owned profiles."""
        custom = validate_custom_profiles(self._entry.data.get(CONF_CUSTOM_PROFILES, {}))
        return {
            "built_in": builtin_profiles(),
            "custom": list(custom.values()),
            "config_hash": self._profile_config_hash(self._entry.data),
        }

    def preview_profile_impact(self, profile_id: str) -> dict[str, object]:
        """Preview every zone that would be affected by changing one custom profile."""
        custom = validate_custom_profiles(self._entry.data.get(CONF_CUSTOM_PROFILES, {}))
        known = {profile["id"] for profile in builtin_profiles()} | set(custom)
        if profile_id not in known:
            raise HomeAssistantError("The irrigation profile does not exist")
        impacted = profile_impacted_zones(
            [
                (subentry.unique_id or subentry.subentry_id, subentry.title, subentry.data)
                for subentry in self._zone_configs
            ],
            dependent_profile_ids(custom, profile_id),
        )
        return {
            "profile_id": profile_id,
            "impacted_zones": impacted,
            "count": len(impacted),
            "config_hash": self._profile_config_hash(self._entry.data),
        }

    async def async_copy_profile(
        self,
        *,
        source_id: str,
        new_id: str,
        name: str,
        expected_config_hash: str | None = None,
    ) -> dict[str, object]:
        """Persist an editable user copy while refusing built-in mutation."""
        async with self._command_lock:
            fresh_data = dict(self._entry.data)
            current_hash = self._profile_config_hash(fresh_data)
            if expected_config_hash is not None and expected_config_hash != current_hash:
                raise HomeAssistantError("Irrigation profiles changed; refresh them before copying")
            try:
                custom = copy_profile(
                    fresh_data.get(CONF_CUSTOM_PROFILES, {}),
                    source_id=source_id,
                    new_id=new_id,
                    name=name,
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
            self._hass.config_entries.async_update_entry(
                self._entry,
                data={**fresh_data, CONF_CUSTOM_PROFILES: custom},
            )
            return {
                "profile": custom[new_id],
                "impacted_zones": [],
                "config_hash": self._profile_config_hash(self._entry.data),
            }

    async def async_update_installation_config(
        self, data: Mapping[str, Any], *, expected_config_hash: str
    ) -> None:
        """Apply an Options Flow edit only if its complete entry snapshot is still current."""
        async with self._command_lock:
            if expected_config_hash != self.installation_config_hash(self._entry.data):
                raise HomeAssistantError(
                    "Irrigation installation configuration changed; reopen the options flow"
                )
            self._hass.config_entries.async_update_entry(
                self._entry,
                title=str(data["name"]),
                data=dict(data),
            )

    @staticmethod
    def installation_config_hash(data: Mapping[str, Any]) -> str:
        """Hash a complete persisted installation config for optimistic locking."""
        return sha256(
            json.dumps(dict(data), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _meter_resolution_liters(self) -> float | None:
        """Return the explicitly configured smallest observable volume step."""
        return self._optional_float(
            self._installation_data, CONF_METER_RESOLUTION_LITERS
        ) or self._optional_float(self._installation_data, CONF_LITERS_PER_COUNT)

    def _round_meter_target(self, amount_liters: float) -> tuple[float, dict[str, object]]:
        """Align a volume target and return immutable rounding provenance."""
        resolution = self._meter_resolution_liters()
        if resolution is None:
            return amount_liters, {
                "requested_liters": amount_liters,
                "target_liters": amount_liters,
                "direction": "exact",
                "resolution_liters": None,
                "expected_error_liters": 0.0,
            }
        rounded = round_target_to_resolution(amount_liters, resolution)
        return rounded.target_liters, {
            "requested_liters": rounded.requested_liters,
            "target_liters": rounded.target_liters,
            "direction": rounded.direction,
            "resolution_liters": rounded.resolution_liters,
            "expected_error_liters": rounded.error_liters,
            "coarse_resolution": resolution > amount_liters * 0.1,
        }

    def _with_meter_continuity(self, state: StoredInstallationState) -> StoredInstallationState:
        """Copy the adapter's accepted continuity state into durable storage."""
        continuity = self._meter.continuity
        if continuity is None:
            return state
        return replace(
            state,
            meter_accumulated_liters=continuity.accumulated_liters,
            meter_last_raw_liters=continuity.last_raw_liters,
            meter_correction_liters=continuity.correction_liters,
            meter_reset_count=continuity.reset_count,
        )

    async def _async_reconcile_meter_source(self) -> None:
        """Rebase changed meter identity/conversion without booking a consumption delta."""
        source = self._installation_data.get(CONF_WATER_METER) or self._installation_data.get(
            CONF_RAW_METER
        )
        source_id = source if isinstance(source, str) else None
        factor = (
            self._optional_float(self._installation_data, CONF_LITERS_PER_COUNT)
            if self._installation_data.get(CONF_RAW_METER)
            else None
        )
        if source_id is None:
            if (
                self._stored_state.meter_source_entity_id is not None
                or self._stored_state.meter_source_liters_per_count is not None
            ):
                self._stored_state = replace(
                    self._stored_state,
                    meter_source_entity_id=None,
                    meter_source_liters_per_count=None,
                    idle_meter_raw_baseline_liters=None,
                )
                await self._store.async_save(self._stored_state)
            return
        if (
            source_id == self._stored_state.meter_source_entity_id
            and factor == self._stored_state.meter_source_liters_per_count
        ):
            return
        continuity = await self._meter.rebase_source()
        self._stored_state = replace(
            self._with_meter_continuity(self._stored_state),
            meter_source_entity_id=source_id,
            meter_source_liters_per_count=factor,
            idle_meter_raw_baseline_liters=continuity.last_raw_liters,
        )
        await self._store.async_save(self._stored_state)

    @staticmethod
    def _measurement_origin(quality: str) -> str:
        """Map public quality to a stable non-misleading source label."""
        return {
            "measured": "cumulative_meter",
            "integrated": "flow_sensor",
            "estimated": "flow_profile",
        }.get(quality, "unknown")

    @staticmethod
    def _with_consumption_record(
        state: StoredInstallationState,
        *,
        amount_liters: float,
        zone_id: str | None,
        source: str,
        quality: str,
        request_id: str | None = None,
        execution_id: str | None = None,
        dose_number: int | None = None,
        warnings: tuple[str, ...] = (),
    ) -> StoredInstallationState:
        """Append one bounded immutable contribution without creating another total."""
        if amount_liters <= 0:
            return state
        now = datetime.now(UTC)
        record = WaterConsumptionRecord(
            recorded_at=now.isoformat(),
            amount_liters=amount_liters,
            zone_id=zone_id,
            source=source,
            quality=quality,
            request_id=request_id,
            execution_id=execution_id,
            dose_number=dose_number,
            warnings=warnings,
        )
        horizon = now.replace(
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) - timedelta(days=WATER_HISTORY_SAFETY_MARGIN_DAYS)
        retained = tuple(
            item
            for item in (*state.water_consumption_history, record)
            if datetime.fromisoformat(item.recorded_at) >= horizon
        )
        cap_reached = len(retained) > WATER_HISTORY_MAX_RECORDS
        if cap_reached:
            retained = retained[-WATER_HISTORY_MAX_RECORDS:]
        return replace(
            state,
            water_consumption_history=retained,
            water_history_incomplete=state.water_history_incomplete or cap_reached,
        )

    def _water_period_totals(self, now: datetime) -> dict[str, float]:
        """Derive local calendar periods from persisted accounting history."""
        local_now = dt_util.as_local(now)
        day = local_now.date()
        week_start = day - timedelta(days=day.weekday())
        totals = {"today": 0.0, "week": 0.0, "month": 0.0, "year": 0.0}
        for record in self._stored_state.water_consumption_history:
            recorded = dt_util.as_local(datetime.fromisoformat(record.recorded_at))
            recorded_day = recorded.date()
            if recorded_day == day:
                totals["today"] += record.amount_liters
            if week_start <= recorded_day <= day:
                totals["week"] += record.amount_liters
            if recorded_day.year == day.year and recorded_day.month == day.month:
                totals["month"] += record.amount_liters
            if recorded_day.year == day.year:
                totals["year"] += record.amount_liters
        return totals

    async def async_correct_physical_meter(
        self, *, physical_total_liters: float
    ) -> dict[str, object]:
        """Persist an explicit future-facing physical meter display correction."""
        async with self._command_lock:
            await self._async_reconcile_meter_source()
            await self._meter.read_liters()
            continuity = self._meter.correct(physical_total_liters=physical_total_liters)
            next_state = self._with_meter_continuity(self._stored_state)
            await self._store.async_save(next_state)
            self._stored_state = next_state
            self._publish(status=self._coordinator.data.status, active_zone_id=None)
            self._events.fire(
                "meter_correction",
                reason="physical_reading_set",
                target=self._events.installation_target(),
                measurements={"physical_total_liters": physical_total_liters},
                quality="measured",
                context={"correction_liters": continuity.correction_liters},
            )
            return {
                "physical_total_liters": continuity.total_liters,
                "correction_liters": continuity.correction_liters,
            }

    @staticmethod
    def _profile_config_hash(data: Mapping[str, Any]) -> str:
        """Hash only user-owned profiles for profile-service optimistic locking."""
        return sha256(
            json.dumps(
                validate_custom_profiles(data.get(CONF_CUSTOM_PROFILES, {})),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def export_portable_config(self) -> dict[str, object]:
        """Return versioned portable config using only declared non-secret fields."""
        installation_keys = {
            CONF_MAIN_VALVE,
            CONF_WATER_METER,
            CONF_RAW_METER,
            CONF_LITERS_PER_COUNT,
            CONF_METER_RESOLUTION_LITERS,
            CONF_METER_MAX_AGE_SECONDS,
            CONF_FLOW_SENSOR,
            CONF_FLOW_MAX_AGE_SECONDS,
            CONF_LEAK_MONITORING,
            CONF_LEAK_FLOW_THRESHOLD,
            CONF_LEAK_DURATION_SECONDS,
            CONF_FROST_ENTITY,
            CONF_FROST_THRESHOLD,
            CONF_RAIN_STOP_ENTITY,
            CONF_RAIN_STOP_THRESHOLD,
            CONF_WEATHER_MAX_AGE_SECONDS,
            CONF_WEATHER_FAILURE_POLICY,
            CONF_INSTALLATION_MAX_DELIVERY_RUNTIME,
            CONF_INSTALLATION_MAX_OPERATION_LIFETIME,
            CONF_INSTALLATION_DAILY_BUDGET_LITERS,
            CONF_INSTALLATION_WEEKLY_BUDGET_LITERS,
            CONF_PAUSE_TIMEOUT_SECONDS,
            CONF_ACTUATOR_TRANSITION_GRACE_SECONDS,
            CONF_MAINTENANCE_MAX_DURATION,
            CONF_MAINTENANCE_CONFIRMATION_INTERVAL,
            CONF_CALIBRATION_SETTLE_SECONDS,
            CONF_CUSTOM_PROFILES,
            CONF_WEATHER_ENTITY,
            "name",
            "notify_entities",
        }
        zone_keys = {
            "name",
            CONF_ZONE_VALVE,
            "default_duration",
            CONF_MIN_FLOW,
            CONF_MAX_FLOW,
            CONF_FLOW_GRACE_SECONDS,
            CONF_METER_FAILURE_STRATEGY,
            CONF_MAX_DOSE_AMOUNT,
            CONF_MAX_DOSE_DURATION,
            CONF_SOAK_DURATION,
            CONF_AUTOMATION_ENABLED,
            CONF_WATERING_MODE,
            CONF_AREA_M2,
            CONF_APPLICATION_EFFICIENCY,
            CONF_CROP_FACTOR,
            CONF_RAIN_FACTOR,
            CONF_MAXIMUM_DEFICIT_MM,
            CONF_MINIMUM_INTERVAL_DAYS,
            CONF_MAXIMUM_INTERVAL_DAYS,
            CONF_MINIMUM_TRIGGER_LITERS,
            CONF_MANDATORY_AMOUNT_LITERS,
            CONF_MINIMUM_EFFECTIVE_LITERS,
            CONF_MAXIMUM_TARGET_LITERS,
            CONF_AUTOMATIC_MAX_DURATION,
            CONF_MAX_DELIVERY_RUNTIME,
            CONF_MAX_OPERATION_LIFETIME,
            CONF_ZONE_PRIORITY,
            CONF_WATERING_WINDOWS,
            CONF_ZONE_DAILY_BUDGET_LITERS,
            CONF_ZONE_WEEKLY_BUDGET_LITERS,
            CONF_AGRONOMIC_VALUES_CONFIRMED,
            CONF_PLANT_PROFILE,
            CONF_SOIL_PROFILE,
            CONF_EXPOSURE_PROFILE,
            CONF_IRRIGATION_PROFILE,
            CONF_SUBAREAS,
            CONF_PROFILE_OVERRIDES,
            CONF_SOIL_MOISTURE_SENSORS,
            CONF_SOIL_MOISTURE_ROLE,
            CONF_SOIL_MOISTURE_AGGREGATION,
            CONF_SOIL_MOISTURE_MAX_AGE_SECONDS,
            CONF_SOIL_MOISTURE_WET_THRESHOLD,
            CONF_SOIL_MOISTURE_CORRECTION_LIMIT_MM,
            CONF_HARDWARE_BATTERY_SENSOR,
            CONF_HARDWARE_BATTERY_MINIMUM,
            CONF_HARDWARE_CONNECTIVITY_SENSOR,
            CONF_HARDWARE_FAULT_SENSOR,
            CONF_HARDWARE_HEALTH_MAX_AGE_SECONDS,
        }
        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "integration": "irrigation_manager",
            "installation": {
                "id": self._entry.unique_id or self._entry.entry_id,
                "config": {
                    key: value
                    for key, value in self._entry.data.items()
                    if key in installation_keys
                },
            },
            "zones": [
                {
                    "id": subentry.unique_id or subentry.subentry_id,
                    "config": {
                        key: value for key, value in subentry.data.items() if key in zone_keys
                    },
                }
                for subentry in self._entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
            ],
        }

    async def async_import_portable_config(
        self,
        *,
        payload: Mapping[str, object],
        entity_remapping: Mapping[str, str],
        zone_remapping: Mapping[str, str],
        dry_run: bool,
        confirm_overwrite: bool,
        expected_config_hash: str | None,
        user: User | None = None,
    ) -> dict[str, object]:
        """Preview or explicitly apply one portable configuration to this entry."""
        if payload.get("integration") != "irrigation_manager":
            raise HomeAssistantError("The import is not an Irrigation Manager export")
        if payload.get("schema_version") != EXPORT_SCHEMA_VERSION:
            raise HomeAssistantError("Unsupported Irrigation Manager import schema version")
        if not all(
            isinstance(source, str) and isinstance(target, str)
            for source, target in (*entity_remapping.items(), *zone_remapping.items())
        ):
            raise HomeAssistantError("Import mappings must contain only string IDs")
        if len(zone_remapping.values()) != len(set(zone_remapping.values())):
            raise HomeAssistantError("Imported zones cannot map to the same target zone")
        installation = payload.get("installation")
        zones = payload.get("zones")
        if not isinstance(installation, Mapping) or not isinstance(zones, list):
            raise HomeAssistantError("The portable configuration is malformed")
        raw_installation = installation.get("config")
        if not isinstance(raw_installation, Mapping):
            raise HomeAssistantError("The portable installation configuration is malformed")
        imported_installation = self._remap_import_entities(
            dict(raw_installation), entity_remapping
        )
        if not isinstance(imported_installation.get("name"), str):
            raise HomeAssistantError("The imported installation requires a name")
        if imported_installation.get(CONF_WATER_METER) and imported_installation.get(
            CONF_RAW_METER
        ):
            raise HomeAssistantError("The import contains multiple water meter sources")
        if bool(imported_installation.get(CONF_RAW_METER)) != bool(
            imported_installation.get(CONF_LITERS_PER_COUNT)
        ):
            raise HomeAssistantError("A raw meter requires an explicit liters-per-count factor")
        try:
            validate_custom_profiles(imported_installation.get(CONF_CUSTOM_PROFILES, {}))
        except (TypeError, ValueError) as err:
            raise HomeAssistantError("The imported profiles are invalid") from err
        zone_changes: list[dict[str, object]] = []
        imported_zone_data: list[tuple[_ZoneConfigSnapshot, dict[str, object]]] = []
        imported_valves: set[str] = set()
        imported_zone_ids: set[str] = set()
        for raw_zone in zones:
            if not isinstance(raw_zone, Mapping) or not isinstance(raw_zone.get("id"), str):
                raise HomeAssistantError("An imported irrigation zone is malformed")
            imported_id = cast(str, raw_zone["id"])
            if imported_id in imported_zone_ids:
                raise HomeAssistantError("The import contains a duplicate source zone ID")
            imported_zone_ids.add(imported_id)
            target_subentry_id = zone_remapping.get(imported_id)
            target = self._zone_configs_by_subentry_id.get(target_subentry_id or "")
            raw_config = raw_zone.get("config")
            if target is None or not isinstance(raw_config, Mapping):
                zone_changes.append({"imported_id": imported_id, "status": "mapping_required"})
                continue
            remapped = self._remap_import_entities(dict(raw_config), entity_remapping)
            name = remapped.get("name")
            valve = remapped.get(CONF_ZONE_VALVE)
            windows = remapped.get(CONF_WATERING_WINDOWS, ["04:00-06:00"])
            if not isinstance(name, str) or not isinstance(valve, str):
                raise HomeAssistantError("An imported irrigation zone requires a name and valve")
            if valve in imported_valves:
                raise HomeAssistantError("Imported irrigation zones cannot share a valve")
            imported_valves.add(valve)
            if not isinstance(windows, list) or not windows:
                raise HomeAssistantError("An imported irrigation zone requires watering windows")
            try:
                for window in windows:
                    parse_window_rule(str(window))
                resolve_effective_zone_profile(
                    remapped,
                    imported_installation.get(CONF_CUSTOM_PROFILES, {}),
                    dt_util.now().date(),
                )
            except (TypeError, ValueError) as err:
                raise HomeAssistantError("An imported irrigation zone is invalid") from err
            imported_zone_data.append((target, remapped))
            zone_changes.append(
                {
                    "imported_id": imported_id,
                    "target_subentry_id": target.subentry_id,
                    "status": "update",
                }
            )
        entity_issues = self._import_entity_issues(
            imported_installation,
            [data for _, data in imported_zone_data],
            user=user,
        )
        config_hash = self._import_config_hash(
            payload=payload,
            imported_installation=imported_installation,
            imported_zone_data=imported_zone_data,
        )
        preview = {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "dry_run": dry_run,
            "config_hash": config_hash,
            "entity_issues": entity_issues,
            "unresolved_entities": sorted(
                issue["entity_id"] for issue in entity_issues if issue["reason"] == "not_found"
            ),
            "installation_changed": imported_installation != dict(self._entry.data),
            "zones": zone_changes,
            "warnings": [
                "No configuration from other integrations is imported automatically",
                *(
                    ["Every imported zone must be explicitly mapped"]
                    if len(imported_zone_data) != len(zones)
                    else []
                ),
            ],
        }
        if dry_run:
            return preview
        if entity_issues:
            raise HomeAssistantError("The import contains invalid Home Assistant target entities")
        if len(imported_zone_data) != len(zones):
            raise HomeAssistantError("Every imported zone requires an explicit target mapping")
        if not confirm_overwrite:
            raise HomeAssistantError("Import overwrite requires explicit confirmation")
        async with self._command_lock:
            if expected_config_hash != self._import_config_hash(
                payload=payload,
                imported_installation=imported_installation,
                imported_zone_data=imported_zone_data,
            ):
                raise HomeAssistantError("The irrigation configuration changed after preview")
            if not self._is_complete_idle():
                raise HomeAssistantError("Configuration can only be imported at complete idle")
            self._hass.config_entries.async_update_entry(
                self._entry,
                title=cast(str, imported_installation["name"]),
                data=imported_installation,
            )
            for target, data in imported_zone_data:
                subentry = self._entry.subentries[target.subentry_id]
                self._hass.config_entries.async_update_subentry(
                    self._entry,
                    subentry,
                    title=str(data.get("name", subentry.title)),
                    data=data,
                )
        return {**preview, "dry_run": False, "applied": True}

    def _import_config_hash(
        self,
        *,
        payload: Mapping[str, object],
        imported_installation: Mapping[str, object],
        imported_zone_data: list[tuple[_ZoneConfigSnapshot, dict[str, object]]],
    ) -> str:
        """Hash canonical source, resolved import, and every current write target."""
        canonical = {
            "source": payload,
            "resolved": {
                "installation": imported_installation,
                "zones": [
                    {"target_subentry_id": target.subentry_id, "data": data}
                    for target, data in sorted(
                        imported_zone_data, key=lambda item: item[0].subentry_id
                    )
                ],
            },
            "target": {
                "installation": {
                    "title": self._entry.title,
                    "data": dict(self._entry.data),
                },
                "zones": [
                    {
                        "subentry_id": target.subentry_id,
                        "title": self._entry.subentries[target.subentry_id].title,
                        "data": dict(self._entry.subentries[target.subentry_id].data),
                    }
                    for target, _ in sorted(
                        imported_zone_data, key=lambda item: item[0].subentry_id
                    )
                ],
            },
        }
        return sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _import_entity_issues(
        self,
        installation: Mapping[str, object],
        zones: list[Mapping[str, object]],
        *,
        user: User | None,
    ) -> list[dict[str, str]]:
        """Validate only remapped target entities against state, domain, and permissions."""
        expectations: list[tuple[Mapping[str, object], dict[str, set[str]]]] = [
            (
                installation,
                {
                    CONF_MAIN_VALVE: {"switch", "valve"},
                    CONF_WATER_METER: {"sensor"},
                    CONF_RAW_METER: {"sensor"},
                    CONF_FLOW_SENSOR: {"sensor"},
                    CONF_FROST_ENTITY: {"sensor"},
                    CONF_RAIN_STOP_ENTITY: {"sensor"},
                    CONF_WEATHER_ENTITY: {"weather"},
                    CONF_TEMPERATURE_SENSORS: {"sensor"},
                    CONF_HUMIDITY_SENSORS: {"sensor"},
                    CONF_WIND_SPEED_SENSORS: {"sensor"},
                    CONF_SOLAR_RADIATION_SENSORS: {"sensor"},
                    CONF_SUNSHINE_DURATION_SENSORS: {"sensor"},
                    CONF_PRESSURE_SENSORS: {"sensor"},
                    CONF_RAIN_SENSORS: {"sensor"},
                    CONF_ET0_SENSORS: {"sensor"},
                    CONF_NOTIFY_ENTITIES: {"notify"},
                },
            )
        ]
        expectations.extend(
            (
                zone,
                {
                    CONF_ZONE_VALVE: {"switch", "valve"},
                    CONF_SOIL_MOISTURE_SENSORS: {"sensor"},
                    CONF_HARDWARE_BATTERY_SENSOR: {"sensor"},
                    CONF_HARDWARE_CONNECTIVITY_SENSOR: {"sensor", "binary_sensor"},
                    CONF_HARDWARE_FAULT_SENSOR: {"sensor", "binary_sensor"},
                },
            )
            for zone in zones
        )
        issues: list[dict[str, str]] = []
        checked: set[tuple[str, tuple[str, ...]]] = set()
        for config, fields in expectations:
            for key, domains in fields.items():
                raw = config.get(key)
                entity_ids = raw if isinstance(raw, list) else [raw]
                for entity_id in entity_ids:
                    if not isinstance(entity_id, str):
                        continue
                    check_key = (entity_id, tuple(sorted(domains)))
                    if check_key in checked:
                        continue
                    checked.add(check_key)
                    domain = entity_id.partition(".")[0]
                    state = self._hass.states.get(entity_id)
                    reason = (
                        "wrong_domain"
                        if domain not in domains
                        else "not_found"
                        if state is None
                        else "unavailable"
                        if state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}
                        else "unauthorized"
                        if user is not None
                        and not user.permissions.check_entity(entity_id, POLICY_CONTROL)
                        else None
                    )
                    if reason is not None:
                        issues.append({"entity_id": entity_id, "field": key, "reason": reason})
        return issues

    @staticmethod
    def _remap_import_entities(
        data: dict[str, object], entity_remapping: Mapping[str, str]
    ) -> dict[str, object]:
        """Replace only explicitly mapped entity-id string values."""

        def remap(value: object) -> object:
            if isinstance(value, str):
                return entity_remapping.get(value, value)
            if isinstance(value, list):
                return [remap(item) for item in value]
            if isinstance(value, dict):
                return {str(key): remap(item) for key, item in value.items()}
            return value

        return {key: remap(value) for key, value in data.items()}

    @staticmethod
    def _import_entity_ids(installation: Mapping[str, object], zones: list[object]) -> set[str]:
        """Collect declared entity references without inspecting other integrations."""
        entity_keys = {
            CONF_MAIN_VALVE,
            CONF_WATER_METER,
            CONF_RAW_METER,
            CONF_FLOW_SENSOR,
            CONF_FROST_ENTITY,
            CONF_RAIN_STOP_ENTITY,
            CONF_WEATHER_ENTITY,
            CONF_ZONE_VALVE,
            CONF_HARDWARE_BATTERY_SENSOR,
            CONF_HARDWARE_CONNECTIVITY_SENSOR,
            CONF_HARDWARE_FAULT_SENSOR,
        }
        result = {
            value
            for key, value in installation.items()
            if key in entity_keys and isinstance(value, str)
        }
        result.update(IrrigationManager._nested_entity_ids(installation))
        for raw_zone in zones:
            if not isinstance(raw_zone, Mapping):
                continue
            config = raw_zone.get("config")
            if isinstance(config, Mapping):
                result.update(IrrigationManager._nested_entity_ids(config))
                result.update(
                    value
                    for key, value in config.items()
                    if key in entity_keys and isinstance(value, str)
                )
        return result

    @staticmethod
    def _nested_entity_ids(value: object) -> set[str]:
        """Find entity-id shaped strings in portable lists and nested objects."""
        if isinstance(value, str):
            domain, separator, object_id = value.partition(".")
            entity_domains = {
                "binary_sensor",
                "climate",
                "input_boolean",
                "notify",
                "number",
                "sensor",
                "switch",
                "valve",
                "weather",
            }
            return {value} if separator and domain in entity_domains and object_id else set()
        if isinstance(value, Mapping):
            result: set[str] = set()
            for item in value.values():
                result.update(IrrigationManager._nested_entity_ids(item))
            return result
        if isinstance(value, list):
            result = set()
            for item in value:
                result.update(IrrigationManager._nested_entity_ids(item))
            return result
        return set()

    def export_history(self, *, limit: int, export_format: str) -> dict[str, object]:
        """Return bounded joined request, execution, dose, calculation, and source history."""
        requests = {request.request_id: request for request in self._stored_state.manual_requests}
        records: list[dict[str, object]] = []
        for execution in self._stored_state.irrigation_executions[-limit:]:
            request = requests.get(execution.request_id)
            request_data = (
                {
                    key: value
                    for key, value in request.as_dict().items()
                    if key not in {"zone_name", "zone_valve", "main_valve"}
                }
                if request is not None
                else None
            )
            records.append(
                {
                    "request": request_data,
                    "execution": execution.as_dict(),
                    "doses": [dict(dose) for dose in execution.doses],
                    "calculation": dict(execution.resolved_inputs),
                    "source": request.source if request is not None else "unknown",
                    "measurement_origin": execution.measurement_origin,
                    "measurement_quality": execution.measurement_quality,
                    "warnings": list(execution.warnings),
                }
            )
        if export_format == "json":
            return {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "format": "json",
                "count": len(records),
                "history": records,
            }
        output = io.StringIO()
        fields = (
            list(records[0])
            if records
            else [
                "request",
                "execution",
                "doses",
                "calculation",
                "source",
                "measurement_origin",
                "measurement_quality",
                "warnings",
            ]
        )
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {
                key: json.dumps(value, sort_keys=True, separators=(",", ":"))
                if isinstance(value, dict | list)
                else value
                for key, value in record.items()
            }
            for record in records
        )
        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "format": "csv",
            "count": len(records),
            "data": output.getvalue(),
        }

    def diagnostics_state_decisions(self) -> dict[str, object]:
        """Expose safety and planning decisions without entity IDs or location names."""
        now = dt_util.now()
        decisions = self._zone_schedule_decisions(now=now)
        active = self._stored_state.active_execution
        weather = self._weather_safety()
        return {
            "status": self._coordinator.data.status,
            "emergency_stop": self._stored_state.emergency_stop,
            "winter_lock": self._stored_state.winter_lock,
            "maintenance_active": self._stored_state.maintenance_test is not None,
            "calibration_proposal_status": (
                self._stored_state.calibration_proposal.status
                if self._stored_state.calibration_proposal is not None
                else None
            ),
            "installation_safety_lock_active": (
                self._stored_state.installation_safety_lock is not None
            ),
            "weather_safety": {
                "status": weather.status,
                "frost_blocked": weather.frost_blocked,
                "rain_stop_active": weather.rain_stop_active,
                "failure_policy": "fail_safe",
            },
            "weather_model": {
                "configured": self._weather_model_configured,
                "automation_available": self._weather_automation_available,
                "quality": self._weather_model_quality,
                "method": self._weather_model_method,
                "period_id": self._weather_period_id,
                "last_finalized_at": self._weather_last_finalized_at,
                "fallback_since": self._stored_state.weather_failure_since,
                "forecast": (
                    self._rain_forecast.as_dict() if self._rain_forecast is not None else None
                ),
                "forecast_deferrals": {
                    zone_id: {
                        "started_at": started_at,
                        "deadline": self._stored_state.forecast_deferral_deadlines.get(zone_id),
                        "cancelled": zone_id in self._stored_state.cancelled_forecast_deferrals,
                    }
                    for zone_id, started_at in self._stored_state.forecast_deferral_started.items()
                },
                "latest_calculation": self._latest_final_weather_snapshot(),
            },
            "pending_config_reload": self._pending_reload_task is not None,
            "profiles": {
                "built_in_count": len(builtin_profiles()),
                "custom_count": len(
                    validate_custom_profiles(self._installation_data.get(CONF_CUSTOM_PROFILES, {}))
                ),
                "effective_zones": self._zone_effective_profiles,
            },
            "soil_moisture": self._zone_soil_moisture,
            "hardware_health": self._zone_hardware_health,
            "zone_safety_lock_ids": sorted(self._stored_state.zone_safety_locks),
            "active": (
                {
                    "zone_id": active.zone_id,
                    "request_id": active.request_id,
                    "execution_id": active.execution_id,
                    "dose_number": active.dose_number,
                }
                if active is not None
                else None
            ),
            "pending_request_count": sum(
                request.status in {"pending", "executing", "soaking", "paused"}
                for request in self._stored_state.manual_requests
            ),
            "uncredited_balance_count": len(self._stored_state.uncredited_balance_deliveries),
            "metering": {
                "configured": self._has_meter,
                "resolution_liters": self._meter_resolution_liters(),
                "continuity_persisted": self._stored_state.meter_last_raw_liters is not None,
                "reset_count": self._stored_state.meter_reset_count,
                "physical_correction_liters": self._stored_state.meter_correction_liters,
                "unassigned_available_liters": self._stored_state.unassigned_available_liters,
                "history_record_count": len(self._stored_state.water_consumption_history),
            },
            "recent_history": self.export_history(limit=25, export_format="json")["history"],
            "planning": [
                {
                    "zone_id": planning.zone_id,
                    "needed": decision.needed,
                    "reason": decision.reason,
                    "target_liters": decision.target_liters,
                    "blocked": planning.blocked,
                    "enabled": planning.enabled,
                }
                for _, planning, decision in decisions
            ],
        }

    async def async_resolve_balance_reconciliation(
        self, *, reconciliation_id: str, resolution: str
    ) -> dict[str, object]:
        """Explicitly apply current zone settings to, or discard, one missing credit."""
        async with self._command_lock:
            record = next(
                (
                    item
                    for item in self._stored_state.uncredited_balance_deliveries
                    if item.reconciliation_id == reconciliation_id
                ),
                None,
            )
            if record is None:
                raise HomeAssistantError("The balance reconciliation record does not exist")
            if resolution not in {"apply", "discard"}:
                raise HomeAssistantError("Unsupported balance reconciliation resolution")
            deficits = self._stored_state.zone_deficit_mm
            last_effective = self._stored_state.zone_last_effective_irrigation
            if resolution == "apply":
                subentry = next(
                    (
                        item
                        for item in self._zone_configs
                        if (item.unique_id or item.subentry_id) == record.zone_id
                    ),
                    None,
                )
                if subentry is None:
                    raise HomeAssistantError("The reconciliation zone no longer exists")
                profile = self._effective_zone_profile(
                    subentry.data, datetime.fromisoformat(record.delivered_at).date()
                )
                deficits, last_effective = self._balance_after_delivery(
                    zone_id=record.zone_id,
                    delivered_liters=record.delivered_liters,
                    effective_delivery=self._crosses_effective_threshold(
                        previous_liters=0,
                        delivered_liters=record.delivered_liters,
                        minimum_effective_liters=self._number(
                            subentry.data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1
                        ),
                    ),
                    delivered_at=datetime.fromisoformat(record.delivered_at),
                    area_m2=profile.area_m2,
                    application_efficiency=profile.application_efficiency,
                    maximum_deficit_mm=profile.maximum_deficit_mm,
                )
            self._stored_state = replace(
                self._stored_state,
                zone_deficit_mm=deficits,
                zone_last_effective_irrigation=last_effective,
                uncredited_balance_deliveries=tuple(
                    item
                    for item in self._stored_state.uncredited_balance_deliveries
                    if item.reconciliation_id != reconciliation_id
                ),
            )
            await self._store.async_save(self._stored_state)
            self._publish(status=self._coordinator.data.status, active_zone_id=None)
            self._planning_event.set()
            self._events.fire(
                "balance_correction",
                reason=f"reconciliation_{resolution}",
                target=self._events.zone_target(record.zone_id),
                measurements={"delivered_liters": record.delivered_liters},
                quality="reconciled" if resolution == "apply" else "discarded",
                context={
                    "reconciliation_id": reconciliation_id,
                    "request_id": record.request_id,
                    "execution_id": record.execution_id,
                },
            )
            return {
                "reconciliation_id": reconciliation_id,
                "resolution": resolution,
                "zone_id": record.zone_id,
                "zone_deficit_mm": deficits.get(record.zone_id),
            }

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
            request = replace(
                request, status="pending", pause_until=None, revision=request.revision + 1
            )
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
            self._events.fire(
                "request_changed",
                reason="user_resume",
                target=self._events.zone_target(request.zone_id),
                context={
                    "request_id": request.request_id,
                    "status": request.status,
                    "revision": request.revision,
                },
            )

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
                    pause_until=(
                        self._pause_deadline(request, datetime.now(UTC)).isoformat()
                        if action == "pause"
                        else None
                    ),
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
                self._events.fire(
                    "request_changed" if action == "pause" else "request_cancelled",
                    reason="user_pause" if action == "pause" else "user_cancelled",
                    target=self._events.zone_target(request.zone_id),
                    context={
                        "request_id": request.request_id,
                        "status": request.status,
                        "revision": request.revision,
                    },
                )
                if action == "cancel":
                    self._signal_terminal(request_id)
                self._queue_event.set()
        if task is not None:
            result = await asyncio.shield(task)
            async with self._command_lock:
                await self._async_finish_dose(request_id, result)
        self._refresh_complete_idle_event()

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
        return self._replace_request_in(self._stored_state.manual_requests, request)

    def _with_execution(
        self, execution: IrrigationExecutionState
    ) -> tuple[IrrigationExecutionState, ...]:
        return self._replace_execution_in(self._stored_state.irrigation_executions, execution)

    @staticmethod
    def _replace_request_in(
        requests: tuple[ManualIrrigationRequest, ...],
        request: ManualIrrigationRequest,
    ) -> tuple[ManualIrrigationRequest, ...]:
        """Replace one request in an explicitly selected durable collection."""
        return tuple(
            request if item.request_id == request.request_id else item for item in requests
        )

    @staticmethod
    def _replace_execution_in(
        executions: tuple[IrrigationExecutionState, ...],
        execution: IrrigationExecutionState,
    ) -> tuple[IrrigationExecutionState, ...]:
        """Replace one execution in an explicitly selected durable collection."""
        return tuple(
            execution if item.execution_id == execution.execution_id else item
            for item in executions
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
        if self._stored_state.winter_lock:
            raise HomeAssistantError("The winter lock is active")
        if self._stored_state.maintenance_test is not None:
            raise HomeAssistantError("A supervised maintenance test is active")
        if self._stored_state.active_execution is not None:
            raise HomeAssistantError("An interrupted irrigation execution needs recovery")
        if self._active_task is not None and not self._active_task.done():
            raise HomeAssistantError("This irrigation installation is busy")
        subentry = self._zone_configs_by_subentry_id.get(manual_request.zone_subentry_id)
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise HomeAssistantError("The irrigation zone does not exist")
        manual_request = self._with_balance_snapshot(manual_request, subentry.data)
        zone_id = manual_request.zone_id
        await self._async_preflight(
            target_zone_id=zone_id,
            source=manual_request.source,
            ignore_weather=False,
        )
        preflight_moisture = self._soil_moisture_assessment(subentry.data, now=datetime.now(UTC))
        manual_request = replace(
            manual_request,
            resolved_inputs={
                **manual_request.resolved_inputs,
                "preflight": {
                    "soil_moisture": (
                        preflight_moisture.as_dict()
                        if preflight_moisture is not None
                        else {"status": "not_configured"}
                    ),
                    "hardware_health": self._hardware_health(subentry.data, now=datetime.now(UTC)),
                },
            },
        )
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
                await self._async_reconcile_meter_source()
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
        new_execution = execution is None
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
                operation_deadline_at=manual_request.operation_deadline_at,
                delivery_runtime_limit_seconds=(manual_request.delivery_runtime_limit_seconds),
                dose_number=dose_number,
                balance_area_m2=manual_request.balance_area_m2,
                balance_application_efficiency=(manual_request.balance_application_efficiency),
                balance_maximum_deficit_mm=manual_request.balance_maximum_deficit_mm,
                balance_minimum_effective_liters=(manual_request.balance_minimum_effective_liters),
                resolved_inputs=dict(manual_request.resolved_inputs),
            )
            executions = (*self._stored_state.irrigation_executions, execution)
        else:
            execution_id = execution.execution_id
            execution = replace(
                execution,
                status="watering",
                dose_number=dose_number,
                balance_area_m2=(execution.balance_area_m2 or manual_request.balance_area_m2),
                balance_application_efficiency=(
                    execution.balance_application_efficiency
                    or manual_request.balance_application_efficiency
                ),
                balance_maximum_deficit_mm=(
                    execution.balance_maximum_deficit_mm
                    or manual_request.balance_maximum_deficit_mm
                ),
                balance_minimum_effective_liters=(
                    execution.balance_minimum_effective_liters
                    or manual_request.balance_minimum_effective_liters
                ),
                resolved_inputs=execution.resolved_inputs or dict(manual_request.resolved_inputs),
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
                delivery_deadline_at=(
                    datetime.now(UTC) + timedelta(seconds=execution_time_limit)
                ).isoformat(),
                operation_deadline_at=manual_request.operation_deadline_at,
                meter_failure_strategy=meter_failure_strategy,
                fallback_quality=(
                    "integrated"
                    if start_in_estimated_fallback and self._flow is not None
                    else "estimated"
                ),
                request_id=manual_request.request_id,
                execution_id=execution_id,
                dose_number=dose_number,
                dose_target_value=dose_value,
                balance_area_m2=execution.balance_area_m2,
                balance_application_efficiency=execution.balance_application_efficiency,
                balance_maximum_deficit_mm=execution.balance_maximum_deficit_mm,
                balance_minimum_effective_liters=(execution.balance_minimum_effective_liters),
                resolved_inputs=dict(execution.resolved_inputs),
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
        if new_execution:
            self._events.fire(
                "execution_started",
                reason="request_accepted",
                target=self._events.zone_target(zone_id),
                measurements={"target_value": manual_request.target_value},
                quality=self._active_measurement_quality,
                context={
                    "request_id": manual_request.request_id,
                    "execution_id": execution_id,
                    "target_type": manual_request.target_type,
                    "source": manual_request.source,
                },
            )
        self._watering = True
        self._active_external_violation = None
        self._weather_watchdog_event.set()
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
                    observe_flow=self._flow is not None,
                    use_flow_consumption=not self._has_meter and self._flow is not None,
                    flow_freshness_seconds=self._number(
                        self._installation_data, CONF_FLOW_MAX_AGE_SECONDS, 30.0
                    ),
                    on_actuator_command=self._async_expect_actuator_state,
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
        self._events.fire(
            "dose_started",
            reason="zone_open_confirmed",
            target=self._events.zone_target(active.zone_id),
            measurements={"dose_target_value": active.dose_target_value},
            quality=self._active_measurement_quality,
            context={
                "request_id": active.request_id,
                "execution_id": active.execution_id,
                "dose_number": active.dose_number,
            },
        )

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
        if active is not None and quality in {"estimated", "integrated"}:
            delivered = max(0.0, (active.requested_amount_liters or 0.0) - remaining)
            now = datetime.now(UTC).isoformat()
            self._stored_state = replace(
                self._stored_state,
                active_execution=replace(
                    active,
                    fallback_started_at=active.fallback_started_at or now,
                    fallback_checkpoint_at=now,
                    delivered_liters_at_fallback=delivered,
                    fallback_quality=quality,
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
        await self.async_stop_maintenance_test(reason="user_stop", require_active=False)
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

    async def async_stop_and_skip(
        self,
        *,
        request_id: str | None = None,
        execution_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, object]:
        """Stop one execution and suppress its zone's current automatic opportunity."""
        opportunity_id: str | None = None
        planning_now = now or dt_util.now()
        task: asyncio.Task[ExecutionResult] | None = None
        async with self._command_lock:
            if execution_id is not None:
                execution = self._execution(execution_id)
                if execution is None:
                    raise HomeAssistantError("The irrigation execution does not exist")
                request_id = execution.request_id
            if request_id is None:
                raise HomeAssistantError("Stop and skip requires a selected request or execution")
            request = self._request(request_id)
            if request is None:
                raise HomeAssistantError("The irrigation request does not exist")
            if request.status in {"completed", "cancelled", "expired"}:
                raise HomeAssistantError("The irrigation request is already final")
            if request.source == "automatic":
                opportunity_id = request.request_id
            else:
                subentry = self._zone_configs_by_subentry_id.get(request.zone_subentry_id)
                if subentry is not None:
                    raw = subentry.data.get(CONF_WATERING_WINDOWS, ["04:00-06:00"])
                    values = (
                        [str(value) for value in raw]
                        if isinstance(raw, list | tuple)
                        else [str(raw)]
                    )
                    active, _ = active_and_next_window(
                        now=planning_now, values=values, sun_resolver=self._sun_event
                    )
                    if active is not None:
                        opportunity_id = self._automatic_request_id(
                            request.zone_id, active.opportunity_id
                        )
            if request.status == "executing":
                self._cancel_requested.add(request_id)
                if opportunity_id is not None:
                    self._skip_requested[request_id] = opportunity_id
                task = self._active_task
                if task is not None:
                    task.cancel()
            else:
                cancelled = replace(
                    request,
                    status="cancelled",
                    soak_until=None,
                    pause_until=None,
                    revision=request.revision + 1,
                )
                execution = self._execution(request.execution_id)
                suppressions = self._stored_state.suppressed_automatic_opportunities
                if opportunity_id is not None and opportunity_id not in suppressions:
                    suppressions = (*suppressions, opportunity_id)
                next_state = replace(
                    self._stored_state,
                    manual_requests=self._with_request(cancelled),
                    irrigation_executions=(
                        self._with_execution(
                            replace(
                                execution,
                                status="cancelled",
                                ended_at=planning_now.astimezone(UTC).isoformat(),
                                result="cancelled",
                            )
                        )
                        if execution is not None
                        else self._stored_state.irrigation_executions
                    ),
                    suppressed_automatic_opportunities=suppressions,
                )
                try:
                    await self._store.async_save(next_state)
                except Exception as err:
                    raise _DurableTransitionError(
                        "The stop-and-skip state could not be persisted"
                    ) from err
                self._stored_state = next_state
                self._events.fire(
                    "request_cancelled",
                    reason="user_cancelled",
                    target=self._events.zone_target(cancelled.zone_id),
                    context={
                        "request_id": cancelled.request_id,
                        "status": cancelled.status,
                        "revision": cancelled.revision,
                    },
                )
                self._signal_terminal(request_id)
                self._queue_event.set()
        if task is not None:
            result = await asyncio.shield(task)
            async with self._command_lock:
                await self._async_finish_dose(request_id, result)
        self._refresh_complete_idle_event()
        self._planning_event.set()
        return {
            "request_id": request_id,
            "opportunity_id": opportunity_id,
            "suppressed": opportunity_id is not None,
        }

    async def async_set_winter_lock(self) -> None:
        """Persist the winter lock before closing and cancelling every water path."""
        async with self._command_lock:
            self._stored_state = replace(self._stored_state, winter_lock=True)
            await self._store.async_save(self._stored_state)
            self._publish(status="winter_lock", active_zone_id=None)
        closure_errors: list[Exception] = []
        try:
            await self._async_close_entities(
                self._all_known_valves(),
                report_failure=False,
            )
        except Exception as err:  # noqa: BLE001
            closure_errors.append(err)
        try:
            await self.async_stop()
        except Exception as err:  # noqa: BLE001
            closure_errors.append(err)
        try:
            await self._async_close_entities(
                self._all_known_valves(),
                report_failure=False,
            )
        except Exception as err:  # noqa: BLE001
            closure_errors.append(err)
        self._events.fire(
            "winter_lock_activated",
            reason="winter_lock_enforced",
            target=self._events.installation_target(),
            context={"lock_active": True},
        )
        await self._events.async_critical(
            "winter_lock",
            title="Irrigation winter lock active",
            message=(
                f"{self._events.installation_name} is winter-locked. Automatic, manual, "
                "maintenance, and calibration watering are blocked until spring release."
            ),
        )
        if len(closure_errors) == 1:
            raise closure_errors[0]
        if closure_errors:
            raise ExceptionGroup("Winter lock valve closure failed", closure_errors)

    async def async_clear_winter_lock(self) -> None:
        """Release winter protection only after proving a closed, idle installation."""
        async with self._command_lock:
            if not self._stored_state.winter_lock:
                return
            if not self._is_complete_idle() or self._stored_state.maintenance_test is not None:
                raise HomeAssistantError("The irrigation installation is busy")
            await self._async_preflight(
                ignore_winter_lock=True,
                ignore_installation_lock=True,
            )
            self._stored_state = replace(self._stored_state, winter_lock=False)
            await self._store.async_save(self._stored_state)
            self._publish(status="idle", active_zone_id=None)
        self._events.fire(
            "winter_lock_cleared",
            reason="spring_release_confirmed",
            target=self._events.installation_target(),
            context={"lock_active": False},
        )
        self._events.dismiss("winter_lock")
        self._planning_event.set()

    async def async_start_maintenance_test(
        self,
        *,
        zone_subentry_id: str,
        duration_seconds: float,
        bypass_checks: tuple[str, ...] = (),
        kind: str = "maintenance",
    ) -> dict[str, object]:
        """Start exactly one bounded, supervised valve test and return immediately."""
        allowed_bypasses = {"flow"}
        unknown_bypasses = set(bypass_checks) - allowed_bypasses
        if unknown_bypasses:
            raise HomeAssistantError(
                f"Unsupported maintenance bypass checks: {', '.join(sorted(unknown_bypasses))}"
            )
        if kind not in {"maintenance", "calibration"}:
            raise HomeAssistantError("Unsupported supervised test kind")
        if kind == "calibration" and bypass_checks:
            raise HomeAssistantError("Calibration cannot bypass measurement checks")
        async with self._command_lock:
            if not self._is_complete_idle() or self._stored_state.maintenance_test is not None:
                raise HomeAssistantError("The irrigation installation is busy")
            if kind == "calibration" and (not self._has_meter or self._flow is None):
                raise HomeAssistantError(
                    "Calibration requires a cumulative water meter and a flow sensor"
                )
            subentry = self._zone_configs_by_subentry_id.get(zone_subentry_id)
            if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
                raise HomeAssistantError("The irrigation zone does not exist")
            max_duration = self._number(
                self._installation_data, CONF_MAINTENANCE_MAX_DURATION, 300.0
            )
            if duration_seconds <= 0 or duration_seconds > max_duration:
                raise HomeAssistantError(
                    f"The supervised test duration must not exceed {max_duration:g} seconds"
                )
            await self._async_preflight(
                target_zone_id=subentry.unique_id or subentry.subentry_id,
                ignore_weather=False,
            )
            confirmation_interval = self._number(
                self._installation_data, CONF_MAINTENANCE_CONFIRMATION_INTERVAL, 30.0
            )
            now = datetime.now(UTC)
            test = MaintenanceTestState(
                test_id=uuid4().hex,
                kind=kind,
                zone_id=subentry.unique_id or subentry.subentry_id,
                zone_subentry_id=subentry.subentry_id,
                started_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=max_duration)).isoformat(),
                confirmation_deadline=(
                    now + timedelta(seconds=min(max_duration, confirmation_interval))
                ).isoformat(),
                bypass_checks=tuple(sorted(set(bypass_checks))),
            )
            meter_baseline = await self._meter.read_raw_liters() if self._has_meter else None
            profile = self._effective_zone_profile(subentry.data, now.date())
            self._stored_state = replace(
                self._stored_state,
                maintenance_test=test,
                active_execution=ActiveExecutionState(
                    zone_id=test.zone_id,
                    zone_valve=str(subentry.data[CONF_ZONE_VALVE]),
                    main_valve=self._installation_data.get(CONF_MAIN_VALVE),
                    meter_raw_baseline_liters=meter_baseline,
                    prepared_at=now.isoformat(),
                    watering_started_at=None,
                    requested_duration_seconds=duration_seconds,
                    estimated_flow_l_min=self._estimated_flow(subentry.data),
                    balance_area_m2=profile.area_m2,
                    balance_application_efficiency=profile.application_efficiency,
                    balance_maximum_deficit_mm=profile.maximum_deficit_mm,
                    balance_minimum_effective_liters=self._number(
                        subentry.data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1
                    ),
                    resolved_inputs=dict(profile.resolved_inputs),
                ),
            )
            await self._store.async_save(self._stored_state)
            self._cancel_leak_observation()
            self._maintenance_stop_reason = None
            self._maintenance_flow_samples = []
            self._watering = True
            self._active_external_violation = None
            self._weather_watchdog_event.set()
            self._maintenance_task = self._hass.async_create_task(
                self._async_run_maintenance_test(test, subentry, duration_seconds),
                f"Irrigation Manager supervised {kind} test",
            )
            self._maintenance_watchdog_task = self._hass.async_create_task(
                self._async_maintenance_watchdog(test.test_id),
                "Irrigation Manager maintenance dead-man watchdog",
            )
            self._publish(status="maintenance", active_zone_id=test.zone_id)
        self._events.fire(
            "maintenance_started",
            reason=f"{kind}_confirmed",
            target=self._events.zone_target(test.zone_id),
            measurements={"duration_seconds": duration_seconds},
            context={
                "test_id": test.test_id,
                "kind": kind,
                "bypass_checks": list(test.bypass_checks),
            },
        )
        await self._events.async_critical(
            "maintenance_active",
            title="Supervised irrigation test active",
            message=(
                f"{self._events.installation_name} is running one supervised {kind} test. "
                "Keep sending dead-man confirmations; missing confirmation closes all valves."
            ),
        )
        return {"test_id": test.test_id, "expires_at": test.expires_at}

    async def async_confirm_maintenance_test(self, *, test_id: str) -> dict[str, object]:
        """Extend only the dead-man deadline, never the fixed test timeout."""
        async with self._command_lock:
            test = self._stored_state.maintenance_test
            if test is None or test.test_id != test_id:
                raise HomeAssistantError("The supervised maintenance test is not active")
            now = datetime.now(UTC)
            expires_at = datetime.fromisoformat(test.expires_at)
            if now >= expires_at:
                raise HomeAssistantError("The supervised maintenance test has expired")
            interval = self._number(
                self._installation_data, CONF_MAINTENANCE_CONFIRMATION_INTERVAL, 30.0
            )
            deadline = min(expires_at, now + timedelta(seconds=interval))
            test = replace(test, confirmation_deadline=deadline.isoformat())
            self._stored_state = replace(self._stored_state, maintenance_test=test)
            await self._store.async_save(self._stored_state)
            self._publish(status="maintenance", active_zone_id=test.zone_id)
            return {"test_id": test_id, "confirmation_deadline": test.confirmation_deadline}

    async def async_stop_maintenance_test(
        self, *, reason: str = "user_stop", require_active: bool = True
    ) -> None:
        """Stop a supervised test; executor cleanup and an explicit closure both fail closed."""
        task: asyncio.Task[ExecutionResult] | None
        async with self._command_lock:
            test = self._stored_state.maintenance_test
            if test is None:
                if require_active:
                    raise HomeAssistantError("No supervised maintenance test is active")
                return
            self._maintenance_stop_reason = reason
            task = self._maintenance_task
            if task is not None and not task.done():
                task.cancel()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await self._async_close_entities(self._all_known_valves())

    async def _async_maintenance_watchdog(self, test_id: str) -> None:
        """Cancel the test at the first missed confirmation or fixed expiry."""
        try:
            while True:
                test = self._stored_state.maintenance_test
                if test is None or test.test_id != test_id:
                    return
                deadline = min(
                    datetime.fromisoformat(test.expires_at),
                    datetime.fromisoformat(test.confirmation_deadline),
                )
                await asyncio.sleep(max(0.0, (deadline - datetime.now(UTC)).total_seconds()))
                current = self._stored_state.maintenance_test
                if current is None or current.test_id != test_id:
                    return
                now = datetime.now(UTC)
                if now >= datetime.fromisoformat(current.expires_at):
                    await self.async_stop_maintenance_test(reason="hard_timeout")
                    return
                if now >= datetime.fromisoformat(current.confirmation_deadline):
                    await self.async_stop_maintenance_test(reason="deadman_timeout")
                    return
        except asyncio.CancelledError:
            return

    async def _async_run_maintenance_test(
        self,
        test: MaintenanceTestState,
        subentry: _ZoneConfigSnapshot,
        duration_seconds: float,
    ) -> ExecutionResult:
        """Execute and account one supervised test through the normal safe executor."""
        try:
            result = await self._executor.execute(
                ExecutionRequest(
                    zone_id=test.zone_id,
                    zone_valve=str(subentry.data[CONF_ZONE_VALVE]),
                    main_valve=self._installation_data.get(CONF_MAIN_VALVE),
                    duration_seconds=duration_seconds,
                    settle_seconds=(
                        self._number(self._installation_data, CONF_CALIBRATION_SETTLE_SECONDS, 2.0)
                        if test.kind == "calibration"
                        else 0.0
                    ),
                    managed_zone_valves=tuple(self._zone_valves()),
                    monitor_interval_seconds=min(1.0, duration_seconds),
                    minimum_flow_l_min=(
                        None
                        if "flow" in test.bypass_checks
                        else self._optional_float(subentry.data, CONF_MIN_FLOW)
                    ),
                    maximum_flow_l_min=(
                        None
                        if "flow" in test.bypass_checks
                        else self._optional_float(subentry.data, CONF_MAX_FLOW)
                    ),
                    flow_grace_seconds=self._number(subentry.data, CONF_FLOW_GRACE_SECONDS, 5.0),
                    observe_flow=test.kind == "calibration",
                    on_flow_sample=self._async_record_maintenance_flow,
                    on_zone_opening=self._async_mark_zone_opening,
                    on_zone_opened=self._async_mark_zone_opened,
                    on_actuator_command=self._async_expect_actuator_state,
                )
            )
        except asyncio.CancelledError:
            result = ExecutionResult(
                zone_id=test.zone_id,
                delivered_liters=0.0,
                duration_seconds=0.0,
                stopped=True,
                target_reached=False,
                measurement_quality="unknown",
            )
        except Exception as err:  # noqa: BLE001
            result = ExecutionResult(
                zone_id=test.zone_id,
                delivered_liters=0.0,
                duration_seconds=0.0,
                safety_violation=str(err),
                safety_scope="zone",
                target_reached=False,
                measurement_quality="unknown",
            )
        identity = f"maintenance:{test.test_id}"
        result = self._consume_external_violation(identity, result)
        try:
            async with self._command_lock:
                await self._async_finish_maintenance_test(test, subentry, result)
        finally:
            self._clear_external_violation(identity)
            self._weather_watchdog_event.set()
        return result

    async def _async_record_maintenance_flow(self, flow_l_min: float) -> None:
        """Collect bounded calibration samples in memory during the active test only."""
        self._maintenance_flow_samples.append(flow_l_min)

    async def _async_finish_maintenance_test(
        self,
        test: MaintenanceTestState,
        subentry: _ZoneConfigSnapshot,
        result: ExecutionResult,
    ) -> None:
        """Book real water, preserve safety violations, and create a review-only proposal."""
        if self._stored_state.maintenance_test is None:
            return
        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[test.zone_id] = zone_totals.get(test.zone_id, 0.0) + result.delivered_liters
        qualities = dict(self._stored_state.zone_measurement_quality)
        qualities[test.zone_id] = result.measurement_quality
        last_delivered = dict(self._stored_state.zone_last_delivered_liters)
        last_delivered[test.zone_id] = result.delivered_liters
        last_duration = dict(self._stored_state.zone_last_duration_seconds)
        last_duration[test.zone_id] = result.duration_seconds
        zone_locks = dict(self._stored_state.zone_safety_locks)
        installation_lock = self._stored_state.installation_safety_lock
        if result.safety_scope == "zone" and result.safety_violation:
            zone_locks[test.zone_id] = result.safety_violation
        if result.safety_scope == "installation" and result.safety_violation:
            installation_lock = result.safety_violation
        profile = self._effective_zone_profile(subentry.data, datetime.now(UTC).date())
        deficits, last_effective = self._balance_after_delivery(
            zone_id=test.zone_id,
            delivered_liters=result.delivered_liters,
            effective_delivery=self._crosses_effective_threshold(
                previous_liters=0.0,
                delivered_liters=result.delivered_liters,
                minimum_effective_liters=self._number(
                    subentry.data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1
                ),
            ),
            delivered_at=datetime.now(UTC),
            area_m2=profile.area_m2,
            application_efficiency=profile.application_efficiency,
            maximum_deficit_mm=profile.maximum_deficit_mm,
        )
        proposal = self._stored_state.calibration_proposal
        successful = (
            self._maintenance_stop_reason is None
            and not result.stopped
            and result.safety_violation is None
            and result.target_reached
        )
        if test.kind == "calibration" and successful and self._maintenance_flow_samples:
            average_flow = sum(self._maintenance_flow_samples) / len(self._maintenance_flow_samples)
            proposal = CalibrationProposal(
                proposal_id=uuid4().hex,
                zone_id=test.zone_id,
                zone_subentry_id=test.zone_subentry_id,
                zone_valve=str(subentry.data[CONF_ZONE_VALVE]),
                zone_config_hash=self._calibration_zone_config_hash(subentry),
                created_at=datetime.now(UTC).isoformat(),
                delivered_liters=result.delivered_liters,
                duration_seconds=result.duration_seconds,
                average_flow_l_min=average_flow,
                opening_latency_seconds=result.opening_latency_seconds,
                post_run_liters=result.post_run_liters,
                proposed_min_flow_l_min=average_flow * 0.8,
                proposed_max_flow_l_min=average_flow * 1.2,
            )
        reason = self._maintenance_stop_reason or (
            "stopped"
            if result.stopped
            else "safety_violation"
            if result.safety_violation
            else "completed"
        )
        self._stored_state = replace(
            self._stored_state,
            installation_total_liters=(
                self._stored_state.installation_total_liters + result.delivered_liters
            ),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=qualities,
            zone_last_delivered_liters=last_delivered,
            zone_last_duration_seconds=last_duration,
            zone_safety_locks=zone_locks,
            installation_safety_lock=installation_lock,
            zone_deficit_mm=deficits,
            zone_last_effective_irrigation=last_effective,
            maintenance_test=None,
            active_execution=None,
            calibration_proposal=proposal,
            budget_usage_liters=self._budget_usage_after_delivery(
                self._stored_state.budget_usage_liters,
                zone_id=test.zone_id,
                delivered_liters=result.delivered_liters,
                delivered_at=datetime.now(UTC),
            ),
        )
        self._stored_state = self._with_consumption_record(
            self._with_meter_continuity(self._stored_state),
            amount_liters=result.delivered_liters,
            zone_id=test.zone_id,
            source=test.kind,
            quality=result.measurement_quality,
            warnings=(() if result.safety_violation is None else (result.safety_violation,)),
        )
        await self._store.async_save(self._stored_state)
        self._watering = False
        watchdog = self._maintenance_watchdog_task
        if watchdog is not None and watchdog is not asyncio.current_task():
            watchdog.cancel()
        self._maintenance_watchdog_task = None
        self._maintenance_task = None
        self._publish(status="idle", active_zone_id=None)
        self._events.fire(
            "calibration_result" if test.kind == "calibration" else "maintenance_ended",
            reason=reason,
            target=self._events.zone_target(test.zone_id),
            measurements={
                "delivered_liters": result.delivered_liters,
                "duration_seconds": result.duration_seconds,
            },
            quality=result.measurement_quality,
            context={
                "test_id": test.test_id,
                "proposal_id": proposal.proposal_id
                if test.kind == "calibration" and successful and proposal is not None
                else None,
            },
        )
        self._events.dismiss("maintenance_active")
        if reason == "deadman_timeout":
            await self._events.async_critical(
                "maintenance_deadman_timeout",
                title="Irrigation maintenance confirmation lost",
                message=(
                    f"{self._events.installation_name} closed all valves because dead-man "
                    "confirmation was not received in time."
                ),
            )
        self._planning_event.set()

    def calibration_proposal(self) -> dict[str, object] | None:
        """Return the latest proposal without applying it."""
        proposal = self._stored_state.calibration_proposal
        return proposal.as_dict() if proposal is not None else None

    @staticmethod
    def _calibration_zone_config_hash(subentry: _ZoneConfigSnapshot) -> str:
        """Hash only zone settings that affect calibration execution and accounting."""
        fields = (
            CONF_ZONE_VALVE,
            CONF_MIN_FLOW,
            CONF_MAX_FLOW,
            CONF_FLOW_GRACE_SECONDS,
            CONF_AREA_M2,
            CONF_APPLICATION_EFFICIENCY,
            CONF_MAXIMUM_DEFICIT_MM,
            CONF_MINIMUM_EFFECTIVE_LITERS,
        )
        payload = {
            "zone_id": subentry.unique_id or subentry.subentry_id,
            "config": {key: subentry.data.get(key) for key in fields},
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    async def async_resolve_calibration(
        self, *, proposal_id: str, resolution: str
    ) -> dict[str, object]:
        """Accept or discard measured flow limits in a separate explicit action."""
        async with self._command_lock:
            proposal = self._stored_state.calibration_proposal
            if (
                proposal is None
                or proposal.proposal_id != proposal_id
                or proposal.status != "pending"
            ):
                raise HomeAssistantError("The calibration proposal is not pending")
            if resolution not in {"accept", "discard"}:
                raise HomeAssistantError("Unsupported calibration resolution")
            subentry = None
            if resolution == "accept":
                live_subentry = self._entry.subentries.get(proposal.zone_subentry_id)
                if live_subentry is None or live_subentry.subentry_type != SUBENTRY_TYPE_ZONE:
                    raise HomeAssistantError("The calibration zone no longer exists")
                subentry = _ZoneConfigSnapshot(
                    subentry_id=live_subentry.subentry_id,
                    subentry_type=live_subentry.subentry_type,
                    title=live_subentry.title,
                    unique_id=live_subentry.unique_id,
                    data=dict(live_subentry.data),
                )
                if (
                    (subentry.unique_id or subentry.subentry_id) != proposal.zone_id
                    or subentry.data.get(CONF_ZONE_VALVE) != proposal.zone_valve
                    or self._calibration_zone_config_hash(subentry) != proposal.zone_config_hash
                ):
                    raise HomeAssistantError(
                        "The irrigation zone changed after calibration; discard the stale "
                        "proposal and calibrate again"
                    )
            proposal = replace(
                proposal,
                status="accepted" if resolution == "accept" else "discarded",
            )
            self._stored_state = replace(self._stored_state, calibration_proposal=proposal)
            await self._store.async_save(self._stored_state)
            if subentry is not None:
                live_subentry = self._entry.subentries[subentry.subentry_id]
                self._hass.config_entries.async_update_subentry(
                    self._entry,
                    live_subentry,
                    data={
                        **live_subentry.data,
                        CONF_MIN_FLOW: proposal.proposed_min_flow_l_min,
                        CONF_MAX_FLOW: proposal.proposed_max_flow_l_min,
                    },
                )
            self._events.fire(
                "calibration_result",
                reason=f"proposal_{resolution}",
                target=self._events.zone_target(proposal.zone_id),
                measurements={"average_flow_l_min": proposal.average_flow_l_min},
                context={"proposal_id": proposal.proposal_id, "status": proposal.status},
            )
            return proposal.as_dict()

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
        if main_valve := self._installation_data.get(CONF_MAIN_VALVE):
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
            await self._async_preflight(ignore_emergency_stop=True)
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
            subentry = self._zone_configs_by_subentry_id.get(zone_subentry_id)
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
                    for subentry in self._zone_configs
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
        subentry = self._zone_configs_by_subentry_id.get(zone_subentry_id)
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise HomeAssistantError("The irrigation zone does not exist")
        if amount_liters > self._stored_state.unassigned_available_liters:
            raise HomeAssistantError("The amount exceeds unassigned consumption")

        zone_id = subentry.unique_id or subentry.subentry_id
        profile = self._effective_zone_profile(subentry.data, datetime.now(UTC).date())
        zone_totals = dict(self._stored_state.zone_totals_liters)
        zone_totals[zone_id] = zone_totals.get(zone_id, 0.0) + amount_liters
        deficits, last_effective = self._balance_after_delivery(
            zone_id=zone_id,
            delivered_liters=amount_liters,
            effective_delivery=self._crosses_effective_threshold(
                previous_liters=0.0,
                delivered_liters=amount_liters,
                minimum_effective_liters=self._number(
                    subentry.data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1
                ),
            ),
            delivered_at=datetime.now(UTC),
            area_m2=profile.area_m2,
            application_efficiency=profile.application_efficiency,
            maximum_deficit_mm=profile.maximum_deficit_mm,
        )
        self._stored_state = replace(
            self._stored_state,
            zone_totals_liters=zone_totals,
            unassigned_available_liters=(
                self._stored_state.unassigned_available_liters - amount_liters
            ),
            zone_deficit_mm=deficits,
            zone_last_effective_irrigation=last_effective,
        )
        await self._store.async_save(self._stored_state)
        self._publish(status="idle", active_zone_id=None)
        self._planning_event.set()
        self._events.fire(
            "balance_correction",
            reason="unassigned_water_credited",
            target=self._events.zone_target(zone_id),
            measurements={"delivered_liters": amount_liters},
            quality=self._stored_state.unassigned_measurement_quality,
            context={},
        )

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
                if result.measurement_quality == "integrated":
                    pass
                elif estimated_flow_l_min is not None:
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
        elif self._stored_state.winter_lock:
            status = "winter_lock"
        elif self._stored_state.installation_safety_lock is not None:
            status = "safety_lock"
        elif self._stored_state.maintenance_test is not None:
            status = "maintenance"
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
        schedule_decisions = self._zone_schedule_decisions(now=dt_util.now())
        weather = self._weather_safety()
        self._coordinator.set_snapshot(
            InstallationSnapshot(
                installation_total_liters=(self._stored_state.installation_total_liters),
                zone_totals_liters=dict(self._stored_state.zone_totals_liters),
                zone_measurement_quality=dict(self._stored_state.zone_measurement_quality),
                zone_last_delivered_liters=dict(self._stored_state.zone_last_delivered_liters),
                zone_last_duration_seconds=dict(self._stored_state.zone_last_duration_seconds),
                zone_safety_locks=dict(self._stored_state.zone_safety_locks),
                unassigned_total_liters=self._stored_state.unassigned_total_liters,
                unassigned_available_liters=self._stored_state.unassigned_available_liters,
                unassigned_measurement_quality=(self._stored_state.unassigned_measurement_quality),
                unassigned_measurement_origin=(self._stored_state.unassigned_measurement_origin),
                water_period_liters=self._water_period_totals(dt_util.now()),
                water_period_quality=(
                    "incomplete" if self._stored_state.water_history_incomplete else "complete"
                ),
                current_flow_l_min=self._current_flow_l_min,
                physical_meter_liters=(
                    self._meter.continuity.total_liters
                    if self._meter.continuity is not None
                    else None
                ),
                meter_measurement_quality=("measured" if self._meter.continuity else "unknown"),
                meter_resolution_liters=self._meter_resolution_liters(),
                status=status,
                active_zone_id=active_zone_id,
                emergency_stop=self._stored_state.emergency_stop,
                installation_safety_lock=(self._stored_state.installation_safety_lock),
                winter_lock=self._stored_state.winter_lock,
                maintenance_active=self._stored_state.maintenance_test is not None,
                maintenance_test_id=(
                    self._stored_state.maintenance_test.test_id
                    if self._stored_state.maintenance_test is not None
                    else None
                ),
                maintenance_kind=(
                    self._stored_state.maintenance_test.kind
                    if self._stored_state.maintenance_test is not None
                    else None
                ),
                maintenance_expires_at=(
                    self._stored_state.maintenance_test.expires_at
                    if self._stored_state.maintenance_test is not None
                    else None
                ),
                maintenance_confirmation_deadline=(
                    self._stored_state.maintenance_test.confirmation_deadline
                    if self._stored_state.maintenance_test is not None
                    else None
                ),
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
                active_zone_subentry_id=(
                    selected_request.zone_subentry_id if selected_request else None
                ),
                zone_deficit_mm=dict(self._stored_state.zone_deficit_mm),
                zone_target_liters={
                    planning_input.zone_id: decision.target_liters
                    for _, planning_input, decision in schedule_decisions
                },
                zone_automation_needed={
                    planning_input.zone_id: decision.needed
                    for _, planning_input, decision in schedule_decisions
                },
                zone_next_window={
                    planning_input.zone_id: decision.next_window_start.isoformat()
                    for _, planning_input, decision in schedule_decisions
                    if decision.next_window_start is not None
                },
                zone_planning_reason={
                    planning_input.zone_id: decision.reason
                    for _, planning_input, decision in schedule_decisions
                },
                frost_blocked=weather.frost_blocked,
                rain_stop_active=weather.rain_stop_active,
                weather_safety_status=weather.status,
                weather_model_quality=self._weather_model_quality,
                weather_model_method=self._weather_model_method,
                reference_evapotranspiration_mm=(self._reference_evapotranspiration_mm),
                measured_rain_mm=self._measured_rain_mm,
                weather_period_id=self._weather_period_id,
                weather_last_finalized_at=self._weather_last_finalized_at,
                weather_automation_available=self._weather_automation_available,
                rain_forecast=(
                    self._rain_forecast.as_dict() if self._rain_forecast is not None else None
                ),
                zone_provisional_deficit_mm=dict(self._zone_provisional_deficit_mm),
                zone_crop_evapotranspiration_mm=dict(self._zone_crop_evapotranspiration_mm),
                zone_effective_rain_mm=dict(self._zone_effective_rain_mm),
                zone_calculation_explanations={
                    key: dict(value) for key, value in self._zone_calculation_explanations.items()
                },
                zone_effective_profiles={
                    key: dict(value) for key, value in self._zone_effective_profiles.items()
                },
                zone_soil_moisture={
                    key: dict(value) for key, value in self._zone_soil_moisture.items()
                },
                zone_hardware_health={
                    key: dict(value) for key, value in self._zone_hardware_health.items()
                },
            )
        )
        self._refresh_complete_idle_event()

    def _clear_active_target(self) -> None:
        """Clear transient target progress after an execution finishes."""
        self._active_target_type = None
        self._active_target_value = None
        self._active_remaining_value = None
        self._active_measurement_quality = None
        self._weather_watchdog_event.set()

    def _consume_external_violation(
        self, identity: str, result: ExecutionResult
    ) -> ExecutionResult:
        """Apply one external violation only to the run that observed it."""
        violation = self._active_external_violation
        if violation is None or violation[0] != identity:
            return result
        self._active_external_violation = None
        return replace(
            result,
            stopped=False,
            safety_violation=violation[1],
            safety_scope=violation[2],
            target_reached=False,
        )

    def _clear_external_violation(self, identity: str) -> None:
        """Discard a stale external violation when its owning run terminates."""
        if (
            self._active_external_violation is not None
            and self._active_external_violation[0] == identity
        ):
            self._active_external_violation = None

    def _balance_after_delivery(
        self,
        *,
        zone_id: str,
        delivered_liters: float,
        effective_delivery: bool,
        delivered_at: datetime,
        area_m2: float | None,
        application_efficiency: float | None,
        maximum_deficit_mm: float | None,
    ) -> tuple[dict[str, float], dict[str, str]]:
        """Return durable balance maps after one physically delivered contribution."""
        deficits = dict(self._stored_state.zone_deficit_mm)
        last_effective = dict(self._stored_state.zone_last_effective_irrigation)
        if delivered_liters <= 0:
            return deficits, last_effective
        self._clear_forecast_deferral_state(zone_id)
        if area_m2 is None or application_efficiency is None or maximum_deficit_mm is None:
            return deficits, last_effective
        effective_mm = calculate_effective_irrigation_mm(
            delivered_liters=delivered_liters,
            area_m2=area_m2,
            application_efficiency=application_efficiency,
        )
        deficits[zone_id] = apply_water_balance(
            ZoneWaterBalance(deficits.get(zone_id, 0.0), maximum_deficit_mm),
            WaterBalancePeriod(0.0, 0.0, effective_mm),
        ).deficit_mm
        if zone_id in self._zone_provisional_deficit_mm:
            self._zone_provisional_deficit_mm[zone_id] = max(
                0.0, self._zone_provisional_deficit_mm[zone_id] - effective_mm
            )
        if effective_delivery:
            last_effective[zone_id] = delivered_at.isoformat()
        return deficits, last_effective

    def _clear_forecast_deferral_state(self, zone_id: str) -> None:
        """Remove one persisted forecast deadline without affecting the water balance."""
        starts = dict(self._stored_state.forecast_deferral_started)
        deadlines = dict(self._stored_state.forecast_deferral_deadlines)
        starts.pop(zone_id, None)
        deadlines.pop(zone_id, None)
        self._stored_state = replace(
            self._stored_state,
            forecast_deferral_started=starts,
            forecast_deferral_deadlines=deadlines,
            cancelled_forecast_deferrals=tuple(
                value
                for value in self._stored_state.cancelled_forecast_deferrals
                if value != zone_id
            ),
        )

    def _crosses_effective_threshold(
        self,
        *,
        previous_liters: float,
        delivered_liters: float,
        minimum_effective_liters: float | None,
    ) -> bool:
        """Return whether an execution newly reached the configured effective amount."""
        if minimum_effective_liters is None:
            return False
        return previous_liters < minimum_effective_liters <= previous_liters + delivered_liters

    def _with_balance_snapshot(
        self, request: ManualIrrigationRequest, data: Mapping[str, object]
    ) -> ManualIrrigationRequest:
        """Hydrate a legacy pending request once before its durable claim."""
        snapshot = self._balance_snapshot(data)
        resolved = self._effective_zone_profile(data, dt_util.now().date()).resolved_inputs
        return replace(
            request,
            balance_area_m2=(request.balance_area_m2 or snapshot[0]),
            balance_application_efficiency=(request.balance_application_efficiency or snapshot[1]),
            balance_maximum_deficit_mm=(request.balance_maximum_deficit_mm or snapshot[2]),
            balance_minimum_effective_liters=(
                request.balance_minimum_effective_liters or snapshot[3]
            ),
            resolved_inputs=request.resolved_inputs or dict(resolved),
        )

    @staticmethod
    def _resolve_balance_snapshot(
        active: ActiveExecutionState,
        execution: IrrigationExecutionState | None,
        request: ManualIrrigationRequest | None,
    ) -> tuple[float, float, float, float] | None:
        """Resolve a complete immutable snapshot from linked durable records."""
        sources = (active, execution, request)

        def first(field: str) -> float | None:
            return next(
                (
                    value
                    for source in sources
                    if source is not None and (value := getattr(source, field)) is not None
                ),
                None,
            )

        area = first("balance_area_m2")
        efficiency = first("balance_application_efficiency")
        maximum = first("balance_maximum_deficit_mm")
        threshold = first("balance_minimum_effective_liters")
        if area is None or efficiency is None or maximum is None or threshold is None:
            return None
        return area, efficiency, maximum, threshold

    @staticmethod
    def _uncredited_balance_delivery(
        *,
        zone_id: str,
        delivered_liters: float,
        delivered_at: datetime,
        request_id: str | None,
        execution_id: str | None,
    ) -> UncreditedBalanceDelivery:
        """Create an explicit reconciliation item instead of dropping balance credit."""
        return UncreditedBalanceDelivery(
            reconciliation_id=uuid4().hex,
            zone_id=zone_id,
            delivered_liters=delivered_liters,
            delivered_at=delivered_at.isoformat(),
            reason="missing_immutable_balance_snapshot",
            request_id=request_id,
            execution_id=execution_id,
        )

    def _balance_snapshot(self, data: Mapping[str, object]) -> tuple[float, float, float, float]:
        """Capture immutable parameters used for later delivery accounting."""
        profile = self._effective_zone_profile(data, dt_util.now().date())
        return (
            profile.area_m2,
            profile.application_efficiency,
            profile.maximum_deficit_mm,
            self._number(data, CONF_MINIMUM_EFFECTIVE_LITERS, 0.1),
        )

    @staticmethod
    def _automatic_request_id(zone_id: str, opportunity_id: str) -> str:
        """Return the durable identity shared by planning and skip-once."""
        return f"automatic:{zone_id}:{opportunity_id}"

    def _delivery_runtime_limit(
        self, zone_data: Mapping[str, object], requested_limit: float | None
    ) -> float:
        """Combine caller, zone, and installation hydraulic limits by minimum."""
        limits = [
            self._number(
                self._installation_data,
                CONF_INSTALLATION_MAX_DELIVERY_RUNTIME,
                14_400,
            ),
            self._number(zone_data, CONF_MAX_DELIVERY_RUNTIME, 3_600),
        ]
        if requested_limit is not None:
            limits.append(requested_limit)
        return min(limits)

    def _operation_lifetime_limit(self, zone_data: Mapping[str, object]) -> float:
        """Combine zone and installation total-lifetime limits by minimum."""
        return min(
            self._number(
                self._installation_data,
                CONF_INSTALLATION_MAX_OPERATION_LIFETIME,
                86_400,
            ),
            self._number(zone_data, CONF_MAX_OPERATION_LIFETIME, 14_400),
        )

    def _sun_event(self, event: str, day: date) -> datetime | None:
        """Resolve a sun event through Home Assistant's configured location helper."""
        return get_astral_event_date(self._hass, event, day)

    @staticmethod
    def _budget_keys(zone_id: str, when: datetime) -> tuple[str, str, str, str]:
        """Return stable local-day and ISO-week accounting keys."""
        local = dt_util.as_local(when)
        day = local.date().isoformat()
        iso_year, iso_week, _ = local.date().isocalendar()
        week = f"{iso_year}-W{iso_week:02d}"
        return (
            f"installation:day:{day}",
            f"installation:week:{week}",
            f"zone:{zone_id}:day:{day}",
            f"zone:{zone_id}:week:{week}",
        )

    def _automatic_budget_remaining_liters(
        self, *, zone_id: str, data: Mapping[str, object], now: datetime
    ) -> float | None:
        """Return the strictest configured automatic budget remainder."""
        keys = self._budget_keys(zone_id, now)
        limits = (
            self._optional_float(self._installation_data, CONF_INSTALLATION_DAILY_BUDGET_LITERS),
            self._optional_float(self._installation_data, CONF_INSTALLATION_WEEKLY_BUDGET_LITERS),
            self._optional_float(data, CONF_ZONE_DAILY_BUDGET_LITERS),
            self._optional_float(data, CONF_ZONE_WEEKLY_BUDGET_LITERS),
        )
        remaining = [
            max(0.0, limit - self._stored_state.budget_usage_liters.get(key, 0.0))
            for key, limit in zip(keys, limits, strict=True)
            if limit is not None
        ]
        return min(remaining) if remaining else None

    def _request_target_liters(self, request: ManualIrrigationRequest) -> float | None:
        """Estimate a request's budget impact when its target is time-based."""
        if request.target_type == "volume":
            return request.target_value
        if request.estimated_flow_l_min is None:
            return None
        return request.target_value * request.estimated_flow_l_min / 60

    def _manual_budget_warnings(
        self, request: ManualIrrigationRequest, *, now: datetime
    ) -> list[str]:
        """Describe manual budget overruns without blocking explicit user intent."""
        target_liters = self._request_target_liters(request)
        subentry = self._zone_configs_by_subentry_id.get(request.zone_subentry_id)
        if target_liters is None or subentry is None:
            return []
        keys = self._budget_keys(request.zone_id, now)
        limits = (
            (
                "installation_daily_budget",
                self._optional_float(
                    self._installation_data, CONF_INSTALLATION_DAILY_BUDGET_LITERS
                ),
            ),
            (
                "installation_weekly_budget",
                self._optional_float(
                    self._installation_data, CONF_INSTALLATION_WEEKLY_BUDGET_LITERS
                ),
            ),
            (
                "zone_daily_budget",
                self._optional_float(subentry.data, CONF_ZONE_DAILY_BUDGET_LITERS),
            ),
            (
                "zone_weekly_budget",
                self._optional_float(subentry.data, CONF_ZONE_WEEKLY_BUDGET_LITERS),
            ),
        )
        return [
            reason
            for key, (reason, limit) in zip(keys, limits, strict=True)
            if limit is not None
            and self._stored_state.budget_usage_liters.get(key, 0.0) + target_liters > limit
        ]

    def _budget_usage_after_delivery(
        self,
        usage: Mapping[str, float],
        *,
        zone_id: str,
        delivered_liters: float,
        delivered_at: datetime,
    ) -> dict[str, float]:
        """Account one measured or estimated delivery for every applicable period."""
        updated = dict(usage)
        if delivered_liters <= 0:
            return updated
        for key in self._budget_keys(zone_id, delivered_at):
            updated[key] = updated.get(key, 0.0) + delivered_liters
        return updated

    @staticmethod
    def _request_deadline(request: ManualIrrigationRequest) -> datetime:
        """Return the immutable total-lifetime deadline, including waits and soaking."""
        return datetime.fromisoformat(request.operation_deadline_at or request.expires_at)

    def _pause_deadline(self, request: ManualIrrigationRequest, now: datetime) -> datetime:
        """Bound a user pause by its configured timeout and immutable request deadline."""
        return min(
            self._request_deadline(request),
            now
            + timedelta(
                seconds=self._number(self._installation_data, CONF_PAUSE_TIMEOUT_SECONDS, 3_600)
            ),
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

    @staticmethod
    def _finite_positive(value: object) -> float | None:
        """Validate an optional positive finite service-input number."""
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise HomeAssistantError("Irrigation targets must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0:
            raise HomeAssistantError("Irrigation targets must be positive and finite")
        return numeric

    @staticmethod
    def _number(data: Mapping[str, object], key: str, default: float) -> float:
        """Read a numeric config value while preserving additive migration defaults."""
        value = data.get(key, default)
        return float(value) if isinstance(value, int | float) else default
