import { describe, expect, it } from "vitest";

import { displayState, localize, translatedValue } from "./localize";
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

});
