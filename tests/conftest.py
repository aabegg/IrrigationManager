"""Shared Home Assistant fixtures for Irrigation Manager."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable loading custom integrations in every HA test."""


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Prevent a flow test from starting the complete integration."""
    with patch(
        "custom_components.irrigation_manager.async_setup_entry",
        return_value=True,
        create=True,
    ):
        yield
