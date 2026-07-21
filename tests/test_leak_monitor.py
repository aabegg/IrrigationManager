"""Focused domain tests for idle-flow leak observation."""

import pytest

from custom_components.irrigation_manager.leak_monitor import LeakObservation


def test_short_idle_flow_artifact_does_not_confirm_a_leak() -> None:
    """Discard flow that falls below the threshold before the minimum duration."""
    observation = LeakObservation.start(at=10.0, flow_l_min=1.2)

    assert observation.confirm(at=39.9, minimum_duration_seconds=30) is None


def test_confirmed_idle_flow_integrates_the_observation_interval() -> None:
    """Use event samples to integrate unassigned water when no meter exists."""
    observation = LeakObservation.start(at=10.0, flow_l_min=1.0)
    observation = observation.observe(at=20.0, flow_l_min=2.0)

    result = observation.confirm(at=40.0, minimum_duration_seconds=30)

    assert result is not None
    assert result.duration_seconds == 30
    assert result.integrated_liters == pytest.approx(0.8333333333)
