"""Structured events and deduplicated critical notifications."""

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_NOTIFY_ENTITIES, DOMAIN, EVENT_IRRIGATION_MANAGER

LOGGER = logging.getLogger(__name__)


class IrrigationEventPublisher:
    """Publish the integration's stable, secret-free operational contract."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        installation_id: str,
        installation_name: str,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize an installation-scoped publisher."""
        self._hass = hass
        self._installation_id = installation_id
        self._installation_name = installation_name
        raw_targets = config.get(CONF_NOTIFY_ENTITIES, [])
        self._notify_entities = (
            tuple(value for value in raw_targets if isinstance(value, str))
            if isinstance(raw_targets, list | tuple)
            else ()
        )
        self._notification_signatures: dict[str, str] = {}

    def fire(
        self,
        event_type: str,
        *,
        reason: str,
        target: Mapping[str, object] | None = None,
        measurements: Mapping[str, object] | None = None,
        quality: str | None = None,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Fire one explicitly shaped event without config or entity values."""
        self._hass.bus.async_fire(
            EVENT_IRRIGATION_MANAGER,
            {
                "event_type": event_type,
                "installation_id": self._installation_id,
                "reason": reason,
                "target": dict(target or {}),
                "measurements": dict(measurements or {}),
                "quality": quality,
                "context": dict(context or {}),
            },
        )

    async def async_critical(
        self,
        notification_key: str,
        *,
        title: str,
        message: str,
    ) -> None:
        """Create or replace one persistent alert and optionally notify targets once."""
        notification_id = f"{DOMAIN}_{self._installation_id}_{notification_key}"
        persistent_notification.async_create(
            self._hass,
            message,
            title=title,
            notification_id=notification_id,
        )
        signature = f"{title}\n{message}"
        if self._notification_signatures.get(notification_key) == signature:
            return
        self._notification_signatures[notification_key] = signature
        for entity_id in self._notify_entities:
            try:
                await self._hass.services.async_call(
                    "notify",
                    "send_message",
                    {"message": message, "title": title},
                    target={"entity_id": entity_id},
                    blocking=False,
                )
            except HomeAssistantError:
                LOGGER.warning("Could not send critical irrigation notification to %s", entity_id)

    def installation_target(self) -> dict[str, str]:
        """Return a stable installation event target."""
        return {"type": "installation", "id": self._installation_id}

    def zone_target(self, zone_id: str) -> dict[str, str]:
        """Return a stable zone event target."""
        return {"type": "zone", "id": zone_id}

    @property
    def installation_name(self) -> str:
        """Return the human-readable name for notification text only."""
        return self._installation_name
