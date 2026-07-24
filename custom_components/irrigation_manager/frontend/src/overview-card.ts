import { LitElement, html, nothing, type TemplateResult } from "lit";

import {
  DOMAIN,
  entity,
  progress,
  resolveOverviewConfig,
  statusIcon,
  stringAttribute,
  usable,
} from "./helpers";
import { displayState, localize, translatedValue } from "./localize";
import { cardStyles } from "./styles";
import type { HassEntity, HomeAssistant, OverviewCardConfig } from "./types";

const DEFAULT_METRICS = ["pending", "next", "today", "month", "meter"];
const DEFAULT_ACTIONS: string[] = [];

export class IrrigationManagerOverviewCard extends LitElement {
  static styles = cardStyles;
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _busy: { state: true },
    _error: { state: true },
    _ordersOpen: { state: true },
    _orders: { state: true },
  };

  hass!: HomeAssistant;
  private _config!: OverviewCardConfig;
  private _busy = false;
  private _error?: string;
  private _ordersOpen = false;
  private _orders: Array<Record<string, unknown>> = [];

  static getConfigElement(): HTMLElement {
    return document.createElement("irrigation-manager-overview-card-editor");
  }

  static getStubConfig(): OverviewCardConfig {
    return {
      type: "custom:irrigation-manager-overview-card",
      configuration_mode: "simple",
      installation: "",
    };
  }

  setConfig(config: OverviewCardConfig): void {
    this._config = { ...config };
  }

  getCardSize(): number {
    return this._config?.display_mode === "compact" ? 3 : 5;
  }

  private metric(key: string, label: string, state?: HassEntity): TemplateResult | typeof nothing {
    if (!(this._config.visible_metrics ?? DEFAULT_METRICS).includes(key)) return nothing;
    return html`<div class="metric"><span>${label}</span><strong>${displayState(this.hass, state)}</strong></div>`;
  }

  private async call(service: string, confirmation?: string, extra: Record<string, unknown> = {}): Promise<void> {
    if (confirmation && !window.confirm(confirmation)) return;
    const config = resolveOverviewConfig(this.hass, this._config);
    const status = entity(this.hass, config.status_entity);
    const configEntryId = stringAttribute(status, "config_entry_id");
    if (!configEntryId) {
      this._error = localize(this.hass, "configuration_error");
      return;
    }
    this._busy = true;
    this._error = undefined;
    try {
      await this.hass.callService(DOMAIN, service, { config_entry_id: configEntryId, ...extra });
    } catch (error) {
      this._error = `${localize(this.hass, "action_failed")}: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      this._busy = false;
    }
  }

  private async openOrders(): Promise<void> {
    const config = resolveOverviewConfig(this.hass, this._config);
    const configEntryId = stringAttribute(entity(this.hass, config.status_entity), "config_entry_id");
    if (!configEntryId) return;
    this._ordersOpen = true;
    this._busy = true;
    this._error = undefined;
    try {
      const response = await this.hass.callService(
        DOMAIN,
        "list_card_orders",
        { config_entry_id: configEntryId },
        undefined,
        true,
      ) as { orders?: Array<Record<string, unknown>> };
      this._orders = response.orders ?? [];
    } catch (error) {
      this._error = `${localize(this.hass, "action_failed")}: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      this._busy = false;
    }
  }

  private target(order: Record<string, unknown>): string {
    return `${String(order.target_value)} ${order.target_type === "volume" ? localize(this.hass, "liters") : localize(this.hass, "seconds")}`;
  }

  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    const config = resolveOverviewConfig(this.hass, this._config);
    if (!config.status_entity || !entity(this.hass, config.status_entity)) {
      return html`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${localize(this.hass, "missing")}</span></div></div></ha-card>`;
    }
    const status = entity(this.hass, config.status_entity);
    const emergency = entity(this.hass, config.emergency_entity);
    const lock = entity(this.hass, config.lock_entity);
    const winter = entity(this.hass, config.winter_entity);
    const maintenance = entity(this.hass, config.maintenance_entity);
    const release = entity(this.hass, config.automation_release_entity);
    const active = entity(this.hass, config.active_zone_entity);
    const configEntryId = stringAttribute(status, "config_entry_id");
    const percent = progress(active);
    const actions = this._config.visible_actions ?? DEFAULT_ACTIONS;
    const statusValue = status?.state ?? "unavailable";
    const locked = emergency?.state === "on" || lock?.state === "on";
    const meteringFunctional = status?.attributes.volume_control_available === true;

    return html`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${statusIcon(statusValue)}></ha-icon>
              <div>
                <h2>${this._config.name ?? localize(this.hass, "overview")}</h2>
                <strong>${usable(status) ? translatedValue(this.hass, status.state) : displayState(this.hass, status)}</strong>
              </div>
            </div>
          </header>

          ${locked
            ? html`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${emergency?.state === "on" ? localize(this.hass, "emergency_stop") : localize(this.hass, "safety_lock")}${stringAttribute(lock, "reason") ? `: ${stringAttribute(lock, "reason")}` : ""}</span></div>`
            : nothing}
          ${winter?.state === "on"
            ? html`<div class="warning"><ha-icon icon="mdi:snowflake-alert"></ha-icon><span>${localize(this.hass, "winter_lock")}</span></div>`
            : nothing}
          ${maintenance?.state === "on"
            ? html`<div class="warning"><ha-icon icon="mdi:wrench-clock"></ha-icon><span>${localize(this.hass, "maintenance_active")}</span></div>`
            : nothing}
          ${release?.state === "off" && stringAttribute(release, "suspended_until")
            ? html`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${localize(this.hass, "automatic_suspended")}: ${stringAttribute(release, "suspended_until")}</span></div>`
            : nothing}

          ${(this._config.visible_metrics ?? DEFAULT_METRICS).includes("active") && active
            ? html`
                <section>
                  <h3>${localize(this.hass, "active_zone")}</h3>
                  <strong>${displayState(this.hass, active)}</strong>
                  ${config.dose_entity
                    ? html`<div class="secondary">${localize(this.hass, "dose")}: ${displayState(this.hass, entity(this.hass, config.dose_entity))}</div>`
                    : nothing}
                  ${percent === undefined
                    ? nothing
                    : html`<div class="secondary">${localize(this.hass, "progress")}: ${Math.round(percent)}%</div><progress max="100" .value=${percent} aria-label=${localize(this.hass, "progress")}></progress>`}
                </section>
              `
            : nothing}

          <div class="metrics details">
            ${(this._config.visible_metrics ?? DEFAULT_METRICS).includes("pending")
              ? html`<button class="metric metric-button" data-testid="open-orders" ?disabled=${this._busy || !configEntryId} @click=${this.openOrders}><span>${localize(this.hass, "pending")}</span><strong>${displayState(this.hass, entity(this.hass, config.pending_entity))}</strong></button>`
              : nothing}
            ${this.metric("next", localize(this.hass, "next_zone"), entity(this.hass, config.next_entity))}
            ${this.metric("next", localize(this.hass, "expected_start"), entity(this.hass, config.next_start_entity))}
            ${this.metric("today", localize(this.hass, meteringFunctional ? "water_today" : "runtime_today"), entity(this.hass, meteringFunctional ? config.today_consumption_entity : config.runtime_today_entity))}
            ${this.metric("month", localize(this.hass, meteringFunctional ? "water_month" : "runtime_month"), entity(this.hass, meteringFunctional ? config.month_consumption_entity : config.runtime_month_entity))}
            ${this.metric("meter", localize(this.hass, "corrected_meter"), entity(this.hass, config.physical_meter_entity))}
            ${this.metric("quality", localize(this.hass, "model_quality"), entity(this.hass, config.model_quality_entity))}
            ${this.metric("maintenance", localize(this.hass, "maintenance_due"), entity(this.hass, config.maintenance_due_entity))}
          </div>

          ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
          <div class="actions">
            ${actions.includes("stop")
              ? html`<button class="danger" ?disabled=${this._busy || !usable(status) || !configEntryId} @click=${() => this.call("stop", localize(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${localize(this.hass, "stop")}</button>`
              : nothing}
            <button class="danger emergency" data-testid="emergency-stop" ?disabled=${this._busy || !configEntryId} @click=${() => this.call("emergency_stop")}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${localize(this.hass, "emergency")}</button>
            ${actions.includes("suspend")
              ? html`<button ?disabled=${this._busy || !configEntryId} @click=${() => this.call("suspend_automatic", localize(this.hass, "confirm_suspend"), { until: new Date(Date.now() + 86400000).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${localize(this.hass, "suspend_24h")}</button>`
              : nothing}
            ${actions.includes("resume")
              ? html`<button ?disabled=${this._busy || !configEntryId} @click=${() => this.call("resume_automatic", localize(this.hass, "confirm_resume"))}><ha-icon icon="mdi:calendar-check"></ha-icon>${localize(this.hass, "resume_automatic")}</button>`
              : nothing}
          </div>
          ${this._ordersOpen ? html`
            <dialog open aria-labelledby="orders-title">
              <div class="dialog-header"><h2 id="orders-title">${localize(this.hass, "irrigation_orders")}</h2><button class="icon-button" aria-label=${localize(this.hass, "close")} @click=${() => { this._ordersOpen = false; }}>×</button></div>
              ${this._busy ? html`<p aria-live="polite">${localize(this.hass, "loading")}</p>` : this._orders.length === 0 ? html`<p>${localize(this.hass, "no_open_orders")}</p>` : html`
                <div class="table" role="table">
                  ${this._orders.map((order) => html`<div class="table-row" role="row"><strong>${String(order.zone)}</strong><span>${translatedValue(this.hass, String(order.source))}</span><span>${this.target(order)}</span><span>${String(order.expected_start)}</span><span>${translatedValue(this.hass, String(order.status))}</span></div>`)}
                </div>`}
            </dialog>` : nothing}
        </div>
      </ha-card>
    `;
  }
}
