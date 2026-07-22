"""Versioned profile registry and effective Teilflaeche calculations."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, cast

from .const import (
    CONF_APPLICATION_EFFICIENCY,
    CONF_AREA_M2,
    CONF_CROP_FACTOR,
    CONF_EXPOSURE_PROFILE,
    CONF_IRRIGATION_PROFILE,
    CONF_MAXIMUM_DEFICIT_MM,
    CONF_PLANT_PROFILE,
    CONF_PROFILE_OVERRIDES,
    CONF_RAIN_FACTOR,
    CONF_SEASONAL_CROP_FACTORS,
    CONF_SOIL_PROFILE,
    CONF_SUBAREAS,
)
from .weather import calculate_seasonal_value

PROFILE_KINDS = ("plant", "soil", "exposure", "irrigation")

# These are deliberately neutral mathematical references, not crop advice. Setup must
# retain the explicit user-confirmation flag before automatic irrigation can be enabled.
_BUILTIN_DATA: dict[str, dict[str, object]] = {
    "builtin:plant:generic-neutral:v1": {
        "id": "builtin:plant:generic-neutral:v1",
        "kind": "plant",
        "name": "Generic neutral plant (confirmation required)",
        "version": 1,
        "values": {"seasonal_kc": (1.0,) * 12},
        "generic": True,
        "confirmation_required": True,
        "assumption_note": "Neutral Kc placeholders; not crop advice.",
    },
    "builtin:soil:generic-reference:v1": {
        "id": "builtin:soil:generic-reference:v1",
        "kind": "soil",
        "name": "Generic soil reference (confirmation required)",
        "version": 1,
        "values": {"maximum_deficit_mm": 50.0},
        "generic": True,
        "confirmation_required": True,
        "assumption_note": "Legacy safe setup placeholder; verify from soil and root data.",
    },
    "builtin:exposure:generic-neutral:v1": {
        "id": "builtin:exposure:generic-neutral:v1",
        "kind": "exposure",
        "name": "Generic neutral exposure (confirmation required)",
        "version": 1,
        "values": {"location_factor": 1.0, "rain_factor": 1.0},
        "generic": True,
        "confirmation_required": True,
        "assumption_note": "Neutral exposure placeholders; verify for the site.",
    },
    "builtin:irrigation:generic-reference:v1": {
        "id": "builtin:irrigation:generic-reference:v1",
        "kind": "irrigation",
        "name": "Generic irrigation reference (confirmation required)",
        "version": 1,
        "values": {"application_efficiency": 0.8},
        "generic": True,
        "confirmation_required": True,
        "assumption_note": "Legacy setup placeholder; measure or verify before automation.",
    },
}
BUILTIN_PROFILES: Mapping[str, Mapping[str, object]] = MappingProxyType(
    {
        key: MappingProxyType(
            {
                **value,
                "values": MappingProxyType(dict(cast(Mapping[str, object], value["values"]))),
            }
        )
        for key, value in _BUILTIN_DATA.items()
    }
)


@dataclass(frozen=True, slots=True)
class EffectiveZoneProfile:
    """Resolved common profile for all Teilflaechen behind one valve."""

    area_m2: float
    crop_and_location_factor: float
    application_efficiency: float
    maximum_deficit_mm: float
    rain_factor: float
    subareas: tuple[dict[str, object], ...]
    distribution_warnings: tuple[str, ...]
    resolved_inputs: dict[str, object]


def builtin_profiles() -> list[dict[str, object]]:
    """Return detached built-in records so callers cannot mutate the registry."""
    return [_detached_profile(value) for value in BUILTIN_PROFILES.values()]


def validate_custom_profiles(raw: object) -> dict[str, dict[str, object]]:
    """Validate user-owned profile copies without accepting built-in replacement."""
    if raw in (None, {}):
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("Custom profiles must be an object keyed by profile ID")
    result: dict[str, dict[str, object]] = {}
    for profile_id, item in raw.items():
        if not isinstance(profile_id, str) or not profile_id or profile_id.startswith("builtin:"):
            raise ValueError("Custom profile IDs must be non-empty and must not use builtin:")
        if not isinstance(item, Mapping):
            raise ValueError(f"Custom profile {profile_id} must be an object")
        kind = item.get("kind")
        values = item.get("values", {})
        if kind not in PROFILE_KINDS or not isinstance(values, Mapping):
            raise ValueError(f"Custom profile {profile_id} has an invalid kind or values")
        based_on = item.get("based_on")
        if based_on is not None and not isinstance(based_on, str):
            raise ValueError(f"Custom profile {profile_id} has an invalid based_on reference")
        _validate_profile_values(str(kind), values)
        result[profile_id] = {
            "id": profile_id,
            "kind": kind,
            "name": str(item.get("name", profile_id)),
            "version": int(item.get("version", 1)),
            "based_on": based_on,
            "values": dict(values),
            "generic": False,
            "confirmation_required": False,
        }
    registry = {**_BUILTIN_DATA, **result}
    for profile in result.values():
        based_on = profile.get("based_on")
        if based_on is not None:
            parent = registry.get(str(based_on))
            if parent is None or parent["kind"] != profile["kind"]:
                raise ValueError(f"Custom profile {profile['id']} has an invalid base profile")
    for profile_id in result:
        seen: set[str] = set()
        current: str | None = profile_id
        while current in result:
            if current in seen:
                raise ValueError(f"Custom profile {profile_id} has a cyclic base profile")
            seen.add(current)
            based_on = result[current].get("based_on")
            current = based_on if isinstance(based_on, str) else None
    return result


def copy_profile(
    custom_profiles: object, *, source_id: str, new_id: str, name: str
) -> dict[str, dict[str, object]]:
    """Create a user-owned detached copy; built-ins remain unchanged."""
    custom = validate_custom_profiles(custom_profiles)
    if not new_id or new_id.startswith("builtin:") or new_id in custom:
        raise ValueError("The custom profile ID is invalid or already exists")
    source = _registry(custom).get(source_id)
    if source is None:
        raise ValueError("The source profile does not exist")
    resolved = _resolve_profile(source_id, str(source["kind"]), custom)
    custom[new_id] = {
        "id": new_id,
        "kind": source["kind"],
        "name": name,
        "version": 1,
        "based_on": source_id,
        "values": dict(resolved),
        "generic": False,
        "confirmation_required": False,
    }
    return custom


def resolve_effective_zone_profile(
    data: Mapping[str, Any], custom_profiles: object, day: date
) -> EffectiveZoneProfile:
    """Resolve profile references and combine Teilflaechen into one zone demand."""
    custom = validate_custom_profiles(custom_profiles)
    raw_subareas = data.get(CONF_SUBAREAS)
    if raw_subareas in (None, []):
        subareas: Sequence[Mapping[str, Any]] = (
            {"id": "zone", "area_m2": data.get(CONF_AREA_M2, 1)},
        )
    elif isinstance(raw_subareas, Sequence) and not isinstance(raw_subareas, str | bytes):
        if not raw_subareas or not all(isinstance(item, Mapping) for item in raw_subareas):
            raise ValueError("Teilflaechen must be a non-empty list of objects")
        subareas = raw_subareas
    else:
        raise ValueError("Teilflaechen must be a list")

    resolved_subareas: list[dict[str, object]] = []
    weighted_factor = 0.0
    total_area = 0.0
    weighted_rain = 0.0
    application_weights: list[float] = []
    maximum_deficits: list[float] = []
    for index, subarea in enumerate(subareas):
        area = _positive_number(subarea.get("area_m2", data.get(CONF_AREA_M2, 1)), "area_m2")
        zone_overrides = data.get(CONF_PROFILE_OVERRIDES, {})
        subarea_overrides = subarea.get("overrides", {})
        if not isinstance(zone_overrides, Mapping) or not isinstance(subarea_overrides, Mapping):
            raise ValueError("Teilflaeche overrides must be an object")
        overrides = {**zone_overrides, **subarea_overrides}
        merged: dict[str, Any] = {**data, **subarea, **overrides}
        plant = _resolve_profile_value(merged, CONF_PLANT_PROFILE, "plant", custom)
        soil = _resolve_profile_value(merged, CONF_SOIL_PROFILE, "soil", custom)
        exposure = _resolve_profile_value(merged, CONF_EXPOSURE_PROFILE, "exposure", custom)
        irrigation = _resolve_profile_value(merged, CONF_IRRIGATION_PROFILE, "irrigation", custom)
        plant_is_custom = _custom_ref(merged.get(CONF_PLANT_PROFILE))
        exposure_is_custom = _custom_ref(merged.get(CONF_EXPOSURE_PROFILE))
        irrigation_is_custom = _custom_ref(merged.get(CONF_IRRIGATION_PROFILE))
        soil_is_custom = _custom_ref(merged.get(CONF_SOIL_PROFILE))
        curve = (
            overrides.get(CONF_SEASONAL_CROP_FACTORS) or plant.get("seasonal_kc")
            if plant_is_custom
            else merged.get(CONF_SEASONAL_CROP_FACTORS, plant.get("seasonal_kc", (1.0,) * 12))
        )
        kc = calculate_seasonal_value(cast(str | Sequence[float], curve), day)
        crop_override = _finite_number(merged.get(CONF_CROP_FACTOR, 1.0), "crop_factor", 0)
        location = _finite_number(
            overrides.get(
                "location_factor",
                exposure.get("location_factor", 1.0)
                if exposure_is_custom
                else merged.get("location_factor", exposure.get("location_factor", 1.0)),
            ),
            "location_factor",
            0,
        )
        factor = kc * crop_override * location
        efficiency = _bounded_number(
            overrides.get(
                CONF_APPLICATION_EFFICIENCY,
                irrigation.get("application_efficiency", 1.0)
                if irrigation_is_custom
                else merged.get(
                    CONF_APPLICATION_EFFICIENCY,
                    irrigation.get("application_efficiency", 1.0),
                ),
            ),
            "application_efficiency",
            0,
            1,
            exclusive_min=True,
        )
        maximum = _positive_number(
            overrides.get(
                CONF_MAXIMUM_DEFICIT_MM,
                soil.get("maximum_deficit_mm", 50.0)
                if soil_is_custom
                else merged.get(CONF_MAXIMUM_DEFICIT_MM, soil.get("maximum_deficit_mm", 50.0)),
            ),
            "maximum_deficit_mm",
        )
        rain = _bounded_number(
            overrides.get(
                CONF_RAIN_FACTOR,
                exposure.get("rain_factor", 1.0)
                if exposure_is_custom
                else merged.get(CONF_RAIN_FACTOR, exposure.get("rain_factor", 1.0)),
            ),
            "rain_factor",
            0,
            1,
        )
        rate = _positive_number(
            subarea.get("relative_application_rate", 1.0), "relative_application_rate"
        )
        total_area += area
        weighted_factor += area * factor
        weighted_rain += area * rain
        application_weights.append(area * rate)
        maximum_deficits.append(maximum)
        resolved_subareas.append(
            {
                "id": str(subarea.get("id", f"subarea-{index + 1}")),
                "area_m2": area,
                "crop_and_location_factor": factor,
                "application_efficiency": efficiency,
                "maximum_deficit_mm": maximum,
                "rain_factor": rain,
                "relative_application_rate": rate,
                "soil_moisture_sensors": [
                    str(value)
                    for value in subarea.get("soil_moisture_sensors", [])
                    if isinstance(value, str)
                ]
                if isinstance(subarea.get("soil_moisture_sensors", []), list | tuple)
                else [],
                "profile_refs": {
                    key: merged.get(key)
                    for key in (
                        CONF_PLANT_PROFILE,
                        CONF_SOIL_PROFILE,
                        CONF_EXPOSURE_PROFILE,
                        CONF_IRRIGATION_PROFILE,
                    )
                    if merged.get(key) is not None
                },
                "overrides": dict(overrides),
            }
        )
    factor = weighted_factor / total_area
    gross_weights: list[float] = []
    for item in resolved_subareas:
        area = cast(float, item["area_m2"])
        local_factor = cast(float, item["crop_and_location_factor"])
        local_efficiency = cast(float, item["application_efficiency"])
        net_depth_factor = local_factor / factor if factor > 0 else 1.0
        gross_liters_per_mm = area * net_depth_factor / local_efficiency
        item["net_depth_factor"] = net_depth_factor
        item["gross_liters_per_zone_deficit_mm"] = gross_liters_per_mm
        gross_weights.append(gross_liters_per_mm)
    gross_liters_per_mm = sum(gross_weights)
    warnings = _distribution_warnings(resolved_subareas, gross_weights, application_weights)
    # This display efficiency is the exact equivalent of summing each Teilflaeche's
    # independently grossed demand. It is not used as a conservative minimum shortcut.
    efficiency = total_area / gross_liters_per_mm
    maximum = min(maximum_deficits)
    rain = weighted_rain / total_area
    resolved_inputs: dict[str, object] = {
        "profile_schema_version": 1,
        "resolved_on": day.isoformat(),
        "area_m2": total_area,
        "crop_and_location_factor": factor,
        "application_efficiency": efficiency,
        "gross_liters_per_zone_deficit_mm": gross_liters_per_mm,
        "maximum_deficit_mm": maximum,
        "rain_factor": rain,
        "subareas": resolved_subareas,
        "distribution_warnings": list(warnings),
    }
    return EffectiveZoneProfile(
        total_area,
        factor,
        efficiency,
        maximum,
        rain,
        tuple(resolved_subareas),
        warnings,
        resolved_inputs,
    )


def profile_impacted_zones(
    zones: Sequence[tuple[str, str, Mapping[str, Any]]], profile_ids: str | set[str]
) -> list[dict[str, str]]:
    """Return zones directly or indirectly referencing one profile."""
    impacted: list[dict[str, str]] = []
    targets = {profile_ids} if isinstance(profile_ids, str) else profile_ids
    for zone_id, name, data in zones:
        serialized = str(data)
        if any(profile_id in serialized for profile_id in targets):
            impacted.append({"zone_id": zone_id, "name": name})
    return impacted


def dependent_profile_ids(custom_profiles: object, profile_id: str) -> set[str]:
    """Return the selected profile and all custom copies derived from it."""
    custom = validate_custom_profiles(custom_profiles)
    result = {profile_id}
    changed = True
    while changed:
        changed = False
        for candidate_id, candidate in custom.items():
            if candidate.get("based_on") in result and candidate_id not in result:
                result.add(candidate_id)
                changed = True
    return result


def _registry(custom: Mapping[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    return {**_BUILTIN_DATA, **custom}


def _custom_ref(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not value.startswith("builtin:")


def _resolve_profile(
    profile_id: str, kind: str, custom: Mapping[str, dict[str, object]]
) -> dict[str, object]:
    registry = _registry(custom)
    profile = registry.get(profile_id)
    if profile is None or profile.get("kind") != kind:
        raise ValueError(f"Unknown {kind} profile: {profile_id}")
    values: dict[str, object] = {}
    based_on = profile.get("based_on")
    if isinstance(based_on, str):
        values.update(_resolve_profile(based_on, kind, custom))
    raw_values = profile.get("values", {})
    if isinstance(raw_values, Mapping):
        values.update(raw_values)
    return values


def _resolve_profile_value(
    data: Mapping[str, Any], key: str, kind: str, custom: Mapping[str, dict[str, object]]
) -> dict[str, object]:
    profile_id = data.get(key)
    return _resolve_profile(str(profile_id), kind, custom) if profile_id else {}


def _validate_profile_values(kind: str, values: Mapping[object, object]) -> None:
    if "seasonal_kc" in values:
        if kind != "plant":
            raise ValueError("seasonal_kc is only valid for plant profiles")
        calculate_seasonal_value(values["seasonal_kc"], date(2000, 1, 15))  # type: ignore[arg-type]
    numeric_bounds = {
        "location_factor": (0.0, None),
        "rain_factor": (0.0, 1.0),
        "application_efficiency": (0.0, 1.0),
        "maximum_deficit_mm": (0.0, None),
    }
    for key, (minimum, maximum) in numeric_bounds.items():
        if key not in values:
            continue
        _bounded_number(values[key], key, minimum, maximum, exclusive_min=key != "rain_factor")


def _distribution_warnings(
    subareas: Sequence[dict[str, object]], demand: Sequence[float], application: Sequence[float]
) -> tuple[str, ...]:
    demand_total = sum(demand)
    application_total = sum(application)
    if demand_total <= 0 or application_total <= 0 or len(subareas) < 2:
        return ()
    warnings = []
    for item, demand_weight, application_weight in zip(subareas, demand, application, strict=True):
        deviation = application_weight / application_total - demand_weight / demand_total
        item["application_share"] = application_weight / application_total
        item["demand_share"] = demand_weight / demand_total
        item["distribution_deviation"] = deviation
        if abs(deviation) > 0.1:
            warnings.append(f"subarea_distribution_mismatch:{item['id']}")
    return tuple(warnings)


def _finite_number(value: object, name: str, minimum: float) -> float:
    return _bounded_number(value, name, minimum, None)


def _positive_number(value: object, name: str) -> float:
    return _bounded_number(value, name, 0, None, exclusive_min=True)


def _bounded_number(
    value: object,
    name: str,
    minimum: float,
    maximum: float | None,
    *,
    exclusive_min: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (result <= minimum if exclusive_min else result < minimum):
        raise ValueError(f"{name} is outside its supported range")
    if maximum is not None and result > maximum:
        raise ValueError(f"{name} is outside its supported range")
    return result


def _detached_profile(profile: Mapping[str, object]) -> dict[str, object]:
    values = profile.get("values", {})
    return {
        **profile,
        "values": dict(values) if isinstance(values, Mapping) else {},
    }
