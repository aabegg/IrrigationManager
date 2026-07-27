import type {
  HassEntity,
  HomeAssistant,
  OverviewCardConfig,
  ResolvedOverviewCardConfig,
  ResolvedZoneCardConfig,
  ZoneCardConfig,
} from "./types";

export const DOMAIN = "irrigation_manager";
export const INVALID_STATES = new Set(["unknown", "unavailable"]);

export interface DurationValue {
  hours: number;
  minutes: number;
  seconds: number;
}

export function parseDuration(value: DurationValue): number | undefined {
  const { hours, minutes, seconds: remainingSeconds } = value;
  if (
    ![hours, minutes, remainingSeconds].every(Number.isFinite)
    || hours < 0
    || minutes < 0
    || minutes >= 60
    || remainingSeconds < 0
    || remainingSeconds >= 60
  ) return undefined;
  const seconds = hours * 3600 + minutes * 60 + remainingSeconds;
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined;
}

export function durationValue(seconds: number): DurationValue {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return { hours, minutes, seconds: seconds - hours * 3600 - minutes * 60 };
}

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remaining = seconds - hours * 3600 - minutes * 60;
  const fractionalSeconds = remaining.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  const secondText = Number.isInteger(remaining)
    ? String(remaining).padStart(2, "0")
    : `${remaining < 10 ? "0" : ""}${fractionalSeconds}`;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${secondText}`;
}

export function responseData<T>(value: unknown): T {
  if (!value || typeof value !== "object" || !("response" in value)) return {} as T;
  return (value as { response: T }).response;
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return String(error);
}

type EntityMap = Record<string, string>;

const overviewRoles: Record<string, keyof ResolvedOverviewCardConfig> = {
  status: "status_entity",
  pending: "pending_entity",
  next: "next_entity",
  next_start: "next_start_entity",
  today_consumption: "today_consumption_entity",
  month_consumption: "month_consumption_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  physical_meter: "physical_meter_entity",
};

const zoneRoles: Record<string, keyof ResolvedZoneCardConfig> = {
  anchor: "zone_entity",
  zone: "zone_entity",
  status: "status_entity",
  water_today: "water_today_entity",
  water_month: "water_month_entity",
  runtime_today: "runtime_today_entity",
  runtime_month: "runtime_month_entity",
  next_irrigation: "next_irrigation_entity",
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

function applyRoles<T extends ResolvedOverviewCardConfig | ResolvedZoneCardConfig>(
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
): ResolvedOverviewCardConfig {
  const anchor = config.entity ? hass.states[config.entity] : undefined;
  const resolved: ResolvedOverviewCardConfig = { ...config };
  return applyRoles(resolved, entityMapAttribute(anchor, "card_entities"), overviewRoles);
}

export function resolveZoneConfig(
  hass: HomeAssistant,
  config: ZoneCardConfig,
): ResolvedZoneCardConfig {
  const anchor = config.entity ? hass.states[config.entity] : undefined;
  const base: ResolvedZoneCardConfig = { ...config };
  const resolved = applyRoles(base, entityMapAttribute(anchor, "card_entities"), zoneRoles);
  if (!resolved.zone_entity && anchor) resolved.zone_entity = anchor.entity_id;
  if (!resolved.status_entity && anchor) resolved.status_entity = anchor.entity_id;
  return resolved;
}

export function isAnchor(
  state: HassEntity | undefined,
  kind: "installation" | "zone",
): state is HassEntity {
  if (!state || !state.entity_id.startsWith("sensor.")) return false;
  const configEntryId = state.attributes.config_entry_id;
  if (typeof configEntryId !== "string" || !configEntryId) return false;
  if (kind === "installation") {
    if (typeof state.attributes.zone_subentry_id === "string") return false;
    return entityMapAttribute(state, "card_entities").status === state.entity_id
      ? true
      : false;
  }
  const zoneSubentryId = state.attributes.zone_subentry_id;
  if (typeof zoneSubentryId !== "string" || !zoneSubentryId) return false;
  const roles = entityMapAttribute(state, "card_entities");
  return roles.anchor
    ? roles.anchor === state.entity_id
    : roles.zone === state.entity_id;
}

export function anchorEntityIds(
  hass: HomeAssistant,
  kind: "installation" | "zone",
): string[] {
  return Object.values(hass.states)
    .filter((state) => isAnchor(state, kind))
    .map((state) => state.entity_id);
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

export function statusIcon(value: string): string {
  const icons: Record<string, string> = {
    idle: "mdi:water-check-outline",
    watering: "mdi:sprinkler-variant",
    error: "mdi:alert-circle-outline",
    safety_lock: "mdi:lock-alert-outline",
    emergency_stop: "mdi:alert-octagon",
    disabled: "mdi:water-off-outline",
    automatic_disabled: "mdi:calendar-remove-outline",
    installation_disabled: "mdi:power-plug-off-outline",
    needs_reconfiguration: "mdi:cog-alert-outline",
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
