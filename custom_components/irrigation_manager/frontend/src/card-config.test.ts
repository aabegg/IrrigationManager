// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from "vitest";

import "./index";
import { anchorChoices, resolveOverviewConfig, resolveZoneConfig, statusIcon } from "./helpers";
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
  it("resolves only the dashboard-contract installation roles", () => {
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
          winter: "binary_sensor.garden_winter",
          maintenance: "binary_sensor.garden_maintenance",
          model_quality: "sensor.garden_quality",
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
    expect(resolved).not.toHaveProperty("winter_entity");
    expect(resolved).not.toHaveProperty("maintenance_entity");
    expect(resolved).not.toHaveProperty("model_quality_entity");
  });

  it("resolves only the selected zone and excludes legacy zone fields", () => {
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
          deficit: "sensor.hedge_deficit",
          safety_lock: "binary_sensor.hedge_lock",
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
    expect(resolved).not.toHaveProperty("deficit_entity");
    expect(resolved).not.toHaveProperty("safety_lock_entity");
    expect(anchorChoices(home, "zone")).toEqual([
      { value: "sensor.hedge_status", label: "Hecke" },
      { value: "sensor.lawn_status", label: "Rasen" },
    ]);
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
    expect((selectors[0] as HTMLElement & {
      selector: { entity: { include_entities: string[] } };
    }).selector.entity.include_entities)
      .toContain(value);
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
  });
});
