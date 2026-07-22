"""Behavior tests for immutable profiles and Teilflaeche aggregation."""

from datetime import date

import pytest

from custom_components.irrigation_manager.profiles import (
    builtin_profiles,
    copy_profile,
    dependent_profile_ids,
    profile_impacted_zones,
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
    assert result.maximum_deficit_mm == 40
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
