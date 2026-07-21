import { describe, expect, it } from "vitest";

import { displayState, localize, translatedValue } from "./localize";
import { MANUAL_REQUEST_SERVICE, activeRequestForZone, progress } from "./helpers";
import type { HassEntity, HomeAssistant } from "./types";

const state = (value: string, attributes: Record<string, unknown> = {}): HassEntity => ({
  entity_id: "sensor.test",
  state: value,
  attributes,
});

describe("frontend state presentation", () => {
  it("uses German for regional language tags", () => {
    expect(localize({ language: "de-CH" }, "watering")).toBe("Bewässerung läuft");
    expect(translatedValue({ language: "de" }, "safety_lock")).toBe("Sicherheitssperre");
  });

  it("does not present unavailable entities as normal values", () => {
    const hass = { language: "en", states: {}, callService: async () => undefined } satisfies HomeAssistant;
    expect(displayState(hass, state("unavailable"))).toBe("Unavailable");
    expect(displayState(hass)).toBe("Entity not found");
  });

  it("clamps active progress to a safe percentage", () => {
    expect(progress(state("zone", { target_value: 100, remaining_value: 25 }))).toBe(75);
    expect(progress(state("zone", { target_value: 0, remaining_value: 0 }))).toBeUndefined();
    expect(progress(state("zone", { target_value: 10, remaining_value: -1 }))).toBe(100);
  });

  it("only exposes request controls to the configured zone", () => {
    const request = state("1", {
      request_id: "request-1",
      execution_id: "execution-1",
      zone_subentry_id: "zone-a",
    });

    expect(activeRequestForZone(request, "zone-a")).toEqual({
      requestId: "request-1",
      executionId: "execution-1",
    });
    expect(activeRequestForZone(request, "zone-b")).toBeUndefined();
    expect(activeRequestForZone(state("1", { request_id: "request-1" }), "zone-a")).toBeUndefined();
  });

  it("submits both manual controls through the non-blocking request action", () => {
    expect(MANUAL_REQUEST_SERVICE).toBe("create_manual");
  });
});
