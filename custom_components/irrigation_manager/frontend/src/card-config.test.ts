// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from "vitest";

import "./index";
import { resolveOverviewConfig, resolveZoneConfig, statusIcon } from "./helpers";
import type { HassEntity, HomeAssistant, OverviewCardConfig, ZoneCardConfig } from "./types";

function state(
  entityId: string,
  friendlyName: string,
  attributes: Record<string, unknown> = {},
  value = "idle",
): HassEntity {
  return {
    entity_id: entityId,
    state: value,
    attributes: { friendly_name: friendlyName, ...attributes },
  };
}

function hass(...states: HassEntity[]): HomeAssistant {
  return {
    language: "de",
    states: Object.fromEntries(states.map((item) => [item.entity_id, item])),
    callService: async () => undefined,
  };
}

beforeEach(() => document.body.replaceChildren());

describe("card anchor resolution", () => {
  it("resolves the dashboard-contract installation roles from a live-shaped anchor", () => {
    const home = hass(
      state("sensor.garden_status", "Garten", {
        config_entry_id: "garden",
        card_entities: {
          status: "sensor.garden_status",
          pending: "sensor.garden_pending",
          next: "sensor.garden_next_zone",
          next_start: "sensor.garden_next_start",
          runtime_today: "sensor.garden_runtime_today",
          runtime_month: "sensor.garden_runtime_month",
          physical_meter: "sensor.garden_physical_meter",
        },
      }),
    );

    const resolved = resolveOverviewConfig(home, {
      type: "custom:irrigation-manager-overview-card",
      entity: "sensor.garden_status",
    });
    expect(resolved).toMatchObject({
      status_entity: "sensor.garden_status",
      pending_entity: "sensor.garden_pending",
      next_entity: "sensor.garden_next_zone",
      next_start_entity: "sensor.garden_next_start",
      runtime_today_entity: "sensor.garden_runtime_today",
      runtime_month_entity: "sensor.garden_runtime_month",
      physical_meter_entity: "sensor.garden_physical_meter",
    });
  });

  it("resolves the selected zone from a live-shaped anchor", () => {
    const home = hass(
      state("sensor.hedge_status", "Hecke", {
        config_entry_id: "front",
        zone_subentry_id: "hedge",
        card_name: "Hecke",
        card_entities: {
          anchor: "sensor.hedge_status",
          status: "sensor.hedge_status",
          runtime_today: "sensor.hedge_runtime_today",
          runtime_month: "sensor.hedge_runtime_month",
          next_irrigation: "sensor.hedge_next",
        },
      }),
      state("sensor.lawn_status", "Rasen", {
        config_entry_id: "back",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    );

    const resolved = resolveZoneConfig(home, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.hedge_status",
    });
    expect(resolved).toMatchObject({
      zone_entity: "sensor.hedge_status",
      status_entity: "sensor.hedge_status",
      runtime_today_entity: "sensor.hedge_runtime_today",
      runtime_month_entity: "sensor.hedge_runtime_month",
      next_irrigation_entity: "sensor.hedge_next",
    });
  });

  it("keeps status icons for all effective release states", () => {
    for (const value of ["disabled", "automatic_disabled", "installation_disabled", "safety_lock"]) {
      expect(statusIcon(value)).not.toBe("mdi:information-outline");
    }
  });
});

describe("card editors", () => {
  it.each([
    ["irrigation-manager-overview-card-editor", "sensor.garden_status"],
    ["irrigation-manager-zone-card-editor", "sensor.lawn_status"],
  ] as const)("%s exposes exactly one entity anchor selector", async (tag, value) => {
    const home = hass(
      state("sensor.garden_status", "Garten", {
        config_entry_id: "garden",
        card_name: "Garten",
        card_entities: { status: "sensor.garden_status" },
      }),
      state("sensor.lawn_status", "Rasen", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    );
    const Editor = customElements.get(tag)!;
    const editor = new Editor() as HTMLElement & {
      hass: HomeAssistant;
      setConfig(config: OverviewCardConfig | ZoneCardConfig): void;
      updateComplete: Promise<boolean>;
      shadowRoot: ShadowRoot;
    };
    editor.hass = home;
    editor.setConfig({ type: `custom:${tag.replace("-editor", "")}` });
    document.body.append(editor);
    await editor.updateComplete;

    const selectors = editor.shadowRoot.querySelectorAll("ha-selector[data-testid=anchor-selector]");
    expect(selectors).toHaveLength(1);
    const selector = (selectors[0] as HTMLElement & {
      selector: { entity: Record<string, unknown> };
    }).selector.entity;
    expect(selector).toMatchObject({
      include_entities: [value],
      filter: {
        integration: "irrigation_manager",
        domain: "sensor",
        device_class: "enum",
      },
    });
    expect(editor.shadowRoot.querySelector("[data-testid=configuration-mode]")).toBeNull();
    expect(editor.shadowRoot.querySelector("input[type=checkbox]")).toBeNull();

    const changed = new Promise<Record<string, unknown>>((resolve) => {
      editor.addEventListener("config-changed", (event) => {
        resolve((event as CustomEvent<{ config: Record<string, unknown> }>).detail.config);
      });
    });
    selectors[0].dispatchEvent(new CustomEvent("value-changed", { detail: { value } }));
    await expect(changed).resolves.toEqual({
      type: `custom:${tag.replace("-editor", "")}`,
      entity: value,
    });
    await editor.updateComplete;
    expect((selectors[0] as HTMLElement & { value: string }).value).toBe(value);
    expect(editor.shadowRoot.querySelector("[role=alert]")).toBeNull();
  });

  it("renders an editor error immediately when the selected sensor is not its anchor", async () => {
    const home = hass(state("sensor.garden_runtime_today", "Runtime", {}, "123"));
    const Editor = customElements.get("irrigation-manager-overview-card-editor")!;
    const editor = new Editor() as HTMLElement & {
      hass: HomeAssistant;
      setConfig(config: OverviewCardConfig): void;
      updateComplete: Promise<boolean>;
      shadowRoot: ShadowRoot;
    };
    editor.hass = home;
    editor.setConfig({
      type: "custom:irrigation-manager-overview-card",
      entity: "sensor.garden_runtime_today",
    });
    document.body.append(editor);
    await editor.updateComplete;

    expect(editor.shadowRoot.querySelector("[role=alert]")?.textContent)
      .toContain("Status-Entity der Bewässerungsanlage");
  });
});
