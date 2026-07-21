import { LitElement, html, nothing, type TemplateResult } from "lit";

import { DOMAIN, entity, progress, statusIcon, stringAttribute, usable } from "./helpers";
import { displayState, localize, translatedValue } from "./localize";
import { cardStyles } from "./styles";
import type { HassEntity, HomeAssistant, OverviewCardConfig } from "./types";

const DEFAULT_METRICS = ["active", "pending", "next", "today", "month", "quality"];
const DEFAULT_ACTIONS = ["stop", "emergency"];

export class IrrigationManagerOverviewCard extends LitElement {
  static styles = cardStyles;
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _busy: { state: true },
    _error: { state: true },
  };

  hass!: HomeAssistant;
  private _config!: OverviewCardConfig;
  private _busy = false;
  private _error?: string;

  static getConfigElement(): HTMLElement {
    return document.createElement("irrigation-manager-overview-card-editor");
  }

  static getStubConfig(): OverviewCardConfig {
    return { type: "custom:irrigation-manager-overview-card", status_entity: "" };
  }

  setConfig(config: OverviewCardConfig): void {
    if (!config.status_entity) throw new Error("status_entity is required");
    this._config = { ...config };
  }

  getCardSize(): number {
    return this._config?.display_mode === "compact" ? 3 : 5;
  }

  private metric(key: string, label: string, state?: HassEntity): TemplateResult | typeof nothing {
    if (!(this._config.visible_metrics ?? DEFAULT_METRICS).includes(key)) return nothing;
    return html`<div class="metric"><span>${label}</span><strong>${displayState(this.hass, state)}</strong></div>`;
  }

  private async call(service: "stop" | "emergency_stop", confirmation: string): Promise<void> {
    if (!window.confirm(confirmation)) return;
    const status = entity(this.hass, this._config.status_entity);
    const configEntryId = stringAttribute(status, "config_entry_id");
    if (!configEntryId) {
      this._error = localize(this.hass, "configuration_error");
      return;
    }
    this._busy = true;
    this._error = undefined;
    try {
      await this.hass.callService(DOMAIN, service, { config_entry_id: configEntryId });
    } catch (error) {
      this._error = `${localize(this.hass, "action_failed")}: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      this._busy = false;
    }
  }

  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    const status = entity(this.hass, this._config.status_entity);
    const emergency = entity(this.hass, this._config.emergency_entity);
    const lock = entity(this.hass, this._config.lock_entity);
    const active = entity(this.hass, this._config.active_zone_entity);
    const percent = progress(active);
    const actions = this._config.visible_actions ?? DEFAULT_ACTIONS;
    const statusValue = status?.state ?? "unavailable";
    const locked = emergency?.state === "on" || lock?.state === "on";

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

          ${(this._config.visible_metrics ?? DEFAULT_METRICS).includes("active") && active
            ? html`
                <section>
                  <h3>${localize(this.hass, "active_zone")}</h3>
                  <strong>${displayState(this.hass, active)}</strong>
                  ${this._config.dose_entity
                    ? html`<div class="secondary">${localize(this.hass, "dose")}: ${displayState(this.hass, entity(this.hass, this._config.dose_entity))}</div>`
                    : nothing}
                  ${percent === undefined
                    ? nothing
                    : html`<div class="secondary">${localize(this.hass, "progress")}: ${Math.round(percent)}%</div><progress max="100" .value=${percent} aria-label=${localize(this.hass, "progress")}></progress>`}
                </section>
              `
            : nothing}

          <div class="metrics details">
            ${this.metric("pending", localize(this.hass, "pending"), entity(this.hass, this._config.pending_entity))}
            ${this.metric("next", localize(this.hass, "next"), entity(this.hass, this._config.next_entity))}
            ${this.metric("today", localize(this.hass, "today"), entity(this.hass, this._config.today_consumption_entity))}
            ${this.metric("month", localize(this.hass, "month"), entity(this.hass, this._config.month_consumption_entity))}
            ${this.metric("quality", localize(this.hass, "model_quality"), entity(this.hass, this._config.model_quality_entity))}
          </div>

          ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
          <div class="actions">
            ${actions.includes("stop")
              ? html`<button class="danger" ?disabled=${this._busy || !usable(status)} @click=${() => this.call("stop", localize(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${localize(this.hass, "stop")}</button>`
              : nothing}
            ${actions.includes("emergency")
              ? html`<button class="danger" ?disabled=${this._busy} @click=${() => this.call("emergency_stop", localize(this.hass, "confirm_emergency"))}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${localize(this.hass, "emergency")}</button>`
              : nothing}
          </div>
        </div>
      </ha-card>
    `;
  }
}
