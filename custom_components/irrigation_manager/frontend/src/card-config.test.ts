// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";

import "./index";
import {
  anchorChoices,
  inferConfigurationMode,
  resolveOverviewConfig,
  resolveZoneConfig,
} from "./helpers";
import type { HassEntity, HomeAssistant, OverviewCardConfig, ZoneCardConfig } from "./types";

function state(
  entityId: string,
  friendlyName: string,
  attributes: Record<string, unknown> = {},
): HassEntity {
  return {
    entity_id: entityId,
    state: "idle",
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

describe("simple card entity resolution", () => {
  it("resolves overview roles and lets explicit expert overrides win", () => {
    const home = hass(
      state("sensor.garden_status", "Garten Status", {
        config_entry_id: "garden",
        card_entities: {
          status: "sensor.garden_status",
          pending: "sensor.garden_pending",
        },
      }),
      state("sensor.garden_pending", "Offene Aufträge"),
      state("sensor.custom_pending", "Eigene Aufträge"),
    );
    const config: OverviewCardConfig = {
      type: "custom:irrigation-manager-overview-card",
      installation: "garden",
      pending_entity: "sensor.custom_pending",
    };

    expect(resolveOverviewConfig(home, config)).toMatchObject({
      status_entity: "sensor.garden_status",
      pending_entity: "sensor.custom_pending",
    });

    const renamedHome = hass(
      state("sensor.renamed_garden_status", "Garten Status", {
        config_entry_id: "garden",
        card_entities: { status: "sensor.renamed_garden_status" },
      }),
    );
    expect(resolveOverviewConfig(renamedHome, config).status_entity).toBe(
      "sensor.renamed_garden_status",
    );
  });

  it("resolves only the selected zone and its own installation", () => {
    const home = hass(
      state("sensor.hedge_water", "Hecke", {
        config_entry_id: "front",
        zone_subentry_id: "hedge",
        card_name: "Hecke",
        card_entities: {
          zone: "sensor.hedge_water",
          deficit: "sensor.hedge_deficit",
        },
        installation_card_entities: {
          active_zone: "sensor.front_active",
          dose: "sensor.front_dose",
        },
      }),
      state("sensor.lawn_water", "Rasen", {
        config_entry_id: "back",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        card_entities: {
          zone: "sensor.lawn_water",
          deficit: "sensor.lawn_deficit",
        },
        installation_card_entities: {
          active_zone: "sensor.back_active",
          dose: "sensor.back_dose",
        },
      }),
    );

    expect(
      resolveZoneConfig(home, {
        type: "custom:irrigation-manager-zone-card",
        zone: "front:hedge",
      }),
    ).toMatchObject({
      zone_entity: "sensor.hedge_water",
      deficit_entity: "sensor.hedge_deficit",
      active_zone_entity: "sensor.front_active",
      request_entity: "sensor.front_dose",
    });
    expect(anchorChoices(home, "zone").map((choice) => choice.label)).toEqual([
      "Hecke",
      "Rasen",
    ]);
    expect(anchorChoices(home, "zone").map((choice) => choice.value)).toEqual([
      "front:hedge",
      "back:lawn",
    ]);
  });

  it("infers expert for legacy entity configs and respects an explicit mode", () => {
    expect(
      inferConfigurationMode(
        { type: "custom:irrigation-manager-overview-card", status_entity: "sensor.old" },
        ["status_entity", "pending_entity"],
      ),
    ).toBe("expert");
    expect(
      inferConfigurationMode(
        {
          type: "custom:irrigation-manager-overview-card",
          configuration_mode: "simple",
          status_entity: "sensor.old",
        },
        ["status_entity"],
      ),
    ).toBe("simple");

    const home = hass(
      state("sensor.old", "Old status", {
        config_entry_id: "old",
        card_entities: {
          status: "sensor.old",
          pending: "sensor.newly_discoverable_pending",
        },
      }),
    );
    expect(
      resolveOverviewConfig(home, {
        type: "custom:irrigation-manager-overview-card",
        status_entity: "sensor.old",
      }).pending_entity,
    ).toBeUndefined();
  });
});

describe("simple card editors", () => {
  it("shows sorted friendly installation choices instead of technical entities", async () => {
    const home = hass(
      state("sensor.z_status", "Zweite Anlage", {
        config_entry_id: "z",
        card_name: "Zweite Anlage",
        card_entities: { status: "sensor.z_status" },
      }),
      state("sensor.a_status", "Erste Anlage", {
        config_entry_id: "a",
        card_name: "Erste Anlage",
        card_entities: { status: "sensor.a_status" },
      }),
      state("sensor.unrelated", "Unrelated"),
    );
    expect(anchorChoices(home, "installation").map((choice) => choice.label)).toEqual([
      "Erste Anlage",
      "Zweite Anlage",
    ]);
    expect(anchorChoices(home, "installation").map((choice) => choice.value)).toEqual(["a", "z"]);

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
      configuration_mode: "simple",
    });
    document.body.append(editor);
    await editor.updateComplete;

    const labels = Array.from(
      editor.shadowRoot.querySelectorAll<HTMLSelectElement>("[data-testid=anchor-selector] option"),
    ).map((option) => option.textContent);
    expect(labels).toEqual(["Entity nicht gefunden", "Erste Anlage", "Zweite Anlage"]);
  });

  it("switches mode without deleting retained expert overrides", async () => {
    const Editor = customElements.get("irrigation-manager-zone-card-editor")!;
    const editor = new Editor() as HTMLElement & {
      hass: HomeAssistant;
      setConfig(config: ZoneCardConfig): void;
      updateComplete: Promise<boolean>;
      shadowRoot: ShadowRoot;
    };
    editor.hass = hass();
    editor.setConfig({
      type: "custom:irrigation-manager-zone-card",
      zone_entity: "sensor.legacy_zone",
      deficit_entity: "sensor.explicit_deficit",
    });
    document.body.append(editor);
    await editor.updateComplete;

    const changed = new Promise<ZoneCardConfig>((resolve) => {
      editor.addEventListener("config-changed", (event) => {
        resolve((event as CustomEvent<{ config: ZoneCardConfig }>).detail.config);
      });
    });
    const mode = editor.shadowRoot.querySelector<HTMLSelectElement>(
      "[data-testid=configuration-mode]",
    )!;
    expect(mode.value).toBe("expert");
    mode.value = "simple";
    mode.dispatchEvent(new Event("change"));

    await expect(changed).resolves.toMatchObject({
      configuration_mode: "simple",
      zone_entity: "sensor.legacy_zone",
      deficit_entity: "sensor.explicit_deficit",
    });
  });
});
