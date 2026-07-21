"""Behavior tests for Home Assistant hardware adapters."""

import pytest
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.irrigation_manager.adapters import HomeAssistantFlow, HomeAssistantMeter


async def test_flow_adapter_rejects_non_finite_values(
    hass: HomeAssistant,
) -> None:
    """Never let NaN silently bypass flow safety comparisons."""
    hass.states.async_set(
        "sensor.flow",
        "nan",
        {ATTR_UNIT_OF_MEASUREMENT: (UnitOfVolumeFlowRate.LITERS_PER_MINUTE)},
    )

    with pytest.raises(HomeAssistantError, match="not plausible"):
        await HomeAssistantFlow(hass, "sensor.flow", max_age_seconds=30).read_l_min()


async def test_meter_adapter_rejects_small_regression_without_corrupting_baseline(
    hass: HomeAssistant,
) -> None:
    """Keep the last accepted raw sample when a decrease is not reset-like."""
    entity_id = "sensor.water_meter"
    attributes = {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS}
    hass.states.async_set(entity_id, "100", attributes)
    meter = HomeAssistantMeter(hass, entity_id)
    assert await meter.read_liters() == 100

    hass.states.async_set(entity_id, "99", attributes)
    with pytest.raises(HomeAssistantError, match="invalid decrease"):
        await meter.read_liters()

    hass.states.async_set(entity_id, "101", attributes)
    assert await meter.read_liters() == 101


async def test_meter_adapter_preserves_continuity_for_conservative_reset(
    hass: HomeAssistant,
) -> None:
    """Accept a material drop back near source origin as a source reset."""
    entity_id = "sensor.water_meter"
    attributes = {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS}
    hass.states.async_set(entity_id, "8490", attributes)
    meter = HomeAssistantMeter(hass, entity_id)
    assert await meter.read_liters() == 8490

    hass.states.async_set(entity_id, "3", attributes)
    assert await meter.read_liters() == 8493
