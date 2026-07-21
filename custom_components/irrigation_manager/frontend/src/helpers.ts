import type { HassEntity, HomeAssistant } from "./types";

export const DOMAIN = "irrigation_manager";
export const MANUAL_REQUEST_SERVICE = "create_manual";
export const INVALID_STATES = new Set(["unknown", "unavailable"]);

export interface ActiveRequestTarget {
  requestId?: string;
  executionId?: string;
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
