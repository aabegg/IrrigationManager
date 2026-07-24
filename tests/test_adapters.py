"""Behavior tests for Home Assistant hardware adapters."""

import asyncio

import pytest
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.irrigation_manager.adapters import (
    HomeAssistantActuators,
    HomeAssistantFlow,
    HomeAssistantMeter,
)


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
        await HomeAssistantFlow(hass, "sensor.flow").read_l_min()


async def test_unchanged_measurements_remain_readable_without_heartbeat(
    hass: HomeAssistant,
) -> None:
    """Treat available cumulative and flow states as observations without republishing."""
    hass.states.async_set(
        "sensor.water_meter",
        "42",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
    )
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    meter = HomeAssistantMeter(hass, "sensor.water_meter")
    flow = HomeAssistantFlow(hass, "sensor.flow")

    await asyncio.sleep(0.01)

    assert await meter.read_liters() == 42
    assert await flow.read_l_min() == 0


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


async def test_raw_count_meter_uses_explicit_liters_per_count(hass: HomeAssistant) -> None:
    """Normalize a unitless pulse total only through its configured factor."""
    hass.states.async_set("sensor.pulses", "42")
    meter = HomeAssistantMeter(hass, "sensor.pulses", liters_per_count=2.5)

    assert await meter.read_raw_liters() == 105
    assert await meter.read_liters() == 105


async def test_separate_feedback_supports_binary_switch_and_valve_states(
    hass: HomeAssistant,
) -> None:
    """Observe the configured feedback while keeping commands on the actuator entity."""
    calls: list[tuple[str, str]] = []

    async def turn_on(call) -> None:
        calls.append(("turn_on", call.data["entity_id"]))
        hass.states.async_set("binary_sensor.zone_feedback", STATE_ON)

    async def turn_off(call) -> None:
        calls.append(("turn_off", call.data["entity_id"]))
        hass.states.async_set("binary_sensor.zone_feedback", STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.zone", STATE_OFF)
    hass.states.async_set("binary_sensor.zone_feedback", STATE_OFF)
    actuators = HomeAssistantActuators(
        hass,
        transition_grace_seconds=0.1,
        feedback_entities={"switch.zone": "binary_sensor.zone_feedback"},
    )

    await actuators.open("switch.zone")
    assert await actuators.is_open("switch.zone")
    await actuators.close("switch.zone")

    assert calls == [("turn_on", "switch.zone"), ("turn_off", "switch.zone")]


async def test_separate_feedback_fails_closed_when_unavailable_or_stale(
    hass: HomeAssistant,
) -> None:
    """Reject unavailable and expired feedback instead of trusting command state."""
    actuators = HomeAssistantActuators(
        hass,
        feedback_entities={"switch.zone": "binary_sensor.zone_feedback"},
        feedback_max_age_seconds=1,
    )
    hass.states.async_set("binary_sensor.zone_feedback", STATE_UNAVAILABLE)
    with pytest.raises(HomeAssistantError, match="not available"):
        await actuators.is_open("switch.zone")

    hass.states.async_set("binary_sensor.zone_feedback", STATE_OFF)
    actuators = HomeAssistantActuators(
        hass,
        feedback_entities={"switch.zone": "binary_sensor.zone_feedback"},
        feedback_max_age_seconds=-1,
    )
    with pytest.raises(HomeAssistantError, match="stale"):
        await actuators.is_open("switch.zone")
