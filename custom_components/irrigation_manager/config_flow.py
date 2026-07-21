"""Config and subentry flows for Irrigation Manager."""

from typing import Any, override
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, Platform, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_DEFAULT_DURATION,
    CONF_FLOW_GRACE_SECONDS,
    CONF_FLOW_MAX_AGE_SECONDS,
    CONF_FLOW_SENSOR,
    CONF_MAIN_VALVE,
    CONF_MAX_FLOW,
    CONF_MIN_FLOW,
    CONF_WATER_METER,
    CONF_WEATHER_ENTITY,
    CONF_ZONE_VALVE,
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)

INSTALLATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Optional(CONF_MAIN_VALVE): EntitySelector(
            EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
        ),
        vol.Optional(CONF_WATER_METER): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_FLOW_SENSOR): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_FLOW_MAX_AGE_SECONDS, default=30): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_WEATHER_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=Platform.WEATHER)
        ),
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Required(CONF_ZONE_VALVE): EntitySelector(
            EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
        ),
        vol.Required(CONF_DEFAULT_DURATION, default=600): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=14_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_MIN_FLOW): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=10_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            )
        ),
        vol.Optional(CONF_MAX_FLOW): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=10_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            )
        ),
        vol.Optional(CONF_FLOW_GRACE_SECONDS, default=5): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=300,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
    }
)


class IrrigationManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create and reconfigure irrigation installations."""

    VERSION = 1
    MINOR_VERSION = 0

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create one physical irrigation installation."""
        if user_input is not None:
            await self.async_set_unique_id(uuid4().hex)
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=INSTALLATION_SCHEMA)

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported repeatable child configurations."""
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlow}


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Create and reconfigure one irrigation zone."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a zone to the parent irrigation installation."""
        if user_input is not None:
            if self._valve_is_configured(user_input[CONF_ZONE_VALVE]):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
                unique_id=uuid4().hex,
            )

        return self.async_show_form(step_id="user", data_schema=ZONE_SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Update an existing zone without changing its stable identity."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            if self._valve_is_configured(
                user_input[CONF_ZONE_VALVE],
                excluding_subentry_id=subentry.subentry_id,
            ):
                return self.async_abort(reason="already_configured")
            return self.async_update_and_abort(
                entry,
                subentry,
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_SCHEMA,
                subentry.data,
            ),
        )

    def _valve_is_configured(
        self, valve_entity_id: str, excluding_subentry_id: str | None = None
    ) -> bool:
        """Return whether another zone already owns the logical valve."""
        return any(
            subentry.subentry_id != excluding_subentry_id
            and subentry.data.get(CONF_ZONE_VALVE) == valve_entity_id
            for subentry in self._get_entry().subentries.values()
        )
