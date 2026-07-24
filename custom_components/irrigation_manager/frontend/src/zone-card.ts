import { LitElement, html, nothing, type TemplateResult } from "lit";

import {
  DOMAIN,
  activeRequestForZone,
  entity,
  numberAttribute,
  progress,
  resolveZoneConfig,
  statusIcon,
  stringAttribute,
  usable,
} from "./helpers";
import { displayState, localize, translatedValue } from "./localize";
import { cardStyles } from "./styles";
import type { HassEntity, HomeAssistant, ZoneCardConfig } from "./types";

const DEFAULT_METRICS = ["status", "today", "month", "next"];
const DEFAULT_ACTIONS: string[] = [];

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
      configuration_mode: "simple",
      zone: "",
    };
  }

  setConfig(config: ZoneCardConfig): void {
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

  private async requestAction(service: "pause_request" | "resume_request"): Promise<void> {
    const context = this.context();
    const request = entity(this.hass, resolveZoneConfig(this.hass, this._config).request_entity);
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
    const request = entity(this.hass, resolveZoneConfig(this.hass, this._config).request_entity);
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

  private lockTimestamp(lock: HassEntity): string | undefined {
    const value = stringAttribute(lock, "occurred_at") ?? lock.last_changed;
    if (!value) return undefined;
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat(this.hass.language, {
          dateStyle: "medium",
          timeStyle: "medium",
        }).format(date);
  }

  private lockReason(lock: HassEntity): string | undefined {
    const reason = stringAttribute(lock, "reason");
    if (!reason) return undefined;
    const patterns: Array<[string, "unexpectedly_opened" | "unexpectedly_opened_during_startup" | "unexpectedly_closed"]> = [
      [" opened unexpectedly during startup", "unexpectedly_opened_during_startup"],
      [" opened unexpectedly", "unexpectedly_opened"],
      [" closed unexpectedly during irrigation", "unexpectedly_closed"],
    ];
    for (const [suffix, message] of patterns) {
      if (!reason.endsWith(suffix)) continue;
      const entityId = reason.slice(0, -suffix.length);
      const friendlyName = entity(this.hass, entityId)?.attributes.friendly_name;
      const actuator = typeof friendlyName === "string" && friendlyName
        ? `${friendlyName} (${entityId})`
        : entityId;
      return `${actuator} ${localize(this.hass, message)}`;
    }
    return reason;
  }

  private async resetSafety(
    context: { config_entry_id: string; zone_subentry_id: string },
    zoneLock: HassEntity | undefined,
  ): Promise<void> {
    await this.perform(
      zoneLock?.state === "on" ? "reset_zone_safety" : "reset_installation_safety",
      zoneLock?.state === "on" ? context : { config_entry_id: context.config_entry_id },
      localize(this.hass, "confirm_reset_safety"),
    );
  }

  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    const config = resolveZoneConfig(this.hass, this._config);
    if (!config.zone_entity || !entity(this.hass, config.zone_entity)) {
      return html`<ha-card><div class="card"><div class="warning"><ha-icon icon="mdi:water-alert"></ha-icon><span>${localize(this.hass, "missing")}</span></div></div></ha-card>`;
    }
    const zone = entity(this.hass, config.zone_entity);
    const needed = entity(this.hass, config.automation_needed_entity);
    const zoneLock = entity(this.hass, config.safety_lock_entity);
    const installationLock = entity(this.hass, config.installation_safety_lock_entity);
    const lock = zoneLock?.state === "on" ? zoneLock : installationLock?.state === "on" ? installationLock : undefined;
    const quality = entity(this.hass, config.quality_entity);
    const zoneStatus = entity(this.hass, config.status_entity);
    const release = entity(this.hass, config.automation_release_entity);
    const archived = entity(this.hass, config.archived_entity);
    const deviation = entity(this.hass, config.flow_deviation_entity);
    const active = entity(this.hass, config.active_zone_entity);
    const request = entity(this.hass, config.request_entity);
    const context = this.context();
    const activeRequest = activeRequestForZone(request, context?.zone_subentry_id);
    const percent = progress(active);
    const metrics = this._config.visible_metrics ?? DEFAULT_METRICS;
    const actions = this._config.visible_actions ?? DEFAULT_ACTIONS;
    const title = this._config.name ?? zone?.attributes.friendly_name ?? localize(this.hass, "zone");
    const qualityValue = quality?.state ?? stringAttribute(zone, "measurement_quality");
    const displayedZoneStatus = lock && zoneStatus
      ? { ...zoneStatus, state: "safety_lock" }
      : zoneStatus;
    const manualBlocked = lock?.state === "on"
      || ["disabled", "installation_disabled", "safety_lock", "needs_reconfiguration"].includes(
        displayedZoneStatus?.state ?? "",
      );
    const lockReason = lock ? this.lockReason(lock) : undefined;
    const lockTimestamp = lock ? this.lockTimestamp(lock) : undefined;
    const maxDuration = numberAttribute(zone, "max_manual_duration_seconds") ?? 604800;
    const maxVolumeRuntime = numberAttribute(zone, "max_manual_volume_runtime_seconds") ?? 604800;
    const lockScope = zoneLock?.state === "on" ? "zone_safety_lock" : "installation_safety_lock";

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

          ${lock
            ? html`<div class="warning danger"><ha-icon icon="mdi:lock-alert-outline"></ha-icon><span><strong>${localize(this.hass, lockScope)}</strong>${lockReason ? html`<br />${localize(this.hass, "lock_reason")}: ${lockReason}` : nothing}${lockTimestamp ? html`<br />${localize(this.hass, "lock_occurred_at")}: ${lockTimestamp}` : nothing}</span></div>`
            : nothing}
          ${qualityValue === "estimated"
            ? html`<div class="warning"><ha-icon icon="mdi:calculator-variant-outline"></ha-icon><span>${localize(this.hass, "warning_estimated")}</span></div>`
            : qualityValue === "unknown"
              ? html`<div class="warning"><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${localize(this.hass, "warning_unknown")}</span></div>`
              : nothing}
          ${release?.state === "off" && stringAttribute(release, "suspended_until")
            ? html`<div class="warning"><ha-icon icon="mdi:calendar-clock"></ha-icon><span>${localize(this.hass, "automatic_suspended")}: ${stringAttribute(release, "suspended_until")}</span></div>`
            : nothing}
          ${archived?.state === "on"
            ? html`<div class="warning"><ha-icon icon="mdi:archive-outline"></ha-icon><span>${localize(this.hass, "archived")}</span></div>`
            : nothing}
          ${deviation && usable(deviation) && Math.abs(Number(deviation.state)) >= 20
            ? html`<div class="warning"><ha-icon icon="mdi:waves-arrow-up"></ha-icon><span>${localize(this.hass, "flow_warning")}: ${displayState(this.hass, deviation)}</span></div>`
            : nothing}

          ${activeRequest && active && usable(active) && percent !== undefined
            ? html`<section><h3>${localize(this.hass, "progress")}</h3><strong>${displayState(this.hass, active)} · ${Math.round(percent)}%</strong><progress max="100" .value=${percent} aria-label=${localize(this.hass, "progress")}></progress></section>`
            : nothing}

          <div class="metrics">
            ${this.metric("status", localize(this.hass, "status"), displayedZoneStatus)}
            ${this.metric("today", localize(this.hass, zone?.attributes.volume_control_available === true ? "water_today" : "runtime_today"), entity(this.hass, zone?.attributes.volume_control_available === true ? config.water_today_entity : config.runtime_today_entity))}
            ${this.metric("month", localize(this.hass, zone?.attributes.volume_control_available === true ? "water_month" : "runtime_month"), entity(this.hass, zone?.attributes.volume_control_available === true ? config.water_month_entity : config.runtime_month_entity))}
            ${this.metric("next", localize(this.hass, "next"), entity(this.hass, config.next_irrigation_entity ?? config.next_window_entity))}
            ${this.metric("balance", localize(this.hass, "water_balance"), entity(this.hass, config.deficit_entity))}
            ${this.metric("balance", localize(this.hass, "target"), entity(this.hass, config.target_entity))}
            ${metrics.includes("balance")
              ? this.metric("balance", localize(this.hass, "explanation"), entity(this.hass, config.planning_reason_entity))
              : nothing}
            ${this.metric("total", localize(this.hass, "total"), zone)}
            ${this.metric("recent", localize(this.hass, "last_delivered"), entity(this.hass, config.last_delivered_entity))}
            ${this.metric("recent", localize(this.hass, "last_duration"), entity(this.hass, config.last_duration_entity))}
            ${this.metric("quality", localize(this.hass, "quality"), quality)}
            ${this.metric("calculation", localize(this.hass, "coverage"), entity(this.hass, config.coverage_entity))}
            ${config.calculation_entity
              ? this.metric("calculation", localize(this.hass, "explanation"), entity(this.hass, config.calculation_entity))
              : nothing}
            ${this.metric("flow", localize(this.hass, "expected_flow"), entity(this.hass, config.expected_flow_entity))}
            ${this.metric("flow", localize(this.hass, "actual_flow"), entity(this.hass, config.actual_flow_entity))}
            ${this.metric("flow", localize(this.hass, "flow_deviation"), deviation)}
          </div>
          ${metrics.includes("history") && Array.isArray(zone?.attributes.recent_history)
            ? html`<section class="details"><h3>${localize(this.hass, "history")}</h3>${(zone.attributes.recent_history as Array<Record<string, unknown>>).slice(-3).reverse().map((item) => html`<div class="secondary">${String(item.ended_at ?? item.created_at ?? "")} · ${String(item.result ?? item.status ?? "")}</div>`)}</section>`
            : nothing}

          ${this._error ? html`<div class="error" role="alert">${this._error}</div>` : nothing}
          <div class="actions">
            <button class="primary" data-testid="manual-irrigation" ?disabled=${this._busy || manualBlocked || !context} @click=${() => this.openManual(zone)}><ha-icon icon="mdi:sprinkler-variant"></ha-icon>${localize(this.hass, "manual_water")}</button>
            <button data-testid="show-history" ?disabled=${this._busy || !context} @click=${() => this.loadHistory(0)}><ha-icon icon="mdi:history"></ha-icon>${localize(this.hass, "show_history")}</button>
            ${actions.includes("pause") ? html`<button ?disabled=${this._busy || !activeRequest?.requestId} @click=${() => this.requestAction("pause_request")}><ha-icon icon="mdi:pause"></ha-icon>${localize(this.hass, "pause")}</button>` : nothing}
            ${actions.includes("resume") ? html`<button ?disabled=${this._busy || !activeRequest?.requestId} @click=${() => this.requestAction("resume_request")}><ha-icon icon="mdi:play-pause"></ha-icon>${localize(this.hass, "resume")}</button>` : nothing}
            ${actions.includes("stop") ? html`<button class="danger" ?disabled=${this._busy || !activeRequest} @click=${() => this.stop()}><ha-icon icon="mdi:stop-circle-outline"></ha-icon>${localize(this.hass, "stop")}</button>` : nothing}
            ${actions.includes("stop_skip") ? html`<button class="danger" ?disabled=${this._busy || !activeRequest} @click=${() => this.stop(true)}><ha-icon icon="mdi:skip-next-circle-outline"></ha-icon>${localize(this.hass, "stop_skip")}</button>` : nothing}
            ${actions.includes("suspend") ? html`<button ?disabled=${this._busy || !context || archived?.state === "on"} @click=${() => context && this.perform("suspend_automatic", { ...context, until: new Date(Date.now() + 86400000).toISOString() })}><ha-icon icon="mdi:calendar-clock"></ha-icon>${localize(this.hass, "suspend_24h")}</button>` : nothing}
            ${actions.includes("resume_auto") ? html`<button ?disabled=${this._busy || !context} @click=${() => context && this.perform("resume_automatic", context)}><ha-icon icon="mdi:calendar-check"></ha-icon>${localize(this.hass, "resume_automatic")}</button>` : nothing}
            ${lock ? html`<button data-testid="reset-safety" class="danger" ?disabled=${this._busy || !context} @click=${() => context && this.resetSafety(context, zoneLock)}><ha-icon icon="mdi:lock-open-alert-outline"></ha-icon>${localize(this.hass, "reset_safety")}</button>` : nothing}
            ${actions.includes("archive") ? html`<button ?disabled=${this._busy || !context || archived?.state === "on"} @click=${() => context && this.perform("archive_zone", context, localize(this.hass, "confirm_archive"))}><ha-icon icon="mdi:archive-arrow-down-outline"></ha-icon>${localize(this.hass, "archive")}</button>` : nothing}
            ${actions.includes("restore") ? html`<button ?disabled=${this._busy || !context || archived?.state !== "on"} @click=${() => context && this.perform("restore_zone", context)}><ha-icon icon="mdi:archive-arrow-up-outline"></ha-icon>${localize(this.hass, "restore")}</button>` : nothing}
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
