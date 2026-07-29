import { LitElement, html, nothing, type TemplateResult } from "lit";

import {
  DOMAIN,
  entity,
  errorMessage,
  formatDuration,
  isAnchor,
  responseData,
  resolveOverviewConfig,
  statusIcon,
  stringAttribute,
  usable,
} from "./helpers";
import { displayState, localize, translatedValue } from "./localize";
import { cardStyles } from "./styles";
import type { HassEntity, HomeAssistant, OverviewCardConfig } from "./types";

export class IrrigationManagerOverviewCard extends LitElement {
  static styles = cardStyles;
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _busy: { state: true },
    _error: { state: true },
    _ordersOpen: { state: true },
    _orders: { state: true },
    _ordersDate: { state: true },
  };

  hass!: HomeAssistant;
  private _config!: OverviewCardConfig;
  private _busy = false;
  private _error?: string;
  private _ordersOpen = false;
  private _orders: Array<Record<string, unknown>> = [];
  private _ordersDate = "";

  static getConfigElement(): HTMLElement {
    return document.createElement("irrigation-manager-overview-card-editor");
  }

  static getStubConfig(): OverviewCardConfig {
    return {
      type: "custom:irrigation-manager-overview-card",
      entity: "",
    };
  }

  setConfig(config: OverviewCardConfig): void {
    this._config = { ...config };
  }

  getCardSize(): number {
    return 5;
  }

  private metric(label: string, state?: HassEntity): TemplateResult {
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
      this._error = `${localize(this.hass, "action_failed")}: ${errorMessage(error)}`;
    } finally {
      this._busy = false;
    }
  }

  private async openOrders(): Promise<void> {
    const config = resolveOverviewConfig(this.hass, this._config);
    const configEntryId = stringAttribute(entity(this.hass, config.status_entity), "config_entry_id");
    if (!configEntryId) return;
    this._ordersDate = this.dateKey(new Date());
    this._ordersOpen = true;
    this._busy = true;
    this._error = undefined;
    try {
      const result = await this.hass.callService(
        DOMAIN,
        "list_card_orders",
        { config_entry_id: configEntryId },
        undefined,
        false,
        true,
      );
      const response = responseData<{ orders?: Array<Record<string, unknown>> }>(result);
      this._orders = response.orders ?? [];
    } catch (error) {
      this._error = `${localize(this.hass, "action_failed")}: ${errorMessage(error)}`;
    } finally {
      this._busy = false;
    }
  }

  private target(order: Record<string, unknown>): string {
    return order.target_type === "volume"
      ? `${String(order.target_value)} ${localize(this.hass, "liters")}`
      : formatDuration(Number(order.target_value));
  }

  private dateKey(value: string | Date): string {
    const date = value instanceof Date ? value : new Date(value);
    const parts = new Intl.DateTimeFormat("en", {
      timeZone: this.hass.config?.time_zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(date);
    const part = (type: Intl.DateTimeFormatPartTypes): string =>
      parts.find((item) => item.type === type)?.value ?? "";
    return `${part("year")}-${part("month")}-${part("day")}`;
  }

  private shiftOrdersDate(days: number): void {
    const date = new Date(`${this._ordersDate}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + days);
    this._ordersDate = date.toISOString().slice(0, 10);
  }

  private formatDate(dateKey: string): string {
    const formatted = new Intl.DateTimeFormat(this.hass.language, {
      timeZone: "UTC",
      weekday: "long",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(`${dateKey}T12:00:00Z`));
    return dateKey === this.dateKey(new Date())
      ? `${localize(this.hass, "today")}, ${formatted}`
      : formatted;
  }

  private formatTime(value: unknown): string {
    return new Intl.DateTimeFormat(this.hass.language, {
      timeZone: this.hass.config?.time_zone,
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(String(value)));
  }

  private ordersForSelectedDate(): Array<Record<string, unknown>> {
    return this._orders
      .filter((order) => this.dateKey(String(order.expected_start)) === this._ordersDate)
      .sort((left, right) =>
        new Date(String(left.expected_start)).getTime() - new Date(String(right.expected_start)).getTime());
  }

  private nextOrdersDate(): string | undefined {
    return this._orders
      .map((order) => this.dateKey(String(order.expected_start)))
      .filter((date) => date > this._ordersDate)
      .sort()[0];
  }

  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    if (!this._config.entity) {
      return html`<ha-card><div class="card"><div class="warning" role="alert"><ha-icon icon="mdi:water-outline"></ha-icon><span>${localize(this.hass, "select_installation")}</span></div></div></ha-card>`;
    }
    if (!isAnchor(entity(this.hass, this._config.entity), "installation")) {
      return html`<ha-card><div class="card"><div class="warning danger" role="alert"><ha-icon icon="mdi:water-alert"></ha-icon><span>${localize(this.hass, "invalid_installation_anchor")}</span></div></div></ha-card>`;
    }
    const config = resolveOverviewConfig(this.hass, this._config);
    if (!config.status_entity || !entity(this.hass, config.status_entity)) {
      return html`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${localize(this.hass, "missing")}</span></div></div></ha-card>`;
    }
    const status = entity(this.hass, config.status_entity);
    const configEntryId = stringAttribute(status, "config_entry_id");
    const statusValue = status?.state ?? "unavailable";
    const meteringFunctional = status?.attributes.volume_control_available === true;
    const title = typeof status?.attributes.card_name === "string"
      ? status.attributes.card_name
      : status?.attributes.friendly_name ?? localize(this.hass, "overview");
    const selectedOrders = this.ordersForSelectedDate();
    const nextOrdersDate = this.nextOrdersDate();

    return html`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${statusIcon(statusValue)}></ha-icon>
              <div>
                <h2>${title}</h2>
                <strong>${usable(status) ? translatedValue(this.hass, status.state) : displayState(this.hass, status)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            <button class="metric metric-button" data-testid="open-orders" ?disabled=${this._busy || !configEntryId} @click=${this.openOrders}><span>${localize(this.hass, "pending")}</span><strong>${displayState(this.hass, entity(this.hass, config.pending_entity))}</strong></button>
            ${this.metric(localize(this.hass, "next_zone"), entity(this.hass, config.next_entity))}
            ${this.metric(localize(this.hass, "expected_start"), entity(this.hass, config.next_start_entity))}
            ${this.metric(localize(this.hass, meteringFunctional ? "water_today" : "runtime_today"), entity(this.hass, meteringFunctional ? config.today_consumption_entity : config.runtime_today_entity))}
            ${this.metric(localize(this.hass, meteringFunctional ? "water_month" : "runtime_month"), entity(this.hass, meteringFunctional ? config.month_consumption_entity : config.runtime_month_entity))}
            ${meteringFunctional ? this.metric(localize(this.hass, "physical_meter"), entity(this.hass, config.physical_meter_entity)) : nothing}
          </div>

          ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
          <div class="actions">
            <button class="danger emergency" data-testid="emergency-stop" ?disabled=${this._busy || !configEntryId} @click=${() => this.call("emergency_stop")}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${localize(this.hass, "emergency")}</button>
          </div>
          ${this._ordersOpen ? html`
            <dialog open aria-labelledby="orders-title">
              <div class="dialog-header"><h2 id="orders-title">${localize(this.hass, "irrigation_orders")}</h2><button class="icon-button" aria-label=${localize(this.hass, "close")} @click=${() => { this._ordersOpen = false; }}>×</button></div>
              <div class="date-navigation">
                <button class="icon-button" aria-label=${localize(this.hass, "previous_day")} @click=${() => this.shiftOrdersDate(-1)}><ha-icon icon="mdi:chevron-left"></ha-icon></button>
                <label class="field"><span>${localize(this.hass, "date")}</span><input data-testid="orders-date" type="date" .value=${this._ordersDate} @change=${(event: Event) => { const input = event.target as HTMLInputElement; this._ordersDate = input.value || this.dateKey(new Date()); input.value = this._ordersDate; }} /></label>
                <button class="icon-button" aria-label=${localize(this.hass, "next_day")} @click=${() => this.shiftOrdersDate(1)}><ha-icon icon="mdi:chevron-right"></ha-icon></button>
              </div>
              <h3 class="selected-date" aria-live="polite">${this.formatDate(this._ordersDate)}</h3>
              ${this._busy ? html`<p aria-live="polite">${localize(this.hass, "loading")}</p>` : this._orders.length === 0 ? html`<p>${localize(this.hass, "no_open_orders")}</p>` : selectedOrders.length === 0 ? html`
                <div class="empty-day"><p>${localize(this.hass, "no_orders_for_day")}</p>${nextOrdersDate ? html`<button data-testid="next-orders-date" @click=${() => { this._ordersDate = nextOrdersDate; }}>${localize(this.hass, "next_orders_on")} ${this.formatDate(nextOrdersDate)}</button>` : nothing}</div>` : html`
                <div class="order-list">
                  ${selectedOrders.map((order) => html`<article><div><strong>${String(order.zone)}</strong><time datetime=${String(order.expected_start)}>${this.formatTime(order.expected_start)}</time></div><span>${translatedValue(this.hass, String(order.source))} · ${this.target(order)} · ${translatedValue(this.hass, String(order.status))}</span></article>`)}
                </div>`}
            </dialog>` : nothing}
        </div>
      </ha-card>
    `;
  }
}
