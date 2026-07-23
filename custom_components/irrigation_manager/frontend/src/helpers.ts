import type {
  ConfigurationMode,
  HassEntity,
  HomeAssistant,
  OverviewCardConfig,
  ZoneCardConfig,
} from "./types";

export const DOMAIN = "irrigation_manager";
export const MANUAL_REQUEST_SERVICE = "create_manual";
export const INVALID_STATES = new Set(["unknown", "unavailable"]);

export interface ActiveRequestTarget {
  requestId?: string;
  executionId?: string;
}

type EntityMap = Record<string, string>;

const overviewRoles: Record<string, keyof OverviewCardConfig> = {
  status: "status_entity",
  emergency: "emergency_entity",
  lock: "lock_entity",
  active_zone: "active_zone_entity",
  dose: "dose_entity",
  pending: "pending_entity",
  next: "next_entity",
  today_consumption: "today_consumption_entity",
  month_consumption: "month_consumption_entity",
  model_quality: "model_quality_entity",
  winter: "winter_entity",
  maintenance: "maintenance_entity",
  automation_release: "automation_release_entity",
  maintenance_due: "maintenance_due_entity",
};

const zoneRoles: Record<string, keyof ZoneCardConfig> = {
  zone: "zone_entity",
  automation_needed: "automation_needed_entity",
  safety_lock: "safety_lock_entity",
  deficit: "deficit_entity",
  target: "target_entity",
  planning_reason: "planning_reason_entity",
  next_window: "next_window_entity",
  last_delivered: "last_delivered_entity",
  last_duration: "last_duration_entity",
  quality: "quality_entity",
  status: "status_entity",
  automation_release: "automation_release_entity",
  archived: "archived_entity",
  coverage: "coverage_entity",
  expected_flow: "expected_flow_entity",
  actual_flow: "actual_flow_entity",
  flow_deviation: "flow_deviation_entity",
  calculation: "calculation_entity",
};

const installationZoneRoles: Record<string, keyof ZoneCardConfig> = {
  active_zone: "active_zone_entity",
  dose: "request_entity",
  lock: "installation_safety_lock_entity",
};

export function entityMapAttribute(
  state: HassEntity | undefined,
  name: string,
): EntityMap {
  const value = state?.attributes[name];
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value).filter(
      (item): item is [string, string] => typeof item[1] === "string" && item[1].includes("."),
    ),
  );
}

function applyRoles<T extends OverviewCardConfig | ZoneCardConfig>(
  config: T,
  mapping: EntityMap,
  roles: Record<string, keyof T>,
): T {
  const resolved = { ...config };
  for (const [role, field] of Object.entries(roles)) {
    const explicit = config[field];
    const value = explicit || mapping[role];
    if (value) Object.assign(resolved, { [field]: value });
  }
  return resolved;
}

export function resolveOverviewConfig(
  hass: HomeAssistant,
  config: OverviewCardConfig,
): OverviewCardConfig {
  if (!config.configuration_mode && !config.installation && config.status_entity) return config;
  const anchor = config.installation
    ? anchorState(hass, "installation", config.installation)
    : entity(hass, config.status_entity);
  return applyRoles(config, entityMapAttribute(anchor, "card_entities"), overviewRoles);
}

export function resolveZoneConfig(hass: HomeAssistant, config: ZoneCardConfig): ZoneCardConfig {
  if (!config.configuration_mode && !config.zone && config.zone_entity) return config;
  const anchor = config.zone
    ? anchorState(hass, "zone", config.zone)
    : entity(hass, config.zone_entity);
  let resolved = applyRoles(config, entityMapAttribute(anchor, "card_entities"), zoneRoles);
  resolved = applyRoles(
    resolved,
    entityMapAttribute(anchor, "installation_card_entities"),
    installationZoneRoles,
  );
  if (!resolved.zone_entity && anchor) resolved.zone_entity = anchor.entity_id;
  return resolved;
}

export function anchorState(
  hass: HomeAssistant,
  kind: "installation" | "zone",
  value: string,
): HassEntity | undefined {
  return Object.values(hass.states).find((state) => anchorValue(state, kind) === value);
}

function anchorValue(state: HassEntity, kind: "installation" | "zone"): string | undefined {
  const configEntryId = state.attributes.config_entry_id;
  if (typeof configEntryId !== "string") return undefined;
  if (kind === "installation") {
    return entityMapAttribute(state, "card_entities").status === state.entity_id
      ? configEntryId
      : undefined;
  }
  const zoneSubentryId = state.attributes.zone_subentry_id;
  return typeof zoneSubentryId === "string" &&
    Object.keys(entityMapAttribute(state, "card_entities")).length > 0
    ? `${configEntryId}:${zoneSubentryId}`
    : undefined;
}

export function inferConfigurationMode(
  config: OverviewCardConfig | ZoneCardConfig,
  entityFields: readonly string[],
): ConfigurationMode {
  if (config.configuration_mode) return config.configuration_mode;
  return entityFields.some((field) => Boolean((config as unknown as Record<string, unknown>)[field]))
    ? "expert"
    : "simple";
}

export function anchorChoices(
  hass: HomeAssistant,
  kind: "installation" | "zone",
): Array<{ value: string; label: string }> {
  return Object.values(hass.states)
    .filter((state) => {
      return anchorValue(state, kind) !== undefined;
    })
    .map((state) => ({
      value: anchorValue(state, kind)!,
      label:
        (typeof state.attributes.card_name === "string" && state.attributes.card_name) ||
        state.attributes.friendly_name ||
        state.entity_id,
    }))
    .sort((left, right) => left.label.localeCompare(right.label, hass.language));
}

export function entity(hass: HomeAssistant, entityId?: string): HassEntity | undefined {
  return entityId ? hass.states[entityId] : undefined;
}

export function usable(state?: HassEntity): state is HassEntity {
  return Boolean(state && !INVALID_STATES.has(state.state));
}

export function stringAttribute(state: HassEntity | undefined, name: string): string | undefined {
  const value = state?.attributes[name];
  return typeof value === "string" && value ? value : undefined;
}

export function numberAttribute(state: HassEntity | undefined, name: string): number | undefined {
  const value = state?.attributes[name];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function activeRequestForZone(
  request: HassEntity | undefined,
  zoneSubentryId: string | undefined,
): ActiveRequestTarget | undefined {
  if (
    !zoneSubentryId ||
    stringAttribute(request, "zone_subentry_id") !== zoneSubentryId
  ) {
    return undefined;
  }
  const requestId = stringAttribute(request, "request_id");
  const executionId = stringAttribute(request, "execution_id");
  return requestId || executionId ? { requestId, executionId } : undefined;
}

export function progress(state: HassEntity | undefined): number | undefined {
  const target = numberAttribute(state, "target_value");
  const remaining = numberAttribute(state, "remaining_value");
  if (target === undefined || remaining === undefined || target <= 0) return undefined;
  return Math.max(0, Math.min(100, ((target - remaining) / target) * 100));
}

export function statusIcon(value: string): string {
  const icons: Record<string, string> = {
    idle: "mdi:water-check-outline",
    watering: "mdi:sprinkler-variant",
    soaking: "mdi:timer-sand",
    error: "mdi:alert-circle-outline",
    safety_lock: "mdi:lock-alert-outline",
    emergency_stop: "mdi:alert-octagon",
    unavailable: "mdi:cloud-alert-outline",
    unknown: "mdi:help-circle-outline",
    on: "mdi:check-circle-outline",
    off: "mdi:minus-circle-outline",
  };
  return icons[value] ?? "mdi:information-outline";
}

export function fireConfigChanged(element: HTMLElement, config: unknown): void {
  element.dispatchEvent(
    new CustomEvent("config-changed", {
      detail: { config },
      bubbles: true,
      composed: true,
    }),
  );
}
