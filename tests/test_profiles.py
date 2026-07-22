"""Behavior tests for immutable profiles and Teilflaeche aggregation."""

from datetime import date

import pytest

from custom_components.irrigation_manager.profiles import (
    PROFILE_SCHEMA_VERSION,
    builtin_profiles,
    copy_profile,
    dependent_profile_ids,
    profile_impacted_zones,
    profile_select_options,
    resolve_effective_zone_profile,
    validate_custom_profiles,
)


def test_builtin_profile_copy_is_user_owned_and_does_not_mutate_source() -> None:
    """Copy a generic built-in into detached customizable storage."""
    source_before = builtin_profiles()

    custom = copy_profile(
        {},
        source_id="builtin:plant:generic-neutral:v1",
        new_id="plant:my-lawn",
        name="My lawn",
    )
    custom["plant:my-lawn"]["values"] = {"seasonal_kc": [0.5] * 12}

    assert builtin_profiles() == source_before
    assert custom["plant:my-lawn"]["based_on"] == "builtin:plant:generic-neutral:v1"
    assert custom["plant:my-lawn"]["name"] == "My lawn"
    assert "localized_names" not in custom["plant:my-lawn"]


def test_custom_profile_cannot_replace_a_builtin() -> None:
    """Reserve built-in IDs for the immutable versioned catalog."""
    with pytest.raises(ValueError, match="must not use builtin"):
        validate_custom_profiles(
            {
                "builtin:plant:generic-neutral:v1": {
                    "kind": "plant",
                    "values": {"seasonal_kc": [2.0] * 12},
                }
            }
        )


def test_impact_preview_follows_profile_copy_chain() -> None:
    """Include zones using a copy derived from the profile being changed."""
    custom = {
        "plant:base": {"kind": "plant", "values": {"seasonal_kc": [1.0] * 12}},
        "plant:copy": {
            "kind": "plant",
            "based_on": "plant:base",
            "values": {},
        },
    }

    impacted = profile_impacted_zones(
        [("zone-1", "Bed", {"plant_profile": "plant:copy"})],
        dependent_profile_ids(custom, "plant:base"),
    )

    assert impacted == [{"zone_id": "zone-1", "name": "Bed"}]


def test_subareas_form_one_area_weighted_effective_zone_profile() -> None:
    """Keep one balance while exposing hydraulic distribution mismatch."""
    result = resolve_effective_zone_profile(
        {
            "seasonal_crop_factors": [1.0] * 12,
            "application_efficiency": 0.8,
            "maximum_deficit_mm": 40,
            "rain_factor": 0.5,
            "subareas": [
                {
                    "id": "lawn",
                    "area_m2": 30,
                    "relative_application_rate": 1,
                    "overrides": {"crop_factor": 1},
                },
                {
                    "id": "bed",
                    "area_m2": 10,
                    "relative_application_rate": 4,
                    "overrides": {"crop_factor": 2},
                },
            ],
        },
        {},
        date(2026, 7, 15),
    )

    assert result.area_m2 == 40
    assert result.crop_and_location_factor == pytest.approx(1.25)
    assert result.application_efficiency == 0.8
    assert result.total_available_water_mm == 25
    assert result.readily_available_water_mm == 25
    assert result.distribution_warnings
    assert len(result.subareas) == 2


def test_mixed_subarea_efficiencies_sum_gross_demand_before_display_efficiency() -> None:
    """Derive one equivalent efficiency from the independently grossed Teilflaechen."""
    result = resolve_effective_zone_profile(
        {
            "subareas": [
                {
                    "id": "efficient",
                    "area_m2": 10,
                    "overrides": {
                        "crop_factor": 1,
                        "application_efficiency": 1,
                    },
                },
                {
                    "id": "lossy",
                    "area_m2": 10,
                    "overrides": {
                        "crop_factor": 1,
                        "application_efficiency": 0.5,
                    },
                },
            ],
        },
        {},
        date(2026, 7, 15),
    )

    assert result.application_efficiency == pytest.approx(2 / 3)
    assert result.resolved_inputs["gross_liters_per_zone_deficit_mm"] == pytest.approx(30)
    assert result.subareas[0]["gross_liters_per_zone_deficit_mm"] == pytest.approx(10)
    assert result.subareas[1]["gross_liters_per_zone_deficit_mm"] == pytest.approx(20)


def test_mixed_crop_factors_and_efficiencies_use_consistent_local_net_depths() -> None:
    """Scale local net depth around the common weighted deficit, then gross each part."""
    result = resolve_effective_zone_profile(
        {
            "subareas": [
                {
                    "id": "low-demand",
                    "area_m2": 10,
                    "overrides": {
                        "crop_factor": 1,
                        "application_efficiency": 1,
                    },
                },
                {
                    "id": "high-demand",
                    "area_m2": 10,
                    "overrides": {
                        "crop_factor": 2,
                        "application_efficiency": 0.5,
                    },
                },
            ],
        },
        {},
        date(2026, 7, 15),
    )

    assert result.crop_and_location_factor == pytest.approx(1.5)
    assert result.application_efficiency == pytest.approx(0.6)
    assert result.resolved_inputs["gross_liters_per_zone_deficit_mm"] == pytest.approx(100 / 3)
    assert result.subareas[0]["net_depth_factor"] == pytest.approx(2 / 3)
    assert result.subareas[1]["net_depth_factor"] == pytest.approx(4 / 3)


def test_monthly_kc_curve_is_interpolated_for_subarea() -> None:
    """Interpolate the annual Kc curve instead of changing it at month boundaries."""
    custom = {
        "plant:seasonal": {
            "kind": "plant",
            "values": {"seasonal_kc": [0.2, 0.4, 0.6, 0.8, 1, 1, 1, 1, 0.8, 0.6, 0.4, 0.2]},
        }
    }
    early = resolve_effective_zone_profile(
        {"area_m2": 1, "plant_profile": "plant:seasonal"}, custom, date(2026, 3, 1)
    )
    middle = resolve_effective_zone_profile(
        {
            "area_m2": 1,
            "plant_profile": "plant:seasonal",
            "seasonal_crop_factors": [1.0] * 12,
        },
        custom,
        date(2026, 3, 16),
    )

    assert 0.4 < early.crop_and_location_factor < 0.6
    assert middle.crop_and_location_factor == pytest.approx(0.6, abs=0.01)


def test_researched_profile_catalog_contains_sources_ranges_and_confirmation() -> None:
    """Expose uncertainty and provenance rather than presenting defaults as exact."""
    profiles = {profile["id"]: profile for profile in builtin_profiles()}

    annuals = profiles["builtin:plant:annual-flowers:v1"]
    assert annuals["confidence"] == "low"
    assert annuals["confirmation_required"] is True
    assert annuals["ranges"]["seasonal_plant_factor"] == [0.6, 0.6]
    assert annuals["values"]["coefficient_basis"] == "landscape_pf"
    assert annuals["sources"]

    custom = copy_profile(
        {},
        source_id="builtin:plant:annual-flowers:v1",
        new_id="plant:my-annuals",
        name="My annuals",
    )
    option = next(
        item
        for item in profile_select_options(custom, "plant")
        if item["value"] == "plant:my-annuals"
    )
    assert option["label"].startswith("My annuals |")


def test_taw_and_raw_are_derived_separately_from_researched_metadata() -> None:
    """Use root-zone storage as TAW and depletion fraction only for RAW."""
    result = resolve_effective_zone_profile(
        {
            "area_m2": 10,
            "plant_profile": "builtin:plant:cool-season-turf:v1",
            "soil_profile": "builtin:soil:sandy-loam:v1",
            "irrigation_profile": "builtin:irrigation:drip:v1",
            "maximum_deficit_mm": 999,
            "application_efficiency": 0.1,
        },
        {},
        date(2026, 7, 15),
    )

    assert result.total_available_water_mm == pytest.approx(120 * 0.3)
    assert result.readily_available_water_mm == pytest.approx(120 * 0.3 * 0.4)
    assert result.maximum_deficit_mm == result.total_available_water_mm
    assert result.application_efficiency == 0.9
    assert result.resolved_inputs["profile_schema_version"] == PROFILE_SCHEMA_VERSION
    assert result.subareas[0]["water_limit_origin"] == "derived_awc_root_depth"


def test_legacy_profile_override_preserves_equal_taw_and_raw() -> None:
    """Preserve the old one-limit behavior explicitly for persisted overrides."""
    result = resolve_effective_zone_profile(
        {
            "plant_profile": "builtin:plant:warm-season-turf:v1",
            "soil_profile": "builtin:soil:sand:v1",
            "profile_overrides": {"maximum_deficit_mm": 7},
        },
        {},
        date(2026, 7, 15),
    )

    assert result.maximum_deficit_mm == 7
    assert result.total_available_water_mm == 7
    assert result.readily_available_water_mm == 7
    assert result.legacy_water_limit is True
    assert result.subareas[0]["water_limit_origin"] == "explicit_legacy_profile_override"


def test_mixed_vegetable_stages_require_and_interpolate_a_local_schedule() -> None:
    """Interpolate explicit local dates without inventing planting months or hemisphere."""
    base = {
        "plant_profile": "builtin:plant:mixed-vegetables:v1",
        "soil_profile": "builtin:soil:loam:v1",
    }
    fallback = resolve_effective_zone_profile(base, {}, date(2026, 7, 15))
    development = resolve_effective_zone_profile(
        {
            **base,
            "phenology_stage_schedule": {
                "season_start": "06-01",
                "initial_days": 10,
                "development_days": 10,
                "mid_days": 10,
                "late_days": 10,
            },
        },
        {},
        date(2026, 6, 16),
    )

    assert fallback.crop_and_location_factor == 1.05
    assert fallback.total_available_water_mm == pytest.approx(150 * 0.45)
    assert fallback.readily_available_water_mm == pytest.approx(150 * 0.45 * 0.35)
    assert fallback.subareas[0]["profile_warnings"] == ["phenology_mapping_required"]
    assert development.crop_and_location_factor == pytest.approx(0.825)
    assert development.total_available_water_mm == pytest.approx(150 * 0.325)
    assert development.readily_available_water_mm == pytest.approx(150 * 0.325 * 0.35)
    assert development.subareas[0]["phenology_stage"] == "development"
    assert development.subareas[0]["phenology_stage_progress"] == 0.5
    assert development.subareas[0]["profile_warnings"] == []


def test_landscape_plant_factor_does_not_apply_location_factor_twice() -> None:
    """Treat a landscape PF as the complete plant/location coefficient."""
    result = resolve_effective_zone_profile(
        {
            "plant_profile": "builtin:plant:annual-flowers:v1",
            "exposure_profile": "exposure:hot-dry",
        },
        {
            "exposure:hot-dry": {
                "kind": "exposure",
                "values": {"location_factor": 1.4},
            }
        },
        date(2026, 7, 15),
    )

    assert result.crop_and_location_factor == 0.6
    assert result.subareas[0]["coefficient_basis"] == "landscape_pf"
    assert result.subareas[0]["location_factor_applied"] == 1
    assert result.subareas[0]["profile_warnings"] == ["location_factor_ignored_for_landscape_pf"]


def test_phenology_schedule_accepts_explicit_recurring_dates_across_year_end() -> None:
    """Resolve a local season across New Year without inferring a hemisphere."""
    result = resolve_effective_zone_profile(
        {
            "plant_profile": "builtin:plant:mixed-vegetables:v1",
            "soil_profile": "builtin:soil:loam:v1",
            "phenology_stage_schedule": {
                "season_start": "11-01",
                "development_start": "11-15",
                "mid_start": "12-01",
                "late_start": "01-15",
                "season_end": "02-15",
            },
        },
        {},
        date(2027, 1, 20),
    )

    assert result.subareas[0]["phenology_stage"] == "late"
    assert 0 < result.subareas[0]["phenology_stage_progress"] < 1
    assert 0.85 < result.crop_and_location_factor < 1.05
