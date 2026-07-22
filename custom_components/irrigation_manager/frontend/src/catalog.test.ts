// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";

import "./index";

describe("Lovelace card catalog", () => {
  it("registers cards whose preview configuration can be applied", () => {
    const cards = window.customCards ?? [];
    expect(cards.map((card) => card.type)).toEqual(
      expect.arrayContaining([
        "irrigation-manager-overview-card",
        "irrigation-manager-zone-card",
      ]),
    );

    for (const type of [
      "irrigation-manager-overview-card",
      "irrigation-manager-zone-card",
    ]) {
      const constructor = customElements.get(type) as
        | (CustomElementConstructor & { getStubConfig(): unknown })
        | undefined;
      expect(constructor).toBeDefined();
      const element = new constructor!() as HTMLElement & {
        setConfig(config: unknown): void;
      };
      const stub = constructor!.getStubConfig();
      expect(stub).toMatchObject({ configuration_mode: "simple" });
      expect(() => element.setConfig(stub)).not.toThrow();
    }
  });
});
