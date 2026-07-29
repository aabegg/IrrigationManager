"""Version 2 service-surface tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.services import async_register_services

EXPECTED_SERVICES = {
    "cancel_request",
    "correct_physical_meter",
    "create_manual",
    "emergency_stop",
    "list_card_orders",
    "list_zone_history",
    "plan_automatic",
    "reset_safety_lock",
    "set_installation_automation",
    "set_installation_operation",
    "set_zone_automation",
    "set_zone_operation",
    "start_manual",
    "start_manual_from_card",
    "stop",
}


async def test_only_version_2_services_are_registered(hass: HomeAssistant) -> None:
    """Keep runtime registration and service metadata on the same narrow contract."""
    hass.data[DOMAIN] = {}

    await async_register_services(hass)

    assert set(hass.services.async_services()[DOMAIN]) == EXPECTED_SERVICES
    service_file = (
        Path(__file__).parents[1] / "custom_components" / "irrigation_manager" / "services.yaml"
    )
    assert set(yaml.safe_load(service_file.read_text(encoding="utf-8"))) == EXPECTED_SERVICES


def test_service_duration_fields_use_structured_selectors() -> None:
    """Present every service duration as separate native duration fields."""
    service_file = (
        Path(__file__).parents[1] / "custom_components" / "irrigation_manager" / "services.yaml"
    )
    metadata = yaml.safe_load(service_file.read_text(encoding="utf-8"))

    for service in ("start_manual", "create_manual", "start_manual_from_card"):
        fields = metadata[service]["fields"]
        assert fields["duration"]["selector"] == {
            "duration": {"enable_day": False, "enable_second": True}
        }
        assert fields["hard_time_limit"]["selector"] == {
            "duration": {"enable_day": False, "enable_second": True}
        }
    assert metadata["start_manual"]["fields"]["expiry"]["selector"] == {
        "duration": {"enable_day": False, "enable_second": True}
    }


async def test_plan_automatic_requires_explicit_legacy_repair_opt_in(
    hass: HomeAssistant,
) -> None:
    """Keep the pre-rc28 cancellation repair disabled unless an admin requests it."""
    manager = SimpleNamespace(async_plan_automatic=AsyncMock(return_value={"created": 1}))
    hass.data[DOMAIN] = {"installation": manager}

    with patch("custom_components.irrigation_manager.services.IrrigationManager", type(manager)):
        await async_register_services(hass)
        await hass.services.async_call(
            DOMAIN,
            "plan_automatic",
            {"config_entry_id": "installation"},
            blocking=True,
            return_response=True,
        )
        manager.async_plan_automatic.assert_awaited_once_with(replace_legacy_cancelled=False)

        manager.async_plan_automatic.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            "plan_automatic",
            {
                "config_entry_id": "installation",
                "replace_legacy_cancelled": True,
            },
            blocking=True,
            return_response=True,
        )

    manager.async_plan_automatic.assert_awaited_once_with(replace_legacy_cancelled=True)


async def test_emergency_stop_requires_admin_or_control_of_all_actuators(
    hass: HomeAssistant,
) -> None:
    """Reject a non-admin user lacking control permission for one affected valve."""
    manager = SimpleNamespace(
        emergency_control_entity_ids=lambda: ("switch.main", "switch.lawn"),
        async_emergency_stop=AsyncMock(),
    )
    hass.data[DOMAIN] = {"installation": manager}
    await async_register_services(hass)
    permissions = SimpleNamespace(
        check_entity=lambda entity_id, _policy: entity_id == "switch.lawn"
    )
    user = SimpleNamespace(is_admin=False, permissions=permissions)

    with (
        patch("custom_components.irrigation_manager.services.IrrigationManager", type(manager)),
        patch.object(hass.auth, "async_get_user", AsyncMock(return_value=user)),
        pytest.raises(Unauthorized),
    ):
        await hass.services.async_call(
            DOMAIN,
            "emergency_stop",
            {"config_entry_id": "installation"},
            blocking=True,
            context=Context(user_id="limited-user"),
        )

    manager.async_emergency_stop.assert_not_awaited()
