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
  timeZone?: string,
): HomeAssistant {
  return {
    language: "de",
    config: { time_zone: timeZone },
    states: Object.fromEntries(states.map((item) => [item.entity_id, item])),
    callService,
  };
}

function localIso(dayOffset: number, hour: number): string {
  const date = new Date();
  date.setDate(date.getDate() + dayOffset);
  date.setHours(hour, 0, 0, 0);
  return date.toISOString();
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
  vi.useRealTimers();
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("dashboard card interactions", () => {
  it.each([
    [false, "Laufzeit heute", "Laufzeit diesen Monat", "Gemessenes Wasser heute"],
    [true, "Gemessenes Wasser heute", "Gemessenes Wasser diesen Monat", "Laufzeit heute"],
  ] as const)(
    "shows the installation's effective period metrics when metering is %s",
    async (metering, todayLabel, monthLabel, excludedLabel) => {
      const hass = home([
        state("sensor.garden_status", "idle", {
          config_entry_id: "garden",
          card_name: "Garten",
          volume_control_available: metering,
          card_entities: {
            status: "sensor.garden_status",
            runtime_today: "sensor.garden_runtime_today",
            runtime_month: "sensor.garden_runtime_month",
            today_consumption: "sensor.garden_water_today",
            month_consumption: "sensor.garden_water_month",
            physical_meter: "sensor.garden_physical_meter",
          },
        }),
        state("sensor.garden_runtime_today", "321", { unit_of_measurement: "s" }),
        state("sensor.garden_runtime_month", "654", { unit_of_measurement: "s" }),
        state("sensor.garden_water_today", "12.3", { unit_of_measurement: "L" }),
        state("sensor.garden_water_month", "45.6", { unit_of_measurement: "L" }),
        state("sensor.garden_physical_meter", "789.1", { unit_of_measurement: "L" }),
      ]);
      const card = await renderCard("irrigation-manager-overview-card", hass, {
        type: "custom:irrigation-manager-overview-card",
        entity: "sensor.garden_status",
      });

      expect(card.shadowRoot.textContent).toContain(todayLabel);
      expect(card.shadowRoot.textContent).toContain(monthLabel);
      expect(card.shadowRoot.textContent).not.toContain(excludedLabel);
      expect(card.shadowRoot.textContent).toContain(metering ? "12.3" : "321");
      expect(card.shadowRoot.textContent).toContain(metering ? "45.6" : "654");
      if (metering) {
        expect(card.shadowRoot.textContent).toContain("Physischer Zählerstand");
        expect(card.shadowRoot.textContent).toContain("789.1");
      }
    },
  );

  it("renders mapped zone values and preserves the two zone actions", async () => {
    const hass = home([
      state("sensor.lawn_status", "safety_lock", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        card_entities: {
          anchor: "sensor.lawn_status",
          status: "sensor.lawn_status",
          runtime_today: "sensor.lawn_runtime_today",
          runtime_month: "sensor.lawn_runtime_month",
          next_irrigation: "sensor.lawn_next",
        },
      }),
      state("sensor.lawn_runtime_today", "600", { unit_of_measurement: "s" }),
      state("sensor.lawn_runtime_month", "3600", { unit_of_measurement: "s" }),
      state("sensor.lawn_next", "2026-07-26T05:00:00+00:00"),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
    });

    expect(card.shadowRoot.textContent).toContain("Sicherheitssperre");
    expect(card.shadowRoot.textContent).toContain("600");
    expect(card.shadowRoot.textContent).toContain("3600");
    expect(card.shadowRoot.textContent).toContain("2026-07-26T05:00:00+00:00");
    expect(card.shadowRoot.querySelector("[data-testid=reset-safety]")).toBeNull();
    expect(card.shadowRoot.querySelectorAll(".actions > button")).toHaveLength(2);
  });

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
      entity: "sensor.garden_status",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=emergency-stop]")!.click();
    await Promise.resolve();

    expect(confirm).not.toHaveBeenCalled();
    expect(callService).toHaveBeenCalledWith("irrigation_manager", "emergency_stop", {
      config_entry_id: "garden",
    });
  });

  it("offers a confirmed stop only for this zone's active irrigation", async () => {
    const callService = vi.fn(async () => undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const hass = home([
      state("sensor.lawn_status", "watering", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        active_execution: true,
        active_execution_id: "execution-1",
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=stop-watering]")!.click();
    await Promise.resolve();

    expect(window.confirm).toHaveBeenCalledWith(
      "Die laufende Bewässerung dieser Zone wirklich stoppen?",
    );
    expect(callService).toHaveBeenCalledWith("irrigation_manager", "stop", {
      config_entry_id: "garden",
      execution_id: "execution-1",
    });
  });

  it("does not show a stop action without this zone's active execution id", async () => {
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        active_execution: true,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
    });

    expect(card.shadowRoot.querySelector("[data-testid=stop-watering]")).toBeNull();
  });

  it("opens an accessible list of open irrigation orders from the metric", async () => {
    const expectedStart = localIso(0, 5);
    const callService = vi.fn(async (_domain, service) => service === "list_card_orders" ? {
      context: { id: "context-1" },
      response: {
        orders: [{
          request_id: "request-1",
          zone: "Rasen",
          source: "automatic",
          target_type: "duration",
          target_value: 600,
          expected_start: expectedStart,
          status: "pending",
        }],
      },
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
      entity: "sensor.garden_status",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=open-orders]")!.click();
    await Promise.resolve();
    await card.updateComplete;

    const dialog = card.shadowRoot.querySelector<HTMLDialogElement>("dialog[open]");
    expect(dialog?.getAttribute("aria-labelledby")).toBe("orders-title");
    expect(dialog?.textContent).toContain("Rasen");
    expect(dialog?.textContent).toContain("600 s");
    expect(dialog?.textContent).not.toContain(expectedStart);
    expect(callService).toHaveBeenCalledWith(
      "irrigation_manager",
      "list_card_orders",
      { config_entry_id: "garden" },
      undefined,
      false,
      true,
    );
  });

  it("navigates open irrigation orders by local calendar day", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-27T10:00:00Z"));
    const callService = vi.fn(async (_domain, service) => service === "list_card_orders" ? {
      response: {
        orders: [
          { zone: "Später", source: "automatic", target_type: "duration", target_value: 300, expected_start: "2026-07-27T08:00:00Z", status: "pending" },
          { zone: "Früher", source: "automatic", target_type: "duration", target_value: 200, expected_start: "2026-07-27T06:00:00Z", status: "pending" },
          { zone: "Übermorgen", source: "automatic", target_type: "duration", target_value: 600, expected_start: "2026-07-29T06:00:00Z", status: "pending" },
        ],
      },
    } : undefined);
    const hass = home([
      state("sensor.garden_status", "idle", {
        config_entry_id: "garden",
        card_entities: { status: "sensor.garden_status", pending: "sensor.pending" },
      }),
      state("sensor.pending", "3"),
    ], callService, "Europe/Zurich");
    const card = await renderCard("irrigation-manager-overview-card", hass, {
      type: "custom:irrigation-manager-overview-card",
      entity: "sensor.garden_status",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=open-orders]")!.click();
    await Promise.resolve();
    await card.updateComplete;

    const dialog = card.shadowRoot.querySelector<HTMLDialogElement>("dialog[open]")!;
    expect(dialog.textContent).toContain("Heute");
    expect(dialog.textContent).not.toContain("Übermorgen");
    expect(dialog.textContent!.indexOf("Früher")).toBeLessThan(dialog.textContent!.indexOf("Später"));

    const dateInput = dialog.querySelector<HTMLInputElement>("[data-testid=orders-date]")!;
    dateInput.value = "";
    dateInput.dispatchEvent(new Event("change"));
    await card.updateComplete;
    expect(dateInput.value).toBe("2026-07-27");

    dialog.querySelector<HTMLButtonElement>("[aria-label='Nächster Tag']")!.click();
    await card.updateComplete;

    expect(dialog.textContent).toContain("An diesem Tag sind keine Bewässerungsaufträge offen.");
    dialog.querySelector<HTMLButtonElement>("[data-testid=next-orders-date]")!.click();
    await card.updateComplete;

    expect(dialog.textContent).not.toContain("Heute");
    expect(dialog.textContent).toContain("Übermorgen");
    vi.useRealTimers();
  });

  it("shows the message from Home Assistant websocket errors", async () => {
    const callService = vi.fn(async () => Promise.reject({
      code: "service_validation_error",
      message: "The action requires a response.",
    }));
    const hass = home([
      state("sensor.garden_status", "idle", {
        config_entry_id: "garden",
        card_entities: { status: "sensor.garden_status" },
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-overview-card", hass, {
      type: "custom:irrigation-manager-overview-card",
      entity: "sensor.garden_status",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=open-orders]")!.click();
    await vi.waitFor(() => {
      expect(card.shadowRoot.querySelector("[role=alert]")?.textContent)
        .toContain("The action requires a response.");
    });

    expect(card.shadowRoot.textContent).not.toContain("[object Object]");
  });

  it("keeps manual inputs in a dialog and offers only effective capabilities", async () => {
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: false,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
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
        }),
      ]);
      const card = await renderCard("irrigation-manager-zone-card", hass, {
        type: "custom:irrigation-manager-zone-card",
        entity: "sensor.lawn_status",
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
      }),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
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
        max_manual_volume_runtime_seconds: 5400,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    ]);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
    });
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")!.click();
    await card.updateComplete;

    const targetHours = card.shadowRoot.querySelector<HTMLInputElement>(
      "[data-testid=manual-target-hours]",
    )!;
    expect(targetHours.type).toBe("number");
    expect(targetHours.max).toBe("");
    expect((targetHours.closest(".duration-input") as HTMLElement | null)?.title)
      .toContain("168:00:00");
    card.shadowRoot.querySelector<HTMLSelectElement>("[data-testid=target-mode]")!.value = "amount";
    card.shadowRoot.querySelector<HTMLSelectElement>("[data-testid=target-mode]")!
      .dispatchEvent(new Event("change"));
    await card.updateComplete;
    const hardLimitHours = card.shadowRoot.querySelector<HTMLInputElement>(
      "[data-testid=hard-limit-hours]",
    )!;
    expect(hardLimitHours.type).toBe("number");
    expect((hardLimitHours.closest(".duration-input") as HTMLElement | null)?.title)
      .toContain("01:30:00");
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
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
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
    }, undefined, false, true);
    expect(callService).toHaveBeenCalledTimes(1);
  });

  it("converts structured manual duration inputs to service seconds", async () => {
    const callService = vi.fn(async () => ({ request_id: "manual-1" }));
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: true,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
    });
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")!.click();
    await card.updateComplete;

    for (const [part, value] of [["hours", "1"], ["minutes", "2"], ["seconds", "3"]]) {
      const input = card.shadowRoot.querySelector<HTMLInputElement>(
        `[data-testid=manual-target-${part}]`,
      )!;
      input.value = value;
      input.dispatchEvent(new Event("input"));
      await card.updateComplete;
    }
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=submit-manual]")!.click();
    await Promise.resolve();

    expect(callService).toHaveBeenCalledWith("irrigation_manager", "start_manual_from_card", {
      config_entry_id: "garden",
      zone_subentry_id: "lawn",
      duration: 3723,
      conflict_policy: "start_now",
    }, undefined, false, true);
  });

  it("converts the structured amount hard limit to seconds", async () => {
    const callService = vi.fn(async () => ({ request_id: "manual-1" }));
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: true,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    ], callService);
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
    });
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=manual-irrigation]")!.click();
    await card.updateComplete;
    const mode = card.shadowRoot.querySelector<HTMLSelectElement>("[data-testid=target-mode]")!;
    mode.value = "amount";
    mode.dispatchEvent(new Event("change"));
    await card.updateComplete;

    const amount = card.shadowRoot.querySelector<HTMLInputElement>("[data-testid=manual-target]")!;
    amount.value = "25";
    amount.dispatchEvent(new Event("input"));
    for (const [part, value] of [["hours", "0"], ["minutes", "45"]]) {
      const input = card.shadowRoot.querySelector<HTMLInputElement>(
        `[data-testid=hard-limit-${part}]`,
      )!;
      input.value = value;
      input.dispatchEvent(new Event("input"));
      await card.updateComplete;
    }
    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=submit-manual]")!.click();
    await Promise.resolve();

    expect(callService).toHaveBeenCalledWith("irrigation_manager", "start_manual_from_card", {
      config_entry_id: "garden",
      zone_subentry_id: "lawn",
      amount: 25,
      hard_time_limit: 2700,
      conflict_policy: "start_now",
    }, undefined, false, true);
  });

  it("loads paginated zone-filtered irrigation history into an accessible dialog", async () => {
    const callService = vi.fn(async (_domain, service) => service === "list_zone_history" ? {
      context: { id: "context-1" },
      response: {
        items: [{
          execution_id: "execution-1",
          started_at: "2026-07-24T05:00:00+00:00",
          ended_at: "2026-07-24T05:10:00+00:00",
          source: "manual",
          target_type: "duration",
          target_value: 600,
          result: "completed",
          actual_duration: 600,
          actual_water: 1044.0001487731902,
          completion_reason: "target_reached",
        }],
        offset: 0,
        limit: 20,
        total: 1,
        has_more: false,
      },
    } : undefined);
    const hass = home([
      state("sensor.lawn_status", "idle", {
        config_entry_id: "garden",
        zone_subentry_id: "lawn",
        card_name: "Rasen",
        volume_control_available: false,
        card_entities: { anchor: "sensor.lawn_status", status: "sensor.lawn_status" },
      }),
    ], callService, "Europe/Zurich");
    const card = await renderCard("irrigation-manager-zone-card", hass, {
      type: "custom:irrigation-manager-zone-card",
      entity: "sensor.lawn_status",
    });

    card.shadowRoot.querySelector<HTMLButtonElement>("[data-testid=show-history]")!.click();
    await Promise.resolve();
    await card.updateComplete;

    const dialogText = card.shadowRoot.querySelector("dialog[open]")?.textContent ?? "";
    expect(dialogText).toContain("24.07.2026, 07:00:00");
    expect(dialogText).toContain("24.07.2026, 07:10:00");
    expect(dialogText).toContain("00:10:00");
    expect(dialogText).toContain("1.044,00 L");
    expect(dialogText).toContain("Seite 1 von 1");
    expect(dialogText).toContain("Einträge 1–1 von 1");
    expect(dialogText).not.toContain("2026-07-24T05:00:00+00:00");
    expect(dialogText).not.toContain("600 s");
    expect(callService).toHaveBeenCalledWith(
      "irrigation_manager",
      "list_zone_history",
      { config_entry_id: "garden", zone_subentry_id: "lawn", offset: 0, limit: 20 },
      undefined,
      false,
      true,
    );
  });

  it.each([
    ["irrigation-manager-overview-card", "Bewässerungsanlage auswählen"],
    ["irrigation-manager-zone-card", "Bewässerungszone auswählen"],
  ] as const)("%s accepts an empty preview config", async (tag, message) => {
    const card = await renderCard(tag, home([]), {});

    expect(card.shadowRoot.querySelector("[role=alert]")?.textContent).toContain(message);
  });

  it.each([
    ["irrigation-manager-overview-card", "Status-Entity der Bewässerungsanlage"],
    ["irrigation-manager-zone-card", "Status-Entity der Bewässerungszone"],
  ] as const)("%s rejects an existing entity that is not the correct anchor", async (tag, message) => {
    const card = await renderCard(tag, home([
      state("sensor.garden_runtime_today", "123", { unit_of_measurement: "s" }),
    ]), { entity: "sensor.garden_runtime_today" });

    expect(card.shadowRoot.querySelector("[role=alert]")?.textContent).toContain(message);
  });
});
