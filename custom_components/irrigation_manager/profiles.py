"""Versioned profile registry and effective Teilflaeche calculations."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType
from typing import Any, cast

from .const import (
    CONF_APPLICATION_EFFICIENCY,
    CONF_AREA_M2,
    CONF_CROP_FACTOR,
    CONF_EXPOSURE_PROFILE,
    CONF_IRRIGATION_PROFILE,
    CONF_MAXIMUM_DEFICIT_MM,
    CONF_PHENOLOGY_STAGE_SCHEDULE,
    CONF_PLANT_PROFILE,
    CONF_PROFILE_OVERRIDES,
    CONF_RAIN_FACTOR,
    CONF_SEASONAL_CROP_FACTORS,
    CONF_SOIL_PROFILE,
    CONF_SUBAREAS,
)
from .weather import calculate_seasonal_value

PROFILE_KINDS = ("plant", "soil", "exposure", "irrigation")
PROFILE_SCHEMA_VERSION = 3

_FAO_56_CH6 = {
    "id": "fao56-ch6-table12",
    "title": "FAO-56 chapter 6 and Table 12",
    "url": "https://www.fao.org/4/X0490E/x0490e0b.htm",
}
_FAO_56_CH8 = {
    "id": "fao56-ch8-tables19-22",
    "title": "FAO-56 chapter 8, Tables 19 and 22",
    "url": "https://www.fao.org/4/X0490E/x0490e0e.htm",
}
_FAO_LANDSCAPE = {
    "id": "wucols-iv",
    "title": "WUCOLS IV landscape water-use classifications",
    "url": "https://ccuh.ucdavis.edu/wucols",
}
_MWELO = {
    "id": "california-mwelo",
    "title": "California Model Water Efficient Landscape Ordinance",
    "url": (
        "https://water.ca.gov/Programs/Water-Use-And-Efficiency/"
        "Urban-Water-Use-Efficiency/Model-Water-Efficient-Landscape-Ordinance"
    ),
}
_CSU_TURF = {
    "id": "csu-watering-established-lawns",
    "title": "Colorado State University Extension lawn-watering guidance",
    "url": "https://extension.colostate.edu/topic-areas/yard-garden/watering-established-lawns-7-199/",
}
_UMN_ESTABLISHMENT = {
    "id": "umn-watering-newly-planted-trees-shrubs",
    "title": "University of Minnesota Extension establishment watering guidance",
    "url": (
        "https://extension.umn.edu/planting-and-growing-guides/"
        "watering-newly-planted-trees-and-shrubs"
    ),
}
_FAO_INFILTRATION = {
    "id": "fao-infiltration-annex2-table7",
    "title": "FAO Irrigation Water Management Annex 2, Table 7",
    "url": "https://www.fao.org/4/S8684E/s8684e0a.htm",
}
_FAO_EFFICIENCY = {
    "id": "fao-irrigation-efficiency-table8",
    "title": "FAO Annex I irrigation efficiencies, Table 8",
    "url": "https://www.fao.org/4/T7202E/t7202e08.htm",
}
_FAO_IRRIGATION_METHOD = {
    "id": "fao-irrigation-method-ch7",
    "title": "FAO Irrigation Water Management chapter 7",
    "url": "https://www.fao.org/4/S8684E/s8684e08.htm",
}


def _researched_profile(
    profile_id: str,
    kind: str,
    name: str,
    values: dict[str, object],
    ranges: dict[str, object],
    confidence: str,
    sources: tuple[dict[str, str], ...],
    assumptions: tuple[str, ...],
    *,
    de_name: str,
) -> dict[str, object]:
    """Build one consistently annotated catalog record."""
    return {
        "id": profile_id,
        "kind": kind,
        "name": name,
        "localized_names": {"en": name, "de": de_name},
        "version": 1,
        "catalog_version": 1,
        "values": values,
        "ranges": ranges,
        "confidence": confidence,
        "sources": sources,
        "assumptions": assumptions,
        "assumption_note": " ".join(assumptions),
        "generic": False,
        "confirmation_required": True,
    }


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
    "builtin:plant:cool-season-turf:v1": _researched_profile(
        "builtin:plant:cool-season-turf:v1",
        "plant",
        "Cool-season turf (active growth)",
        {
            "seasonal_kc": (0.9,) * 12,
            "effective_root_depth_m": 0.3,
            "depletion_fraction": 0.4,
            "coefficient_basis": "fao_kc",
        },
        {
            "seasonal_kc": [0.9, 0.9],
            "effective_root_depth_m": [0.3, 0.3],
            "depletion_fraction": [0.4, 0.4],
        },
        "medium",
        (_FAO_56_CH6, _FAO_56_CH8, _CSU_TURF),
        (
            "Kc applies to active growth, not dormancy.",
            "Effective root depth is deliberately conservative and must be confirmed for the site.",
        ),
        de_name="Kühlklimatischer Rasen (aktives Wachstum)",
    ),
    "builtin:plant:warm-season-turf:v1": _researched_profile(
        "builtin:plant:warm-season-turf:v1",
        "plant",
        "Warm-season turf (active growth)",
        {
            "seasonal_kc": (0.8,) * 12,
            "effective_root_depth_m": 0.3,
            "depletion_fraction": 0.5,
            "coefficient_basis": "fao_kc",
        },
        {
            "seasonal_kc": [0.8, 0.8],
            "effective_root_depth_m": [0.3, 0.3],
            "depletion_fraction": [0.5, 0.5],
        },
        "medium",
        (_FAO_56_CH6, _FAO_56_CH8, _CSU_TURF),
        (
            "Kc applies to active growth, not dormancy.",
            "Effective root depth is deliberately conservative and must be confirmed for the site.",
        ),
        de_name="Warmklimatischer Rasen (aktives Wachstum)",
    ),
    "builtin:plant:mixed-vegetables:v1": _researched_profile(
        "builtin:plant:mixed-vegetables:v1",
        "plant",
        "Mixed vegetables (phenology mapping required)",
        {
            "phenology_stages": {
                "initial": {"kc": 0.6, "effective_root_depth_m": 0.2},
                "mid": {"kc": 1.05, "effective_root_depth_m": 0.45},
                "late": {"kc": 0.85, "effective_root_depth_m": 0.45},
            },
            "conservative_stage": "mid",
            "depletion_fraction": 0.35,
            "coefficient_basis": "fao_kc",
        },
        {
            "kc": [0.6, 1.05],
            "effective_root_depth_m": [0.2, 0.45],
            "depletion_fraction": [0.35, 0.35],
        },
        "medium",
        (_FAO_56_CH6, _FAO_56_CH8),
        (
            "Provide explicit recurring local dates or stage durations for planting, "
            "development, maturity, and harvest.",
            "Without a mapping the resolver conservatively uses the mid-season Kc and "
            "root depth; no hemisphere or universal planting dates are assumed.",
        ),
        de_name="Gemischtes Gemüse (Phänologie-Zuordnung erforderlich)",
    ),
    "builtin:plant:annual-flowers:v1": _researched_profile(
        "builtin:plant:annual-flowers:v1",
        "plant",
        "Annual flowers",
        {
            "seasonal_plant_factor": (0.6,) * 12,
            "effective_root_depth_m": 0.3,
            "depletion_fraction": 0.3,
            "coefficient_basis": "landscape_pf",
        },
        {
            "seasonal_plant_factor": [0.6, 0.6],
            "effective_root_depth_m": [0.3, 0.3],
            "depletion_fraction": [0.3, 0.3],
        },
        "low",
        (_FAO_LANDSCAPE, _MWELO, _FAO_56_CH8),
        (
            "The landscape plant factor is a broad planning assumption, not a crop "
            "coefficient measured for every annual species.",
        ),
        de_name="Einjährige Blumen",
    ),
    "builtin:plant:established-shrubs-hedges:v1": _researched_profile(
        "builtin:plant:established-shrubs-hedges:v1",
        "plant",
        "Established shrubs and hedges",
        {
            "seasonal_plant_factor": (0.5,) * 12,
            "effective_root_depth_m": 0.45,
            "depletion_fraction": 0.5,
            "coefficient_basis": "landscape_pf",
        },
        {
            "seasonal_plant_factor": [0.5, 0.5],
            "effective_root_depth_m": [0.45, 0.45],
            "depletion_fraction": [0.5, 0.5],
        },
        "medium",
        (_FAO_LANDSCAPE, _MWELO, _FAO_56_CH8),
        (
            "Use only for established mixed landscape plantings; species, density, and "
            "microclimate can materially change demand.",
        ),
        de_name="Etablierte Sträucher und Hecken",
    ),
    "builtin:plant:groundcover-perennials:v1": _researched_profile(
        "builtin:plant:groundcover-perennials:v1",
        "plant",
        "Groundcover and perennials",
        {
            "seasonal_plant_factor": (0.45,) * 12,
            "effective_root_depth_m": 0.3,
            "depletion_fraction": 0.35,
            "coefficient_basis": "landscape_pf",
        },
        {
            "seasonal_plant_factor": [0.45, 0.45],
            "effective_root_depth_m": [0.3, 0.3],
            "depletion_fraction": [0.35, 0.35],
        },
        "medium",
        (_FAO_LANDSCAPE, _MWELO, _FAO_56_CH8),
        (
            "The landscape plant factor represents a mixed category and must be adjusted "
            "for actual species and cover.",
        ),
        de_name="Bodendecker und Stauden",
    ),
    "builtin:plant:young-fruit-tree:v1": _researched_profile(
        "builtin:plant:young-fruit-tree:v1",
        "plant",
        "Young fruit tree (establishment)",
        {
            "seasonal_kc": (0.5,) * 12,
            "effective_root_depth_m": 0.7,
            "depletion_fraction": 0.4,
            "coefficient_basis": "approximate_kc",
        },
        {
            "seasonal_kc": [0.5, 0.5],
            "effective_root_depth_m": [0.7, 0.7],
            "depletion_fraction": [0.4, 0.4],
        },
        "low",
        (_FAO_56_CH8, _UMN_ESTABLISHMENT),
        (
            "Approximation only: establishment irrigation depends on root-ball size, "
            "planting date, canopy, soil, and expanding wetted area.",
            "Do not use this profile as a substitute for frequent establishment checks.",
        ),
        de_name="Junger Obstbaum (Anwuchsphase)",
    ),
    "builtin:plant:mature-deciduous-fruit-orchard-no-groundcover:v1": _researched_profile(
        "builtin:plant:mature-deciduous-fruit-orchard-no-groundcover:v1",
        "plant",
        "Mature deciduous fruit orchard, no groundcover",
        {
            "phenology_stages": {
                "initial": {"kc": 0.45, "effective_root_depth_m": 1.0},
                "mid": {"kc": 0.9, "effective_root_depth_m": 1.0},
                "late": {"kc": 0.65, "effective_root_depth_m": 1.0},
            },
            "conservative_stage": "mid",
            "depletion_fraction": 0.5,
            "coefficient_basis": "fao_kc",
        },
        {
            "kc": [0.45, 0.9],
            "effective_root_depth_m": [1.0, 1.0],
            "depletion_fraction": [0.5, 0.5],
        },
        "medium",
        (_FAO_56_CH6, _FAO_56_CH8),
        (
            "Map initial, mid, and late stages to local budbreak, canopy, harvest, and "
            "leaf-fall timing; no hemisphere or calendar months are assumed.",
            "No active groundcover is assumed.",
        ),
        de_name="Erwachsene laubabwerfende Obstanlage ohne Unterwuchs",
    ),
}

for _soil_id, _soil_name, _soil_name_de, _awc, _awc_range, _infiltration in (
    ("sand", "Sand", "Sand", 60.0, [50.0, 110.0], 25.0),
    ("sandy-loam", "Sandy loam", "Sandiger Lehm", 120.0, [100.0, 150.0], 15.0),
    ("loam", "Loam", "Lehm", 150.0, [130.0, 210.0], 8.0),
    ("clay-loam", "Clay loam", "Toniger Lehm", 150.0, [130.0, 210.0], 4.0),
    ("clay", "Clay", "Ton", 120.0, [110.0, 200.0], 2.0),
):
    _BUILTIN_DATA[f"builtin:soil:{_soil_id}:v1"] = _researched_profile(
        f"builtin:soil:{_soil_id}:v1",
        "soil",
        _soil_name,
        {"available_water_capacity_mm_m": _awc, "infiltration_ceiling_mm_h": _infiltration},
        {
            "available_water_capacity_mm_m": _awc_range,
            "infiltration_ceiling_mm_h": {"provisional_ceiling": _infiltration},
        },
        "medium",
        (_FAO_56_CH8, _FAO_INFILTRATION),
        (
            "AWC is a texture-class default within a broad range.",
            "The infiltration value is a provisional planning ceiling, not a measured site "
            "rate; soil structure and condition can dominate texture.",
        ),
        de_name=_soil_name_de,
    )

for _method_id, _method_name, _method_name_de, _efficiency, _efficiency_range in (
    ("drip", "Drip", "Tropfbewässerung", 0.9, [0.8, 0.95]),
    ("microspray", "Microspray", "Mikrosprüher", 0.8, [0.75, 0.9]),
    ("fixed-spray", "Fixed spray", "Fester Sprühregner", 0.7, [0.65, 0.8]),
    ("rotor", "Rotor", "Rotorregner", 0.75, [0.65, 0.85]),
):
    _BUILTIN_DATA[f"builtin:irrigation:{_method_id}:v1"] = _researched_profile(
        f"builtin:irrigation:{_method_id}:v1",
        "irrigation",
        _method_name,
        {"application_efficiency": _efficiency},
        {"application_efficiency": _efficiency_range},
        "medium",
        (_FAO_EFFICIENCY, _FAO_IRRIGATION_METHOD),
        (
            "Efficiency is a planning default; pressure, spacing, wind, maintenance, and "
            "distribution uniformity must be checked locally.",
        ),
        de_name=_method_name_de,
    )


def _freeze(value: object) -> object:
    """Recursively freeze public catalog data."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


BUILTIN_PROFILES: Mapping[str, Mapping[str, object]] = cast(
    Mapping[str, Mapping[str, object]], _freeze(_BUILTIN_DATA)
)


@dataclass(frozen=True, slots=True)
class EffectiveZoneProfile:
    """Resolved common profile for all Teilflaechen behind one valve."""

    area_m2: float
    crop_and_location_factor: float
    application_efficiency: float
    total_available_water_mm: float
    readily_available_water_mm: float
    maximum_deficit_mm: float
    legacy_water_limit: bool
    rain_factor: float
    subareas: tuple[dict[str, object], ...]
    distribution_warnings: tuple[str, ...]
    resolved_inputs: dict[str, object]


def builtin_profiles() -> list[dict[str, object]]:
    """Return detached built-in records so callers cannot mutate the registry."""
    return [_detached_profile(value) for value in BUILTIN_PROFILES.values()]


def profile_select_options(
    custom_profiles: object, kind: str, language: str = "en"
) -> list[dict[str, str]]:
    """Return localized selector labels with provenance and uncertainty."""
    custom = validate_custom_profiles(custom_profiles)
    options: list[dict[str, str]] = []
    for profile in _registry(custom).values():
        if profile.get("kind") != kind:
            continue
        names = profile.get("localized_names")
        name = (
            str(names.get(language, names.get("en", profile["name"])))
            if isinstance(names, Mapping)
            else str(profile["name"])
        )
        ranges = profile.get("ranges")
        range_note = (
            "; ".join(f"{key}={value}" for key, value in ranges.items())
            if isinstance(ranges, Mapping)
            else "legacy fixed values"
        )
        sources = profile.get("sources")
        source_note = (
            ", ".join(
                str(source.get("id"))
                for source in sources
                if isinstance(source, Mapping) and source.get("id")
            )
            if isinstance(sources, Sequence)
            else "migration profile"
        )
        confidence = str(profile.get("confidence", "not rated"))
        if language == "de":
            confidence = {
                "low": "niedrig",
                "medium": "mittel",
                "high": "hoch",
                "not rated": "nicht bewertet",
            }.get(confidence, confidence)
            range_prefix = "Bereich"
            confidence_prefix = "Vertrauen"
        else:
            range_prefix = "range"
            confidence_prefix = "confidence"
        options.append(
            {
                "value": str(profile["id"]),
                "label": (
                    f"{name} | {range_prefix}: {range_note} | "
                    f"{confidence_prefix}: {confidence} | {source_note}"
                ),
            }
        )
    return options


def profile_selection_summary(
    data: Mapping[str, Any], custom_profiles: object, day: date, language: str = "en"
) -> dict[str, object]:
    """Describe selected source metadata and the resulting TAW and RAW limits."""
    custom = validate_custom_profiles(custom_profiles)
    selected: list[dict[str, object]] = []
    registry = _registry(custom)
    for profile_id in referenced_profile_ids(data):
        profile = registry.get(profile_id)
        if profile is None:
            continue
        names = profile.get("localized_names")
        name = (
            str(names.get(language, names.get("en", profile["name"])))
            if isinstance(names, Mapping)
            else str(profile["name"])
        )
        selected.append(
            {
                "id": profile_id,
                "name": name,
                "ranges": deepcopy(profile.get("ranges", {})),
                "confidence": profile.get("confidence", "not rated"),
                "sources": deepcopy(profile.get("sources", [])),
                "assumptions": deepcopy(profile.get("assumptions", [])),
                "confirmation_required": profile_requires_confirmation(profile_id, custom),
            }
        )
    effective = resolve_effective_zone_profile(data, custom, day)
    return {
        "profiles": selected,
        "total_available_water_mm": effective.total_available_water_mm,
        "readily_available_water_mm": effective.readily_available_water_mm,
        "legacy_water_limit": effective.legacy_water_limit,
        "water_limit_origin": [item.get("water_limit_origin") for item in effective.subareas],
        "warnings": [
            warning
            for item in effective.subareas
            for warning in cast(list[str], item.get("profile_warnings", []))
        ],
    }


def referenced_profile_ids(data: object) -> tuple[str, ...]:
    """Recursively collect profile references from zones, Teilflaechen, and overrides."""
    keys = {
        CONF_PLANT_PROFILE,
        CONF_SOIL_PROFILE,
        CONF_EXPOSURE_PROFILE,
        CONF_IRRIGATION_PROFILE,
    }
    found: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key in keys and isinstance(item, str) and item not in found:
                    found.append(item)
                visit(item)
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
            for item in value:
                visit(item)

    visit(data)
    return tuple(found)


def profile_requires_confirmation(profile_id: str, custom_profiles: object) -> bool:
    """Derive confirmation from immutable built-ins, never imported boolean flags."""
    custom = validate_custom_profiles(custom_profiles)
    current: str | None = profile_id
    seen: set[str] = set()
    while current is not None and current not in seen:
        seen.add(current)
        builtin = _BUILTIN_DATA.get(current)
        if builtin is not None:
            return bool(builtin.get("confirmation_required", False)) and not bool(
                builtin.get("generic", False)
            )
        profile = custom.get(current)
        if profile is None:
            return False
        based_on = profile.get("based_on")
        current = based_on if isinstance(based_on, str) else None
    return False


def selection_requires_confirmation(data: object, custom_profiles: object) -> bool:
    """Return whether any recursively referenced profile has researched ancestry."""
    return any(
        profile_requires_confirmation(profile_id, custom_profiles)
        for profile_id in referenced_profile_ids(data)
    )


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
            "confirmation_required": bool(item.get("confirmation_required", False)),
            **{
                key: deepcopy(item[key])
                for key in (
                    "localized_names",
                    "ranges",
                    "confidence",
                    "sources",
                    "assumptions",
                    "assumption_note",
                )
                if key in item
            },
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
        "confirmation_required": bool(source.get("confirmation_required", False)),
        **{
            key: deepcopy(source[key])
            for key in (
                "ranges",
                "confidence",
                "sources",
                "assumptions",
                "assumption_note",
            )
            if key in source
        },
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
    for index, subarea in enumerate(subareas):
        area = _positive_number(subarea.get("area_m2", data.get(CONF_AREA_M2, 1)), "area_m2")
        zone_overrides = data.get(CONF_PROFILE_OVERRIDES, {})
        subarea_overrides = subarea.get("overrides", {})
        if not isinstance(zone_overrides, Mapping) or not isinstance(subarea_overrides, Mapping):
            raise ValueError("Teilflaeche overrides must be an object")
        overrides = {**zone_overrides, **subarea_overrides}
        merged: dict[str, Any] = {**data, **subarea, **overrides}
        plant_ref = merged.get(CONF_PLANT_PROFILE)
        irrigation_ref = merged.get(CONF_IRRIGATION_PROFILE)
        plant = _resolve_profile_value(merged, CONF_PLANT_PROFILE, "plant", custom)
        soil = _resolve_profile_value(merged, CONF_SOIL_PROFILE, "soil", custom)
        exposure = _resolve_profile_value(merged, CONF_EXPOSURE_PROFILE, "exposure", custom)
        irrigation = _resolve_profile_value(merged, CONF_IRRIGATION_PROFILE, "irrigation", custom)
        plant_is_custom = _custom_ref(plant_ref)
        exposure_is_custom = _custom_ref(merged.get(CONF_EXPOSURE_PROFILE))
        irrigation_is_custom = _custom_ref(irrigation_ref)
        soil_is_custom = _custom_ref(merged.get(CONF_SOIL_PROFILE))
        plant_preferred = plant_is_custom or _researched_ref(plant_ref)
        irrigation_preferred = irrigation_is_custom or _researched_ref(irrigation_ref)
        profile_warnings: list[str] = []
        coefficient_basis = str(plant.get("coefficient_basis", "legacy_multiplier"))
        effective_root_depth = plant.get("effective_root_depth_m")
        stages = plant.get("phenology_stages")
        if isinstance(stages, Mapping):
            staged = _interpolated_phenology(
                stages,
                merged.get(CONF_PHENOLOGY_STAGE_SCHEDULE),
                day,
            )
            if staged is None:
                conservative = stages.get(str(plant.get("conservative_stage", "mid")))
                if not isinstance(conservative, Mapping):
                    raise ValueError("The conservative phenology stage is invalid")
                coefficient = _finite_number(conservative.get("kc"), "phenology_stage.kc", 0)
                effective_root_depth = conservative.get("effective_root_depth_m")
                stage_name = str(plant.get("conservative_stage", "mid"))
                stage_progress = 1.0
                profile_warnings.append("phenology_mapping_required")
            else:
                coefficient, effective_root_depth, stage_name, stage_progress = staged
        else:
            seasonal_key = (
                "seasonal_plant_factor" if coefficient_basis == "landscape_pf" else "seasonal_kc"
            )
            curve = (
                overrides.get(CONF_SEASONAL_CROP_FACTORS) or plant.get(seasonal_key)
                if plant_preferred
                else merged.get(CONF_SEASONAL_CROP_FACTORS, plant.get(seasonal_key, (1.0,) * 12))
            )
            coefficient = calculate_seasonal_value(cast(str | Sequence[float], curve), day)
            stage_name = None
            stage_progress = None
        crop_override = _finite_number(merged.get(CONF_CROP_FACTOR, 1.0), "crop_factor", 0)
        if coefficient_basis == "landscape_pf":
            location = 1.0
            configured_location = overrides.get(
                "location_factor",
                merged.get("location_factor", exposure.get("location_factor", 1.0)),
            )
            if configured_location != 1.0:
                profile_warnings.append("location_factor_ignored_for_landscape_pf")
        else:
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
        factor = coefficient * crop_override * location
        efficiency = _bounded_number(
            overrides.get(
                CONF_APPLICATION_EFFICIENCY,
                irrigation.get("application_efficiency", 1.0)
                if irrigation_preferred
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
        total_available: float | None = None
        readily_available: float | None = None
        if all(
            value is not None
            for value in (
                effective_root_depth,
                plant.get("depletion_fraction"),
                soil.get("available_water_capacity_mm_m"),
            )
        ):
            root_depth = _positive_number(effective_root_depth, "effective_root_depth_m")
            depletion = _bounded_number(
                plant["depletion_fraction"], "depletion_fraction", 0, 1, exclusive_min=True
            )
            awc = _positive_number(
                soil["available_water_capacity_mm_m"], "available_water_capacity_mm_m"
            )
            total_available = awc * root_depth
            readily_available = total_available * depletion
        legacy_water_limit = total_available is None or readily_available is None
        if CONF_MAXIMUM_DEFICIT_MM in overrides:
            legacy_maximum = _positive_number(
                overrides[CONF_MAXIMUM_DEFICIT_MM], CONF_MAXIMUM_DEFICIT_MM
            )
            total_available = legacy_maximum
            readily_available = legacy_maximum
            legacy_water_limit = True
            water_limit_origin = "explicit_legacy_profile_override"
        elif total_available is not None and readily_available is not None:
            total_available = _positive_number(
                overrides.get("total_available_water_mm", total_available),
                "total_available_water_mm",
            )
            readily_available = _positive_number(
                overrides.get("readily_available_water_mm", readily_available),
                "readily_available_water_mm",
            )
            if readily_available > total_available:
                raise ValueError(
                    "readily_available_water_mm must not exceed total_available_water_mm"
                )
            water_limit_origin = "derived_awc_root_depth"
        else:
            legacy_maximum = _positive_number(
                soil.get("maximum_deficit_mm", 50.0)
                if soil_is_custom
                else merged.get(CONF_MAXIMUM_DEFICIT_MM, soil.get("maximum_deficit_mm", 50.0)),
                CONF_MAXIMUM_DEFICIT_MM,
            )
            total_available = legacy_maximum
            readily_available = legacy_maximum
            water_limit_origin = "legacy_fixed_value"
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
        resolved_subareas.append(
            {
                "id": str(subarea.get("id", f"subarea-{index + 1}")),
                "area_m2": area,
                "crop_and_location_factor": factor,
                "plant_coefficient": coefficient,
                "coefficient_basis": coefficient_basis,
                "location_factor_applied": location,
                "phenology_stage": stage_name,
                "phenology_stage_progress": stage_progress,
                "application_efficiency": efficiency,
                "total_available_water_mm": total_available,
                "readily_available_water_mm": readily_available,
                "maximum_deficit_mm": total_available,
                "legacy_water_limit": legacy_water_limit,
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
                "water_limit_origin": water_limit_origin,
                "available_water_capacity_mm_m": soil.get("available_water_capacity_mm_m"),
                "effective_root_depth_m": effective_root_depth,
                "depletion_fraction": plant.get("depletion_fraction"),
                "infiltration_ceiling_mm_h": soil.get("infiltration_ceiling_mm_h"),
                "profile_warnings": profile_warnings,
            }
        )
    factor = weighted_factor / total_area
    gross_weights: list[float] = []
    transformed_taw: list[float] = []
    transformed_raw: list[float] = []
    for item in resolved_subareas:
        area = cast(float, item["area_m2"])
        local_factor = cast(float, item["crop_and_location_factor"])
        local_efficiency = cast(float, item["application_efficiency"])
        net_depth_factor = local_factor / factor if factor > 0 else 1.0
        gross_liters_per_mm = area * net_depth_factor / local_efficiency
        item["net_depth_factor"] = net_depth_factor
        item["gross_liters_per_zone_deficit_mm"] = gross_liters_per_mm
        if net_depth_factor > 0:
            zone_taw = cast(float, item["total_available_water_mm"]) / net_depth_factor
            zone_raw = cast(float, item["readily_available_water_mm"]) / net_depth_factor
            transformed_taw.append(zone_taw)
            transformed_raw.append(zone_raw)
            item["zone_equivalent_total_available_water_mm"] = zone_taw
            item["zone_equivalent_readily_available_water_mm"] = zone_raw
        else:
            item["zone_equivalent_total_available_water_mm"] = None
            item["zone_equivalent_readily_available_water_mm"] = None
        gross_weights.append(gross_liters_per_mm)
    gross_liters_per_mm = sum(gross_weights)
    warnings = _distribution_warnings(resolved_subareas, gross_weights, application_weights)
    # This display efficiency is the exact equivalent of summing each Teilflaeche's
    # independently grossed demand. It is not used as a conservative minimum shortcut.
    efficiency = total_area / gross_liters_per_mm
    total_available_water = min(transformed_taw)
    readily_available_water = min(transformed_raw)
    legacy_water_limit = all(bool(item["legacy_water_limit"]) for item in resolved_subareas)
    coefficient_bases = {str(item["coefficient_basis"]) for item in resolved_subareas}
    coefficient_basis = next(iter(coefficient_bases)) if len(coefficient_bases) == 1 else "mixed"
    rain = weighted_rain / total_area
    resolved_inputs: dict[str, object] = {
        "profile_schema_version": PROFILE_SCHEMA_VERSION,
        "resolved_on": day.isoformat(),
        "area_m2": total_area,
        "crop_and_location_factor": factor,
        "coefficient_basis": coefficient_basis,
        "application_efficiency": efficiency,
        "gross_liters_per_zone_deficit_mm": gross_liters_per_mm,
        "total_available_water_mm": total_available_water,
        "readily_available_water_mm": readily_available_water,
        "maximum_deficit_mm": total_available_water,
        "legacy_water_limit": legacy_water_limit,
        "rain_factor": rain,
        "subareas": resolved_subareas,
        "distribution_warnings": list(warnings),
    }
    return EffectiveZoneProfile(
        area_m2=total_area,
        crop_and_location_factor=factor,
        application_efficiency=efficiency,
        total_available_water_mm=total_available_water,
        readily_available_water_mm=readily_available_water,
        maximum_deficit_mm=total_available_water,
        legacy_water_limit=legacy_water_limit,
        rain_factor=rain,
        subareas=tuple(resolved_subareas),
        distribution_warnings=warnings,
        resolved_inputs=resolved_inputs,
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


def _researched_ref(value: object) -> bool:
    """Return whether a built-in uses catalog values instead of legacy fixed fields."""
    return (
        isinstance(value, str)
        and value.startswith("builtin:")
        and not bool(_BUILTIN_DATA.get(value, {}).get("generic", True))
    )


def _interpolated_phenology(
    stages: Mapping[object, object], schedule: object, day: date
) -> tuple[float, object, str, float] | None:
    """Resolve a local recurring season and interpolate development and late stages."""
    if schedule in (None, {}):
        return None
    if not isinstance(schedule, Mapping):
        raise ValueError("phenology_stage_schedule must be an object")
    initial = _stage_values(stages, "initial")
    mid = _stage_values(stages, "mid")
    late = _stage_values(stages, "late")
    boundaries = _phenology_boundaries(schedule, day)
    if boundaries is None:
        return (0.0, mid[1], "inactive", 0.0)
    start, development_start, mid_start, late_start, end = boundaries
    if day < development_start:
        return (initial[0], initial[1], "initial", _period_progress(start, development_start, day))
    if day < mid_start:
        progress = _period_progress(development_start, mid_start, day)
        return (
            _lerp(initial[0], mid[0], progress),
            _lerp(initial[1], mid[1], progress),
            "development",
            progress,
        )
    if day < late_start:
        return (mid[0], mid[1], "mid", _period_progress(mid_start, late_start, day))
    progress = _period_progress(late_start, end, day)
    return (
        _lerp(mid[0], late[0], progress),
        _lerp(mid[1], late[1], progress),
        "late",
        progress,
    )


def _stage_values(stages: Mapping[object, object], name: str) -> tuple[float, float]:
    """Return validated coefficient and effective root depth for one stage."""
    stage = stages.get(name)
    if not isinstance(stage, Mapping):
        raise ValueError(f"The {name} phenology stage is invalid")
    return (
        _finite_number(stage.get("kc"), f"phenology_stage.{name}.kc", 0),
        _positive_number(
            stage.get("effective_root_depth_m"),
            f"phenology_stage.{name}.effective_root_depth_m",
        ),
    )


def _phenology_boundaries(
    schedule: Mapping[object, object], day: date
) -> tuple[date, date, date, date, date] | None:
    """Return the season containing day from explicit recurring dates or durations."""
    for start_year in (day.year, day.year - 1):
        start = _recurring_date(schedule.get("season_start"), start_year, "season_start")
        if all(
            key in schedule for key in ("initial_days", "development_days", "mid_days", "late_days")
        ):
            durations = [
                _positive_integer(schedule[key], key)
                for key in ("initial_days", "development_days", "mid_days", "late_days")
            ]
            development_start = start + timedelta(days=durations[0])
            mid_start = development_start + timedelta(days=durations[1])
            late_start = mid_start + timedelta(days=durations[2])
            end = late_start + timedelta(days=durations[3])
        elif all(
            key in schedule
            for key in ("development_start", "mid_start", "late_start", "season_end")
        ):
            development_start = _next_recurring_date(
                schedule["development_start"], start, "development_start"
            )
            mid_start = _next_recurring_date(schedule["mid_start"], development_start, "mid_start")
            late_start = _next_recurring_date(schedule["late_start"], mid_start, "late_start")
            end = _next_recurring_date(schedule["season_end"], late_start, "season_end")
        else:
            raise ValueError(
                "phenology_stage_schedule requires four durations or four stage boundary dates"
            )
        if start <= day < end:
            return start, development_start, mid_start, late_start, end
    return None


def _recurring_date(value: object, year: int, name: str) -> date:
    """Parse one explicit recurring MM-DD date."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must use MM-DD")
    try:
        return date.fromisoformat(f"{year}-{value}")
    except ValueError as err:
        raise ValueError(f"{name} must use MM-DD") from err


def _next_recurring_date(value: object, after: date, name: str) -> date:
    """Resolve a recurring boundary strictly after the preceding boundary."""
    candidate = _recurring_date(value, after.year, name)
    if candidate <= after:
        candidate = _recurring_date(value, after.year + 1, name)
    return candidate


def _positive_integer(value: object, name: object) -> int:
    """Validate one positive integral stage duration."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _period_progress(start: date, end: date, day: date) -> float:
    """Return bounded elapsed progress through one non-empty stage."""
    return min(1.0, max(0.0, (day - start).days / (end - start).days))


def _lerp(start: float, end: float, progress: float) -> float:
    """Linearly interpolate one stage value."""
    return start + (end - start) * progress


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
    if "seasonal_plant_factor" in values:
        if kind != "plant":
            raise ValueError("seasonal_plant_factor is only valid for plant profiles")
        calculate_seasonal_value(values["seasonal_plant_factor"], date(2000, 1, 15))  # type: ignore[arg-type]
    basis = values.get("coefficient_basis")
    if basis is not None and basis not in {
        "fao_kc",
        "approximate_kc",
        "landscape_pf",
        "legacy_multiplier",
    }:
        raise ValueError("coefficient_basis is invalid")
    if "phenology_stages" in values:
        stages = values["phenology_stages"]
        if kind != "plant" or not isinstance(stages, Mapping) or not stages:
            raise ValueError("phenology_stages is only valid for plant profiles")
        for stage in stages.values():
            if not isinstance(stage, Mapping):
                raise ValueError("phenology stages must be objects")
            _bounded_number(stage.get("kc"), "phenology stage kc", 0, None)
            _positive_number(stage.get("effective_root_depth_m"), "effective_root_depth_m")
    numeric_bounds = {
        "location_factor": (0.0, None),
        "rain_factor": (0.0, 1.0),
        "application_efficiency": (0.0, 1.0),
        "maximum_deficit_mm": (0.0, None),
        "effective_root_depth_m": (0.0, None),
        "depletion_fraction": (0.0, 1.0),
        "available_water_capacity_mm_m": (0.0, None),
        "infiltration_ceiling_mm_h": (0.0, None),
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
    return deepcopy(_BUILTIN_DATA[str(profile["id"])])
