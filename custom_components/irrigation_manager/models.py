"""Runtime models shared by the Home Assistant platforms."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import cast


@dataclass(frozen=True, slots=True)
class ManualIrrigationRequest:
    """Durable manual irrigation order with an immutable zone snapshot."""

    request_id: str
    sequence: int
    zone_id: str
    zone_subentry_id: str
    zone_name: str
    zone_valve: str
    main_valve: str | None
    target_type: str
    target_value: float
    remaining_value: float
    created_at: str
    expires_at: str
    requested_start_at: str | None = None
    pause_until: str | None = None
    plan_id: str | None = None
    status: str = "pending"
    source: str = "manual"
    automatic_window_end: str | None = None
    automatic_relative_need: float | None = None
    automatic_priority: int | None = None
    execution_id: str | None = None
    hard_time_limit_seconds: float | None = None
    delivery_runtime_limit_seconds: float | None = None
    operation_deadline_at: str | None = None
    runtime_limits_need_config_derivation: bool = False
    max_dose_value: float | None = None
    soak_duration_seconds: float = 0.0
    soak_until: str | None = None
    meter_failure_strategy: str = "abort"
    estimated_flow_l_min: float | None = None
    minimum_flow_l_min: float | None = None
    maximum_flow_l_min: float | None = None
    flow_grace_seconds: float = 5.0
    balance_area_m2: float | None = None
    balance_application_efficiency: float | None = None
    balance_maximum_deficit_mm: float | None = None
    balance_total_available_water_mm: float | None = None
    balance_readily_available_water_mm: float | None = None
    balance_minimum_effective_liters: float | None = None
    resolved_inputs: dict[str, object] = field(default_factory=dict)
    revision: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ManualIrrigationRequest:
        """Deserialize one persisted manual order."""
        required_strings = (
            "request_id",
            "zone_id",
            "zone_subentry_id",
            "zone_name",
            "zone_valve",
            "target_type",
            "created_at",
            "expires_at",
        )
        if not all(isinstance(data.get(key), str) for key in required_strings):
            raise ValueError("Stored manual irrigation request is malformed")
        main_valve = data.get("main_valve")
        execution_id = data.get("execution_id")
        soak_until = data.get("soak_until")
        requested_start_at = data.get("requested_start_at")
        pause_until = data.get("pause_until")
        plan_id = data.get("plan_id")
        automatic_window_end = data.get("automatic_window_end")
        operation_deadline_at = data.get("operation_deadline_at")
        status = data.get("status", "pending")
        source = data.get("source", "manual")
        runtime_limits_need_config_derivation = data.get(
            "runtime_limits_need_config_derivation", False
        )
        if (
            not all(
                value is None or isinstance(value, str)
                for value in (
                    main_valve,
                    execution_id,
                    soak_until,
                    automatic_window_end,
                    operation_deadline_at,
                    requested_start_at,
                    pause_until,
                    plan_id,
                )
            )
            or not isinstance(status, str)
            or not isinstance(source, str)
            or not isinstance(runtime_limits_need_config_derivation, bool)
        ):
            raise ValueError("Stored manual irrigation request metadata is malformed")
        main_valve = cast(str | None, main_valve)
        execution_id = cast(str | None, execution_id)
        soak_until = cast(str | None, soak_until)
        automatic_window_end = cast(str | None, automatic_window_end)
        operation_deadline_at = cast(str | None, operation_deadline_at)
        return cls(
            request_id=str(data["request_id"]),
            sequence=int(StoredInstallationState._float(data.get("sequence"))),
            zone_id=str(data["zone_id"]),
            zone_subentry_id=str(data["zone_subentry_id"]),
            zone_name=str(data["zone_name"]),
            zone_valve=str(data["zone_valve"]),
            main_valve=main_valve,
            target_type=str(data["target_type"]),
            target_value=StoredInstallationState._float(data.get("target_value")),
            remaining_value=StoredInstallationState._float(data.get("remaining_value")),
            created_at=str(data["created_at"]),
            expires_at=str(data["expires_at"]),
            requested_start_at=cast(str | None, requested_start_at),
            pause_until=cast(str | None, pause_until),
            plan_id=cast(str | None, plan_id),
            status=status,
            source=source,
            automatic_window_end=automatic_window_end,
            automatic_relative_need=_optional_stored_float(data, "automatic_relative_need"),
            automatic_priority=(
                int(StoredInstallationState._float(data["automatic_priority"]))
                if data.get("automatic_priority") is not None
                else None
            ),
            execution_id=execution_id,
            hard_time_limit_seconds=_optional_stored_float(data, "hard_time_limit_seconds"),
            delivery_runtime_limit_seconds=_optional_stored_float(
                data, "delivery_runtime_limit_seconds"
            ),
            operation_deadline_at=operation_deadline_at,
            runtime_limits_need_config_derivation=runtime_limits_need_config_derivation,
            max_dose_value=_optional_stored_float(data, "max_dose_value"),
            soak_duration_seconds=StoredInstallationState._float(
                data.get("soak_duration_seconds", 0.0)
            ),
            soak_until=soak_until,
            meter_failure_strategy=(
                str(data["meter_failure_strategy"])
                if isinstance(data.get("meter_failure_strategy"), str)
                else "abort"
            ),
            estimated_flow_l_min=_optional_stored_float(data, "estimated_flow_l_min"),
            minimum_flow_l_min=_optional_stored_float(data, "minimum_flow_l_min"),
            maximum_flow_l_min=_optional_stored_float(data, "maximum_flow_l_min"),
            flow_grace_seconds=StoredInstallationState._float(data.get("flow_grace_seconds", 5.0)),
            balance_area_m2=_optional_stored_float(data, "balance_area_m2"),
            balance_application_efficiency=_optional_stored_float(
                data, "balance_application_efficiency"
            ),
            balance_maximum_deficit_mm=_optional_stored_float(data, "balance_maximum_deficit_mm"),
            balance_total_available_water_mm=_optional_stored_float(
                data, "balance_total_available_water_mm"
            ),
            balance_readily_available_water_mm=_optional_stored_float(
                data, "balance_readily_available_water_mm"
            ),
            balance_minimum_effective_liters=_optional_stored_float(
                data, "balance_minimum_effective_liters"
            ),
            resolved_inputs=_stored_object_dict(data, "resolved_inputs"),
            revision=int(StoredInstallationState._float(data.get("revision", 1))),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one manual order."""
        result = {field: getattr(self, field) for field in self.__dataclass_fields__}
        result["resolved_inputs"] = deepcopy(self.resolved_inputs)
        return result


@dataclass(frozen=True, slots=True)
class IrrigationExecutionState:
    """Durable lifecycle of one accepted irrigation order."""

    execution_id: str
    request_id: str
    zone_id: str
    target_type: str
    target_value: float
    remaining_value: float
    status: str
    created_at: str
    operation_deadline_at: str | None = None
    delivery_runtime_limit_seconds: float | None = None
    runtime_limits_need_config_derivation: bool = False
    dose_number: int = 0
    delivered_liters: float = 0.0
    delivered_duration_seconds: float = 0.0
    ended_at: str | None = None
    result: str | None = None
    balance_area_m2: float | None = None
    balance_application_efficiency: float | None = None
    balance_maximum_deficit_mm: float | None = None
    balance_total_available_water_mm: float | None = None
    balance_readily_available_water_mm: float | None = None
    balance_minimum_effective_liters: float | None = None
    resolved_inputs: dict[str, object] = field(default_factory=dict)
    measurement_quality: str = "unknown"
    measurement_origin: str = "unknown"
    warnings: tuple[str, ...] = ()
    doses: tuple[dict[str, object], ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> IrrigationExecutionState:
        """Deserialize one persisted execution."""
        strings = ("execution_id", "request_id", "zone_id", "target_type", "status", "created_at")
        if not all(isinstance(data.get(key), str) for key in strings):
            raise ValueError("Stored irrigation execution is malformed")
        ended_at = data.get("ended_at")
        result = data.get("result")
        operation_deadline_at = data.get("operation_deadline_at")
        runtime_limits_need_config_derivation = data.get(
            "runtime_limits_need_config_derivation", False
        )
        if not all(
            value is None or isinstance(value, str)
            for value in (ended_at, result, operation_deadline_at)
        ):
            raise ValueError("Stored irrigation execution result is malformed")
        if not isinstance(runtime_limits_need_config_derivation, bool):
            raise ValueError("Stored irrigation execution runtime migration is malformed")
        ended_at = cast(str | None, ended_at)
        result = cast(str | None, result)
        return cls(
            execution_id=str(data["execution_id"]),
            request_id=str(data["request_id"]),
            zone_id=str(data["zone_id"]),
            target_type=str(data["target_type"]),
            target_value=StoredInstallationState._float(data.get("target_value")),
            remaining_value=StoredInstallationState._float(data.get("remaining_value")),
            status=str(data["status"]),
            created_at=str(data["created_at"]),
            operation_deadline_at=cast(str | None, operation_deadline_at),
            delivery_runtime_limit_seconds=_optional_stored_float(
                data, "delivery_runtime_limit_seconds"
            ),
            runtime_limits_need_config_derivation=runtime_limits_need_config_derivation,
            dose_number=int(StoredInstallationState._float(data.get("dose_number", 0))),
            delivered_liters=StoredInstallationState._float(data.get("delivered_liters", 0.0)),
            delivered_duration_seconds=StoredInstallationState._float(
                data.get("delivered_duration_seconds", 0.0)
            ),
            ended_at=ended_at,
            result=result,
            balance_area_m2=_optional_stored_float(data, "balance_area_m2"),
            balance_application_efficiency=_optional_stored_float(
                data, "balance_application_efficiency"
            ),
            balance_maximum_deficit_mm=_optional_stored_float(data, "balance_maximum_deficit_mm"),
            balance_total_available_water_mm=_optional_stored_float(
                data, "balance_total_available_water_mm"
            ),
            balance_readily_available_water_mm=_optional_stored_float(
                data, "balance_readily_available_water_mm"
            ),
            balance_minimum_effective_liters=_optional_stored_float(
                data, "balance_minimum_effective_liters"
            ),
            resolved_inputs=_stored_object_dict(data, "resolved_inputs"),
            measurement_quality=str(data.get("measurement_quality", "unknown")),
            measurement_origin=str(data.get("measurement_origin", "unknown")),
            warnings=_stored_string_tuple(data, "warnings"),
            doses=_stored_object_tuple(data, "doses"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one irrigation execution."""
        result = {field: getattr(self, field) for field in self.__dataclass_fields__}
        result["resolved_inputs"] = deepcopy(self.resolved_inputs)
        result["warnings"] = list(self.warnings)
        result["doses"] = [deepcopy(dose) for dose in self.doses]
        return result


def _optional_stored_float(data: dict[str, object], key: str) -> float | None:
    """Read one optional persisted number."""
    value = data.get(key)
    return None if value is None else StoredInstallationState._float(value)


def _stored_object_dict(data: dict[str, object], key: str) -> dict[str, object]:
    """Read one JSON object without accepting malformed historical snapshots."""
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Stored {key} snapshot is malformed")
    return deepcopy(value)


def _stored_string_tuple(data: dict[str, object], key: str) -> tuple[str, ...]:
    """Read one persisted string list."""
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Stored {key} is malformed")
    return tuple(value)


def _stored_object_tuple(data: dict[str, object], key: str) -> tuple[dict[str, object], ...]:
    """Read one persisted list of JSON objects."""
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Stored {key} is malformed")
    return tuple(deepcopy(item) for item in value)


@dataclass(frozen=True, slots=True)
class WaterConsumptionRecord:
    """One immutable contribution used to derive period consumption safely."""

    recorded_at: str
    amount_liters: float
    zone_id: str | None
    source: str
    quality: str
    request_id: str | None = None
    execution_id: str | None = None
    dose_number: int | None = None
    warnings: tuple[str, ...] = ()
    cost: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> WaterConsumptionRecord:
        """Deserialize one bounded accounting-history record."""
        recorded_at = data.get("recorded_at")
        source = data.get("source")
        quality = data.get("quality")
        if not all(isinstance(value, str) for value in (recorded_at, source, quality)):
            raise ValueError("Stored water consumption history is malformed")
        optional_strings = (data.get("zone_id"), data.get("request_id"), data.get("execution_id"))
        if not all(value is None or isinstance(value, str) for value in optional_strings):
            raise ValueError("Stored water consumption links are malformed")
        dose_number = data.get("dose_number")
        if dose_number is not None and (
            isinstance(dose_number, bool) or not isinstance(dose_number, int)
        ):
            raise ValueError("Stored dose number is malformed")
        return cls(
            recorded_at=cast(str, recorded_at),
            amount_liters=StoredInstallationState._float(data.get("amount_liters")),
            zone_id=cast(str | None, optional_strings[0]),
            source=cast(str, source),
            quality=cast(str, quality),
            request_id=cast(str | None, optional_strings[1]),
            execution_id=cast(str | None, optional_strings[2]),
            dose_number=dose_number,
            warnings=_stored_string_tuple(data, "warnings"),
            cost=_optional_stored_float(data, "cost"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize the accounting contribution."""
        return {
            "recorded_at": self.recorded_at,
            "amount_liters": self.amount_liters,
            "zone_id": self.zone_id,
            "source": self.source,
            "quality": self.quality,
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "dose_number": self.dose_number,
            "warnings": list(self.warnings),
            "cost": self.cost,
        }


@dataclass(frozen=True, slots=True)
class UncreditedBalanceDelivery:
    """Delivered water awaiting reconciliation because its snapshot was unavailable."""

    reconciliation_id: str
    zone_id: str
    delivered_liters: float
    delivered_at: str
    reason: str
    request_id: str | None = None
    execution_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> UncreditedBalanceDelivery:
        """Deserialize one explicit uncredited delivery record."""
        required = ("reconciliation_id", "zone_id", "delivered_at", "reason")
        if not all(isinstance(data.get(key), str) for key in required):
            raise ValueError("Stored uncredited balance delivery is malformed")
        request_id = data.get("request_id")
        execution_id = data.get("execution_id")
        if not all(value is None or isinstance(value, str) for value in (request_id, execution_id)):
            raise ValueError("Stored uncredited balance delivery links are malformed")
        return cls(
            reconciliation_id=str(data["reconciliation_id"]),
            zone_id=str(data["zone_id"]),
            delivered_liters=StoredInstallationState._float(data.get("delivered_liters")),
            delivered_at=str(data["delivered_at"]),
            reason=str(data["reason"]),
            request_id=cast(str | None, request_id),
            execution_id=cast(str | None, execution_id),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one reconciliation record."""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class InstallationSnapshot:
    """Current published state of one irrigation installation."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    zone_last_delivered_liters: dict[str, float] = field(default_factory=dict)
    zone_last_duration_seconds: dict[str, float] = field(default_factory=dict)
    zone_safety_locks: dict[str, str] = field(default_factory=dict)
    zone_safety_lock_at: dict[str, str] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    unassigned_available_liters: float = 0.0
    unassigned_measurement_quality: str = "unknown"
    unassigned_measurement_origin: str = "unknown"
    water_period_liters: dict[str, float] = field(default_factory=dict)
    zone_water_period_liters: dict[str, dict[str, float]] = field(default_factory=dict)
    water_period_quality: str = "complete"
    current_flow_l_min: float | None = None
    physical_meter_liters: float | None = None
    meter_measurement_quality: str = "unknown"
    meter_resolution_liters: float | None = None
    status: str = "idle"
    active_zone_id: str | None = None
    emergency_stop: bool = False
    installation_safety_lock: str | None = None
    installation_safety_lock_at: str | None = None
    winter_lock: bool = False
    maintenance_active: bool = False
    maintenance_test_id: str | None = None
    maintenance_kind: str | None = None
    maintenance_expires_at: str | None = None
    maintenance_confirmation_deadline: str | None = None
    active_target_type: str | None = None
    active_target_value: float | None = None
    active_remaining_value: float | None = None
    active_measurement_quality: str | None = None
    pending_request_count: int = 0
    current_dose_number: int | None = None
    active_request_id: str | None = None
    active_execution_id: str | None = None
    active_zone_subentry_id: str | None = None
    zone_deficit_mm: dict[str, float] = field(default_factory=dict)
    zone_target_liters: dict[str, float] = field(default_factory=dict)
    zone_automation_needed: dict[str, bool] = field(default_factory=dict)
    zone_next_window: dict[str, str] = field(default_factory=dict)
    zone_next_irrigation: dict[str, str] = field(default_factory=dict)
    zone_planning_reason: dict[str, str] = field(default_factory=dict)
    frost_blocked: bool = False
    rain_stop_active: bool = False
    external_safety_blocked: bool = False
    zone_external_safety_blocked: dict[str, bool] = field(default_factory=dict)
    zone_wind_blocked: dict[str, bool] = field(default_factory=dict)
    weather_safety_status: str = "not_configured"
    weather_model_quality: str = "unavailable"
    weather_model_method: str = "unavailable"
    reference_evapotranspiration_mm: float | None = None
    measured_rain_mm: float | None = None
    weather_period_id: str | None = None
    weather_last_finalized_at: str | None = None
    weather_automation_available: bool = False
    rain_forecast: dict[str, object] | None = None
    zone_provisional_deficit_mm: dict[str, float] = field(default_factory=dict)
    zone_crop_evapotranspiration_mm: dict[str, float] = field(default_factory=dict)
    zone_effective_rain_mm: dict[str, float] = field(default_factory=dict)
    zone_calculation_explanations: dict[str, dict[str, object]] = field(default_factory=dict)
    zone_effective_profiles: dict[str, dict[str, object]] = field(default_factory=dict)
    zone_soil_moisture: dict[str, dict[str, object]] = field(default_factory=dict)
    zone_hardware_health: dict[str, dict[str, object]] = field(default_factory=dict)
    installation_cost: float | None = None
    zone_costs: dict[str, float] = field(default_factory=dict)
    unassigned_cost: float | None = None
    water_tariff_per_m3: float | None = None
    automation_enabled: bool = True
    operation_enabled: bool = True
    zone_operation_enabled: dict[str, bool] = field(default_factory=dict)
    automatic_suspended_until: str | None = None
    zone_automatic_suspended_until: dict[str, str] = field(default_factory=dict)
    zone_automation_enabled: dict[str, bool] = field(default_factory=dict)
    archived_zones: dict[str, str] = field(default_factory=dict)
    next_zone_id: str | None = None
    next_start_at: str | None = None
    zone_status: dict[str, str] = field(default_factory=dict)
    zone_priority: dict[str, int] = field(default_factory=dict)
    zone_last_effective_irrigation: dict[str, str] = field(default_factory=dict)
    zone_coverage_percent: dict[str, float] = field(default_factory=dict)
    zone_expected_flow_l_min: dict[str, float] = field(default_factory=dict)
    zone_actual_flow_l_min: dict[str, float] = field(default_factory=dict)
    zone_flow_deviation_percent: dict[str, float] = field(default_factory=dict)
    maintenance_due_count: int = 0
    maintenance_next_due: str | None = None
    spring_checklist_status: str = "not_configured"
    spring_test_status: str = "not_started"
    recent_history: tuple[dict[str, object], ...] = ()
    runtime_today_seconds: float = 0.0
    runtime_month_seconds: float = 0.0
    zone_runtime_today_seconds: dict[str, float] = field(default_factory=dict)
    zone_runtime_month_seconds: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActiveExecutionState:
    """Minimum durable state needed to recover an interrupted dose."""

    zone_id: str
    zone_valve: str
    main_valve: str | None
    meter_raw_baseline_liters: float | None
    prepared_at: str
    watering_started_at: str | None
    requested_duration_seconds: float
    estimated_flow_l_min: float | None
    requested_amount_liters: float | None = None
    hard_time_limit_seconds: float | None = None
    delivery_deadline_at: str | None = None
    operation_deadline_at: str | None = None
    meter_failure_strategy: str = "abort"
    zone_opening_at: str | None = None
    fallback_started_at: str | None = None
    fallback_checkpoint_at: str | None = None
    delivered_liters_at_fallback: float = 0.0
    fallback_quality: str = "estimated"
    request_id: str | None = None
    execution_id: str | None = None
    dose_number: int = 1
    dose_target_value: float | None = None
    balance_area_m2: float | None = None
    balance_application_efficiency: float | None = None
    balance_maximum_deficit_mm: float | None = None
    balance_total_available_water_mm: float | None = None
    balance_readily_available_water_mm: float | None = None
    balance_minimum_effective_liters: float | None = None
    resolved_inputs: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ActiveExecutionState:
        """Deserialize and validate an active execution record."""

        def required_string(key: str) -> str:
            value = data.get(key)
            if not isinstance(value, str):
                raise ValueError(f"Stored active execution {key} is malformed")
            return value

        def optional_string(key: str) -> str | None:
            value = data.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Stored active execution {key} is malformed")
            return value

        def optional_float(key: str) -> float | None:
            value = data.get(key)
            if value is None:
                return None
            return StoredInstallationState._float(value)

        return cls(
            zone_id=required_string("zone_id"),
            zone_valve=required_string("zone_valve"),
            main_valve=optional_string("main_valve"),
            meter_raw_baseline_liters=optional_float("meter_raw_baseline_liters"),
            prepared_at=required_string("prepared_at"),
            watering_started_at=optional_string("watering_started_at"),
            requested_duration_seconds=StoredInstallationState._float(
                data.get("requested_duration_seconds")
            ),
            estimated_flow_l_min=optional_float("estimated_flow_l_min"),
            requested_amount_liters=optional_float("requested_amount_liters"),
            hard_time_limit_seconds=optional_float("hard_time_limit_seconds"),
            delivery_deadline_at=optional_string("delivery_deadline_at"),
            operation_deadline_at=optional_string("operation_deadline_at"),
            meter_failure_strategy=(
                required_string("meter_failure_strategy")
                if "meter_failure_strategy" in data
                else "abort"
            ),
            zone_opening_at=optional_string("zone_opening_at"),
            fallback_started_at=optional_string("fallback_started_at"),
            fallback_checkpoint_at=optional_string("fallback_checkpoint_at"),
            delivered_liters_at_fallback=StoredInstallationState._float(
                data.get("delivered_liters_at_fallback", 0.0)
            ),
            fallback_quality=str(data.get("fallback_quality", "estimated")),
            request_id=optional_string("request_id"),
            execution_id=optional_string("execution_id"),
            dose_number=int(StoredInstallationState._float(data.get("dose_number", 1))),
            dose_target_value=optional_float("dose_target_value"),
            balance_area_m2=optional_float("balance_area_m2"),
            balance_application_efficiency=optional_float("balance_application_efficiency"),
            balance_maximum_deficit_mm=optional_float("balance_maximum_deficit_mm"),
            balance_total_available_water_mm=optional_float("balance_total_available_water_mm"),
            balance_readily_available_water_mm=optional_float("balance_readily_available_water_mm"),
            balance_minimum_effective_liters=optional_float("balance_minimum_effective_liters"),
            resolved_inputs=_stored_object_dict(data, "resolved_inputs"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize the active execution for Home Assistant storage."""
        return {
            "zone_id": self.zone_id,
            "zone_valve": self.zone_valve,
            "main_valve": self.main_valve,
            "meter_raw_baseline_liters": self.meter_raw_baseline_liters,
            "prepared_at": self.prepared_at,
            "watering_started_at": self.watering_started_at,
            "requested_duration_seconds": self.requested_duration_seconds,
            "estimated_flow_l_min": self.estimated_flow_l_min,
            "requested_amount_liters": self.requested_amount_liters,
            "hard_time_limit_seconds": self.hard_time_limit_seconds,
            "delivery_deadline_at": self.delivery_deadline_at,
            "operation_deadline_at": self.operation_deadline_at,
            "meter_failure_strategy": self.meter_failure_strategy,
            "zone_opening_at": self.zone_opening_at,
            "fallback_started_at": self.fallback_started_at,
            "fallback_checkpoint_at": self.fallback_checkpoint_at,
            "delivered_liters_at_fallback": self.delivered_liters_at_fallback,
            "fallback_quality": self.fallback_quality,
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "dose_number": self.dose_number,
            "dose_target_value": self.dose_target_value,
            "balance_area_m2": self.balance_area_m2,
            "balance_application_efficiency": self.balance_application_efficiency,
            "balance_maximum_deficit_mm": self.balance_maximum_deficit_mm,
            "balance_total_available_water_mm": self.balance_total_available_water_mm,
            "balance_readily_available_water_mm": self.balance_readily_available_water_mm,
            "balance_minimum_effective_liters": self.balance_minimum_effective_liters,
            "resolved_inputs": deepcopy(self.resolved_inputs),
        }


@dataclass(frozen=True, slots=True)
class MaintenanceTestState:
    """Durable supervised test state used to fail closed after restart."""

    test_id: str
    kind: str
    zone_id: str
    zone_subentry_id: str
    started_at: str
    expires_at: str
    confirmation_deadline: str
    bypass_checks: tuple[str, ...] = ()
    water_attribution: str = "zone"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MaintenanceTestState:
        """Deserialize one active supervised test."""
        required = (
            "test_id",
            "kind",
            "zone_id",
            "zone_subentry_id",
            "started_at",
            "expires_at",
            "confirmation_deadline",
        )
        if not all(isinstance(data.get(key), str) for key in required):
            raise ValueError("Stored maintenance test is malformed")
        raw_bypass = data.get("bypass_checks", [])
        if not isinstance(raw_bypass, list) or not all(
            isinstance(value, str) for value in raw_bypass
        ):
            raise ValueError("Stored maintenance bypass checks are malformed")
        return cls(
            test_id=str(data["test_id"]),
            kind=str(data["kind"]),
            zone_id=str(data["zone_id"]),
            zone_subentry_id=str(data["zone_subentry_id"]),
            started_at=str(data["started_at"]),
            expires_at=str(data["expires_at"]),
            confirmation_deadline=str(data["confirmation_deadline"]),
            bypass_checks=tuple(raw_bypass),
            water_attribution=str(data.get("water_attribution", "zone")),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one active supervised test."""
        return {
            "test_id": self.test_id,
            "kind": self.kind,
            "zone_id": self.zone_id,
            "zone_subentry_id": self.zone_subentry_id,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "confirmation_deadline": self.confirmation_deadline,
            "bypass_checks": list(self.bypass_checks),
            "water_attribution": self.water_attribution,
        }


@dataclass(frozen=True, slots=True)
class CalibrationProposal:
    """Measured calibration values awaiting an explicit user decision."""

    proposal_id: str
    zone_id: str
    zone_subentry_id: str
    zone_valve: str
    zone_config_hash: str
    created_at: str
    delivered_liters: float
    duration_seconds: float
    average_flow_l_min: float
    opening_latency_seconds: float
    post_run_liters: float
    proposed_min_flow_l_min: float
    proposed_max_flow_l_min: float
    status: str = "pending"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CalibrationProposal:
        """Deserialize one calibration proposal."""
        required = (
            "proposal_id",
            "zone_id",
            "zone_subentry_id",
            "zone_valve",
            "zone_config_hash",
            "created_at",
            "status",
        )
        if not all(isinstance(data.get(key), str) for key in required):
            raise ValueError("Stored calibration proposal is malformed")
        return cls(
            proposal_id=str(data["proposal_id"]),
            zone_id=str(data["zone_id"]),
            zone_subentry_id=str(data["zone_subentry_id"]),
            zone_valve=str(data["zone_valve"]),
            zone_config_hash=str(data["zone_config_hash"]),
            created_at=str(data["created_at"]),
            delivered_liters=StoredInstallationState._float(data.get("delivered_liters")),
            duration_seconds=StoredInstallationState._float(data.get("duration_seconds")),
            average_flow_l_min=StoredInstallationState._float(data.get("average_flow_l_min")),
            opening_latency_seconds=StoredInstallationState._float(
                data.get("opening_latency_seconds")
            ),
            post_run_liters=StoredInstallationState._float(data.get("post_run_liters")),
            proposed_min_flow_l_min=StoredInstallationState._float(
                data.get("proposed_min_flow_l_min")
            ),
            proposed_max_flow_l_min=StoredInstallationState._float(
                data.get("proposed_max_flow_l_min")
            ),
            status=str(data["status"]),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one calibration proposal."""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class StoredInstallationState:
    """Versioned critical state persisted independently of entities."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    zone_last_delivered_liters: dict[str, float] = field(default_factory=dict)
    zone_last_duration_seconds: dict[str, float] = field(default_factory=dict)
    zone_safety_locks: dict[str, str] = field(default_factory=dict)
    zone_safety_lock_at: dict[str, str] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    unassigned_available_liters: float = 0.0
    unassigned_measurement_quality: str = "unknown"
    unassigned_measurement_origin: str = "unknown"
    idle_meter_raw_baseline_liters: float | None = None
    emergency_stop: bool = False
    installation_safety_lock: str | None = None
    installation_safety_lock_at: str | None = None
    winter_lock: bool = False
    maintenance_test: MaintenanceTestState | None = None
    calibration_proposal: CalibrationProposal | None = None
    active_execution: ActiveExecutionState | None = None
    manual_requests: tuple[ManualIrrigationRequest, ...] = ()
    irrigation_executions: tuple[IrrigationExecutionState, ...] = ()
    next_request_sequence: int = 1
    zone_deficit_mm: dict[str, float] = field(default_factory=dict)
    zone_last_effective_irrigation: dict[str, str] = field(default_factory=dict)
    finalized_weather_periods: dict[str, str] = field(default_factory=dict)
    suppressed_automatic_opportunities: tuple[str, ...] = ()
    uncredited_balance_deliveries: tuple[UncreditedBalanceDelivery, ...] = ()
    weather_calculation_snapshots: dict[str, dict[str, object]] = field(default_factory=dict)
    weather_failure_since: str | None = None
    forecast_deferral_started: dict[str, str] = field(default_factory=dict)
    forecast_deferral_deadlines: dict[str, str] = field(default_factory=dict)
    cancelled_forecast_deferrals: tuple[str, ...] = ()
    budget_usage_liters: dict[str, float] = field(default_factory=dict)
    meter_accumulated_liters: float | None = None
    meter_last_raw_liters: float | None = None
    meter_correction_liters: float = 0.0
    meter_reset_count: int = 0
    meter_source_entity_id: str | None = None
    meter_source_liters_per_count: float | None = None
    water_consumption_history: tuple[WaterConsumptionRecord, ...] = ()
    water_history_incomplete: bool = False
    installation_cost: float = 0.0
    zone_costs: dict[str, float] = field(default_factory=dict)
    unassigned_cost: float = 0.0
    archived_zones: dict[str, str] = field(default_factory=dict)
    automatic_suspended_until: str | None = None
    zone_automatic_suspended_until: dict[str, str] = field(default_factory=dict)
    maintenance_task_state: dict[str, dict[str, object]] = field(default_factory=dict)
    maintenance_history: tuple[dict[str, object], ...] = ()
    maintenance_test_history: tuple[dict[str, object], ...] = ()
    spring_checklist_completed: tuple[str, ...] = ()
    spring_test_status: str = "not_started"
    winter_reminder_last_year: int | None = None
    operation_enabled: bool | None = None
    automation_enabled: bool | None = None
    zone_operation_enabled: dict[str, bool] = field(default_factory=dict)
    zone_automation_enabled: dict[str, bool] = field(default_factory=dict)

    @staticmethod
    def _float(value: object) -> float:
        """Return numeric JSON values without silently discarding corruption."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Stored irrigation total is not numeric")
        return float(value)

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> StoredInstallationState:
        """Deserialize storage data with safe defaults."""
        if data is None:
            return cls()
        raw_zone_totals = data.get("zone_totals_liters", {})
        if not isinstance(raw_zone_totals, dict):
            raise ValueError("Stored zone totals are malformed")
        zone_totals = {str(key): cls._float(value) for key, value in raw_zone_totals.items()}
        raw_last_delivered = data.get("zone_last_delivered_liters", {})
        if not isinstance(raw_last_delivered, dict):
            raise ValueError("Stored last delivered amounts are malformed")
        last_delivered = {str(key): cls._float(value) for key, value in raw_last_delivered.items()}
        raw_last_duration = data.get("zone_last_duration_seconds", {})
        if not isinstance(raw_last_duration, dict):
            raise ValueError("Stored last delivery durations are malformed")
        last_duration = {str(key): cls._float(value) for key, value in raw_last_duration.items()}
        raw_quality = data.get("zone_measurement_quality", {})
        if not isinstance(raw_quality, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_quality.items()
        ):
            raise ValueError("Stored measurement quality is malformed")
        raw_zone_locks = data.get("zone_safety_locks", {})
        if not isinstance(raw_zone_locks, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_zone_locks.items()
        ):
            raise ValueError("Stored zone safety locks are malformed")
        raw_zone_lock_at = data.get("zone_safety_lock_at", {})
        if not isinstance(raw_zone_lock_at, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_zone_lock_at.items()
        ):
            raise ValueError("Stored zone safety lock timestamps are malformed")
        emergency_stop = data.get("emergency_stop", False)
        if not isinstance(emergency_stop, bool):
            raise ValueError("Stored emergency stop is not boolean")
        installation_lock = data.get("installation_safety_lock")
        if installation_lock is not None and not isinstance(installation_lock, str):
            raise ValueError("Stored installation safety lock is malformed")
        installation_lock_at = data.get("installation_safety_lock_at")
        if installation_lock_at is not None and not isinstance(installation_lock_at, str):
            raise ValueError("Stored installation safety lock timestamp is malformed")
        winter_lock = data.get("winter_lock", False)
        if not isinstance(winter_lock, bool):
            raise ValueError("Stored winter lock is not boolean")
        raw_maintenance = data.get("maintenance_test")
        if raw_maintenance is not None and not isinstance(raw_maintenance, dict):
            raise ValueError("Stored maintenance test is malformed")
        raw_calibration = data.get("calibration_proposal")
        if raw_calibration is not None and not isinstance(raw_calibration, dict):
            raise ValueError("Stored calibration proposal is malformed")
        raw_active_execution = data.get("active_execution")
        if raw_active_execution is not None and not isinstance(raw_active_execution, dict):
            raise ValueError("Stored active execution is malformed")
        raw_requests = data.get("manual_requests", [])
        raw_executions = data.get("irrigation_executions", [])
        if not isinstance(raw_requests, list) or not all(
            isinstance(item, dict) for item in raw_requests
        ):
            raise ValueError("Stored manual irrigation requests are malformed")
        if not isinstance(raw_executions, list) or not all(
            isinstance(item, dict) for item in raw_executions
        ):
            raise ValueError("Stored irrigation executions are malformed")
        unassigned_quality = data.get("unassigned_measurement_quality", "unknown")
        unassigned_origin = data.get("unassigned_measurement_origin", "unknown")
        if not isinstance(unassigned_quality, str) or not isinstance(unassigned_origin, str):
            raise ValueError("Stored unassigned measurement metadata is malformed")
        raw_idle_baseline = data.get("idle_meter_raw_baseline_liters")
        idle_baseline = None if raw_idle_baseline is None else cls._float(raw_idle_baseline)
        raw_deficits = data.get("zone_deficit_mm", {})
        raw_last_effective = data.get("zone_last_effective_irrigation", {})
        raw_weather_periods = data.get("finalized_weather_periods", {})
        raw_suppressions = data.get("suppressed_automatic_opportunities", [])
        raw_uncredited_deliveries = data.get("uncredited_balance_deliveries", [])
        raw_weather_snapshots = data.get("weather_calculation_snapshots", {})
        weather_failure_since = data.get("weather_failure_since")
        raw_forecast_deferrals = data.get("forecast_deferral_started", {})
        raw_forecast_deadlines = data.get("forecast_deferral_deadlines", {})
        raw_cancelled_deferrals = data.get("cancelled_forecast_deferrals", [])
        raw_budget_usage = data.get("budget_usage_liters", {})
        raw_consumption_history = data.get("water_consumption_history", [])
        if not isinstance(raw_deficits, dict):
            raise ValueError("Stored zone water deficits are malformed")
        if not isinstance(raw_last_effective, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_last_effective.items()
        ):
            raise ValueError("Stored effective irrigation timestamps are malformed")
        if not isinstance(raw_weather_periods, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_weather_periods.items()
        ):
            raise ValueError("Stored finalized weather periods are malformed")
        if not isinstance(raw_suppressions, list) or not all(
            isinstance(value, str) for value in raw_suppressions
        ):
            raise ValueError("Stored automatic opportunity suppressions are malformed")
        if not isinstance(raw_uncredited_deliveries, list) or not all(
            isinstance(value, dict) for value in raw_uncredited_deliveries
        ):
            raise ValueError("Stored uncredited balance deliveries are malformed")
        if not isinstance(raw_weather_snapshots, dict) or not all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in raw_weather_snapshots.items()
        ):
            raise ValueError("Stored weather calculation snapshots are malformed")
        if weather_failure_since is not None and not isinstance(weather_failure_since, str):
            raise ValueError("Stored weather failure timestamp is malformed")
        if not isinstance(raw_forecast_deferrals, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_forecast_deferrals.items()
        ):
            raise ValueError("Stored forecast deferral progress is malformed")
        if not isinstance(raw_forecast_deadlines, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_forecast_deadlines.items()
        ):
            raise ValueError("Stored forecast deferral deadlines are malformed")
        if not isinstance(raw_cancelled_deferrals, list) or not all(
            isinstance(value, str) for value in raw_cancelled_deferrals
        ):
            raise ValueError("Stored cancelled forecast deferrals are malformed")
        if not isinstance(raw_budget_usage, dict):
            raise ValueError("Stored budget usage is malformed")
        if not isinstance(raw_consumption_history, list) or not all(
            isinstance(value, dict) for value in raw_consumption_history
        ):
            raise ValueError("Stored water consumption history is malformed")
        meter_accumulated = data.get("meter_accumulated_liters")
        meter_last_raw = data.get("meter_last_raw_liters")
        meter_reset_count = data.get("meter_reset_count", 0)
        if isinstance(meter_reset_count, bool) or not isinstance(meter_reset_count, int):
            raise ValueError("Stored meter reset count is malformed")
        meter_source_entity_id = data.get("meter_source_entity_id")
        if meter_source_entity_id is not None and not isinstance(meter_source_entity_id, str):
            raise ValueError("Stored meter source identity is malformed")
        water_history_incomplete = data.get("water_history_incomplete", False)
        if not isinstance(water_history_incomplete, bool):
            raise ValueError("Stored water history quality is malformed")
        raw_zone_costs = data.get("zone_costs", {})
        raw_archived_zones = data.get("archived_zones", {})
        raw_zone_suspensions = data.get("zone_automatic_suspended_until", {})
        raw_zone_operation = data.get("zone_operation_enabled", {})
        raw_zone_automation = data.get("zone_automation_enabled", {})
        raw_task_state = data.get("maintenance_task_state", {})
        automatic_suspended_until = data.get("automatic_suspended_until")
        spring_test_status = data.get("spring_test_status", "not_started")
        winter_reminder_last_year = data.get("winter_reminder_last_year")
        if not isinstance(raw_zone_costs, dict):
            raise ValueError("Stored zone costs are malformed")
        if not isinstance(raw_archived_zones, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_archived_zones.items()
        ):
            raise ValueError("Stored archived zones are malformed")
        if not isinstance(raw_zone_suspensions, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_zone_suspensions.items()
        ):
            raise ValueError("Stored zone suspensions are malformed")
        if not isinstance(raw_zone_operation, dict) or not all(
            isinstance(key, str) and isinstance(value, bool)
            for key, value in raw_zone_operation.items()
        ):
            raise ValueError("Stored zone operation releases are malformed")
        if not isinstance(raw_zone_automation, dict) or not all(
            isinstance(key, str) and isinstance(value, bool)
            for key, value in raw_zone_automation.items()
        ):
            raise ValueError("Stored zone automation releases are malformed")
        operation_enabled = data.get("operation_enabled")
        automation_enabled = data.get("automation_enabled")
        if operation_enabled is not None and not isinstance(operation_enabled, bool):
            raise ValueError("Stored installation operation release is malformed")
        if automation_enabled is not None and not isinstance(automation_enabled, bool):
            raise ValueError("Stored installation automation release is malformed")
        if not isinstance(raw_task_state, dict) or not all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in raw_task_state.items()
        ):
            raise ValueError("Stored maintenance task state is malformed")
        if automatic_suspended_until is not None and not isinstance(automatic_suspended_until, str):
            raise ValueError("Stored installation suspension is malformed")
        if not isinstance(spring_test_status, str):
            raise ValueError("Stored spring test status is malformed")
        if winter_reminder_last_year is not None and (
            isinstance(winter_reminder_last_year, bool)
            or not isinstance(winter_reminder_last_year, int)
        ):
            raise ValueError("Stored winter reminder year is malformed")
        return cls(
            installation_total_liters=cls._float(data.get("installation_total_liters", 0.0)),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=dict(raw_quality),
            zone_last_delivered_liters=last_delivered,
            zone_last_duration_seconds=last_duration,
            zone_safety_locks=dict(raw_zone_locks),
            zone_safety_lock_at=dict(raw_zone_lock_at),
            unassigned_total_liters=cls._float(data.get("unassigned_total_liters", 0.0)),
            unassigned_available_liters=cls._float(
                data.get("unassigned_available_liters", data.get("unassigned_total_liters", 0.0))
            ),
            unassigned_measurement_quality=unassigned_quality,
            unassigned_measurement_origin=unassigned_origin,
            idle_meter_raw_baseline_liters=idle_baseline,
            emergency_stop=emergency_stop,
            installation_safety_lock=installation_lock,
            installation_safety_lock_at=installation_lock_at,
            winter_lock=winter_lock,
            maintenance_test=(
                MaintenanceTestState.from_dict(raw_maintenance)
                if raw_maintenance is not None
                else None
            ),
            calibration_proposal=(
                CalibrationProposal.from_dict(raw_calibration)
                if raw_calibration is not None
                else None
            ),
            active_execution=(
                ActiveExecutionState.from_dict(raw_active_execution)
                if raw_active_execution is not None
                else None
            ),
            manual_requests=tuple(ManualIrrigationRequest.from_dict(item) for item in raw_requests),
            irrigation_executions=tuple(
                IrrigationExecutionState.from_dict(item) for item in raw_executions
            ),
            next_request_sequence=int(
                cls._float(data.get("next_request_sequence", len(raw_requests) + 1))
            ),
            zone_deficit_mm={str(key): cls._float(value) for key, value in raw_deficits.items()},
            zone_last_effective_irrigation=dict(raw_last_effective),
            finalized_weather_periods=dict(raw_weather_periods),
            suppressed_automatic_opportunities=tuple(raw_suppressions),
            uncredited_balance_deliveries=tuple(
                UncreditedBalanceDelivery.from_dict(value) for value in raw_uncredited_deliveries
            ),
            weather_calculation_snapshots={
                str(key): dict(value) for key, value in raw_weather_snapshots.items()
            },
            weather_failure_since=weather_failure_since,
            forecast_deferral_started=dict(raw_forecast_deferrals),
            forecast_deferral_deadlines=dict(raw_forecast_deadlines),
            cancelled_forecast_deferrals=tuple(raw_cancelled_deferrals),
            budget_usage_liters={
                str(key): cls._float(value) for key, value in raw_budget_usage.items()
            },
            meter_accumulated_liters=(
                None if meter_accumulated is None else cls._float(meter_accumulated)
            ),
            meter_last_raw_liters=None if meter_last_raw is None else cls._float(meter_last_raw),
            meter_correction_liters=cls._float(data.get("meter_correction_liters", 0.0)),
            meter_reset_count=meter_reset_count,
            meter_source_entity_id=meter_source_entity_id,
            meter_source_liters_per_count=_optional_stored_float(
                data, "meter_source_liters_per_count"
            ),
            water_consumption_history=tuple(
                WaterConsumptionRecord.from_dict(value) for value in raw_consumption_history
            ),
            water_history_incomplete=water_history_incomplete,
            installation_cost=cls._float(data.get("installation_cost", 0.0)),
            zone_costs={str(key): cls._float(value) for key, value in raw_zone_costs.items()},
            unassigned_cost=cls._float(data.get("unassigned_cost", 0.0)),
            archived_zones=dict(raw_archived_zones),
            automatic_suspended_until=automatic_suspended_until,
            zone_automatic_suspended_until=dict(raw_zone_suspensions),
            maintenance_task_state={
                str(key): deepcopy(value) for key, value in raw_task_state.items()
            },
            maintenance_history=_stored_object_tuple(data, "maintenance_history"),
            maintenance_test_history=_stored_object_tuple(data, "maintenance_test_history"),
            spring_checklist_completed=_stored_string_tuple(data, "spring_checklist_completed"),
            spring_test_status=spring_test_status,
            winter_reminder_last_year=winter_reminder_last_year,
            operation_enabled=operation_enabled,
            automation_enabled=automation_enabled,
            zone_operation_enabled=dict(raw_zone_operation),
            zone_automation_enabled=dict(raw_zone_automation),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize state to JSON-compatible storage data."""
        return {
            "installation_total_liters": self.installation_total_liters,
            "zone_totals_liters": self.zone_totals_liters,
            "zone_measurement_quality": self.zone_measurement_quality,
            "zone_last_delivered_liters": self.zone_last_delivered_liters,
            "zone_last_duration_seconds": self.zone_last_duration_seconds,
            "zone_safety_locks": self.zone_safety_locks,
            "zone_safety_lock_at": self.zone_safety_lock_at,
            "unassigned_total_liters": self.unassigned_total_liters,
            "unassigned_available_liters": self.unassigned_available_liters,
            "unassigned_measurement_quality": self.unassigned_measurement_quality,
            "unassigned_measurement_origin": self.unassigned_measurement_origin,
            "idle_meter_raw_baseline_liters": self.idle_meter_raw_baseline_liters,
            "emergency_stop": self.emergency_stop,
            "installation_safety_lock": self.installation_safety_lock,
            "installation_safety_lock_at": self.installation_safety_lock_at,
            "winter_lock": self.winter_lock,
            "maintenance_test": (
                self.maintenance_test.as_dict() if self.maintenance_test is not None else None
            ),
            "calibration_proposal": (
                self.calibration_proposal.as_dict()
                if self.calibration_proposal is not None
                else None
            ),
            "active_execution": (
                self.active_execution.as_dict() if self.active_execution is not None else None
            ),
            "manual_requests": [request.as_dict() for request in self.manual_requests],
            "irrigation_executions": [
                execution.as_dict() for execution in self.irrigation_executions
            ],
            "next_request_sequence": self.next_request_sequence,
            "zone_deficit_mm": self.zone_deficit_mm,
            "zone_last_effective_irrigation": self.zone_last_effective_irrigation,
            "finalized_weather_periods": self.finalized_weather_periods,
            "suppressed_automatic_opportunities": list(self.suppressed_automatic_opportunities),
            "uncredited_balance_deliveries": [
                delivery.as_dict() for delivery in self.uncredited_balance_deliveries
            ],
            "weather_calculation_snapshots": self.weather_calculation_snapshots,
            "weather_failure_since": self.weather_failure_since,
            "forecast_deferral_started": self.forecast_deferral_started,
            "forecast_deferral_deadlines": self.forecast_deferral_deadlines,
            "cancelled_forecast_deferrals": list(self.cancelled_forecast_deferrals),
            "budget_usage_liters": self.budget_usage_liters,
            "meter_accumulated_liters": self.meter_accumulated_liters,
            "meter_last_raw_liters": self.meter_last_raw_liters,
            "meter_correction_liters": self.meter_correction_liters,
            "meter_reset_count": self.meter_reset_count,
            "meter_source_entity_id": self.meter_source_entity_id,
            "meter_source_liters_per_count": self.meter_source_liters_per_count,
            "water_consumption_history": [
                record.as_dict() for record in self.water_consumption_history
            ],
            "water_history_incomplete": self.water_history_incomplete,
            "installation_cost": self.installation_cost,
            "zone_costs": self.zone_costs,
            "unassigned_cost": self.unassigned_cost,
            "archived_zones": self.archived_zones,
            "automatic_suspended_until": self.automatic_suspended_until,
            "zone_automatic_suspended_until": self.zone_automatic_suspended_until,
            "maintenance_task_state": self.maintenance_task_state,
            "maintenance_history": [deepcopy(value) for value in self.maintenance_history],
            "maintenance_test_history": [
                deepcopy(value) for value in self.maintenance_test_history
            ],
            "spring_checklist_completed": list(self.spring_checklist_completed),
            "spring_test_status": self.spring_test_status,
            "winter_reminder_last_year": self.winter_reminder_last_year,
            "operation_enabled": self.operation_enabled,
            "automation_enabled": self.automation_enabled,
            "zone_operation_enabled": self.zone_operation_enabled,
            "zone_automation_enabled": self.zone_automation_enabled,
        }
