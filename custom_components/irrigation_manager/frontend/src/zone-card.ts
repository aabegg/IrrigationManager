import { LitElement, html, nothing, type TemplateResult } from "lit";

import {
  DOMAIN,
  MANUAL_REQUEST_SERVICE,
  activeRequestForZone,
  entity,
  progress,
  statusIcon,
  stringAttribute,
  usable,
} from "./helpers";
import { displayState, localize } from "./localize";
import { cardStyles } from "./styles";
import type { HassEntity, HomeAssistant, ZoneCardConfig } from "./types";

const DEFAULT_METRICS = ["balance", "next", "total", "recent", "quality"];
const DEFAULT_ACTIONS = ["create", "start", "pause", "resume", "stop", "stop_skip"];

export class IrrigationManagerZoneCard extends LitElement {
  static styles = cardStyles;
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _targetMode: { state: true },
    _targetValue: { state: true },
    _hardLimit: { state: true },
    _busy: { state: true },
    _error: { state: true },
  };

  hass!: HomeAssistant;
  private _config!: ZoneCardConfig;
  private _targetMode: "duration" | "amount" = "duration";
  private _targetValue = 600;
  private _hardLimit = 3600;
  private _busy = false;
  private _error?: string;

  static getConfigElement(): HTMLElement {
    return document.createElement("irrigation-manager-zone-card-editor");
  }

  static getStubConfig(): ZoneCardConfig {
    return { type: "custom:irrigation-manager-zone-card", zone_entity: "" };
  }

  setConfig(config: ZoneCardConfig): void {
    if (!config.zone_entity) throw new Error("zone_entity is required");
    this._config = { ...config };
  }

  getCardSize(): number {
    return this._config?.display_mode === "compact" ? 4 : 7;
  }

  private metric(key: string, label: string, state?: HassEntity): TemplateResult | typeof nothing {
    if (!(this._config.visible_metrics ?? DEFAULT_METRICS).includes(key)) return nothing;
    return html`<div class="metric"><span>${label}</span><strong>${displayState(this.hass, state)}</strong></div>`;
  }

  private context(): { config_entry_id: string; zone_subentry_id: string } | undefined {
    const zone = entity(this.hass, this._config.zone_entity);
    const configEntryId = stringAttribute(zone, "config_entry_id");
    const zoneSubentryId = stringAttribute(zone, "zone_subentry_id");
    return configEntryId && zoneSubentryId
      ? { config_entry_id: configEntryId, zone_subentry_id: zoneSubentryId }
      : undefined;
  }

  private async perform(service: string, data: Record<string, unknown>, confirmation?: string): Promise<void> {
    if (confirmation && !window.confirm(confirmation)) return;
    this._busy = true;
    this._error = undefined;
    try {
      await this.hass.callService(DOMAIN, service, data);
    } catch (error) {
      this._error = `${localize(this.hass, "action_failed")}: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      this._busy = false;
    }
  }

  private async request(): Promise<void> {
    const context = this.context();
    if (!context) {
      this._error = localize(this.hass, "configuration_error");
      return;
    }
    if (!Number.isFinite(this._targetValue) || this._targetValue <= 0) {
      this._error = localize(this.hass, "invalid_target");
      return;
    }
    if (this._targetMode === "amount" && (!Number.isFinite(this._hardLimit) || this._hardLimit <= 0)) {
      this._error = localize(this.hass, "hard_limit_required");
      return;
    }
    const target = this._targetMode === "duration"
      ? { duration: this._targetValue }
      : { amount: this._targetValue, hard_time_limit: this._hardLimit };
    await this.perform(MANUAL_REQUEST_SERVICE, { ...context, ...target });
  }

  private async requestAction(service: "pause_request" | "resume_request"): Promise<void> {
    const context = this.context();
    const request = entity(this.hass, this._config.request_entity);
    const activeRequest = activeRequestForZone(request, context?.zone_subentry_id);
    if (!context || !activeRequest?.requestId) {
      this._error = localize(this.hass, "configuration_error");
      return;
    }
    await this.perform(service, {
      config_entry_id: context.config_entry_id,
      request_id: activeRequest.requestId,
    });
  }

  private async stop(skip = false): Promise<void> {
    const context = this.context();
    const request = entity(this.hass, this._config.request_entity);
    const activeRequest = activeRequestForZone(request, context?.zone_subentry_id);
    if (!context || !activeRequest) {
      this._error = localize(this.hass, "configuration_error");
      return;
    }
    const target = activeRequest.executionId
      ? { execution_id: activeRequest.executionId }
      : { request_id: activeRequest.requestId };
    await this.perform(
      skip ? "stop_and_skip" : "stop",
      { config_entry_id: context.config_entry_id, ...target },
      localize(this.hass, skip ? "confirm_stop_skip" : "confirm_stop"),
    );
  }

  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    const zone = entity(this.hass, this._config.zone_entity);
    const needed = entity(this.hass, this._config.automation_needed_entity);
    const lock = entity(this.hass, this._config.safety_lock_entity);
    const quality = entity(this.hass, this._config.quality_entity);
    const active = entity(this.hass, this._config.active_zone_entity);
    const request = entity(this.hass, this._config.request_entity);
    const context = this.context();
    const activeRequest = activeRequestForZone(request, context?.zone_subentry_id);
    const percent = progress(active);
    const metrics = this._config.visible_metrics ?? DEFAULT_METRICS;
    const actions = this._config.visible_actions ?? DEFAULT_ACTIONS;
    const title = this._config.name ?? zone?.attributes.friendly_name ?? localize(this.hass, "zone");
    const qualityValue = quality?.state ?? stringAttribute(zone, "measurement_quality");

    return html`
      <ha-card>
        <div class="card ${this._config.display_mode === "compact" ? "compact" : ""}">
          <header>
            <div class="hero">
              <ha-icon .icon=${statusIcon(lock?.state === "on" ? "safety_lock" : needed?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${title}</h2>
                <strong>${lock?.state === "on" ? localize(this.hass, "locked") : needed?.state === "on" ? localize(this.hass, "automation_needed") : needed?.state === "off" ? localize(this.hass, "automation_not_needed") : displayState(this.hass, needed)}</strong>
              </div>
            </div>
          </header>

          ${lock?.state === "on"
            ? html`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span>${localize(this.hass, "safety_lock")}${stringAttribute(lock, "reason") ? `: ${stringAttribute(lock, "reason")}` : ""}</span></div>`
            : nothing}
          ${qualityValue === "estimated"
            ? html`<div class="warning"><ha-icon icon="mdi:calculator-variant-outline"></ha-icon><span>${localize(this.hass, "warning_estimated")}</span></div>`
            : qualityValue === "unknown"
              ? html`<div class="warning"><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${localize(this.hass, "warning_unknown")}</span></div>`
              : nothing}

          ${activeRequest && active && usable(active) && percent !== undefined
            ? html`<section><h3>${localize(this.hass, "progress")}</h3><strong>${displayState(this.hass, active)} · ${Math.round(percent)}%</strong><progress max="100" .value=${percent} aria-label=${localize(this.hass, "progress")}></progress></section>`
            : nothing}

          <div class="metrics">
            ${this.metric("balance", localize(this.hass, "water_balance"), entity(this.hass, this._config.deficit_entity))}
            ${this.metric("balance", localize(this.hass, "target"), entity(this.hass, this._config.target_entity))}
            ${metrics.includes("balance")
              ? this.metric("balance", localize(this.hass, "explanation"), entity(this.hass, this._config.planning_reason_entity))
              : nothing}
            ${this.metric("next", localize(this.hass, "next_window"), entity(this.hass, this._config.next_window_entity))}
            ${this.metric("total", localize(this.hass, "total"), zone)}
            ${this.metric("recent", localize(this.hass, "last_delivered"), entity(this.hass, this._config.last_delivered_entity))}
            ${this.metric("recent", localize(this.hass, "last_duration"), entity(this.hass, this._config.last_duration_entity))}
            ${this.metric("quality", localize(this.hass, "quality"), quality)}
          </div>

          <section class="details">
            <h3>${localize(this.hass, "manual")}</h3>
            <div class="form-grid">
              <label class="field">
                <span>${localize(this.hass, "target")}</span>
                <select .value=${this._targetMode} @change=${(event: Event) => { this._targetMode = (event.target as HTMLSelectElement).value as "duration" | "amount"; }}>
                  <option value="duration">${localize(this.hass, "duration_mode")}</option>
                  <option value="amount">${localize(this.hass, "amount_mode")}</option>
                </select>
              </label>
              <label class="field">
                <span>${this._targetMode === "duration" ? localize(this.hass, "duration") : localize(this.hass, "amount")}</span>
                <input type="number" min="0.001" step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${(event: Event) => { this._targetValue = Number((event.target as HTMLInputElement).value); }} />
                <span>${this._targetMode === "duration" ? localize(this.hass, "seconds") : localize(this.hass, "liters")}</span>
              </label>
              ${this._targetMode === "amount"
                ? html`<label class="field"><span>${localize(this.hass, "hard_limit")}</span><input type="number" min="0.001" max="14400" step="1" .value=${String(this._hardLimit)} @input=${(event: Event) => { this._hardLimit = Number((event.target as HTMLInputElement).value); }} /><span>${localize(this.hass, "seconds")}</span></label>`
                : nothing}
            </div>
          </section>

          ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
          <div class="actions">
            ${actions.includes("create") ? html`<button ?disabled=${this._busy || lock?.state === "on"} @click=${this.request}><ha-icon icon="mdi:playlist-plus"></ha-icon>${localize(this.hass, "create")}</button>` : nothing}
            ${actions.includes("start") ? html`<button class="primary" ?disabled=${this._busy || lock?.state === "on"} @click=${this.request}><ha-icon icon="mdi:play"></ha-icon>${localize(this.hass, "start")}</button>` : nothing}
            ${actions.includes("pause") ? html`<button ?disabled=${this._busy || !activeRequest?.requestId} @click=${() => this.requestAction("pause_request")}><ha-icon icon="mdi:pause"></ha-icon>${localize(this.hass, "pause")}</button>` : nothing}
            ${actions.includes("resume") ? html`<button ?disabled=${this._busy || !activeRequest?.requestId} @click=${() => this.requestAction("resume_request")}><ha-icon icon="mdi:play-pause"></ha-icon>${localize(this.hass, "resume")}</button>` : nothing}
            ${actions.includes("stop") ? html`<button class="danger" ?disabled=${this._busy || !activeRequest} @click=${() => this.stop()}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${localize(this.hass, "stop")}</button>` : nothing}
            ${actions.includes("stop_skip") ? html`<button class="danger" ?disabled=${this._busy || !activeRequest} @click=${() => this.stop(true)}><ha-icon icon="mdi:skip-next-circle-outline"></ha-icon>${localize(this.hass, "stop_skip")}</button>` : nothing}
          </div>
        </div>
      </ha-card>
    `;
  }
}
