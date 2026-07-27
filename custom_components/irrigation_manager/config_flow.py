"""Version 2 config and zone subentry flows for Irrigation Manager."""

import asyncio
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
from homeassistant.data_entry_flow import section
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


def _localized_enabled(language: str, enabled: bool) -> str:
    """Return the user-facing state of one independent release."""
    if language == "de":
        return "Aktiviert" if enabled else "Deaktiviert"
    return "Enabled" if enabled else "Disabled"


def _localized_installation_status(language: str, enabled: bool, locked: bool) -> str:
    """Give the safety lock precedence over the operation release."""
    if locked:
        return "Sicherheitssperre" if language == "de" else "Safety lock"
    return _localized_enabled(language, enabled)


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


def _weekly_schedule_schema(control_type: str) -> vol.Schema:
    schema: dict[object, object] = {}
    for weekday in WEEKDAYS:
        schema[vol.Optional(weekday)] = section(
            vol.Schema(
                {
                    vol.Optional("start"): TimeSelector(),
                    vol.Optional("end"): TimeSelector(),
                    vol.Optional("target"): NumberSelector(
                        NumberSelectorConfig(
                            min=0.001,
                            max=1_000_000,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement=(
                                UnitOfTime.SECONDS
                                if control_type == CONTROL_TYPE_TIME
                                else UnitOfVolume.LITERS
                            ),
                        )
                    ),
                }
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
        day_values = {
            field: row[field] for field in ("start", "end", "target") if row.get(field) is not None
        }
        if day_values:
            values[weekday] = day_values
    return values


def _canonical_weekly_schedule(
    user_input: Mapping[str, Any], *, control_type: str, volume_max_runtime: float | None
) -> tuple[list[dict[str, object]], str | None]:
    """Normalize and validate exactly seven fixed weekday slots."""
    schedule: list[dict[str, object]] = []
    intervals: list[tuple[float, float]] = []
    week_seconds = 7 * 86_400
    for weekday_index, weekday in enumerate(WEEKDAYS):
        row_input = user_input.get(weekday, {})
        if not isinstance(row_input, Mapping):
            return [], "schedule_row_invalid"
        start_value = row_input.get("start")
        end_value = row_input.get("end")
        target_value = row_input.get("target")
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
        return self.async_show_form(
            step_id="create", data_schema=_installation_basics_schema(), last_step=False
        )

    async def async_step_installation_hardware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the optional main valve."""
        if user_input is not None:
            self._installation[CONF_MAIN_VALVE] = user_input.get(CONF_MAIN_VALVE)
            return await self.async_step_installation_meter()
        return self.async_show_form(
            step_id="installation_hardware",
            data_schema=_installation_main_valve_schema(),
            last_step=False,
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
        return self.async_show_form(
            step_id="installation_meter", data_schema=schema, last_step=False
        )

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
                    last_step=False,
                )
            self._installation.update(meter)
            return await self.async_step_installation_zone()
        return self.async_show_form(
            step_id="installation_meter_details", data_schema=schema, last_step=False
        )

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
                    last_step=False,
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
        return self.async_show_form(
            step_id="installation_zone", data_schema=schema, last_step=False
        )

    async def async_step_installation_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the installation and first zone after the seven-day schedule."""
        schema = _weekly_schedule_schema(str(self._first_zone[CONF_CONTROL_TYPE]))
        if user_input is None:
            return self.async_show_form(
                step_id="installation_schedule", data_schema=schema, last_step=True
            )
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
                last_step=True,
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
                    last_step=False,
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
        return self.async_show_form(step_id="minimal", data_schema=schema, last_step=False)

    async def async_step_minimal_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Validate and save all seven weekday rows for a new zone."""
        schema = _weekly_schedule_schema(str(self._zone[CONF_CONTROL_TYPE]))
        if user_input is None:
            return self.async_show_form(
                step_id="minimal_schedule", data_schema=schema, last_step=True
            )
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
                last_step=True,
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
                last_step=False,
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
                last_step=False,
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
        schema = _weekly_schedule_schema(str(self._zone[CONF_CONTROL_TYPE]))
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_minimal_schedule",
                data_schema=self.add_suggested_values_to_schema(
                    schema, _weekly_schedule_form_values(subentry.data.get(CONF_WEEKLY_SCHEDULE))
                ),
                last_step=True,
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
                last_step=True,
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
        """Expose zone actions appropriate to the current release state."""
        manager = self._manager()
        zone = self._get_reconfigure_subentry()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        zone_id = zone.unique_id or zone.subentry_id
        snapshot = manager.snapshot()
        operation_enabled = snapshot.zone_operation_enabled[zone_id]
        automation_enabled = snapshot.zone_automation_enabled[zone_id]
        return self.async_show_menu(
            step_id="releases",
            menu_options=[
                "deactivate_zone" if operation_enabled else "activate_zone",
                ("disable_zone_automatic" if automation_enabled else "enable_zone_automatic"),
            ],
            description_placeholders={
                "zone_status": _localized_enabled(self.hass.config.language, operation_enabled),
                "automatic_status": _localized_enabled(
                    self.hass.config.language, automation_enabled
                ),
            },
        )

    async def async_step_activate_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Activate the zone without changing its automatic release."""
        manager = self._manager()
        zone = self._get_reconfigure_subentry()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        if self._zone_requires_reconfiguration():
            return self.async_abort(reason="reconfiguration_required")
        try:
            await manager.async_set_zone_operation(zone_subentry_id=zone.subentry_id, enabled=True)
        except HomeAssistantError as err:
            return self._abort_zone_action_error(err)
        return self.async_abort(reason="zone_activated")

    async def async_step_deactivate_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Deactivate the zone without changing its automatic release."""
        manager = self._manager()
        zone = self._get_reconfigure_subentry()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        await manager.async_set_zone_operation(zone_subentry_id=zone.subentry_id, enabled=False)
        return self.async_abort(reason="zone_deactivated")

    async def async_step_enable_zone_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Enable automatic irrigation for the zone."""
        manager = self._manager()
        zone = self._get_reconfigure_subentry()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        if self._zone_requires_reconfiguration():
            return self.async_abort(reason="reconfiguration_required")
        try:
            await manager.async_set_zone_automation(
                zone_subentry_id=zone.subentry_id, enabled=True, stop_active=False
            )
        except HomeAssistantError as err:
            return self._abort_zone_action_error(err)
        return self.async_abort(reason="zone_automatic_enabled")

    async def async_step_disable_zone_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Disable automatic irrigation and optionally stop its active execution."""
        manager = self._manager()
        zone = self._get_reconfigure_subentry()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        if user_input is None and manager.automatic_execution_active(
            zone_subentry_id=zone.subentry_id
        ):
            return self.async_show_form(
                step_id="disable_zone_automatic",
                data_schema=_active_automatic_schema(),
                last_step=True,
            )
        stop_active = bool(user_input and user_input["active_execution"] == "stop")
        await manager.async_set_zone_automation(
            zone_subentry_id=zone.subentry_id,
            enabled=False,
            stop_active=stop_active,
        )
        return self.async_abort(
            reason=("zone_automatic_disabled_stopped" if stop_active else "zone_automatic_disabled")
        )

    def _abort_zone_action_error(self, error: HomeAssistantError) -> SubentryFlowResult:
        """Turn zone manager failures into visible, actionable flow results."""
        return self.async_abort(
            reason="action_failed", description_placeholders={"error": str(error)}
        )

    def _zone_requires_reconfiguration(self) -> bool:
        """Return whether installation or this zone still blocks activation."""
        return (
            self._get_entry().data.get(CONF_NEEDS_RECONFIGURATION) is True
            or self._get_reconfigure_subentry().data.get(CONF_NEEDS_RECONFIGURATION) is True
        )

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
        self._meter_type = METER_TYPE_NONE
        self._pending_installation: dict[str, object] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Expose configuration and actions appropriate to the current state."""
        manager = self._manager()
        snapshot = manager.snapshot() if manager is not None else None
        locked = (
            snapshot is not None and getattr(snapshot, "installation_safety_lock", None) is not None
        )
        options = ["configuration", "releases", "replan"]
        if locked:
            options.append("reset_safety")
        if self.config_entry.data.get(CONF_METER_TYPE) != METER_TYPE_NONE:
            options.append("physical_meter_correction")
        return self.async_show_menu(step_id="init", menu_options=options)

    async def async_step_releases(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Expose installation operation and automatic irrigation controls."""
        manager = self._manager()
        snapshot = manager.snapshot() if manager is not None else None
        operation_enabled = (
            snapshot.operation_enabled
            if snapshot is not None
            else bool(self.config_entry.data.get(CONF_OPERATION_ENABLED, True))
        )
        automation_enabled = (
            snapshot.automation_enabled
            if snapshot is not None
            else bool(self.config_entry.data.get(CONF_AUTOMATION_ENABLED, True))
        )
        locked = (
            snapshot is not None and getattr(snapshot, "installation_safety_lock", None) is not None
        )
        options: list[str] = []
        if operation_enabled:
            options.append("deactivate_installation")
        else:
            options.append("activate_installation")
        if automation_enabled:
            options.append("disable_automatic")
        else:
            options.append("enable_automatic")
        return self.async_show_menu(
            step_id="releases",
            menu_options=options,
            description_placeholders={
                "installation_status": (
                    _localized_installation_status(
                        self.hass.config.language, operation_enabled, locked
                    )
                ),
                "automatic_status": _localized_enabled(
                    self.hass.config.language, automation_enabled
                ),
            },
        )

    async def async_step_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the atomic installation configuration wizard with its name."""
        schema = _installation_basics_schema()
        if user_input is None:
            self._pending_installation = dict(self.config_entry.data)
            return self.async_show_form(
                step_id="configuration",
                data_schema=self.add_suggested_values_to_schema(schema, self._pending_installation),
                last_step=False,
            )
        self._pending_installation[CONF_NAME] = user_input[CONF_NAME]
        return await self.async_step_configuration_main_valve()

    async def async_step_configuration_main_valve(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain and collect the optional shared main valve."""
        schema = _installation_main_valve_schema()
        if user_input is not None:
            self._pending_installation[CONF_MAIN_VALVE] = user_input.get(CONF_MAIN_VALVE)
            return await self.async_step_configuration_meter()
        return self.async_show_form(
            step_id="configuration_main_valve",
            data_schema=self.add_suggested_values_to_schema(schema, self._pending_installation),
            last_step=False,
        )

    async def async_step_configuration_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain and collect the water measurement type."""
        schema = _meter_type_schema()
        if user_input is not None:
            self._meter_type = str(user_input[CONF_METER_TYPE])
            if self._meter_type == METER_TYPE_NONE and self._has_volume_zones():
                return self.async_show_form(
                    step_id="configuration_meter",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "meter_required_by_volume_zones"},
                    last_step=False,
                )
            self._pending_installation[CONF_METER_TYPE] = self._meter_type
            if self._meter_type == METER_TYPE_NONE:
                return await self._finish_configuration({CONF_METER_TYPE: METER_TYPE_NONE})
            return await self.async_step_configuration_meter_details()
        return self.async_show_form(
            step_id="configuration_meter",
            data_schema=self.add_suggested_values_to_schema(schema, self._pending_installation),
            last_step=False,
        )

    async def async_step_configuration_meter_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect only fields relevant to the selected water meter."""
        schema = _meter_details_schema(self._meter_type)
        if user_input is None:
            suggested = dict(self._pending_installation)
            if self._meter_type == METER_TYPE_PULSE:
                suggested["pulse_factor_mode"] = "liters_per_pulse"
                suggested["pulse_factor"] = self._pending_installation.get(CONF_LITERS_PER_PULSE)
            return self.async_show_form(
                step_id="configuration_meter_details",
                data_schema=self.add_suggested_values_to_schema(schema, suggested),
                last_step=True,
            )
        meter, error = _meter_data({CONF_METER_TYPE: self._meter_type, **user_input})
        if error is not None:
            return self.async_show_form(
                step_id="configuration_meter_details",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
                last_step=True,
            )
        return await self._finish_configuration(meter)

    async def _finish_configuration(self, meter: Mapping[str, object]) -> ConfigFlowResult:
        data = {**self._pending_installation, **meter}
        for key in (CONF_METER_ENTITY, CONF_LITERS_PER_PULSE):
            if data[CONF_METER_TYPE] == METER_TYPE_NONE or key not in meter:
                data.pop(key, None)
        data.pop(CONF_NEEDS_RECONFIGURATION, None)
        candidate = _owned_endpoints(data, ())
        async with _ACTUATOR_OWNERSHIP_LOCK:
            if _ownership_conflicts(
                self.hass,
                candidate,
                excluding_entry_id=self.config_entry.entry_id,
                exclude_installation=True,
            ):
                return self.async_abort(reason="actuator_already_owned")
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=str(data[CONF_NAME]), data=data
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

    def _requires_reconfiguration(self) -> bool:
        """Return whether installation or zone configuration still blocks activation."""
        return self.config_entry.data.get(CONF_NEEDS_RECONFIGURATION) is True or any(
            zone.data.get(CONF_NEEDS_RECONFIGURATION) is True
            for zone in self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        )

    def _localized_result(self, key: str, **values: object) -> str:
        """Render a localized human action result without exposing technical data."""
        messages = {
            "de": {
                "activated": "Die Bewässerungsanlage wurde aktiviert.",
                "deactivated": (
                    "Die Bewässerungsanlage wurde deaktiviert; "
                    "der aktive Bewässerungsvorgang wurde beendet."
                ),
                "automatic_enabled": (
                    "Die automatische Bewässerung wurde aktiviert und die "
                    "Bewässerungsplanung neu berechnet."
                ),
                "automatic_disabled": "Die automatische Bewässerung wurde deaktiviert.",
                "automatic_disabled_stopped": (
                    "Die automatische Bewässerung wurde deaktiviert und der aktive automatische "
                    "Bewässerungsvorgang gestoppt."
                ),
                "reset": "Die Sicherheitssperre wurde nach bestätigter Prüfung zurückgesetzt.",
                "replan": (
                    "Bewässerungsplanung neu berechnet: {created} erstellt, "
                    "{replaced} ersetzt, {removed} entfernt."
                ),
                "meter": "Zählerstand korrigiert: {total} l (Änderung {difference} l).",
            },
            "en": {
                "activated": "The irrigation installation was activated.",
                "deactivated": (
                    "The irrigation installation was deactivated and active irrigation was stopped."
                ),
                "automatic_enabled": "Automatic irrigation was enabled and replanned.",
                "automatic_disabled": "Automatic irrigation was disabled.",
                "automatic_disabled_stopped": (
                    "Automatic irrigation was disabled and the active automatic execution was "
                    "stopped."
                ),
                "reset": "The safety lock was reset after the inspection was confirmed.",
                "replan": (
                    "Replanning completed: {created} created, {replaced} replaced, "
                    "{removed} removed."
                ),
                "meter": "Meter total corrected to {total} L (change {difference} L).",
            },
        }
        language = "de" if self.hass.config.language == "de" else "en"
        return messages[language][key].format(**values)

    async def async_step_activate_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Activate installation operation."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        if self._requires_reconfiguration():
            return self.async_abort(reason="reconfiguration_required")
        try:
            await manager.async_set_installation_operation(enabled=True)
        except HomeAssistantError as err:
            return self._abort_action_error(err)
        return await self._show_action_result(self._localized_result("activated"))

    async def async_step_deactivate_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Deactivate installation operation."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        await manager.async_set_installation_operation(enabled=False)
        return await self._show_action_result(self._localized_result("deactivated"))

    async def async_step_enable_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable automatic irrigation."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        if self._requires_reconfiguration():
            return self.async_abort(reason="reconfiguration_required")
        try:
            await manager.async_set_installation_automation(enabled=True, stop_active=False)
        except HomeAssistantError as err:
            return self._abort_action_error(err)
        return await self._show_action_result(self._localized_result("automatic_enabled"))

    def _abort_action_error(self, error: HomeAssistantError) -> ConfigFlowResult:
        """Turn manager action failures into visible, actionable flow results."""
        return self.async_abort(
            reason="action_failed", description_placeholders={"error": str(error)}
        )

    async def async_step_disable_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Disable automatic irrigation, asking how to handle an active execution."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        if user_input is None and manager.automatic_execution_active():
            return self.async_show_form(
                step_id="disable_automatic",
                data_schema=_active_automatic_schema(),
                last_step=True,
            )
        stop_active = bool(user_input and user_input["active_execution"] == "stop")
        await manager.async_set_installation_automation(enabled=False, stop_active=stop_active)
        result_key = "automatic_disabled_stopped" if stop_active else "automatic_disabled"
        return await self._show_action_result(self._localized_result(result_key))

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
        return await self._show_action_result(self._localized_result("reset"))

    async def async_step_replan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Recalculate unstarted automatic irrigation orders."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        report = await manager.async_plan_automatic()
        return await self._show_action_result(
            self._localized_result(
                "replan",
                created=report.get("created", 0),
                replaced=report.get("replaced", 0),
                removed=report.get("removed", 0),
            )
        )

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
        return await self._show_action_result(
            self._localized_result(
                "meter",
                total=result.get("new_total_liters", user_input["physical_total_liters"]),
                difference=result.get("difference_liters", 0),
            )
        )

    async def _show_action_result(self, result: str) -> ConfigFlowResult:
        self._action_result = result
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
