"""Config and subentry flows for Irrigation Manager."""

from typing import Any, override
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_NAME,
    Platform,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_APPLICATION_EFFICIENCY,
    CONF_AREA_M2,
    CONF_AUTOMATIC_MAX_DURATION,
    CONF_AUTOMATION_ENABLED,
    CONF_CALIBRATION_SETTLE_SECONDS,
    CONF_CROP_FACTOR,
    CONF_DEFAULT_DURATION,
    CONF_FLOW_GRACE_SECONDS,
    CONF_FLOW_MAX_AGE_SECONDS,
    CONF_FLOW_SENSOR,
    CONF_LEAK_DURATION_SECONDS,
    CONF_LEAK_FLOW_THRESHOLD,
    CONF_LEAK_MONITORING,
    CONF_MAIN_VALVE,
    CONF_MAINTENANCE_CONFIRMATION_INTERVAL,
    CONF_MAINTENANCE_MAX_DURATION,
    CONF_MANDATORY_AMOUNT_LITERS,
    CONF_MAX_DOSE_AMOUNT,
    CONF_MAX_DOSE_DURATION,
    CONF_MAX_FLOW,
    CONF_MAXIMUM_DEFICIT_MM,
    CONF_MAXIMUM_INTERVAL_DAYS,
    CONF_MAXIMUM_TARGET_LITERS,
    CONF_METER_FAILURE_STRATEGY,
    CONF_METER_MAX_AGE_SECONDS,
    CONF_MIN_FLOW,
    CONF_MINIMUM_EFFECTIVE_LITERS,
    CONF_MINIMUM_INTERVAL_DAYS,
    CONF_MINIMUM_TRIGGER_LITERS,
    CONF_NOTIFY_ENTITIES,
    CONF_RAIN_FACTOR,
    CONF_SOAK_DURATION,
    CONF_WATER_METER,
    CONF_WATERING_MODE,
    CONF_WATERING_WINDOWS,
    CONF_WEATHER_ENTITY,
    CONF_ZONE_PRIORITY,
    CONF_ZONE_VALVE,
    DOMAIN,
    METER_FAILURE_ABORT,
    METER_FAILURE_ESTIMATED_TIME_FALLBACK,
    SUBENTRY_TYPE_ZONE,
    WATERING_MODE_DEMAND,
    WATERING_MODE_MINIMUM,
)
from .scheduler import parse_daily_window

ATTR_ZONE_SUBENTRY_ID = "zone_subentry_id"

INSTALLATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Optional(CONF_MAIN_VALVE): EntitySelector(
            EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
        ),
        vol.Optional(CONF_WATER_METER): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_METER_MAX_AGE_SECONDS, default=300): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=86_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_FLOW_SENSOR): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_LEAK_MONITORING, default=True): BooleanSelector(),
        vol.Optional(CONF_LEAK_FLOW_THRESHOLD, default=0.5): NumberSelector(
            NumberSelectorConfig(
                min=0.1,
                max=10_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            )
        ),
        vol.Optional(CONF_LEAK_DURATION_SECONDS, default=30): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
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
        vol.Optional(CONF_NOTIFY_ENTITIES, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.NOTIFY, multiple=True)
        ),
        vol.Optional(CONF_MAINTENANCE_MAX_DURATION, default=300): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_MAINTENANCE_CONFIRMATION_INTERVAL, default=30): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=300,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_CALIBRATION_SETTLE_SECONDS, default=2): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=60,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
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
        vol.Optional(CONF_METER_FAILURE_STRATEGY, default=METER_FAILURE_ABORT): SelectSelector(
            SelectSelectorConfig(
                options=[METER_FAILURE_ABORT, METER_FAILURE_ESTIMATED_TIME_FALLBACK],
                translation_key=CONF_METER_FAILURE_STRATEGY,
            )
        ),
        vol.Optional(CONF_MAX_DOSE_AMOUNT): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=1_000_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
        ),
        vol.Optional(CONF_MAX_DOSE_DURATION): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=14_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_SOAK_DURATION, default=0): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=86_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_AUTOMATION_ENABLED, default=False): BooleanSelector(),
        vol.Optional(CONF_WATERING_MODE, default=WATERING_MODE_DEMAND): SelectSelector(
            SelectSelectorConfig(
                options=[WATERING_MODE_DEMAND, WATERING_MODE_MINIMUM],
                translation_key=CONF_WATERING_MODE,
            )
        ),
        vol.Optional(CONF_AREA_M2, default=1): NumberSelector(
            NumberSelectorConfig(min=0.1, max=100_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_APPLICATION_EFFICIENCY, default=0.8): NumberSelector(
            NumberSelectorConfig(min=0.01, max=1, step=0.01, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_CROP_FACTOR, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=5, step=0.05, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_RAIN_FACTOR, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=1, step=0.05, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAXIMUM_DEFICIT_MM, default=50): NumberSelector(
            NumberSelectorConfig(min=0.1, max=1_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MINIMUM_INTERVAL_DAYS, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=365, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAXIMUM_INTERVAL_DAYS, default=7): NumberSelector(
            NumberSelectorConfig(min=0.1, max=365, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MINIMUM_TRIGGER_LITERS, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MANDATORY_AMOUNT_LITERS, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MINIMUM_EFFECTIVE_LITERS, default=0.1): NumberSelector(
            NumberSelectorConfig(min=0.001, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAXIMUM_TARGET_LITERS, default=1_000): NumberSelector(
            NumberSelectorConfig(min=0.001, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_AUTOMATIC_MAX_DURATION, default=3600): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=14_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_ZONE_PRIORITY, default=0): NumberSelector(
            NumberSelectorConfig(min=-100, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WATERING_WINDOWS, default=["04:00-06:00"]): TextSelector(
            {"multiple": True}
        ),
    }
)


def _validate_zone_input(user_input: dict[str, Any]) -> str | None:
    """Return a form error for invalid interval/window automation settings."""
    try:
        windows = user_input.get(CONF_WATERING_WINDOWS, [])
        if not isinstance(windows, list) or not windows:
            raise ValueError
        for value in windows:
            parse_daily_window(value)
        if float(user_input[CONF_MAXIMUM_INTERVAL_DAYS]) < float(
            user_input[CONF_MINIMUM_INTERVAL_DAYS]
        ):
            return "invalid_intervals"
        if user_input.get(CONF_AUTOMATION_ENABLED) and not all(
            isinstance(user_input.get(key), int | float) and float(user_input[key]) > 0
            for key in (CONF_MIN_FLOW, CONF_MAX_FLOW)
        ):
            return "automation_requires_flow_profile"
    except KeyError, TypeError, ValueError:
        return "invalid_watering_windows"
    return None


class IrrigationManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create and reconfigure irrigation installations."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the installation and zone expert settings flow."""
        return IrrigationManagerOptionsFlow()

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
            if error := _validate_zone_input(user_input):
                return self.async_show_form(
                    step_id="user", data_schema=ZONE_SCHEMA, errors={"base": error}
                )
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
            if error := _validate_zone_input(user_input):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self.add_suggested_values_to_schema(ZONE_SCHEMA, user_input),
                    errors={"base": error},
                )
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


class IrrigationManagerOptionsFlow(OptionsFlow):
    """Edit installation and zone expert settings after setup."""

    def __init__(self) -> None:
        """Initialize transient zone selection."""
        self._zone_subentry_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer installation and zone settings."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["installation", "zone"],
        )

    async def async_step_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update installation sources, safety thresholds, and notifications."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=str(user_input[CONF_NAME]),
                data=user_input,
            )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="installation",
            data_schema=self.add_suggested_values_to_schema(
                INSTALLATION_SCHEMA,
                self.config_entry.data,
            ),
        )

    async def async_step_zone(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Select a zone whose expert settings should be edited."""
        zones = self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        if not zones:
            return self.async_abort(reason="no_zones")
        if user_input is not None:
            self._zone_subentry_id = str(user_input[ATTR_ZONE_SUBENTRY_ID])
            return await self.async_step_zone_settings()
        return self.async_show_form(
            step_id="zone",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_ZONE_SUBENTRY_ID): SelectSelector(
                        SelectSelectorConfig(options=[subentry.subentry_id for subentry in zones])
                    )
                }
            ),
        )

    async def async_step_zone_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and update all expert settings for the selected zone."""
        subentry = self.config_entry.subentries.get(self._zone_subentry_id or "")
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            return self.async_abort(reason="zone_not_found")
        if user_input is not None:
            if error := _validate_zone_input(user_input):
                return self.async_show_form(
                    step_id="zone_settings",
                    data_schema=self.add_suggested_values_to_schema(ZONE_SCHEMA, user_input),
                    errors={"base": error},
                )
            if any(
                other.subentry_id != subentry.subentry_id
                and other.data.get(CONF_ZONE_VALVE) == user_input[CONF_ZONE_VALVE]
                for other in self.config_entry.subentries.values()
            ):
                return self.async_abort(reason="already_configured")
            self.hass.config_entries.async_update_subentry(
                self.config_entry,
                subentry,
                title=str(user_input[CONF_NAME]),
                data=user_input,
            )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="zone_settings",
            data_schema=self.add_suggested_values_to_schema(ZONE_SCHEMA, subentry.data),
        )
