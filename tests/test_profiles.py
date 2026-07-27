"""Behavioral tests for the qualitative profile recommender."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from custom_components.irrigation_manager.profiles import (
    APPLICATION_PROFILE_OPTIONS,
    CATALOG_VERSION,
    DEVELOPMENT_STAGE_OPTIONS,
    EXPOSURE_OPTIONS,
    PLANT_PROFILE_OPTIONS,
    SOIL_PROFILE_OPTIONS,
    ProfileRecommendation,
    recommend_profiles,
)


def _subarea(**overrides: object) -> dict[str, object]:
    subarea: dict[str, object] = {
        "name": "Main bed",
        "area_m2": 12.0,
        "plant_profile": "perennials",
        "development_stage": "established",
        "exposure": "partial_shade",
        "soil_profile": "loamy",
        "application_profile": "dripline",
    }
    subarea.update(overrides)
    return subarea


def test_catalog_exposes_stable_config_flow_options() -> None:
    """Expose the complete first catalog through ordered immutable options."""
    assert CATALOG_VERSION
    assert PLANT_PROFILE_OPTIONS == (
        "lawn",
        "hedge_woody",
        "perennials",
        "vegetables",
        "containers",
        "young_plants",
        "groundcover",
        "custom",
    )
    assert SOIL_PROFILE_OPTIONS == (
        "sandy",
        "sandy_loam",
        "loamy",
        "clayey",
        "custom",
    )
    assert APPLICATION_PROFILE_OPTIONS == ("dripline", "sprinkler", "micro", "custom")
    assert DEVELOPMENT_STAGE_OPTIONS == ("new", "established")
    assert EXPOSURE_OPTIONS == ("sunny", "partial_shade", "shade")


def test_complete_known_homogeneous_input_returns_high_quality_recommendation() -> None:
    """Known catalog data is sufficient for a fully qualitative recommendation."""
    recommendation = recommend_profiles([_subarea()])

    assert isinstance(recommendation, ProfileRecommendation)
    assert recommendation.catalog_version == CATALOG_VERSION
    assert recommendation.quality == "high"
    assert recommendation.water_need == "medium"
    assert recommendation.drought_sensitivity == "medium"
    assert recommendation.soil_storage == "high"
    assert recommendation.infiltration == "medium"
    assert recommendation.watering_tendency == "deep_infrequent"
    assert recommendation.soak_suitability == "low"
    assert recommendation.conflicts == ()
    assert recommendation.warnings == ()


def test_recommendation_is_frozen_and_serializes_without_absolute_targets() -> None:
    """Config flows can serialize output without exposing absolute scheduling claims."""
    source = [_subarea(slope_percent=8, mulched=True, relative_application_rate=1.0)]
    original = deepcopy(source)

    recommendation = recommend_profiles(source)
    serialized = recommendation.as_dict()

    assert source == original
    assert json.loads(json.dumps(serialized)) == serialized
    assert isinstance(serialized["reasons"], list)
    assert isinstance(serialized["warnings"], list)
    assert isinstance(serialized["conflicts"], list)
    assert not {"liters", "seconds", "frequency"} & serialized.keys()
    with pytest.raises(FrozenInstanceError):
        recommendation.quality = "low"  # type: ignore[misc]


def test_custom_and_unknown_profiles_lower_quality_with_explicit_explanations() -> None:
    """Uncatalogued data remains usable but cannot imply unwarranted confidence."""
    recommendation = recommend_profiles(
        [
            _subarea(
                plant_profile="custom",
                soil_profile="volcanic",
                application_profile="custom",
            )
        ]
    )

    assert recommendation.quality == "low"
    assert "custom_plant_profile" in recommendation.reasons
    assert "unknown_soil_profile" in recommendation.reasons
    assert "custom_application_profile" in recommendation.reasons


def test_materially_different_subareas_report_conflicts_and_reduce_quality() -> None:
    """One valve cannot independently satisfy substantially different subareas."""
    recommendation = recommend_profiles(
        [
            _subarea(
                name="Dry groundcover",
                plant_profile="groundcover",
                soil_profile="sandy",
                relative_application_rate=0.6,
            ),
            _subarea(
                name="Vegetable bed",
                plant_profile="vegetables",
                soil_profile="clayey",
                application_profile="sprinkler",
                relative_application_rate=1.4,
            ),
        ]
    )

    assert recommendation.quality == "medium"
    assert "different_plant_water_need" in recommendation.conflicts
    assert "different_soil_storage" in recommendation.conflicts
    assert "different_relative_application_rates" in recommendation.conflicts


def test_missing_required_profile_data_returns_low_quality_instead_of_guessing() -> None:
    """Incomplete mappings produce transparent fallbacks for an in-progress wizard."""
    subarea = _subarea()
    del subarea["plant_profile"]

    recommendation = recommend_profiles([subarea])

    assert recommendation.quality == "low"
    assert "missing_plant_profile" in recommendation.reasons
