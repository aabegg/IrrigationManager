"""Broad qualitative profile catalog and Stage-1 recommender.

The deliberately non-numeric catalog is informed by FAO Irrigation and
Drainage Paper 56 (https://www.fao.org/4/x0490e/x0490e00.htm) and US EPA
WaterSense Watering Tips
(https://www.epa.gov/watersense/watering-tips). It must not be used to derive
an absolute irrigation target or schedule.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Literal

CATALOG_VERSION = "1.0.0"
CATALOG_SOURCE_URLS = (
    "https://www.fao.org/4/x0490e/x0490e00.htm",
    "https://www.epa.gov/watersense/watering-tips",
)

PLANT_PROFILE_OPTIONS = (
    "lawn",
    "hedge_woody",
    "perennials",
    "vegetables",
    "containers",
    "young_plants",
    "groundcover",
    "custom",
)
SOIL_PROFILE_OPTIONS = ("sandy", "sandy_loam", "loamy", "clayey", "custom")
APPLICATION_PROFILE_OPTIONS = ("dripline", "sprinkler", "micro", "custom")
DEVELOPMENT_STAGE_OPTIONS = ("new", "established")
EXPOSURE_OPTIONS = ("sunny", "partial_shade", "shade")

QualitativeLevel = Literal["low", "medium", "high"]
WateringTendency = Literal["small_frequent", "balanced", "deep_infrequent"]

_LEVELS: tuple[QualitativeLevel, ...] = ("low", "medium", "high")


@dataclass(frozen=True, slots=True)
class _PlantProfile:
    water_need: QualitativeLevel
    drought_sensitivity: QualitativeLevel
    watering_tendency: WateringTendency


@dataclass(frozen=True, slots=True)
class _SoilProfile:
    storage: QualitativeLevel
    infiltration: QualitativeLevel


@dataclass(frozen=True, slots=True)
class _ApplicationProfile:
    soak_suitability: QualitativeLevel


_PLANTS: dict[str, _PlantProfile] = {
    "lawn": _PlantProfile("high", "high", "small_frequent"),
    "hedge_woody": _PlantProfile("medium", "low", "deep_infrequent"),
    "perennials": _PlantProfile("medium", "medium", "balanced"),
    "vegetables": _PlantProfile("high", "high", "small_frequent"),
    "containers": _PlantProfile("high", "high", "small_frequent"),
    "young_plants": _PlantProfile("high", "high", "small_frequent"),
    "groundcover": _PlantProfile("low", "low", "deep_infrequent"),
}
_SOILS: dict[str, _SoilProfile] = {
    "sandy": _SoilProfile("low", "high"),
    "sandy_loam": _SoilProfile("medium", "high"),
    "loamy": _SoilProfile("high", "medium"),
    "clayey": _SoilProfile("high", "low"),
}
_APPLICATIONS: dict[str, _ApplicationProfile] = {
    "dripline": _ApplicationProfile("low"),
    "sprinkler": _ApplicationProfile("high"),
    "micro": _ApplicationProfile("medium"),
}

_FALLBACK_PLANT = _PlantProfile("medium", "medium", "balanced")
_FALLBACK_SOIL = _SoilProfile("medium", "medium")
_FALLBACK_APPLICATION = _ApplicationProfile("medium")


@dataclass(frozen=True, slots=True)
class ProfileRecommendation:
    """Immutable qualitative recommendation for one irrigation zone."""

    catalog_version: str
    quality: QualitativeLevel
    water_need: QualitativeLevel
    drought_sensitivity: QualitativeLevel
    soil_storage: QualitativeLevel
    infiltration: QualitativeLevel
    watering_tendency: WateringTendency
    soak_suitability: QualitativeLevel
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    conflicts: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a detached JSON-friendly representation for config flows."""
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        result["warnings"] = list(self.warnings)
        result["conflicts"] = list(self.conflicts)
        return result


@dataclass(frozen=True, slots=True)
class _SubareaAssessment:
    water_need: QualitativeLevel
    drought_sensitivity: QualitativeLevel
    soil_storage: QualitativeLevel
    infiltration: QualitativeLevel
    watering_tendency: WateringTendency
    soak_suitability: QualitativeLevel
    relative_application_rate: float | None


def _level_index(value: QualitativeLevel) -> int:
    return _LEVELS.index(value)


def _shift(value: QualitativeLevel, amount: int) -> QualitativeLevel:
    return _LEVELS[min(2, max(0, _level_index(value) + amount))]


def _highest(values: Sequence[QualitativeLevel]) -> QualitativeLevel:
    return max(values, key=_level_index)


def _representative(values: Sequence[QualitativeLevel]) -> QualitativeLevel:
    return _LEVELS[round(sum(_level_index(value) for value in values) / len(values))]


def _materially_different(values: Sequence[QualitativeLevel]) -> bool:
    indexes = [_level_index(value) for value in values]
    return max(indexes) - min(indexes) == 2


def _profile_id(subarea: Mapping[str, object], key: str) -> str | None:
    value = subarea.get(key)
    return value if isinstance(value, str) and value else None


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    result = float(value)
    return result if math.isfinite(result) and result > 0 else None


def _unique(messages: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(messages))


def recommend_profiles(subareas: Sequence[Mapping[str, object]]) -> ProfileRecommendation:
    """Recommend broad qualitative behavior without mutating subarea input."""
    reasons: list[str] = []
    warnings: list[str] = []
    assessments: list[_SubareaAssessment] = []
    low_quality = False

    for subarea in subareas:
        name_value = subarea.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            reasons.append("missing_name")
            low_quality = True
        if _positive_number(subarea.get("area_m2")) is None:
            reasons.append("missing_or_invalid_area")
            low_quality = True

        plant_id = _profile_id(subarea, "plant_profile")
        plant = _PLANTS.get(plant_id or "")
        if plant is None:
            plant = _FALLBACK_PLANT
            if plant_id is None:
                reasons.append("missing_plant_profile")
            elif plant_id == "custom":
                reasons.append("custom_plant_profile")
            else:
                reasons.append("unknown_plant_profile")
            low_quality = True

        soil_id = _profile_id(subarea, "soil_profile")
        soil = _SOILS.get(soil_id or "")
        if soil is None:
            soil = _FALLBACK_SOIL
            if soil_id is None:
                reasons.append("missing_soil_profile")
            elif soil_id == "custom":
                reasons.append("custom_soil_profile")
            else:
                reasons.append("unknown_soil_profile")
            low_quality = True

        application_id = _profile_id(subarea, "application_profile")
        application = _APPLICATIONS.get(application_id or "")
        if application is None:
            application = _FALLBACK_APPLICATION
            if application_id is None:
                reasons.append("missing_application_profile")
            elif application_id == "custom":
                reasons.append("custom_application_profile")
            else:
                reasons.append("unknown_application_profile")
            low_quality = True

        development = _profile_id(subarea, "development_stage")
        if development not in DEVELOPMENT_STAGE_OPTIONS:
            reasons.append("missing_or_unknown_development_stage")
            low_quality = True
            development = "established"
        exposure = _profile_id(subarea, "exposure")
        if exposure not in EXPOSURE_OPTIONS:
            reasons.append("missing_or_unknown_exposure")
            low_quality = True
            exposure = "partial_shade"

        water_shift = {"sunny": 1, "partial_shade": 0, "shade": -1}[exposure]
        if development == "new":
            water_shift += 1
        mulched = subarea.get("mulched")
        if mulched is True:
            water_shift -= 1
        elif mulched is not None and mulched is not False:
            warnings.append("invalid_mulch_ignored")

        tendency_index = {
            "small_frequent": 0,
            "balanced": 1,
            "deep_infrequent": 2,
        }[plant.watering_tendency]
        tendency_index += _level_index(soil.storage) - 1
        tendency: WateringTendency = (
            "small_frequent",
            "balanced",
            "deep_infrequent",
        )[min(2, max(0, tendency_index))]

        soak = application.soak_suitability
        slope = subarea.get("slope_percent")
        if slope is not None:
            if (
                isinstance(slope, bool)
                or not isinstance(slope, int | float)
                or not math.isfinite(slope)
                or slope < 0
            ):
                warnings.append("invalid_slope_ignored")
            elif slope > 0:
                soak = _shift(soak, 1)
        if soil.infiltration == "low":
            soak = _shift(soak, 1)
        elif soil.infiltration == "high":
            soak = _shift(soak, -1)

        relative_rate = None
        if "relative_application_rate" in subarea:
            relative_rate = _positive_number(subarea["relative_application_rate"])
            if relative_rate is None:
                warnings.append("invalid_relative_application_rate_ignored")
                low_quality = True

        assessments.append(
            _SubareaAssessment(
                water_need=_shift(plant.water_need, water_shift),
                drought_sensitivity=_shift(
                    plant.drought_sensitivity, 1 if development == "new" else 0
                ),
                soil_storage=soil.storage,
                infiltration=soil.infiltration,
                watering_tendency=tendency,
                soak_suitability=soak,
                relative_application_rate=relative_rate,
            )
        )

    if not assessments:
        reasons.append("no_subareas")
        low_quality = True
        assessments.append(
            _SubareaAssessment(
                water_need="medium",
                drought_sensitivity="medium",
                soil_storage="medium",
                infiltration="medium",
                watering_tendency="balanced",
                soak_suitability="medium",
                relative_application_rate=None,
            )
        )

    conflicts: list[str] = []
    water_needs = [assessment.water_need for assessment in assessments]
    storages = [assessment.soil_storage for assessment in assessments]
    if _materially_different(water_needs):
        conflicts.append("different_plant_water_need")
    if _materially_different(storages):
        conflicts.append("different_soil_storage")
    relative_rates = [
        assessment.relative_application_rate
        for assessment in assessments
        if assessment.relative_application_rate is not None
    ]
    if len(set(relative_rates)) > 1:
        conflicts.append("different_relative_application_rates")

    if low_quality:
        quality: QualitativeLevel = "low"
    elif conflicts:
        quality = "medium"
        reasons.append("subarea_conflicts")
    else:
        quality = "high"
        reasons.append("complete_known_profiles")

    tendencies = [assessment.watering_tendency for assessment in assessments]
    tendency_order: tuple[WateringTendency, ...] = (
        "small_frequent",
        "balanced",
        "deep_infrequent",
    )
    watering_tendency: WateringTendency = tendency_order[
        round(sum(tendency_order.index(value) for value in tendencies) / len(tendencies))
    ]

    return ProfileRecommendation(
        catalog_version=CATALOG_VERSION,
        quality=quality,
        water_need=_highest(water_needs),
        drought_sensitivity=_highest(
            [assessment.drought_sensitivity for assessment in assessments]
        ),
        soil_storage=_representative(storages),
        infiltration=_representative([assessment.infiltration for assessment in assessments]),
        watering_tendency=watering_tendency,
        soak_suitability=_highest([assessment.soak_suitability for assessment in assessments]),
        reasons=_unique(reasons),
        warnings=_unique(warnings),
        conflicts=_unique(conflicts),
    )
