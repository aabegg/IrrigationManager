"""Version 2 config and zone subentry flows for Irrigation Manager."""

import asyncio
import json
import math
from collections.abc import Mapping, Sequence
from datetime import time
from typing import Any, cast, override
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, Platform, UnitOfTime, UnitOfVolume
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TimeSelector,
)

from .const import (
    CONF_AUTOMATION_ENABLED,
    CONF_CALIBRATION_CONFIRMATION_INTERVAL,
    CONF_CALIBRATION_MAX_DURATION,
    CONF_CALIBRATION_SETTLE_SECONDS,
    CONF_CONTROL_TYPE,
    CONF_LITERS_PER_PULSE,
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
    CONF_METER_TYPE,
    CONF_NEEDS_RECONFIGURATION,
    CONF_OPERATION_ENABLED,
    CONF_VOLUME_MAX_RUNTIME,
    CONF_WEEKLY_SCHEDULE,
    CONF_ZONE_VALVE,
    CONTROL_TYPE_TIME,
    CONTROL_TYPE_VOLUME,
    DOMAIN,
    METER_TYPE_CUMULATIVE,
    METER_TYPE_NONE,
    METER_TYPE_PULSE,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
)
from .manager import IrrigationManager

_ACTUATOR_OWNERSHIP_LOCK = asyncio.Lock()


def _owned_endpoints(
    installation: Mapping[str, object], zones: Sequence[Mapping[str, object]]
) -> set[str]:
    """Collect actuator entities owned by one installation."""
    endpoints = {
        entity_id
        for key in (CONF_MAIN_VALVE,)
        if isinstance((entity_id := installation.get(key)), str)
    }
    endpoints.update(
        entity_id for zone in zones if isinstance((entity_id := zone.get(CONF_ZONE_VALVE)), str)
    )
    return endpoints


def _has_duplicate_endpoints(
    installation: Mapping[str, object], zones: Sequence[Mapping[str, object]]
) -> bool:
    """Return whether a candidate assigns one actuator more than once."""
    values = [
        entity_id
        for data, key in (
            (installation, CONF_MAIN_VALVE),
            *((zone, CONF_ZONE_VALVE) for zone in zones),
        )
        if isinstance((entity_id := data.get(key)), str)
    ]
    return len(values) != len(set(values))


def _ownership_conflicts(
    hass: Any,
    candidate: set[str],
    *,
    excluding_entry_id: str | None = None,
    excluding_subentry_id: str | None = None,
    exclude_installation: bool = False,
) -> bool:
    """Check candidate actuators against every persisted integration entry."""
    existing: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id != excluding_entry_id or not exclude_installation:
            existing.update(_owned_endpoints(entry.data, ()))
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE):
            if (
                entry.entry_id == excluding_entry_id
                and subentry.subentry_id == excluding_subentry_id
            ):
                continue
            existing.update(_owned_endpoints({}, (subentry.data,)))
    return not candidate.isdisjoint(existing)


def _choice(options: list[str], translation_key: str) -> SelectSelector:
    """Return a translated single-choice selector."""
    return SelectSelector(SelectSelectorConfig(options=options, translation_key=translation_key))


def _installation_basics_schema() -> vol.Schema:
    return vol.Schema({vol.Required(CONF_NAME): TextSelector()})


def _installation_main_valve_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_MAIN_VALVE): EntitySelector(
                EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
            )
        }
    )


def _meter_type_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_METER_TYPE, default=METER_TYPE_NONE): _choice(
                [METER_TYPE_NONE, METER_TYPE_CUMULATIVE, METER_TYPE_PULSE], CONF_METER_TYPE
            )
        }
    )


def _meter_details_schema(meter_type: str) -> vol.Schema:
    schema: dict[object, object] = {
        vol.Optional(CONF_METER_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        )
    }
    if meter_type == METER_TYPE_PULSE:
        schema.update(
            {
                vol.Optional("pulse_factor_mode", default="liters_per_pulse"): _choice(
                    ["liters_per_pulse", "pulses_per_liter"], "pulse_factor_mode"
                ),
                vol.Optional("pulse_factor"): NumberSelector(
                    NumberSelectorConfig(
                        min=0.001,
                        max=1_000_000,
                        step=0.001,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
    return vol.Schema(schema)


def _installation_reconfiguration_schema() -> vol.Schema:
    """Return the complete migrated-installation reconfiguration form."""
    schema = dict(_installation_basics_schema().schema)
    schema.update(_installation_main_valve_schema().schema)
    schema.update(_meter_type_schema().schema)
    return vol.Schema(schema)


def _minimal_zone_schema(has_meter: bool) -> vol.Schema:
    schema: dict[object, object] = {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Required(CONF_ZONE_VALVE): EntitySelector(
            EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
        ),
        vol.Required(CONF_CONTROL_TYPE, default=CONTROL_TYPE_TIME): _choice(
            [CONTROL_TYPE_TIME, CONTROL_TYPE_VOLUME] if has_meter else [CONTROL_TYPE_TIME],
            CONF_CONTROL_TYPE,
        ),
    }
    if has_meter:
        schema[vol.Optional(CONF_VOLUME_MAX_RUNTIME)] = NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=604_800,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        )
    return vol.Schema(schema)


def _weekly_schedule_schema() -> vol.Schema:
    schema: dict[object, object] = {}
    for weekday in WEEKDAYS:
        schema[vol.Optional(f"{weekday}_start")] = TimeSelector()
        schema[vol.Optional(f"{weekday}_end")] = TimeSelector()
        schema[vol.Optional(f"{weekday}_target")] = NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=1_000_000,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        )
    return vol.Schema(schema)


def _weekly_schedule_form_values(schedule: object) -> dict[str, object]:
    """Flatten canonical weekday rows back into form fields."""
    values: dict[str, object] = {}
    if not isinstance(schedule, list):
        return values
    for row in schedule:
        if not isinstance(row, Mapping) or row.get("weekday") not in WEEKDAYS:
            continue
        weekday = str(row["weekday"])
        for field in ("start", "end", "target"):
            if row.get(field) is not None:
                values[f"{weekday}_{field}"] = row[field]
    return values


def _canonical_weekly_schedule(
    user_input: Mapping[str, Any], *, control_type: str, volume_max_runtime: float | None
) -> tuple[list[dict[str, object]], str | None]:
    """Normalize and validate exactly seven fixed weekday slots."""
    schedule: list[dict[str, object]] = []
    intervals: list[tuple[float, float]] = []
    week_seconds = 7 * 86_400
    for weekday_index, weekday in enumerate(WEEKDAYS):
        start_value = user_input.get(f"{weekday}_start")
        end_value = user_input.get(f"{weekday}_end")
        target_value = user_input.get(f"{weekday}_target")
        present = (
            start_value not in (None, ""),
            end_value not in (None, ""),
            target_value is not None,
        )
        if any(present) and not all(present):
            return [], "schedule_row_incomplete"
        if not any(present):
            schedule.append({"weekday": weekday, "start": None, "end": None, "target": None})
            continue
        try:
            start = time.fromisoformat(str(start_value))
            end = time.fromisoformat(str(end_value))
            if not isinstance(target_value, int | float):
                raise ValueError
            target = float(target_value)
        except TypeError, ValueError:
            return [], "schedule_row_invalid"
        if target <= 0 or not math.isfinite(target):
            return [], "schedule_target_invalid"
        start_seconds = (
            weekday_index * 86_400 + start.hour * 3600 + start.minute * 60 + start.second
        )
        end_seconds = weekday_index * 86_400 + end.hour * 3600 + end.minute * 60 + end.second
        if end_seconds <= start_seconds:
            end_seconds += 86_400
        required_seconds = target if control_type == CONTROL_TYPE_TIME else volume_max_runtime
        if required_seconds is None or required_seconds > end_seconds - start_seconds:
            return [], "schedule_target_does_not_fit"
        intervals.append((start_seconds, end_seconds))
        schedule.append(
            {
                "weekday": weekday,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "target": target,
            }
        )
    cyclic = [*intervals, *((start + week_seconds, end + week_seconds) for start, end in intervals)]
    for index, (interval_start, interval_end) in enumerate(intervals):
        for other_index, (other_start, other_end) in enumerate(cyclic):
            if index == other_index:
                continue
            if max(interval_start, other_start) < min(interval_end, other_end):
                return [], "schedule_overlap"
    return schedule, None


def _meter_data(user_input: Mapping[str, object]) -> tuple[dict[str, object], str | None]:
    """Normalize one v2 meter form to persisted fields."""
    meter_type = str(user_input[CONF_METER_TYPE])
    entity = user_input.get(CONF_METER_ENTITY)
    factor = user_input.get("pulse_factor")
    if meter_type != METER_TYPE_NONE and not entity:
        return {}, "selected_meter_required"
    if meter_type == METER_TYPE_PULSE and factor is None:
        return {}, "raw_meter_requires_factor"
    data: dict[str, object] = {CONF_METER_TYPE: meter_type}
    if meter_type != METER_TYPE_NONE:
        data[CONF_METER_ENTITY] = entity
    if meter_type == METER_TYPE_PULSE:
        numeric_factor = float(cast(float, factor))
        data[CONF_LITERS_PER_PULSE] = (
            numeric_factor
            if user_input.get("pulse_factor_mode") == "liters_per_pulse"
            else 1 / numeric_factor
        )
    return data, None


class IrrigationManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one v2 irrigation installation with its mandatory first zone."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize wizard state."""
        self._installation: dict[str, Any] = {}
        self._first_zone: dict[str, Any] = {}
        self._meter_type = METER_TYPE_NONE

    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the v2 installation options flow."""
        return IrrigationManagerOptionsFlow()

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Start the only supported creation wizard."""
        return self.async_show_menu(step_id="user", menu_options=["create"])

    async def async_step_create(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the installation name."""
        if user_input is not None:
            self._installation = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_OPERATION_ENABLED: True,
                CONF_AUTOMATION_ENABLED: True,
            }
            return await self.async_step_installation_hardware()
        return self.async_show_form(step_id="create", data_schema=_installation_basics_schema())

    async def async_step_installation_hardware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the optional main valve."""
        if user_input is not None:
            self._installation[CONF_MAIN_VALVE] = user_input.get(CONF_MAIN_VALVE)
            return await self.async_step_installation_meter()
        return self.async_show_form(
            step_id="installation_hardware", data_schema=_installation_main_valve_schema()
        )

    async def async_step_installation_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose whether and how water is measured."""
        schema = _meter_type_schema()
        if user_input is not None:
            self._meter_type = str(user_input[CONF_METER_TYPE])
            if self._meter_type == METER_TYPE_NONE:
                self._installation[CONF_METER_TYPE] = METER_TYPE_NONE
                return await self.async_step_installation_zone()
            return await self.async_step_installation_meter_details()
        return self.async_show_form(step_id="installation_meter", data_schema=schema)

    async def async_step_installation_meter_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect only the source fields required by the selected meter type."""
        schema = _meter_details_schema(self._meter_type)
        if user_input is not None:
            meter, error = _meter_data({CONF_METER_TYPE: self._meter_type, **user_input})
            if error is not None:
                return self.async_show_form(
                    step_id="installation_meter_details",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": error},
                )
            self._installation.update(meter)
            return await self.async_step_installation_zone()
        return self.async_show_form(step_id="installation_meter_details", data_schema=schema)

    async def async_step_installation_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the mandatory first zone."""
        has_meter = self._installation.get(CONF_METER_TYPE) != METER_TYPE_NONE
        schema = _minimal_zone_schema(has_meter)
        if user_input is not None:
            control_type = str(user_input[CONF_CONTROL_TYPE])
            max_runtime = user_input.get(CONF_VOLUME_MAX_RUNTIME)
            if control_type == CONTROL_TYPE_VOLUME and max_runtime is None:
                return self.async_show_form(
                    step_id="installation_zone",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "volume_max_runtime_required"},
                )
            self._first_zone = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_ZONE_VALVE: user_input[CONF_ZONE_VALVE],
                CONF_CONTROL_TYPE: control_type,
                CONF_OPERATION_ENABLED: True,
                CONF_AUTOMATION_ENABLED: True,
            }
            if max_runtime is not None:
                self._first_zone[CONF_VOLUME_MAX_RUNTIME] = float(max_runtime)
            return await self.async_step_installation_schedule()
        return self.async_show_form(step_id="installation_zone", data_schema=schema)

    async def async_step_installation_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the installation and first zone after the seven-day schedule."""
        schema = _weekly_schedule_schema()
        if user_input is None:
            return self.async_show_form(step_id="installation_schedule", data_schema=schema)
        schedule, error = _canonical_weekly_schedule(
            user_input,
            control_type=str(self._first_zone[CONF_CONTROL_TYPE]),
            volume_max_runtime=cast(float | None, self._first_zone.get(CONF_VOLUME_MAX_RUNTIME)),
        )
        if error is not None:
            return self.async_show_form(
                step_id="installation_schedule",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
            )
        self._first_zone[CONF_WEEKLY_SCHEDULE] = schedule
        candidate = _owned_endpoints(self._installation, (self._first_zone,))
        async with _ACTUATOR_OWNERSHIP_LOCK:
            if _has_duplicate_endpoints(self._installation, (self._first_zone,)) or (
                _ownership_conflicts(self.hass, candidate)
            ):
                return self.async_abort(reason="actuator_already_owned")
            await self.async_set_unique_id(uuid4().hex)
            return self.async_create_entry(
                title=str(self._installation[CONF_NAME]),
                data=self._installation,
                subentries=[
                    ConfigSubentryData(
                        data=self._first_zone,
                        subentry_type=SUBENTRY_TYPE_ZONE,
                        title=str(self._first_zone[CONF_NAME]),
                        unique_id=uuid4().hex,
                    )
                ],
            )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the repeatable zone subentry type."""
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlow}


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Create or reconfigure one minimal v2 irrigation zone."""

    def __init__(self) -> None:
        """Initialize zone and action state."""
        self._zone: dict[str, Any] = {}
        self._calibration_test_id: str | None = None
        self._calibration_previous_proposal_id: str | None = None
        self._calibration_proposal: dict[str, object] | None = None
        self._calibration_supervision_renewed = False
        self._pending_release_input: dict[str, bool] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Start the minimal zone form directly."""
        self._zone = {}
        return await self.async_step_minimal(user_input)

    async def async_step_minimal(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect a new zone's name, valve, and control type."""
        has_meter = self._get_entry().data.get(CONF_METER_TYPE) != METER_TYPE_NONE
        schema = _minimal_zone_schema(has_meter)
        if user_input is not None:
            if self._valve_is_configured(str(user_input[CONF_ZONE_VALVE])):
                return self.async_abort(reason="actuator_already_owned")
            control_type = str(user_input[CONF_CONTROL_TYPE])
            max_runtime = user_input.get(CONF_VOLUME_MAX_RUNTIME)
            if control_type == CONTROL_TYPE_VOLUME and max_runtime is None:
                return self.async_show_form(
                    step_id="minimal",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "volume_max_runtime_required"},
                )
            self._zone = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_ZONE_VALVE: user_input[CONF_ZONE_VALVE],
                CONF_CONTROL_TYPE: control_type,
                CONF_OPERATION_ENABLED: True,
                CONF_AUTOMATION_ENABLED: True,
            }
            if max_runtime is not None:
                self._zone[CONF_VOLUME_MAX_RUNTIME] = float(max_runtime)
            return await self.async_step_minimal_schedule()
        return self.async_show_form(step_id="minimal", data_schema=schema)

    async def async_step_minimal_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Validate and save all seven weekday rows for a new zone."""
        schema = _weekly_schedule_schema()
        if user_input is None:
            return self.async_show_form(step_id="minimal_schedule", data_schema=schema)
        schedule, error = _canonical_weekly_schedule(
            user_input,
            control_type=str(self._zone[CONF_CONTROL_TYPE]),
            volume_max_runtime=cast(float | None, self._zone.get(CONF_VOLUME_MAX_RUNTIME)),
        )
        if error is not None:
            return self.async_show_form(
                step_id="minimal_schedule",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
            )
        self._zone[CONF_WEEKLY_SCHEDULE] = schedule
        async with _ACTUATOR_OWNERSHIP_LOCK:
            if self._valve_is_configured(str(self._zone[CONF_ZONE_VALVE])):
                return self.async_abort(reason="actuator_already_owned")
            return self.async_create_entry(
                title=str(self._zone[CONF_NAME]), data=self._zone, unique_id=uuid4().hex
            )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Offer zone configuration, releases, and documented flow calibration."""
        options = ["reconfigure_minimal", "releases"]
        if self._get_entry().data.get(CONF_METER_TYPE) != METER_TYPE_NONE:
            options.append("calibration")
        return self.async_show_menu(step_id="reconfigure", menu_options=options)

    async def async_step_reconfigure_minimal(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a zone's minimal v2 configuration."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        has_meter = entry.data.get(CONF_METER_TYPE) != METER_TYPE_NONE
        schema = _minimal_zone_schema(has_meter)
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_minimal",
                data_schema=self.add_suggested_values_to_schema(schema, subentry.data),
            )
        if self._valve_is_configured(
            str(user_input[CONF_ZONE_VALVE]), excluding_subentry_id=subentry.subentry_id
        ):
            return self.async_abort(reason="actuator_already_owned")
        control_type = str(user_input[CONF_CONTROL_TYPE])
        max_runtime = user_input.get(CONF_VOLUME_MAX_RUNTIME)
        if control_type == CONTROL_TYPE_VOLUME and max_runtime is None:
            return self.async_show_form(
                step_id="reconfigure_minimal",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "volume_max_runtime_required"},
            )
        self._zone = dict(subentry.data)
        self._zone.update(
            {
                CONF_NAME: user_input[CONF_NAME],
                CONF_ZONE_VALVE: user_input[CONF_ZONE_VALVE],
                CONF_CONTROL_TYPE: control_type,
            }
        )
        if max_runtime is not None:
            self._zone[CONF_VOLUME_MAX_RUNTIME] = float(max_runtime)
        elif control_type == CONTROL_TYPE_TIME:
            self._zone.pop(CONF_VOLUME_MAX_RUNTIME, None)
        return await self.async_step_reconfigure_minimal_schedule()

    async def async_step_reconfigure_minimal_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Replace a zone's complete seven-day schedule."""
        subentry = self._get_reconfigure_subentry()
        schema = _weekly_schedule_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_minimal_schedule",
                data_schema=self.add_suggested_values_to_schema(
                    schema, _weekly_schedule_form_values(subentry.data.get(CONF_WEEKLY_SCHEDULE))
                ),
            )
        schedule, error = _canonical_weekly_schedule(
            user_input,
            control_type=str(self._zone[CONF_CONTROL_TYPE]),
            volume_max_runtime=cast(float | None, self._zone.get(CONF_VOLUME_MAX_RUNTIME)),
        )
        if error is not None:
            return self.async_show_form(
                step_id="reconfigure_minimal_schedule",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
            )
        self._zone[CONF_WEEKLY_SCHEDULE] = schedule
        self._zone.pop(CONF_NEEDS_RECONFIGURATION, None)
        async with _ACTUATOR_OWNERSHIP_LOCK:
            if self._valve_is_configured(
                str(self._zone[CONF_ZONE_VALVE]), excluding_subentry_id=subentry.subentry_id
            ):
                return self.async_abort(reason="actuator_already_owned")
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=str(self._zone[CONF_NAME]),
                data=self._zone,
            )

    async def async_step_releases(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Update the zone's operation and automatic releases."""
        manager = self._manager()
        zone = self._get_reconfigure_subentry()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        zone_id = zone.unique_id or zone.subentry_id
        schema = vol.Schema(
            {
                vol.Required(CONF_OPERATION_ENABLED): BooleanSelector(),
                vol.Required(CONF_AUTOMATION_ENABLED): BooleanSelector(),
            }
        )
        if user_input is None:
            snapshot = manager.snapshot()
            return self.async_show_form(
                step_id="releases",
                data_schema=self.add_suggested_values_to_schema(
                    schema,
                    {
                        CONF_OPERATION_ENABLED: snapshot.zone_operation_enabled[zone_id],
                        CONF_AUTOMATION_ENABLED: snapshot.zone_automation_enabled[zone_id],
                    },
                ),
            )
        self._pending_release_input = {
            CONF_OPERATION_ENABLED: bool(user_input[CONF_OPERATION_ENABLED]),
            CONF_AUTOMATION_ENABLED: bool(user_input[CONF_AUTOMATION_ENABLED]),
        }
        if not self._pending_release_input[
            CONF_AUTOMATION_ENABLED
        ] and manager.automatic_execution_active(zone_subentry_id=zone.subentry_id):
            return await self.async_step_automation_disable()
        return await self._apply_releases(stop_active=False)

    async def async_step_automation_disable(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Ask whether an active automatic execution should stop or finish."""
        if user_input is None:
            return self.async_show_form(
                step_id="automation_disable", data_schema=_active_automatic_schema()
            )
        return await self._apply_releases(stop_active=user_input["active_execution"] == "stop")

    async def _apply_releases(self, *, stop_active: bool) -> SubentryFlowResult:
        manager = self._manager()
        pending = self._pending_release_input
        zone = self._get_reconfigure_subentry()
        if manager is None or pending is None:
            return self.async_abort(reason="release_change_not_pending")
        self._pending_release_input = None
        await manager.async_set_zone_operation(
            zone_subentry_id=zone.subentry_id, enabled=pending[CONF_OPERATION_ENABLED]
        )
        await manager.async_set_zone_automation(
            zone_subentry_id=zone.subentry_id,
            enabled=pending[CONF_AUTOMATION_ENABLED],
            stop_active=stop_active,
        )
        return self.async_abort(reason="releases_updated")

    def _manager(self) -> IrrigationManager | None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._get_entry().entry_id)
        return cast(IrrigationManager, runtime) if runtime is not None else None

    def _calibration_duration_limit(self) -> float:
        data = self._get_entry().data
        hard_limit = float(data.get(CONF_CALIBRATION_MAX_DURATION, 300.0))
        settle = float(data.get(CONF_CALIBRATION_SETTLE_SECONDS, 2.0))
        return hard_limit - settle - 5.0

    def _calibration_running_placeholders(self) -> dict[str, str]:
        confirmation = float(
            self._get_entry().data.get(CONF_CALIBRATION_CONFIRMATION_INTERVAL, 30.0)
        )
        return {
            "zone": self._get_reconfigure_subentry().title,
            "interval": str(max(1, min(20, int(confirmation) - 5))),
            "status": "renewed" if self._calibration_supervision_renewed else "started",
        }

    async def async_step_calibration(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start one supervised flow-profile calibration."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        duration_limit = self._calibration_duration_limit()
        if duration_limit < 1:
            return self.async_abort(reason="calibration_configuration_invalid")
        schema = vol.Schema(
            {
                vol.Required("duration", default=min(60.0, duration_limit)): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=duration_limit,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=UnitOfTime.SECONDS,
                    )
                ),
                vol.Required("confirm_supervision", default=False): BooleanSelector(),
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="calibration",
                data_schema=schema,
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        if user_input.get("confirm_supervision") is not True:
            return self.async_show_form(
                step_id="calibration",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_supervision_required"},
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        previous = manager.calibration_proposal()
        self._calibration_previous_proposal_id = (
            str(previous["proposal_id"]) if previous is not None else None
        )
        try:
            started = await manager.async_start_calibration(
                zone_subentry_id=self._get_reconfigure_subentry().subentry_id,
                duration_seconds=float(user_input["duration"]),
            )
        except HomeAssistantError:
            return self.async_show_form(
                step_id="calibration",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_start_failed"},
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        self._calibration_test_id = str(started["test_id"])
        return await self.async_step_calibration_running()

    async def async_step_calibration_running(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Renew supervision until the calibration proposal is available."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        test_id = self._calibration_test_id
        if test_id is None:
            return self.async_abort(reason="calibration_not_started")
        if user_input is None:
            return self.async_show_form(
                step_id="calibration_running",
                data_schema=vol.Schema({}),
                description_placeholders=self._calibration_running_placeholders(),
            )
        if manager.is_calibration_active(test_id):
            await manager.async_confirm_calibration(test_id=test_id)
            self._calibration_supervision_renewed = True
            return self.async_show_form(
                step_id="calibration_running",
                data_schema=vol.Schema({}),
                description_placeholders=self._calibration_running_placeholders(),
            )
        proposal = manager.calibration_proposal()
        if (
            proposal is None
            or proposal.get("proposal_id") == self._calibration_previous_proposal_id
            or proposal.get("zone_subentry_id") != self._get_reconfigure_subentry().subentry_id
            or proposal.get("status") != "pending"
        ):
            return self.async_abort(reason="calibration_no_proposal")
        self._calibration_proposal = proposal
        return await self.async_step_calibration_review()

    async def async_step_calibration_review(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Apply or discard a measured flow profile after explicit review."""
        proposal = self._calibration_proposal
        manager = self._manager()
        if proposal is None:
            return self.async_abort(reason="calibration_no_proposal")
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        schema = vol.Schema(
            {
                vol.Required("resolution", default="discard"): _choice(
                    ["accept", "discard"], "calibration_resolution"
                ),
                vol.Required("confirm_resolution", default=False): BooleanSelector(),
            }
        )
        result = (
            f"{proposal.get('average_flow_l_min', 0)} L/min; "
            f"{proposal.get('proposed_min_flow_l_min', 0)}-"
            f"{proposal.get('proposed_max_flow_l_min', 0)} L/min"
        )
        if user_input is None or user_input.get("confirm_resolution") is not True:
            return self.async_show_form(
                step_id="calibration_review",
                data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
                errors={"base": "calibration_resolution_required"} if user_input else None,
                description_placeholders={"result": result},
            )
        resolution = str(user_input["resolution"])
        try:
            await manager.async_resolve_calibration(
                proposal_id=str(proposal["proposal_id"]), resolution=resolution
            )
        except HomeAssistantError:
            return self.async_show_form(
                step_id="calibration_review",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_resolution_failed"},
                description_placeholders={"result": result},
            )
        return self.async_abort(
            reason="calibration_accepted" if resolution == "accept" else "calibration_discarded"
        )

    def _valve_is_configured(
        self, valve_entity_id: str, excluding_subentry_id: str | None = None
    ) -> bool:
        entry = self._get_entry()
        return _ownership_conflicts(
            self.hass,
            {valve_entity_id},
            excluding_entry_id=entry.entry_id,
            excluding_subentry_id=excluding_subentry_id,
            exclude_installation=False,
        )


def _active_automatic_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("active_execution"): SelectSelector(
                SelectSelectorConfig(options=["stop", "finish"])
            )
        }
    )


class IrrigationManagerOptionsFlow(OptionsFlow):
    """Edit v2 installation modules and execute installation actions."""

    def __init__(self) -> None:
        """Initialize action state."""
        self._action_result = ""
        self._pending_release_input: dict[str, bool] | None = None
        self._meter_type = METER_TYPE_NONE
        self._pending_installation: dict[str, object] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Expose v2 installation sections directly."""
        options = [
            "basics",
            "main_valve",
            "meter",
            "installation_releases",
            "replan",
            "emergency_stop",
            "reset_safety",
        ]
        if self.config_entry.data.get(CONF_NEEDS_RECONFIGURATION) is True:
            options.insert(0, "installation_reconfiguration")
        if self.config_entry.data.get(CONF_METER_TYPE) != METER_TYPE_NONE:
            options.append("physical_meter_correction")
        return self.async_show_menu(step_id="init", menu_options=options)

    async def async_step_basics(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the installation name."""
        schema = _installation_basics_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="basics",
                data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
            )
        return self._update_installation(
            {CONF_NAME: user_input[CONF_NAME]}, title=str(user_input[CONF_NAME])
        )

    async def async_step_main_valve(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the optional main valve independently."""
        schema = _installation_main_valve_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="main_valve",
                data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
            )
        data = {CONF_MAIN_VALVE: user_input.get(CONF_MAIN_VALVE)}
        candidate = _owned_endpoints(data, ())
        async with _ACTUATOR_OWNERSHIP_LOCK:
            if _ownership_conflicts(
                self.hass,
                candidate,
                excluding_entry_id=self.config_entry.entry_id,
                exclude_installation=True,
            ):
                return self.async_abort(reason="actuator_already_owned")
            return self._update_installation(data)

    async def async_step_meter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the optional water meter independently."""
        schema = _meter_type_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="meter",
                data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
            )
        self._meter_type = str(user_input[CONF_METER_TYPE])
        if self._meter_type == METER_TYPE_NONE and self._has_volume_zones():
            return self.async_show_form(
                step_id="meter",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "meter_required_by_volume_zones"},
            )
        if self._meter_type == METER_TYPE_NONE:
            return self._update_installation(
                {CONF_METER_TYPE: METER_TYPE_NONE}, remove_meter_fields=True
            )
        return await self.async_step_meter_details()

    async def async_step_meter_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit only fields relevant to the selected water meter."""
        schema = _meter_details_schema(self._meter_type)
        if user_input is None:
            suggested = dict(self.config_entry.data)
            if self._meter_type == METER_TYPE_PULSE:
                suggested["pulse_factor_mode"] = "liters_per_pulse"
                suggested["pulse_factor"] = self.config_entry.data.get(CONF_LITERS_PER_PULSE)
            return self.async_show_form(
                step_id="meter_details",
                data_schema=self.add_suggested_values_to_schema(schema, suggested),
            )
        meter, error = _meter_data({CONF_METER_TYPE: self._meter_type, **user_input})
        if error is not None:
            return self.async_show_form(
                step_id="meter_details",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
            )
        return self._update_installation(meter, remove_meter_fields=True)

    async def async_step_installation_reconfiguration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate every aggregate installation field before clearing migration state."""
        if self.config_entry.data.get(CONF_NEEDS_RECONFIGURATION) is not True:
            return self.async_abort(reason="reconfiguration_not_required")
        schema = _installation_reconfiguration_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="installation_reconfiguration",
                data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
            )
        if user_input[CONF_METER_TYPE] == METER_TYPE_NONE and self._has_volume_zones():
            return self.async_show_form(
                step_id="installation_reconfiguration",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "meter_required_by_volume_zones"},
            )
        self._meter_type = str(user_input[CONF_METER_TYPE])
        self._pending_installation = {
            CONF_NAME: user_input[CONF_NAME],
            CONF_MAIN_VALVE: user_input.get(CONF_MAIN_VALVE),
        }
        if self._meter_type == METER_TYPE_NONE:
            return await self._finish_installation_reconfiguration(
                {CONF_METER_TYPE: METER_TYPE_NONE}
            )
        return await self.async_step_installation_reconfiguration_meter()

    async def async_step_installation_reconfiguration_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the selected meter's required fields during aggregate reconfiguration."""
        schema = _meter_details_schema(self._meter_type)
        if user_input is None:
            suggested = dict(self.config_entry.data)
            if self._meter_type == METER_TYPE_PULSE:
                suggested["pulse_factor_mode"] = "liters_per_pulse"
                suggested["pulse_factor"] = self.config_entry.data.get(CONF_LITERS_PER_PULSE)
            return self.async_show_form(
                step_id="installation_reconfiguration_meter",
                data_schema=self.add_suggested_values_to_schema(schema, suggested),
            )
        meter, error = _meter_data({CONF_METER_TYPE: self._meter_type, **user_input})
        if error is not None:
            return self.async_show_form(
                step_id="installation_reconfiguration_meter",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
            )
        return await self._finish_installation_reconfiguration(meter)

    async def _finish_installation_reconfiguration(
        self, meter: Mapping[str, object]
    ) -> ConfigFlowResult:
        data = {**self._pending_installation, **meter}
        candidate = _owned_endpoints(data, ())
        async with _ACTUATOR_OWNERSHIP_LOCK:
            if _ownership_conflicts(
                self.hass,
                candidate,
                excluding_entry_id=self.config_entry.entry_id,
                exclude_installation=True,
            ):
                return self.async_abort(reason="actuator_already_owned")
            return self._update_installation(
                data,
                title=str(data[CONF_NAME]),
                remove_meter_fields=True,
                clear_reconfiguration=True,
            )

    def _update_installation(
        self,
        changes: Mapping[str, object],
        *,
        title: str | None = None,
        remove_meter_fields: bool = False,
        clear_reconfiguration: bool = False,
    ) -> ConfigFlowResult:
        data = dict(self.config_entry.data)
        if remove_meter_fields:
            for key in (CONF_METER_ENTITY, CONF_LITERS_PER_PULSE):
                data.pop(key, None)
        data.update(changes)
        if clear_reconfiguration:
            data.pop(CONF_NEEDS_RECONFIGURATION, None)
        self.hass.config_entries.async_update_entry(
            self.config_entry, title=title or self.config_entry.title, data=data
        )
        return self.async_create_entry(data={})

    def _has_volume_zones(self) -> bool:
        return any(
            zone.data.get(CONF_CONTROL_TYPE) == CONTROL_TYPE_VOLUME
            for zone in self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        )

    def _manager(self) -> IrrigationManager | None:
        manager = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        return cast(IrrigationManager, manager) if manager is not None else None

    async def async_step_installation_releases(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update both durable installation releases."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        schema = vol.Schema(
            {
                vol.Required(CONF_OPERATION_ENABLED): BooleanSelector(),
                vol.Required(CONF_AUTOMATION_ENABLED): BooleanSelector(),
            }
        )
        if user_input is None:
            snapshot = manager.snapshot()
            return self.async_show_form(
                step_id="installation_releases",
                data_schema=self.add_suggested_values_to_schema(
                    schema,
                    {
                        CONF_OPERATION_ENABLED: snapshot.operation_enabled,
                        CONF_AUTOMATION_ENABLED: snapshot.automation_enabled,
                    },
                ),
            )
        self._pending_release_input = {
            CONF_OPERATION_ENABLED: bool(user_input[CONF_OPERATION_ENABLED]),
            CONF_AUTOMATION_ENABLED: bool(user_input[CONF_AUTOMATION_ENABLED]),
        }
        if (
            not self._pending_release_input[CONF_AUTOMATION_ENABLED]
            and manager.automatic_execution_active()
        ):
            return await self.async_step_installation_automation_disable()
        return await self._apply_installation_releases(stop_active=False)

    async def async_step_installation_automation_disable(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask whether an active automatic execution should stop or finish."""
        if user_input is None:
            return self.async_show_form(
                step_id="installation_automation_disable",
                data_schema=_active_automatic_schema(),
            )
        return await self._apply_installation_releases(
            stop_active=user_input["active_execution"] == "stop"
        )

    async def _apply_installation_releases(self, *, stop_active: bool) -> ConfigFlowResult:
        manager = self._manager()
        pending = self._pending_release_input
        if manager is None or pending is None:
            return self.async_abort(reason="release_change_not_pending")
        self._pending_release_input = None
        operation = await manager.async_set_installation_operation(
            enabled=pending[CONF_OPERATION_ENABLED]
        )
        automation = await manager.async_set_installation_automation(
            enabled=pending[CONF_AUTOMATION_ENABLED], stop_active=stop_active
        )
        return await self._show_action_result({**operation, **automation})

    async def async_step_emergency_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Execute the emergency stop immediately."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        await manager.async_emergency_stop()
        return await self._show_action_result({"emergency_stop": True})

    async def async_step_reset_safety(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require inspection confirmation before clearing the safety lock."""
        schema = vol.Schema({vol.Required("confirm_reset", default=False): BooleanSelector()})
        if user_input is None or user_input.get("confirm_reset") is not True:
            return self.async_show_form(
                step_id="reset_safety",
                data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
                errors={"base": "reset_confirmation_required"} if user_input else None,
            )
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        await manager.async_reset_safety_lock()
        return await self._show_action_result({"safety_lock": "cleared"})

    async def async_step_replan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Recalculate unstarted automatic irrigation orders."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        return await self._show_action_result(await manager.async_plan_automatic())

    async def async_step_physical_meter_correction(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Correct the future-facing physical meter total."""
        if self.config_entry.data.get(CONF_METER_TYPE) == METER_TYPE_NONE:
            return self.async_abort(reason="meter_not_configured")
        schema = vol.Schema(
            {
                vol.Required("physical_total_liters"): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=1_000_000_000,
                        step=0.001,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=UnitOfVolume.LITERS,
                    )
                ),
                vol.Optional("reason"): TextSelector(),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="physical_meter_correction", data_schema=schema)
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        try:
            result = await manager.async_correct_physical_meter(
                physical_total_liters=float(user_input["physical_total_liters"]),
                reason=str(reason) if (reason := user_input.get("reason")) else None,
            )
        except HomeAssistantError, ValueError:
            return self.async_show_form(
                step_id="physical_meter_correction",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "meter_correction_failed"},
            )
        return await self._show_action_result(result)

    async def _show_action_result(self, result: Mapping[str, object]) -> ConfigFlowResult:
        self._action_result = json.dumps(result, ensure_ascii=True, sort_keys=True)
        return await self.async_step_action_result()

    async def async_step_action_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the completed action result."""
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="action_result",
            data_schema=vol.Schema({}),
            description_placeholders={"result": self._action_result},
        )
