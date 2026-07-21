"""Behavior tests for Home Assistant hardware adapters."""

import pytest
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.irrigation_manager.adapters import HomeAssistantFlow


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
