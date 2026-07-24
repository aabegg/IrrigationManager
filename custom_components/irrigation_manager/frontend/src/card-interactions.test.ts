// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from "vitest";

import "./index";
import type { HassEntity, HomeAssistant, OverviewCardConfig, ZoneCardConfig } from "./types";

function state(
  entityId: string,
  value: string,
  attributes: Record<string, unknown> = {},
): HassEntity {
  return { entity_id: entityId, state: value, attributes };
}

function home(
  states: HassEntity[],
  callService: HomeAssistant["callService"] = vi.fn(async () => undefined),
): HomeAssistant {
  return {
    language: "de",
    states: Object.fromEntries(states.map((item) => [item.entity_id, item])),
    callService,
  };
}

async function renderCard<T extends OverviewCardConfig | ZoneCardConfig>(
  tag: string,
  hass: HomeAssistant,
  config: T,
) {
  const Card = customElements.get(tag)!;
  const card = new Card() as HTMLElement & {
    hass: HomeAssistant;
    setConfig(value: T): void;
    updateComplete: Promise<boolean>;
    shadowRoot: ShadowRoot;
  };
  card.hass = hass;
  card.setConfig(config);
  document.body.append(card);
  await card.updateComplete;
  return card;
}

beforeEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("dashboard card interactions", () => {
  it("executes the mandatory emergency stop immediately without confirmation", async () => {
    const callService = vi.fn(async () => undefined);
    const confirm = vi.spyOn(window, "confirm");
    const hass = home([
      state("sensor.garden_status", "idle", {
        config_entry_id: "garden",
        card_name: "Garten",
        card_entities: { status: "sensor.garden_status" },
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-overview-card", hass, {
      type: "custom:irrigation-manager-overview-card",
      installation: "garden",
      visible_actions: [],
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=emergency-stop]")!.click();
    await Promise.resolve();

    expect(confirm).not.toHaveBeenCalled();
    expect(callService).toHaveBeenCalledWith("irrigation_manager", "emergency_stop", {
      config_entry_id: "garden",
    });
  });

  it("opens an accessible list of open irrigation orders from the metric", async () => {
    const callService = vi.fn(async (_domain, service) => service === "list_card_orders" ? {
      orders: [{
        request_id: "request-1",
        zone: "Rasen",
        source: "automatic",
        target_type: "duration",
        target_value: 600,
        expected_start: "2026-07-25T05:00:00+00:00",
        status: "pending",
      }],
    } : undefined);
    const hass = home([
      state("sensor.garden_status", "idle", {
        config_entry_id: "garden",
        card_name: "Garten",
        card_entities: {
          status: "sensor.garden_status",
          pending: "sensor.garden_pending",
        },
      }),
      state("sensor.garden_pending", "1"),
    ], callService);
    const card = await renderCard("irrigation-manager-overview-card", hass, {
      type: "custom:irrigation-manager-overview-card",
      installation: "garden",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=open-orders]")!.click();
    await Promise.resolve();
    await card.updateComplete;

    const dialog = card.shadowRoot.querySelector<HTMLDialogElement>("dialog[open]");
    expect(dialog?.getAttribute("aria-labelledby")).toBe("orders-title");
    expect(dialog?.textContent).toContain("Rasen");
    expect(dialog?.textContent).toContain("600 s");
    expect(callService).toHaveBeenCalledWith(
      "irrigation_manager",
      "list_card_orders",
      { config_entry_id: "garden" },
      undefined,
      true,
    );
  });

  it("keeps manual inputs in a dialog and offers only effective capabilities", async () => {
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: false,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
        installation_card_entities: {},
      }),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      zone: "garden:lawn",
      display_mode: "compact",
    });

    expect(card.shadowRoot.querySelector("input")).toBeNull();
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")!.click();
    await card.updateComplete;

    const dialog = card.shadowRoot.querySelector<HTMLDialogElement>("dialog[open]");
    expect(dialog?.querySelector("input")).toBeTruthy();
    expect(dialog?.querySelector("option[value=amount]")).toBeNull();
    expect(dialog?.querySelector<HTMLButtonElement>("[data-testid=submit-manual]")).toBeTruthy();
  });

  it.each(["disabled", "installation_disabled", "safety_lock"])(
    "disables manual irrigation while the effective zone status is %s",
    async (zoneStatus) => {
      const hass = home([
        state("sensor.lawn_status", zoneStatus, {
          config_entry_id: "garden",
          zone_subentry_id: "lawn",
          card_name: "Rasen",
          card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
          installation_card_entities: {},
        }),
      ]);
      const card = await renderCard("irrigation-manager-zone-card", hass, {
        type: "custom:irrigation-manager-zone-card",
        zone: "garden:lawn",
      });

      expect(
        card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")
          ?.disabled,
      ).toBe(true);
    },
  );

  it("disables manual irrigation while reconfiguration is required", async () => {
    const hass = home([
      state("sensor.lawn_status", "needs_reconfiguration", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
        installation_card_entities: {},
      }),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      zone: "garden:lawn",
    });

    expect(
      card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")
        ?.disabled,
    ).toBe(true);
  });

  it("uses the backend manual runtime capabilities as input maxima", async () => {
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: true,
        max_manual_duration_seconds: 7200,
        max_manual_volume_runtime_seconds: 5400,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
        installation_card_entities: {},
      }),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      zone: "garden:lawn",
    });
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")!.click();
    await card.updateComplete;

    const target = card.shadowRoot.querySelector<HTMLInputElement>("[data-testid=manual-target]")!;
    expect(target.max).toBe("7200");
    card.shadowRoot.querySelector<HTMLSelectElement>("[data-testid=target-mode]")!.value = "amount";
    card.shadowRoot.querySelector<HTMLSelectElement>("[data-testid=target-mode]")!
      .dispatchEvent(new Event("change"));
    await card.updateComplete;
    expect(card.shadowRoot.querySelector<HTMLInputElement>("[data-testid=hard-limit]")!.max)
      .toBe("5400");
  });

  it("submits one atomic conflict policy when another execution is active", async () => {
    const callService = vi.fn(async () => ({ request_id: "manual-1" }));
    const hass = home([
      state("sensor.lawn_status", "installation_busy", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: true,
        active_execution: true,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
        installation_card_entities: {},
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      zone: "garden:lawn",
    });
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")!.click();
    await card.updateComplete;

    const policy = card.shadowRoot.querySelector<HTMLSelectElement>("[data-testid=conflict-policy]")!;
    expect(Array.from(policy.options).map((item) => item.value)).toEqual([
      "stop_active",
      "priority_next",
    ]);
    policy.value = "priority_next";
    policy.dispatchEvent(new Event("change"));
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=submit-manual]")!.click();
    await Promise.resolve();

    expect(callService).toHaveBeenCalledWith("irrigation_manager", "start_manual_from_card", {
      config_entry_id: "garden",
      zone_subentry_id: "lawn",
      duration: 600,
      conflict_policy: "priority_next",
    });
    expect(callService).toHaveBeenCalledTimes(1);
  });

  it("loads paginated zone-filtered irrigation history into an accessible dialog", async () => {
    const callService = vi.fn(async (_domain, service) => service === "list_zone_history" ? {
      items: [{
        execution_id: "execution-1",
        started_at: "2026-07-24T05:00:00+00:00",
        ended_at: "2026-07-24T05:10:00+00:00",
        source: "manual",
        target_type: "duration",
        target_value: 600,
        result: "completed",
        actual_duration: 600,
        actual_water: null,
        completion_reason: "target_reached",
      }],
      offset: 0,
      limit: 20,
      total: 1,
      has_more: false,
    } : undefined);
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: false,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
        installation_card_entities: {},
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      zone: "garden:lawn",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=show-history]")!.click();
    await Promise.resolve();
    await card.updateComplete;

    expect(card.shadowRoot.querySelector("dialog[open]")?.textContent).toContain("600 s");
    expect(callService).toHaveBeenCalledWith(
      "irrigation_manager",
      "list_zone_history",
      { config_entry_id: "garden", zone_subentry_id: "lawn", offset: 0, limit: 20 },
      undefined,
      true,
    );
  });
});
