import { LitElement, html, nothing, type TemplateResult } from "lit";

import {
  DOMAIN,
  entity,
  isAnchor,
  numberAttribute,
  resolveZoneConfig,
  statusIcon,
  stringAttribute,
} from "./helpers";
import { displayState, localize, translatedValue } from "./localize";
import { cardStyles } from "./styles";
import type { HassEntity, HomeAssistant, ZoneCardConfig } from "./types";

function translatedHistory(hass: HomeAssistant, value: unknown): string {
  return value == null ? "–" : translatedValue(hass, String(value));
}

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
    _manualOpen: { state: true },
    _historyOpen: { state: true },
    _conflictPolicy: { state: true },
    _history: { state: true },
    _historyOffset: { state: true },
    _historyTotal: { state: true },
    _historySource: { state: true },
    _historyResult: { state: true },
  };

  hass!: HomeAssistant;
  private _config!: ZoneCardConfig;
  private _targetMode: "duration" | "amount" = "duration";
  private _targetValue = 600;
  private _hardLimit = 3600;
  private _busy = false;
  private _error?: string;
  private _manualOpen = false;
  private _historyOpen = false;
  private _conflictPolicy: "start_now" | "stop_active" | "priority_next" = "start_now";
  private _history: Array<Record<string, unknown>> = [];
  private _historyOffset = 0;
  private _historyTotal = 0;
  private _historySource = "";
  private _historyResult = "";

  static getConfigElement(): HTMLElement {
    return document.createElement("irrigation-manager-zone-card-editor");
  }

  static getStubConfig(): ZoneCardConfig {
    return {
      type: "custom:irrigation-manager-zone-card",
      entity: "",
    };
  }

  setConfig(config: ZoneCardConfig): void {
    this._config = { ...config };
  }

  getCardSize(): number {
    return 6;
  }

  private metric(label: string, state?: HassEntity): TemplateResult {
    return html`<div class="metric"><span>${label}</span><strong>${displayState(this.hass, state)}</strong></div>`;
  }

  private context(): { config_entry_id: string; zone_subentry_id: string } | undefined {
    const config = resolveZoneConfig(this.hass, this._config);
    const zone = entity(this.hass, config.zone_entity);
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
    const anchor = entity(this.hass, resolveZoneConfig(this.hass, this._config).zone_entity);
    const maximum = this._targetMode === "duration"
      ? numberAttribute(anchor, "max_manual_duration_seconds")
      : numberAttribute(anchor, "max_manual_volume_runtime_seconds");
    const runtime = this._targetMode === "duration" ? this._targetValue : this._hardLimit;
    if (maximum !== undefined && runtime > maximum) {
      this._error = localize(this.hass, "invalid_target");
      return;
    }
    const target = this._targetMode === "duration"
      ? { duration: this._targetValue }
      : { amount: this._targetValue, hard_time_limit: this._hardLimit };
    const activeExecution = anchor?.attributes.active_execution === true;
    await this.perform("start_manual_from_card", {
      ...context,
      ...target,
      conflict_policy: activeExecution ? this._conflictPolicy : "start_now",
    });
    if (!this._error) this._manualOpen = false;
  }

  private openManual(anchor: HassEntity | undefined): void {
    this._conflictPolicy = anchor?.attributes.active_execution === true
      ? "stop_active"
      : "start_now";
    this._manualOpen = true;
    this._error = undefined;
  }

  private async loadHistory(offset = 0): Promise<void> {
    const context = this.context();
    if (!context) return;
    this._historyOpen = true;
    this._busy = true;
    this._error = undefined;
    try {
      const filters: Record<string, unknown> = { ...context, offset, limit: 20 };
      if (this._historySource) filters.source = this._historySource;
      if (this._historyResult) filters.result = this._historyResult;
      const response = await this.hass.callService(
        DOMAIN,
        "list_zone_history",
        filters,
        undefined,
        true,
      ) as { items?: Array<Record<string, unknown>>; offset?: number; total?: number };
      this._history = response.items ?? [];
      this._historyOffset = response.offset ?? offset;
      this._historyTotal = response.total ?? 0;
    } catch (error) {
      this._error = `${localize(this.hass, "action_failed")}: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      this._busy = false;
    }
  }

  private historyTarget(item: Record<string, unknown>): string {
    return `${String(item.target_value)} ${item.target_type === "volume" ? localize(this.hass, "liters") : localize(this.hass, "seconds")}`;
  }

  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    if (!this._config.entity) {
      return html`<ha-card><div class="card"><div class="warning" role="alert"><ha-icon icon="mdi:water-outline"></ha-icon><span>${localize(this.hass, "select_zone")}</span></div></div></ha-card>`;
    }
    if (!isAnchor(entity(this.hass, this._config.entity), "zone")) {
      return html`<ha-card><div class="card"><div class="warning danger" role="alert"><ha-icon icon="mdi:water-alert"></ha-icon><span>${localize(this.hass, "invalid_zone_anchor")}</span></div></div></ha-card>`;
    }
    const config = resolveZoneConfig(this.hass, this._config);
    if (!config.zone_entity || !entity(this.hass, config.zone_entity)) {
      return html`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${localize(this.hass, "missing")}</span></div></div></ha-card>`;
    }
    const zone = entity(this.hass, config.zone_entity);
    const zoneStatus = entity(this.hass, config.status_entity);
    const context = this.context();
    const title = typeof zone?.attributes.card_name === "string"
      ? zone.attributes.card_name
      : zone?.attributes.friendly_name ?? localize(this.hass, "zone");
    const manualBlocked = ["disabled", "installation_disabled", "safety_lock", "needs_reconfiguration"].includes(
      zoneStatus?.state ?? "",
    );
    const maxDuration = numberAttribute(zone, "max_manual_duration_seconds") ?? 604800;
    const maxVolumeRuntime = numberAttribute(zone, "max_manual_volume_runtime_seconds") ?? 604800;

    return html`
      <ha-card>
        <div class="card">
          <header>
            <div class="hero">
              <ha-icon .icon=${statusIcon(zoneStatus?.state ?? "unknown")}></ha-icon>
              <div>
                <h2>${title}</h2>
                <strong>${displayState(this.hass, zoneStatus)}</strong>
              </div>
            </div>
          </header>

          <div class="metrics">
            ${this.metric(localize(this.hass, "status"), zoneStatus)}
            ${this.metric(localize(this.hass, zone?.attributes.volume_control_available === true ? "water_today" : "runtime_today"), entity(this.hass, zone?.attributes.volume_control_available === true ? config.water_today_entity : config.runtime_today_entity))}
            ${this.metric(localize(this.hass, zone?.attributes.volume_control_available === true ? "water_month" : "runtime_month"), entity(this.hass, zone?.attributes.volume_control_available === true ? config.water_month_entity : config.runtime_month_entity))}
            ${this.metric(localize(this.hass, "next"), entity(this.hass, config.next_irrigation_entity))}
          </div>

          ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
          <div class="actions">
            <button class="primary" data-testid="manual-irrigation" ?disabled=${this._busy || manualBlocked || !context} @click=${() => this.openManual(zone)}><ha-icon icon="mdi:sprinkler-variant"></ha-icon>${localize(this.hass, "manual_water")}</button>
            <button data-testid="show-history" ?disabled=${this._busy || !context} @click=${() => this.loadHistory(0)}><ha-icon icon="mdi:history"></ha-icon>${localize(this.hass, "show_history")}</button>
          </div>
          ${this._manualOpen ? html`
            <dialog open aria-labelledby="manual-title">
              <div class="dialog-header"><h2 id="manual-title">${localize(this.hass, "manual_water")}</h2><button class="icon-button" aria-label=${localize(this.hass, "close")} @click=${() => { this._manualOpen = false; }}>×</button></div>
              <div class="form-grid">
                <label class="field"><span>${localize(this.hass, "target")}</span><select data-testid="target-mode" .value=${this._targetMode} @change=${(event: Event) => { this._targetMode = (event.target as HTMLSelectElement).value as "duration" | "amount"; }}><option value="duration">${localize(this.hass, "duration_mode")}</option>${zone?.attributes.volume_control_available === true ? html`<option value="amount">${localize(this.hass, "amount_mode")}</option>` : nothing}</select></label>
                <label class="field"><span>${this._targetMode === "duration" ? localize(this.hass, "duration") : localize(this.hass, "amount")}</span><input data-testid="manual-target" type="number" min="0.001" max=${this._targetMode === "duration" ? String(maxDuration) : "1000000"} step=${this._targetMode === "duration" ? "1" : "0.1"} .value=${String(this._targetValue)} @input=${(event: Event) => { this._targetValue = Number((event.target as HTMLInputElement).value); }} /><span>${this._targetMode === "duration" ? localize(this.hass, "seconds") : localize(this.hass, "liters")}</span></label>
                ${this._targetMode === "amount" ? html`<label class="field"><span>${localize(this.hass, "hard_limit")}</span><input data-testid="hard-limit" type="number" min="0.001" max=${String(maxVolumeRuntime)} step="1" .value=${String(this._hardLimit)} @input=${(event: Event) => { this._hardLimit = Number((event.target as HTMLInputElement).value); }} /><span>${localize(this.hass, "seconds")}</span></label>` : nothing}
                ${zone?.attributes.active_execution === true ? html`<label class="field"><span>${localize(this.hass, "active_execution_choice")}</span><select data-testid="conflict-policy" .value=${this._conflictPolicy} @change=${(event: Event) => { this._conflictPolicy = (event.target as HTMLSelectElement).value as "stop_active" | "priority_next"; }}><option value="stop_active">${localize(this.hass, "stop_active_start_now")}</option><option value="priority_next">${localize(this.hass, "finish_then_priority")}</option></select></label>` : nothing}
              </div>
              ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
              <div class="actions dialog-actions"><button data-testid="submit-manual" class="primary" ?disabled=${this._busy} @click=${this.request}>${localize(this.hass, "start")}</button></div>
            </dialog>` : nothing}
          ${this._historyOpen ? html`
            <dialog open aria-labelledby="history-title">
              <div class="dialog-header"><h2 id="history-title">${localize(this.hass, "irrigation_history")}</h2><button class="icon-button" aria-label=${localize(this.hass, "close")} @click=${() => { this._historyOpen = false; }}>×</button></div>
              <div class="filters"><label class="field"><span>${localize(this.hass, "source")}</span><select .value=${this._historySource} @change=${(event: Event) => { this._historySource = (event.target as HTMLSelectElement).value; void this.loadHistory(0); }}><option value="">${localize(this.hass, "all")}</option><option value="manual">${localize(this.hass, "manual")}</option><option value="automatic">${localize(this.hass, "automatic")}</option></select></label><label class="field"><span>${localize(this.hass, "result")}</span><select .value=${this._historyResult} @change=${(event: Event) => { this._historyResult = (event.target as HTMLSelectElement).value; void this.loadHistory(0); }}><option value="">${localize(this.hass, "all")}</option><option value="completed">${localize(this.hass, "completed")}</option><option value="failed">${localize(this.hass, "failed")}</option><option value="cancelled">${localize(this.hass, "cancelled")}</option></select></label></div>
              ${this._busy ? html`<p aria-live="polite">${localize(this.hass, "loading")}</p>` : html`<div class="history-list">${this._history.map((item) => html`<article><strong>${this.historyTarget(item)}</strong><span>${String(item.started_at)} – ${String(item.ended_at ?? "")}</span><span>${translatedHistory(this.hass, item.source)} · ${translatedHistory(this.hass, item.result)} · ${String(item.actual_duration)} s${item.actual_water == null ? "" : ` · ${String(item.actual_water)} L`} · ${translatedHistory(this.hass, item.completion_reason)}</span></article>`)}</div>`}
              <div class="actions"><button ?disabled=${this._busy || this._historyOffset === 0} @click=${() => this.loadHistory(Math.max(0, this._historyOffset - 20))}>${localize(this.hass, "previous")}</button><span>${this._historyTotal === 0 ? 0 : this._historyOffset + 1}–${Math.min(this._historyOffset + this._history.length, this._historyTotal)} / ${this._historyTotal}</span><button ?disabled=${this._busy || this._historyOffset + this._history.length >= this._historyTotal} @click=${() => this.loadHistory(this._historyOffset + 20)}>${localize(this.hass, "next_page")}</button></div>
            </dialog>` : nothing}
        </div>
      </ha-card>
    `;
  }
}
