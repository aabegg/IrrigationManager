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

const DEFAULT_METRICS = ["active", "pending", "next", "today", "month", "quality", "maintenance"];
const DEFAULT_ACTIONS = ["stop", "emergency", "suspend", "resume"];

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

  private async call(service: string, confirmation: string, extra: Record<string, unknown> = {}): Promise<void> {
    if (!window.confirm(confirmation)) return;
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
            ${this.metric("pending", localize(this.hass, "pending"), entity(this.hass, config.pending_entity))}
            ${this.metric("next", localize(this.hass, "next"), entity(this.hass, config.next_entity))}
            ${this.metric("today", localize(this.hass, "today"), entity(this.hass, config.today_consumption_entity))}
            ${this.metric("month", localize(this.hass, "month"), entity(this.hass, config.month_consumption_entity))}
            ${this.metric("quality", localize(this.hass, "model_quality"), entity(this.hass, config.model_quality_entity))}
            ${this.metric("maintenance", localize(this.hass, "maintenance_due"), entity(this.hass, config.maintenance_due_entity))}
          </div>

          ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
          <div class="actions">
            ${actions.includes("stop")
              ? html`<button class="danger" ?disabled=${this._busy || !usable(status) || !configEntryId} @click=${() => this.call("stop", localize(this.hass, "confirm_stop"))}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${localize(this.hass, "stop")}</button>`
              : nothing}
            ${actions.includes("emergency")
              ? html`<button class="danger" ?disabled=${this._busy || !configEntryId} @click=${() => this.call("emergency_stop", localize(this.hass, "confirm_emergency"))}><ha-icon icon="mdi:alert-octagon-outline"></ha-icon>${localize(this.hass, "emergency")}</button>`
              : nothing}
            ${actions.includes("suspend")
              ? html`<button ?disabled=${this._busy || !configEntryId} @click=${() => this.call("suspend_automatic", localize(this.hass, "confirm_suspend"), { until: new Date(Date.now() + 86400000).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${localize(this.hass, "suspend_24h")}</button>`
              : nothing}
            ${actions.includes("resume")
              ? html`<button ?disabled=${this._busy || !configEntryId} @click=${() => this.call("resume_automatic", localize(this.hass, "confirm_resume"))}><ha-icon icon="mdi:calendar-check"></ha-icon>${localize(this.hass, "resume_automatic")}</button>`
              : nothing}
          </div>
        </div>
      </ha-card>
    `;
  }
}
