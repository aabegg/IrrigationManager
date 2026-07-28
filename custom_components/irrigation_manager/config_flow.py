"""Version 2 config and zone subentry flows for Irrigation Manager."""

import asyncio
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from homeassistant.const import CONF_NAME, Platform, UnitOfVolume
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    DurationSelectorConfig,
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
    CONF_BASE_TARGET,
    CONF_CALIBRATION_CONFIRMATION_INTERVAL,
    CONF_CALIBRATION_MAX_DURATION,
    CONF_CALIBRATION_SETTLE_SECONDS,
    CONF_CONTROL_TYPE,
    CONF_EXPECTED_FLOW_L_MIN,
    CONF_LITERS_PER_PULSE,
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
    CONF_METER_TYPE,
    CONF_NEEDS_RECONFIGURATION,
    CONF_OPERATION_ENABLED,
    CONF_PLANT_SITE_MODULE_ENABLED,
    CONF_SEASONAL_FACTORS,
    CONF_SEASONAL_MODULE_ENABLED,
    CONF_SOAK_MODULE_ENABLED,
    CONF_SUBAREAS,
    CONF_USE_PLANT_SITE_MODEL,
    CONF_USE_SEASONAL_ADJUSTMENT,
    CONF_VOLUME_MAX_RUNTIME,
    CONF_WEATHER_MODULE_ENABLED,
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
from .duration import format_duration, parse_duration
from .manager import IrrigationManager
from .profiles import (
    APPLICATION_PROFILE_OPTIONS,
    DEVELOPMENT_STAGE_OPTIONS,
    EXPOSURE_OPTIONS,
    PLANT_PROFILE_OPTIONS,
    SOIL_PROFILE_OPTIONS,
    ProfileRecommendation,
    recommend_profiles,
)
from .scheduler import planned_volume_duration_seconds
from .seasonal import (
    DEFAULT_SEASONAL_FACTOR,
    MAX_SEASONAL_FACTOR,
    MIN_SEASONAL_FACTOR,
    MONTHS,
    canonical_seasonal_factors,
)
from .zone_config import positive_number

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


def _extensions_schema() -> vol.Schema:
    """Expose only extension modules completed in the current stage."""
    return vol.Schema(
        {
            vol.Required(CONF_PLANT_SITE_MODULE_ENABLED, default=False): BooleanSelector(),
            vol.Required(CONF_SEASONAL_MODULE_ENABLED, default=False): BooleanSelector(),
        }
    )


def _target_selector(control_type: str) -> DurationSelector | NumberSelector:
    if control_type == CONTROL_TYPE_TIME:
        return _duration_selector()
    return NumberSelector(
        NumberSelectorConfig(
            min=0.001,
            max=1_000_000,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement=UnitOfVolume.LITERS,
        )
    )


def _baseline_schema(control_type: str) -> vol.Schema:
    return vol.Schema({vol.Optional(CONF_BASE_TARGET): _target_selector(control_type)})


def _canonical_target(value: object, control_type: str) -> float:
    target = parse_duration(value) if control_type == CONTROL_TYPE_TIME else positive_number(value)
    if target is None or target <= 0 or not math.isfinite(target):
        raise ValueError("Target must be positive")
    return float(target)


def _set_optional_baseline(
    data: dict[str, Any], user_input: Mapping[str, Any], control_type: str
) -> None:
    value = user_input.get(CONF_BASE_TARGET)
    if value is None:
        data.pop(CONF_BASE_TARGET, None)
        return
    data[CONF_BASE_TARGET] = _canonical_target(value, control_type)


def _plant_usage_schema(default: bool = False) -> vol.Schema:
    return vol.Schema({vol.Required(CONF_USE_PLANT_SITE_MODEL, default=default): BooleanSelector()})


def _seasonal_usage_schema(default: bool = False) -> vol.Schema:
    """Choose whether one zone uses seasonal adjustment."""
    return vol.Schema(
        {vol.Required(CONF_USE_SEASONAL_ADJUSTMENT, default=default): BooleanSelector()}
    )


def _seasonal_curve_schema(factors: Mapping[str, object] | None = None) -> vol.Schema:
    """Collect a complete bounded twelve-month curve with native selectors."""
    existing = factors or {}
    return vol.Schema(
        {
            vol.Required(
                month, default=existing.get(month, DEFAULT_SEASONAL_FACTOR)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SEASONAL_FACTOR,
                    max=MAX_SEASONAL_FACTOR,
                    step=0.01,
                    mode=NumberSelectorMode.BOX,
                )
            )
            for month in MONTHS
        }
    )


@dataclass(frozen=True, slots=True)
class _SeasonalCurveSubmission:
    """Shared validation result for every seasonal curve flow."""

    schema: vol.Schema
    factors: dict[str, float] | None
    errors: dict[str, str] | None


def _seasonal_curve_submission(
    user_input: Mapping[str, object] | None,
    *,
    existing: Mapping[str, object] | None = None,
) -> _SeasonalCurveSubmission:
    """Validate one seasonal curve submission for any config-flow context."""
    schema = _seasonal_curve_schema(existing)
    if user_input is None:
        return _SeasonalCurveSubmission(schema, None, None)
    try:
        factors = canonical_seasonal_factors(user_input)
    except ValueError:
        return _SeasonalCurveSubmission(schema, None, {"base": "seasonal_curve_invalid"})
    return _SeasonalCurveSubmission(schema, factors, None)


@dataclass(frozen=True, slots=True)
class _SeasonalReviewSubmission:
    """Shared preview and confirmation state for every seasonal flow."""

    preview: str
    confirmed: bool
    errors: dict[str, str] | None


def _seasonal_review_submission(
    *,
    language: str,
    zone: Mapping[str, object],
    factors: Mapping[str, float],
    user_input: Mapping[str, object] | None,
) -> _SeasonalReviewSubmission:
    """Build the common seasonal preview and require explicit confirmation."""
    preview = _seasonal_preview(
        language=language,
        control_type=str(zone[CONF_CONTROL_TYPE]),
        base_target=positive_number(zone.get(CONF_BASE_TARGET)),
        factors=factors,
    )
    confirmed = bool(user_input and user_input.get("confirm_seasonal_curve") is True)
    return _SeasonalReviewSubmission(
        preview=preview,
        confirmed=confirmed,
        errors=(
            {"base": "seasonal_confirmation_required"}
            if user_input is not None and not confirmed
            else None
        ),
    )


def _apply_seasonal_usage(
    zone: dict[str, Any],
    user_input: Mapping[str, object],
    *,
    reset_curve_when_disabled: bool,
) -> bool:
    """Apply the shared zone opt-in without discarding dormant curves on reconfigure."""
    enabled = user_input.get(CONF_USE_SEASONAL_ADJUSTMENT) is True
    zone[CONF_USE_SEASONAL_ADJUSTMENT] = enabled
    if not enabled and reset_curve_when_disabled:
        zone[CONF_SEASONAL_FACTORS] = canonical_seasonal_factors({})
    return enabled


def _seasonal_preview(
    *, language: str, control_type: str, base_target: float | None, factors: Mapping[str, float]
) -> str:
    """Render explicit month-anchor targets for the confirmation step."""
    labels = (
        (
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember",
        )
        if language == "de"
        else tuple(month.capitalize() for month in MONTHS)
    )
    lines: list[str] = []
    for month, label in zip(MONTHS, labels, strict=True):
        factor = factors[month]
        if base_target is None:
            target = "—"
        elif control_type == CONTROL_TYPE_TIME:
            total_seconds = base_target * factor
            hours, remainder = divmod(total_seconds, 3_600)
            minutes, seconds = divmod(remainder, 60)
            target = f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}".rstrip("0").rstrip(".")
            if seconds.is_integer():
                target = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            target = f"{base_target * factor:.2f} L"
        lines.append(f"{label}: x{factor:.2f} → {target}")
    return "\n".join(lines)


def _seasonal_confirmation_schema() -> vol.Schema:
    return vol.Schema({vol.Required("confirm_seasonal_curve", default=False): BooleanSelector()})


def _reconfigure_plant_schema(default: bool, has_subareas: bool) -> vol.Schema:
    schema: dict[object, object] = {
        vol.Required(CONF_USE_PLANT_SITE_MODEL, default=default): BooleanSelector()
    }
    if has_subareas:
        schema[vol.Optional("replace_subareas", default=False)] = BooleanSelector()
    return vol.Schema(schema)


def _subarea_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("name"): TextSelector(),
            vol.Required("area_m2"): NumberSelector(
                NumberSelectorConfig(min=0.01, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required("plant_profile"): _choice(list(PLANT_PROFILE_OPTIONS), "plant_profile"),
            vol.Required("development_stage"): _choice(
                list(DEVELOPMENT_STAGE_OPTIONS), "development_stage"
            ),
            vol.Required("exposure"): _choice(list(EXPOSURE_OPTIONS), "exposure"),
            vol.Required("soil_profile"): _choice(list(SOIL_PROFILE_OPTIONS), "soil_profile"),
            vol.Required("application_profile"): _choice(
                list(APPLICATION_PROFILE_OPTIONS), "application_profile"
            ),
            vol.Optional("advanced"): section(
                vol.Schema(
                    {
                        vol.Optional("slope_percent"): NumberSelector(
                            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
                        ),
                        vol.Optional("mulched", default=False): BooleanSelector(),
                        vol.Optional("relative_application_rate"): NumberSelector(
                            NumberSelectorConfig(min=0.01, step=0.01, mode=NumberSelectorMode.BOX)
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("add_another", default=False): BooleanSelector(),
        }
    )


def _accept_subarea(target: list[dict[str, object]], user_input: Mapping[str, Any]) -> bool:
    """Append one normalized subarea and return whether another was requested."""
    subarea = {
        key: value for key, value in user_input.items() if key not in {"add_another", "advanced"}
    }
    advanced = user_input.get("advanced")
    if isinstance(advanced, Mapping):
        subarea.update(advanced)
    subarea["id"] = uuid4().hex
    target.append(subarea)
    return user_input.get("add_another") is True


def _recommendation_placeholders(
    language: str, recommendation: ProfileRecommendation | None
) -> dict[str, str]:
    if recommendation is None:
        return {"recommendation": ""}
    if language == "de":
        levels = {"low": "niedrig", "medium": "mittel", "high": "hoch"}
        tendencies = {
            "small_frequent": "eher kleine, häufigere Gaben",
            "balanced": "ausgewogene Gaben",
            "deep_infrequent": "eher tiefe, seltenere Gaben",
        }
        messages = {
            "missing_name": "Name fehlt",
            "missing_or_invalid_area": "Fläche fehlt oder ist ungültig",
            "missing_plant_profile": "Pflanzenprofil fehlt",
            "custom_plant_profile": "benutzerdefiniertes Pflanzenprofil ist nicht klassifiziert",
            "unknown_plant_profile": "Pflanzenprofil ist unbekannt",
            "missing_soil_profile": "Bodenprofil fehlt",
            "custom_soil_profile": "benutzerdefiniertes Bodenprofil ist nicht klassifiziert",
            "unknown_soil_profile": "Bodenprofil ist unbekannt",
            "missing_application_profile": "Ausbringungsprofil fehlt",
            "custom_application_profile": (
                "benutzerdefiniertes Ausbringungsprofil ist nicht klassifiziert"
            ),
            "unknown_application_profile": "Ausbringungsprofil ist unbekannt",
            "missing_or_unknown_development_stage": "Entwicklungszustand fehlt oder ist unbekannt",
            "missing_or_unknown_exposure": "Exposition fehlt oder ist unbekannt",
            "no_subareas": "keine Teilfläche vorhanden",
            "subarea_conflicts": "Teilflächen unterscheiden sich deutlich",
            "complete_known_profiles": "alle Teilflächen verwenden vollständige Katalogprofile",
            "different_plant_water_need": "stark unterschiedlicher Pflanzenwasserbedarf",
            "different_soil_storage": "stark unterschiedliche Bodenspeicherung",
            "different_relative_application_rates": "unterschiedliche relative Ausbringungsraten",
            "invalid_mulch_ignored": "ungültige Mulchangabe wurde ignoriert",
            "invalid_slope_ignored": "ungültige Hangneigung wurde ignoriert",
            "invalid_relative_application_rate_ignored": (
                "ungültige Ausbringungsrate wurde ignoriert"
            ),
        }
        text = (
            f"Qualität: {levels[recommendation.quality]}; relativer Wasserbedarf: "
            f"{levels[recommendation.water_need]}; Trockenheitsempfindlichkeit: "
            f"{levels[recommendation.drought_sensitivity]}; Speicher: "
            f"{levels[recommendation.soil_storage]}; Versickerung: "
            f"{levels[recommendation.infiltration]}; Eignung für Teilgaben: "
            f"{levels[recommendation.soak_suitability]}; "
            f"{tendencies[recommendation.watering_tendency]}."
        )
        details = "; ".join(messages.get(item, item) for item in recommendation.reasons)
        text = f"{text} Gründe: {details}."
        if recommendation.conflicts:
            details = "; ".join(messages.get(item, item) for item in recommendation.conflicts)
            text = f"{text} Konflikte: {details}."
        if recommendation.warnings:
            details = "; ".join(messages.get(item, item) for item in recommendation.warnings)
            text = f"{text} Hinweise: {details}."
    else:
        messages = {
            "missing_name": "name is missing",
            "missing_or_invalid_area": "area is missing or invalid",
            "missing_plant_profile": "plant profile is missing",
            "custom_plant_profile": "custom plant profile is not classified",
            "unknown_plant_profile": "plant profile is unknown",
            "missing_soil_profile": "soil profile is missing",
            "custom_soil_profile": "custom soil profile is not classified",
            "unknown_soil_profile": "soil profile is unknown",
            "missing_application_profile": "application profile is missing",
            "custom_application_profile": "custom application profile is not classified",
            "unknown_application_profile": "application profile is unknown",
            "missing_or_unknown_development_stage": "development stage is missing or unknown",
            "missing_or_unknown_exposure": "exposure is missing or unknown",
            "no_subareas": "no subarea is available",
            "subarea_conflicts": "subareas differ materially",
            "complete_known_profiles": "all subareas use complete catalog profiles",
            "different_plant_water_need": "materially different plant water need",
            "different_soil_storage": "materially different soil storage",
            "different_relative_application_rates": "different relative application rates",
            "invalid_mulch_ignored": "invalid mulch input was ignored",
            "invalid_slope_ignored": "invalid slope was ignored",
            "invalid_relative_application_rate_ignored": "invalid application rate was ignored",
        }
        text = (
            f"Quality: {recommendation.quality}; relative water need: "
            f"{recommendation.water_need}; drought sensitivity: "
            f"{recommendation.drought_sensitivity}; storage: "
            f"{recommendation.soil_storage}; infiltration: "
            f"{recommendation.infiltration}; soak suitability: "
            f"{recommendation.soak_suitability}; "
            f"tendency: {recommendation.watering_tendency}."
        )
        details = "; ".join(messages.get(item, item) for item in recommendation.reasons)
        text = f"{text} Reasons: {details}."
        if recommendation.conflicts:
            details = "; ".join(messages.get(item, item) for item in recommendation.conflicts)
            text = f"{text} Conflicts: {details}."
        if recommendation.warnings:
            text = (
                f"{text} Notes: "
                f"{'; '.join(messages.get(item, item) for item in recommendation.warnings)}."
            )
    return {"recommendation": text}


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
        schema[vol.Optional(CONF_VOLUME_MAX_RUNTIME)] = _duration_selector()
    return vol.Schema(schema)


def _weekly_schedule_schema(control_type: str) -> vol.Schema:
    schema: dict[object, object] = {}
    for weekday in WEEKDAYS:
        schema[vol.Optional(weekday)] = section(
            vol.Schema(
                {
                    vol.Optional("start"): TimeSelector(),
                    vol.Optional("end"): TimeSelector(),
                    vol.Optional("target"): _target_selector(control_type),
                }
            )
        )
    return vol.Schema(schema)


def _duration_selector() -> DurationSelector:
    """Return a structured duration selector with unlimited total hours."""
    return DurationSelector(DurationSelectorConfig(enable_day=False, enable_second=True))


def _zone_form_values(data: Mapping[str, object]) -> dict[str, object]:
    """Format persisted seconds for one zone form."""
    values = dict(data)
    runtime = data.get(CONF_VOLUME_MAX_RUNTIME)
    if isinstance(runtime, int | float) and not isinstance(runtime, bool):
        values[CONF_VOLUME_MAX_RUNTIME] = format_duration(float(runtime))
    return values


def _form_duration(value: object, *, maximum: float = 604_800) -> float:
    """Validate one structured form value against its configured limit."""
    seconds = parse_duration(value)
    if seconds > maximum:
        raise ValueError("Duration exceeds its maximum")
    return seconds


def _weekly_schedule_form_values(schedule: object, *, control_type: str) -> dict[str, object]:
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
        if control_type == CONTROL_TYPE_TIME and "target" in day_values:
            day_values["target"] = format_duration(float(cast(float, day_values["target"])))
        if day_values:
            values[weekday] = day_values
    return values


def _canonical_weekly_schedule(
    user_input: Mapping[str, Any],
    *,
    control_type: str,
    base_target: float | None,
    volume_max_runtime: float | None,
    expected_flow_l_min: float | None = None,
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
        has_start = start_value not in (None, "")
        has_end = end_value not in (None, "")
        has_override = target_value is not None
        if has_start != has_end:
            return [], "schedule_row_incomplete"
        if not has_start:
            if has_override:
                return [], "schedule_row_incomplete"
            schedule.append({"weekday": weekday, "start": None, "end": None, "target": None})
            continue
        if base_target is None:
            return [], "schedule_baseline_required"
        try:
            start = time.fromisoformat(str(start_value))
            end = time.fromisoformat(str(end_value))
        except TypeError, ValueError:
            return [], "schedule_row_invalid"
        try:
            target_override = (
                _canonical_target(target_value, control_type) if has_override else None
            )
            target = target_override if target_override is not None else base_target
        except TypeError, ValueError:
            return [], "schedule_target_invalid"
        if target <= 0 or not math.isfinite(target):
            return [], "schedule_target_invalid"
        start_seconds = (
            weekday_index * 86_400 + start.hour * 3600 + start.minute * 60 + start.second
        )
        end_seconds = weekday_index * 86_400 + end.hour * 3600 + end.minute * 60 + end.second
        if end_seconds <= start_seconds:
            end_seconds += 86_400
        required_seconds = target
        if control_type == CONTROL_TYPE_VOLUME and volume_max_runtime is not None:
            required_seconds = planned_volume_duration_seconds(
                target_liters=target,
                max_runtime_seconds=volume_max_runtime,
                expected_flow_l_min=expected_flow_l_min,
            )
        if required_seconds is None or required_seconds > end_seconds - start_seconds:
            return [], "schedule_target_does_not_fit"
        intervals.append((start_seconds, end_seconds))
        schedule.append(
            {
                "weekday": weekday,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "target": target_override,
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
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize wizard state."""
        self._installation: dict[str, Any] = {}
        self._first_zone: dict[str, Any] = {}
        self._meter_type = METER_TYPE_NONE
        self._subareas: list[dict[str, object]] = []
        self._recommendation: ProfileRecommendation | None = None
        self._seasonal_factors: dict[str, float] = {}

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
                return await self.async_step_installation_extensions()
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
            return await self.async_step_installation_extensions()
        return self.async_show_form(
            step_id="installation_meter_details", data_schema=schema, last_step=False
        )

    async def async_step_installation_extensions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose completed optional modules without collecting their details."""
        if user_input is not None:
            self._installation.update(
                {
                    CONF_PLANT_SITE_MODULE_ENABLED: bool(
                        user_input[CONF_PLANT_SITE_MODULE_ENABLED]
                    ),
                    CONF_SEASONAL_MODULE_ENABLED: bool(user_input[CONF_SEASONAL_MODULE_ENABLED]),
                    CONF_WEATHER_MODULE_ENABLED: False,
                    CONF_SOAK_MODULE_ENABLED: False,
                }
            )
            return await self.async_step_installation_zone()
        return self.async_show_form(
            step_id="installation_extensions",
            data_schema=_extensions_schema(),
            last_step=False,
        )

    async def async_step_installation_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the mandatory first zone."""
        has_meter = self._installation.get(CONF_METER_TYPE) != METER_TYPE_NONE
        schema = _minimal_zone_schema(has_meter)
        if user_input is not None:
            control_type = str(user_input[CONF_CONTROL_TYPE])
            max_runtime: float | None = None
            if (
                control_type == CONTROL_TYPE_VOLUME
                and user_input.get(CONF_VOLUME_MAX_RUNTIME) is None
            ):
                return self.async_show_form(
                    step_id="installation_zone",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "volume_max_runtime_required"},
                    last_step=False,
                )
            if control_type == CONTROL_TYPE_VOLUME:
                try:
                    max_runtime = _form_duration(user_input[CONF_VOLUME_MAX_RUNTIME])
                except ValueError:
                    return self.async_show_form(
                        step_id="installation_zone",
                        data_schema=self.add_suggested_values_to_schema(schema, user_input),
                        errors={"base": "duration_format_invalid"},
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
                self._first_zone[CONF_VOLUME_MAX_RUNTIME] = max_runtime
            if self._installation[CONF_PLANT_SITE_MODULE_ENABLED]:
                return await self.async_step_installation_zone_plant()
            self._first_zone[CONF_USE_PLANT_SITE_MODEL] = False
            self._first_zone[CONF_SUBAREAS] = []
            return await self.async_step_installation_baseline()
        return self.async_show_form(
            step_id="installation_zone", data_schema=schema, last_step=False
        )

    async def async_step_installation_zone_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose whether the first zone uses plant and site profiles."""
        if user_input is not None:
            enabled = bool(user_input[CONF_USE_PLANT_SITE_MODEL])
            self._first_zone[CONF_USE_PLANT_SITE_MODEL] = enabled
            if not enabled:
                self._first_zone[CONF_SUBAREAS] = []
                return await self.async_step_installation_baseline()
            self._subareas = []
            return await self.async_step_installation_subarea()
        return self.async_show_form(
            step_id="installation_zone_plant",
            data_schema=_plant_usage_schema(),
            last_step=False,
        )

    async def async_step_installation_subarea(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect one subarea and repeat only when explicitly requested."""
        if user_input is not None:
            if _accept_subarea(self._subareas, user_input):
                return self.async_show_form(
                    step_id="installation_subarea",
                    data_schema=_subarea_schema(),
                    last_step=False,
                )
            self._first_zone[CONF_SUBAREAS] = list(self._subareas)
            self._recommendation = recommend_profiles(self._subareas)
            return await self.async_step_installation_baseline()
        return self.async_show_form(
            step_id="installation_subarea", data_schema=_subarea_schema(), last_step=False
        )

    async def async_step_installation_baseline(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the common target without applying profile data automatically."""
        control_type = str(self._first_zone[CONF_CONTROL_TYPE])
        schema = _baseline_schema(control_type)
        if user_input is not None:
            try:
                _set_optional_baseline(self._first_zone, user_input, control_type)
            except ValueError:
                return self.async_show_form(
                    step_id="installation_baseline",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "schedule_target_invalid"},
                    description_placeholders=_recommendation_placeholders(
                        self.hass.config.language, self._recommendation
                    ),
                )
            if self._installation.get(CONF_SEASONAL_MODULE_ENABLED) is True:
                return await self.async_step_first_zone_seasonal()
            self._first_zone[CONF_USE_SEASONAL_ADJUSTMENT] = False
            self._first_zone[CONF_SEASONAL_FACTORS] = canonical_seasonal_factors({})
            return await self.async_step_installation_schedule()
        return self.async_show_form(
            step_id="installation_baseline",
            data_schema=schema,
            description_placeholders=_recommendation_placeholders(
                self.hass.config.language, self._recommendation
            ),
            last_step=False,
        )

    async def async_step_first_zone_seasonal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose whether the first zone uses seasonal adjustment."""
        if user_input is None:
            return self.async_show_form(
                step_id="first_zone_seasonal",
                data_schema=_seasonal_usage_schema(),
                last_step=False,
            )
        enabled = _apply_seasonal_usage(
            self._first_zone, user_input, reset_curve_when_disabled=True
        )
        if not enabled:
            return await self.async_step_installation_schedule()
        return await self.async_step_first_zone_seasonal_curve()

    async def async_step_first_zone_seasonal_curve(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect a complete first-zone curve before previewing it."""
        submission = _seasonal_curve_submission(user_input)
        if submission.factors is None:
            return self.async_show_form(
                step_id="first_zone_seasonal_curve",
                data_schema=(
                    self.add_suggested_values_to_schema(submission.schema, user_input)
                    if user_input is not None
                    else submission.schema
                ),
                errors=submission.errors,
                last_step=False,
            )
        self._seasonal_factors = submission.factors
        return await self.async_step_first_zone_seasonal_review()

    async def async_step_first_zone_seasonal_review(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Preview and explicitly confirm the first-zone seasonal curve."""
        submission = _seasonal_review_submission(
            language=self.hass.config.language,
            zone=self._first_zone,
            factors=self._seasonal_factors,
            user_input=user_input,
        )
        if not submission.confirmed:
            return self.async_show_form(
                step_id="first_zone_seasonal_review",
                data_schema=_seasonal_confirmation_schema(),
                errors=submission.errors,
                description_placeholders={"preview": submission.preview},
                last_step=True,
            )
        self._first_zone[CONF_SEASONAL_FACTORS] = dict(self._seasonal_factors)
        return await self.async_step_installation_schedule()

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
            base_target=positive_number(self._first_zone.get(CONF_BASE_TARGET)),
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
        self._subareas: list[dict[str, object]] = []
        self._recommendation: ProfileRecommendation | None = None
        self._seasonal_factors: dict[str, float] = {}

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
            max_runtime: float | None = None
            if (
                control_type == CONTROL_TYPE_VOLUME
                and user_input.get(CONF_VOLUME_MAX_RUNTIME) is None
            ):
                return self.async_show_form(
                    step_id="minimal",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "volume_max_runtime_required"},
                    last_step=False,
                )
            if control_type == CONTROL_TYPE_VOLUME:
                try:
                    max_runtime = _form_duration(user_input[CONF_VOLUME_MAX_RUNTIME])
                except ValueError:
                    return self.async_show_form(
                        step_id="minimal",
                        data_schema=self.add_suggested_values_to_schema(schema, user_input),
                        errors={"base": "duration_format_invalid"},
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
                self._zone[CONF_VOLUME_MAX_RUNTIME] = max_runtime
            if self._get_entry().data.get(CONF_PLANT_SITE_MODULE_ENABLED) is True:
                return await self.async_step_plant_usage()
            self._zone[CONF_USE_PLANT_SITE_MODEL] = False
            self._zone[CONF_SUBAREAS] = []
            return await self.async_step_baseline()
        return self.async_show_form(step_id="minimal", data_schema=schema, last_step=False)

    async def async_step_plant_usage(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose whether a new zone uses the available profile module."""
        if user_input is not None:
            enabled = bool(user_input[CONF_USE_PLANT_SITE_MODEL])
            self._zone[CONF_USE_PLANT_SITE_MODEL] = enabled
            if not enabled:
                self._zone[CONF_SUBAREAS] = []
                return await self.async_step_baseline()
            self._subareas = []
            return await self.async_step_subarea()
        return self.async_show_form(
            step_id="plant_usage", data_schema=_plant_usage_schema(), last_step=False
        )

    async def async_step_subarea(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect repeated subareas for a new zone."""
        if user_input is not None:
            if _accept_subarea(self._subareas, user_input):
                return self.async_show_form(
                    step_id="subarea", data_schema=_subarea_schema(), last_step=False
                )
            self._zone[CONF_SUBAREAS] = list(self._subareas)
            self._recommendation = recommend_profiles(self._subareas)
            return await self.async_step_baseline()
        return self.async_show_form(step_id="subarea", data_schema=_subarea_schema())

    async def async_step_baseline(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm one common target for a new zone."""
        control_type = str(self._zone[CONF_CONTROL_TYPE])
        schema = _baseline_schema(control_type)
        if user_input is not None:
            try:
                _set_optional_baseline(self._zone, user_input, control_type)
            except ValueError:
                return self.async_show_form(
                    step_id="baseline",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "schedule_target_invalid"},
                    description_placeholders=_recommendation_placeholders(
                        self.hass.config.language, self._recommendation
                    ),
                )
            if self._get_entry().data.get(CONF_SEASONAL_MODULE_ENABLED) is True:
                return await self.async_step_seasonal()
            self._zone[CONF_USE_SEASONAL_ADJUSTMENT] = False
            self._zone[CONF_SEASONAL_FACTORS] = canonical_seasonal_factors({})
            return await self.async_step_minimal_schedule()
        return self.async_show_form(
            step_id="baseline",
            data_schema=schema,
            description_placeholders=_recommendation_placeholders(
                self.hass.config.language, self._recommendation
            ),
            last_step=False,
        )

    async def async_step_seasonal(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose whether a new zone uses seasonal adjustment."""
        if user_input is None:
            return self.async_show_form(
                step_id="seasonal",
                data_schema=_seasonal_usage_schema(),
                last_step=False,
            )
        enabled = _apply_seasonal_usage(self._zone, user_input, reset_curve_when_disabled=True)
        if not enabled:
            return await self.async_step_minimal_schedule()
        return await self.async_step_seasonal_curve()

    async def async_step_seasonal_curve(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect a complete new-zone curve before previewing it."""
        submission = _seasonal_curve_submission(user_input)
        if submission.factors is None:
            return self.async_show_form(
                step_id="seasonal_curve",
                data_schema=(
                    self.add_suggested_values_to_schema(submission.schema, user_input)
                    if user_input is not None
                    else submission.schema
                ),
                errors=submission.errors,
                last_step=False,
            )
        self._seasonal_factors = submission.factors
        return await self.async_step_seasonal_review()

    async def async_step_seasonal_review(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Preview and explicitly confirm a new-zone seasonal curve."""
        submission = _seasonal_review_submission(
            language=self.hass.config.language,
            zone=self._zone,
            factors=self._seasonal_factors,
            user_input=user_input,
        )
        if not submission.confirmed:
            return self.async_show_form(
                step_id="seasonal_review",
                data_schema=_seasonal_confirmation_schema(),
                errors=submission.errors,
                description_placeholders={"preview": submission.preview},
                last_step=True,
            )
        self._zone[CONF_SEASONAL_FACTORS] = dict(self._seasonal_factors)
        return await self.async_step_minimal_schedule()

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
            base_target=positive_number(self._zone.get(CONF_BASE_TARGET)),
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
        options = [
            "reconfigure_minimal",
            "reconfigure_plant",
            "reconfigure_seasonal",
            "reconfigure_baseline",
            "reconfigure_schedule",
            "releases",
        ]
        if self._get_entry().data.get(CONF_PLANT_SITE_MODULE_ENABLED) is not True:
            options.remove("reconfigure_plant")
        if self._get_entry().data.get(CONF_SEASONAL_MODULE_ENABLED) is not True:
            options.remove("reconfigure_seasonal")
        if self._get_entry().data.get(CONF_METER_TYPE) != METER_TYPE_NONE:
            options.append("calibration")
        return self.async_show_menu(step_id="reconfigure", menu_options=options)

    async def async_step_reconfigure_minimal(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a zone's minimal v2 configuration."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        previous_control_type = str(subentry.data.get(CONF_CONTROL_TYPE, CONTROL_TYPE_TIME))
        has_meter = entry.data.get(CONF_METER_TYPE) != METER_TYPE_NONE
        schema = _minimal_zone_schema(has_meter)
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_minimal",
                data_schema=self.add_suggested_values_to_schema(
                    schema, _zone_form_values(subentry.data)
                ),
                last_step=False,
            )
        if self._valve_is_configured(
            str(user_input[CONF_ZONE_VALVE]), excluding_subentry_id=subentry.subentry_id
        ):
            return self.async_abort(reason="actuator_already_owned")
        control_type = str(user_input[CONF_CONTROL_TYPE])
        max_runtime: float | None = None
        if control_type == CONTROL_TYPE_VOLUME and user_input.get(CONF_VOLUME_MAX_RUNTIME) is None:
            return self.async_show_form(
                step_id="reconfigure_minimal",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "volume_max_runtime_required"},
                last_step=False,
            )
        if control_type == CONTROL_TYPE_VOLUME:
            try:
                max_runtime = _form_duration(user_input[CONF_VOLUME_MAX_RUNTIME])
            except ValueError:
                return self.async_show_form(
                    step_id="reconfigure_minimal",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "duration_format_invalid"},
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
            self._zone[CONF_VOLUME_MAX_RUNTIME] = max_runtime
        else:
            self._zone.pop(CONF_VOLUME_MAX_RUNTIME, None)
        if (
            previous_control_type == control_type
            and subentry.data.get(CONF_NEEDS_RECONFIGURATION) is not True
        ):
            async with _ACTUATOR_OWNERSHIP_LOCK:
                if self._valve_is_configured(
                    str(self._zone[CONF_ZONE_VALVE]),
                    excluding_subentry_id=subentry.subentry_id,
                ):
                    return self.async_abort(reason="actuator_already_owned")
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=str(self._zone[CONF_NAME]),
                    data=self._zone,
                )
        return await self.async_step_reconfigure_minimal_baseline()

    async def async_step_reconfigure_minimal_baseline(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm the baseline while completing the atomic legacy reconfiguration path."""
        control_type = str(self._zone[CONF_CONTROL_TYPE])
        schema = _baseline_schema(control_type)
        if user_input is None:
            suggested: dict[str, object] = {}
            subentry = self._get_reconfigure_subentry()
            existing = (
                self._zone.get(CONF_BASE_TARGET)
                if subentry.data.get(CONF_CONTROL_TYPE) == control_type
                else None
            )
            if isinstance(existing, int | float):
                suggested[CONF_BASE_TARGET] = (
                    format_duration(float(existing))
                    if control_type == CONTROL_TYPE_TIME
                    else existing
                )
            return self.async_show_form(
                step_id="reconfigure_minimal_baseline",
                data_schema=self.add_suggested_values_to_schema(schema, suggested),
                last_step=False,
            )
        try:
            _set_optional_baseline(self._zone, user_input, control_type)
        except ValueError:
            return self.async_show_form(
                step_id="reconfigure_minimal_baseline",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "schedule_target_invalid"},
            )
        return await self.async_step_reconfigure_minimal_schedule()

    async def async_step_reconfigure_minimal_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Replace a zone's complete seven-day schedule."""
        subentry = self._get_reconfigure_subentry()
        schema = _weekly_schedule_schema(str(self._zone[CONF_CONTROL_TYPE]))
        if user_input is None:
            existing_schedule = (
                subentry.data.get(CONF_WEEKLY_SCHEDULE)
                if subentry.data.get(CONF_CONTROL_TYPE) == self._zone[CONF_CONTROL_TYPE]
                else None
            )
            return self.async_show_form(
                step_id="reconfigure_minimal_schedule",
                data_schema=self.add_suggested_values_to_schema(
                    schema,
                    _weekly_schedule_form_values(
                        existing_schedule,
                        control_type=str(self._zone[CONF_CONTROL_TYPE]),
                    ),
                ),
                last_step=True,
            )
        schedule, error = _canonical_weekly_schedule(
            user_input,
            control_type=str(self._zone[CONF_CONTROL_TYPE]),
            base_target=positive_number(self._zone.get(CONF_BASE_TARGET)),
            volume_max_runtime=cast(float | None, self._zone.get(CONF_VOLUME_MAX_RUNTIME)),
            expected_flow_l_min=cast(float | None, self._zone.get(CONF_EXPECTED_FLOW_L_MIN)),
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

    async def async_step_reconfigure_baseline(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit only the shared baseline."""
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        control_type = str(data[CONF_CONTROL_TYPE])
        schema = _baseline_schema(control_type)
        if user_input is None:
            value = data.get(CONF_BASE_TARGET)
            suggested = {
                CONF_BASE_TARGET: (
                    format_duration(float(cast(float, value)))
                    if control_type == CONTROL_TYPE_TIME and isinstance(value, int | float)
                    else value
                )
            }
            return self.async_show_form(
                step_id="reconfigure_baseline",
                data_schema=self.add_suggested_values_to_schema(schema, suggested),
                last_step=True,
            )
        try:
            _set_optional_baseline(data, user_input, control_type)
        except ValueError:
            return self.async_show_form(
                step_id="reconfigure_baseline",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "schedule_target_invalid"},
                last_step=True,
            )
        schedule, error = _canonical_weekly_schedule(
            _weekly_schedule_form_values(data.get(CONF_WEEKLY_SCHEDULE), control_type=control_type),
            control_type=control_type,
            base_target=positive_number(data.get(CONF_BASE_TARGET)),
            volume_max_runtime=cast(float | None, data.get(CONF_VOLUME_MAX_RUNTIME)),
            expected_flow_l_min=cast(float | None, data.get(CONF_EXPECTED_FLOW_L_MIN)),
        )
        if error is not None:
            return self.async_show_form(
                step_id="reconfigure_baseline",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
                last_step=True,
            )
        data[CONF_WEEKLY_SCHEDULE] = schedule
        return self.async_update_and_abort(self._get_entry(), subentry, data=data)

    async def async_step_reconfigure_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit only weekly windows and day overrides."""
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        control_type = str(data[CONF_CONTROL_TYPE])
        baseline = positive_number(data.get(CONF_BASE_TARGET))
        if baseline is None:
            return self.async_abort(reason="reconfiguration_required")
        schema = _weekly_schedule_schema(control_type)
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_schedule",
                data_schema=self.add_suggested_values_to_schema(
                    schema,
                    _weekly_schedule_form_values(
                        data.get(CONF_WEEKLY_SCHEDULE), control_type=control_type
                    ),
                ),
                last_step=True,
            )
        schedule, error = _canonical_weekly_schedule(
            user_input,
            control_type=control_type,
            base_target=baseline,
            volume_max_runtime=cast(float | None, data.get(CONF_VOLUME_MAX_RUNTIME)),
            expected_flow_l_min=cast(float | None, data.get(CONF_EXPECTED_FLOW_L_MIN)),
        )
        if error is not None:
            return self.async_show_form(
                step_id="reconfigure_schedule",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
                last_step=True,
            )
        data[CONF_WEEKLY_SCHEDULE] = schedule
        return self.async_update_and_abort(self._get_entry(), subentry, data=data)

    async def async_step_reconfigure_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Replace or disable the profile data without touching other zone settings."""
        subentry = self._get_reconfigure_subentry()
        if user_input is None:
            existing_subareas = subentry.data.get(CONF_SUBAREAS)
            return self.async_show_form(
                step_id="reconfigure_plant",
                data_schema=_reconfigure_plant_schema(
                    bool(subentry.data.get(CONF_USE_PLANT_SITE_MODEL, False)),
                    isinstance(existing_subareas, list) and bool(existing_subareas),
                ),
                last_step=False,
            )
        if user_input[CONF_USE_PLANT_SITE_MODEL] is not True:
            data = {**subentry.data, CONF_USE_PLANT_SITE_MODEL: False}
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)
        existing_subareas = subentry.data.get(CONF_SUBAREAS)
        if (
            isinstance(existing_subareas, list)
            and existing_subareas
            and user_input.get("replace_subareas") is not True
        ):
            self._subareas = [dict(item) for item in existing_subareas if isinstance(item, Mapping)]
            self._recommendation = recommend_profiles(self._subareas)
            return await self.async_step_reconfigure_plant_review()
        self._subareas = []
        return await self.async_step_reconfigure_subarea()

    async def async_step_reconfigure_subarea(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect replacement subareas before one atomic profile update."""
        if user_input is not None:
            if _accept_subarea(self._subareas, user_input):
                return self.async_show_form(
                    step_id="reconfigure_subarea",
                    data_schema=_subarea_schema(),
                    last_step=False,
                )
            self._recommendation = recommend_profiles(self._subareas)
            return await self.async_step_reconfigure_plant_review()
        return self.async_show_form(
            step_id="reconfigure_subarea", data_schema=_subarea_schema(), last_step=False
        )

    async def async_step_reconfigure_plant_review(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show the qualitative result before storing replacement profiles."""
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_plant_review",
                data_schema=vol.Schema({}),
                description_placeholders=_recommendation_placeholders(
                    self.hass.config.language, self._recommendation
                ),
                last_step=True,
            )
        subentry = self._get_reconfigure_subentry()
        data = {
            **subentry.data,
            CONF_USE_PLANT_SITE_MODEL: True,
            CONF_SUBAREAS: list(self._subareas),
        }
        return self.async_update_and_abort(self._get_entry(), subentry, data=data)

    async def async_step_reconfigure_seasonal(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Enable, disable, or continue to edit one zone's seasonal curve."""
        subentry = self._get_reconfigure_subentry()
        enabled = bool(subentry.data.get(CONF_USE_SEASONAL_ADJUSTMENT, False))
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_seasonal",
                data_schema=_seasonal_usage_schema(enabled),
                last_step=False,
            )
        self._zone = dict(subentry.data)
        if not _apply_seasonal_usage(self._zone, user_input, reset_curve_when_disabled=False):
            return self.async_update_and_abort(self._get_entry(), subentry, data=self._zone)
        return await self.async_step_reconfigure_seasonal_curve()

    async def async_step_reconfigure_seasonal_curve(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect but do not yet persist a complete seasonal curve."""
        existing = self._zone.get(CONF_SEASONAL_FACTORS)
        factors = existing if isinstance(existing, Mapping) else None
        submission = _seasonal_curve_submission(user_input, existing=factors)
        if submission.factors is None:
            return self.async_show_form(
                step_id="reconfigure_seasonal_curve",
                data_schema=(
                    self.add_suggested_values_to_schema(submission.schema, user_input)
                    if user_input is not None
                    else submission.schema
                ),
                errors=submission.errors,
                last_step=False,
            )
        self._seasonal_factors = submission.factors
        return await self.async_step_reconfigure_seasonal_review()

    async def async_step_reconfigure_seasonal_review(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Preview month-anchor targets and persist only after confirmation."""
        submission = _seasonal_review_submission(
            language=self.hass.config.language,
            zone=self._zone,
            factors=self._seasonal_factors,
            user_input=user_input,
        )
        if not submission.confirmed:
            return self.async_show_form(
                step_id="reconfigure_seasonal_review",
                data_schema=_seasonal_confirmation_schema(),
                errors=submission.errors,
                description_placeholders={"preview": submission.preview},
                last_step=True,
            )
        subentry = self._get_reconfigure_subentry()
        data = {
            **subentry.data,
            CONF_USE_SEASONAL_ADJUSTMENT: True,
            CONF_SEASONAL_FACTORS: dict(self._seasonal_factors),
        }
        return self.async_update_and_abort(self._get_entry(), subentry, data=data)

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
                vol.Required(
                    "duration", default=format_duration(min(60.0, duration_limit))
                ): _duration_selector(),
                vol.Required("confirm_supervision", default=False): BooleanSelector(),
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="calibration",
                data_schema=schema,
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        try:
            duration = _form_duration(user_input["duration"], maximum=duration_limit)
        except ValueError:
            return self.async_show_form(
                step_id="calibration",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_duration_invalid"},
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
                duration_seconds=duration,
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
        options = (
            ["configuration"]
            if self._requires_reconfiguration()
            else [
                "configuration_basics",
                "configuration_main_valve_only",
                "configuration_meter_only",
            ]
        )
        options.extend(["extensions", "releases", "replan"])
        if locked:
            options.append("reset_safety")
        if self.config_entry.data.get(CONF_METER_TYPE) != METER_TYPE_NONE:
            options.append("physical_meter_correction")
        return self.async_show_menu(step_id="init", menu_options=options)

    async def async_step_configuration_basics(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit only the installation name."""
        schema = _installation_basics_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="configuration_basics",
                data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
                last_step=True,
            )
        data = {**self.config_entry.data, CONF_NAME: user_input[CONF_NAME]}
        self.hass.config_entries.async_update_entry(
            self.config_entry, title=str(user_input[CONF_NAME]), data=data
        )
        return self.async_create_entry(data={})

    async def async_step_configuration_main_valve_only(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit only the optional main valve."""
        schema = _installation_main_valve_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="configuration_main_valve_only",
                data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
                last_step=True,
            )
        data = {**self.config_entry.data, CONF_MAIN_VALVE: user_input.get(CONF_MAIN_VALVE)}
        candidate = _owned_endpoints(data, ())
        async with _ACTUATOR_OWNERSHIP_LOCK:
            if _ownership_conflicts(
                self.hass,
                candidate,
                excluding_entry_id=self.config_entry.entry_id,
                exclude_installation=True,
            ):
                return self.async_abort(reason="actuator_already_owned")
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        return self.async_create_entry(data={})

    async def async_step_configuration_meter_only(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the measurement type without traversing unrelated settings."""
        schema = _meter_type_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="configuration_meter_only",
                data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
                last_step=False,
            )
        self._meter_type = str(user_input[CONF_METER_TYPE])
        if self._meter_type == METER_TYPE_NONE:
            if self._has_volume_zones():
                return self.async_show_form(
                    step_id="configuration_meter_only",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "meter_required_by_volume_zones"},
                )
            data = {**self.config_entry.data, CONF_METER_TYPE: METER_TYPE_NONE}
            data.pop(CONF_METER_ENTITY, None)
            data.pop(CONF_LITERS_PER_PULSE, None)
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            return self.async_create_entry(data={})
        return await self.async_step_configuration_meter_only_details()

    async def async_step_configuration_meter_only_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit only the source fields for the selected measurement type."""
        schema = _meter_details_schema(self._meter_type)
        if user_input is None:
            suggested = dict(self.config_entry.data)
            if self._meter_type == METER_TYPE_PULSE:
                suggested["pulse_factor_mode"] = "liters_per_pulse"
                suggested["pulse_factor"] = self.config_entry.data.get(CONF_LITERS_PER_PULSE)
            return self.async_show_form(
                step_id="configuration_meter_only_details",
                data_schema=self.add_suggested_values_to_schema(schema, suggested),
                last_step=True,
            )
        meter, error = _meter_data({CONF_METER_TYPE: self._meter_type, **user_input})
        if error is not None:
            return self.async_show_form(
                step_id="configuration_meter_only_details",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": error},
                last_step=True,
            )
        data = {**self.config_entry.data, **meter}
        if self._meter_type != METER_TYPE_PULSE:
            data.pop(CONF_LITERS_PER_PULSE, None)
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        return self.async_create_entry(data={})

    async def async_step_extensions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable or disable completed comfort modules without deleting zone data."""
        schema = _extensions_schema()
        if user_input is None:
            return self.async_show_form(
                step_id="extensions",
                data_schema=self.add_suggested_values_to_schema(
                    schema,
                    {
                        CONF_PLANT_SITE_MODULE_ENABLED: bool(
                            self.config_entry.data.get(CONF_PLANT_SITE_MODULE_ENABLED, False)
                        ),
                        CONF_SEASONAL_MODULE_ENABLED: bool(
                            self.config_entry.data.get(CONF_SEASONAL_MODULE_ENABLED, False)
                        ),
                    },
                ),
                last_step=True,
            )
        data = {
            **self.config_entry.data,
            CONF_PLANT_SITE_MODULE_ENABLED: bool(user_input[CONF_PLANT_SITE_MODULE_ENABLED]),
            CONF_SEASONAL_MODULE_ENABLED: bool(user_input[CONF_SEASONAL_MODULE_ENABLED]),
        }
        data.setdefault(CONF_WEATHER_MODULE_ENABLED, False)
        data.setdefault(CONF_SOAK_MODULE_ENABLED, False)
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        return self.async_create_entry(data={})

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
