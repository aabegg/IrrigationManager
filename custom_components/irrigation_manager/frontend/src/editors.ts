import { LitElement, html, nothing, type TemplateResult } from "lit";

import { anchorChoices, fireConfigChanged, inferConfigurationMode } from "./helpers";
import { localize } from "./localize";
import { editorStyles } from "./styles";
import type { HomeAssistant, OverviewCardConfig, ZoneCardConfig } from "./types";

type CardConfig = OverviewCardConfig | ZoneCardConfig;

const overviewFields = [
  ["status_entity", "Installation status"],
  ["emergency_entity", "Emergency stop"],
  ["lock_entity", "Installation safety lock"],
  ["active_zone_entity", "Active zone / progress"],
  ["dose_entity", "Current dose"],
  ["pending_entity", "Open requests"],
  ["next_entity", "Next irrigation"],
  ["next_start_entity", "Expected start"],
  ["today_consumption_entity", "Today's consumption"],
  ["month_consumption_entity", "Monthly consumption"],
  ["runtime_today_entity", "Runtime today"],
  ["runtime_month_entity", "Runtime this month"],
  ["physical_meter_entity", "Corrected meter total"],
  ["model_quality_entity", "Model quality"],
  ["winter_entity", "Winter lock"],
  ["maintenance_entity", "Maintenance mode"],
  ["automation_release_entity", "Automatic release"],
  ["maintenance_due_entity", "Maintenance due"],
] as const;

const zoneFields = [
  ["zone_entity", "Zone total / action identity"],
  ["automation_needed_entity", "Automatic demand"],
  ["safety_lock_entity", "Zone safety lock"],
  ["installation_safety_lock_entity", "Installation safety lock"],
  ["deficit_entity", "Water deficit"],
  ["target_entity", "Automatic target"],
  ["planning_reason_entity", "Planning explanation"],
  ["next_window_entity", "Next watering window"],
  ["active_zone_entity", "Active zone / progress"],
  ["request_entity", "Current request / dose"],
  ["last_delivered_entity", "Last delivered amount"],
  ["last_duration_entity", "Last duration"],
  ["quality_entity", "Measurement quality"],
  ["status_entity", "Zone status"],
  ["automation_release_entity", "Automatic release"],
  ["archived_entity", "Archived"],
  ["coverage_entity", "Demand coverage"],
  ["expected_flow_entity", "Expected flow"],
  ["actual_flow_entity", "Actual flow"],
  ["flow_deviation_entity", "Flow deviation"],
  ["calculation_entity", "Calculation"],
  ["water_today_entity", "Measured water today"],
  ["water_month_entity", "Measured water this month"],
  ["runtime_today_entity", "Runtime today"],
  ["runtime_month_entity", "Runtime this month"],
  ["next_irrigation_entity", "Next irrigation"],
] as const;

const overviewEntityFields = overviewFields.map(([key]) => key);
const zoneEntityFields = zoneFields.map(([key]) => key);

const germanLabels: Record<string, string> = {
  "Installation status": "Anlagenzustand",
  "Emergency stop": "Not-Aus",
  "Installation safety lock": "Sicherheitssperre der Anlage",
  "Active zone / progress": "Aktive Zone / Fortschritt",
  "Current dose": "Aktuelle Teilgabe",
  "Open requests": "Offene Aufträge",
  "Next irrigation": "Nächste Bewässerung",
  "Today's consumption": "Heutiger Verbrauch",
  "Monthly consumption": "Monatsverbrauch",
  "Model quality": "Modellqualität",
  "Zone total / action identity": "Zonenverbrauch / Aktionskennung",
  "Automatic demand": "Automatischer Bedarf",
  "Zone safety lock": "Sicherheitssperre der Zone",
  "Water deficit": "Wasserdefizit",
  "Automatic target": "Automatisches Ziel",
  "Planning explanation": "Planungsbegründung",
  "Next watering window": "Nächstes Bewässerungsfenster",
  "Current request / dose": "Aktueller Auftrag / Teilgabe",
  "Last delivered amount": "Zuletzt gelieferte Menge",
  "Last duration": "Letzte Dauer",
  "Measurement quality": "Messqualität",
};

const overviewMetrics = ["active", "pending", "next", "today", "month", "quality", "maintenance"];
const overviewActions = ["stop", "emergency", "suspend", "resume"];
const zoneMetrics = ["status", "today", "month", "next", "balance", "total", "recent", "quality", "calculation", "flow", "history"];
const zoneActions = ["create", "start", "pause", "resume", "stop", "stop_skip", "suspend", "resume_auto", "archive", "restore"];

abstract class BaseEditor<T extends CardConfig> extends LitElement {
  static styles = editorStyles;
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  hass!: HomeAssistant;
  protected _config!: T;

  setConfig(config: T): void {
    this._config = { ...config };
  }

  protected updateValue(key: keyof T, value: unknown): void {
    const next = { ...this._config, [key]: value || undefined };
    if (!value) delete next[key];
    this._config = next;
    fireConfigChanged(this, next);
  }

  protected entitySelector(key: keyof T, label: string, required: boolean): TemplateResult {
    const translated = this.hass.language.toLowerCase().startsWith("de")
      ? germanLabels[label] ?? label
      : label;
    return html`
      <label class="selector">
        <span>${translated}${required ? " *" : ""}</span>
        <ha-selector
          .hass=${this.hass}
          .selector=${{ entity: { filter: { integration: "irrigation_manager" } } }}
          .value=${this._config[key] ?? ""}
          @value-changed=${(event: CustomEvent<{ value: string }>) =>
            this.updateValue(key, event.detail.value)}
        ></ha-selector>
      </label>
    `;
  }

  protected displayMode(): TemplateResult {
    return html`
      <label class="selector">
        <span>${localize(this.hass, "display")}</span>
        <select
          .value=${this._config.display_mode ?? "detailed"}
          @change=${(event: Event) =>
            this.updateValue("display_mode", (event.target as HTMLSelectElement).value)}
        >
          <option value="compact">${localize(this.hass, "compact")}</option>
          <option value="detailed">${localize(this.hass, "detailed")}</option>
        </select>
      </label>
    `;
  }

  protected configurationMode(entityFields: readonly string[]): TemplateResult {
    const mode = inferConfigurationMode(this._config, entityFields);
    return html`
      <label class="selector">
        <span>${localize(this.hass, "configuration_mode")}</span>
        <select
          data-testid="configuration-mode"
          .value=${mode}
          @change=${(event: Event) =>
            this.updateValue("configuration_mode", (event.target as HTMLSelectElement).value)}
        >
          <option value="simple">${localize(this.hass, "simple")}</option>
          <option value="expert">${localize(this.hass, "expert")}</option>
        </select>
        <small>${localize(this.hass, mode === "simple" ? "simple_description" : "expert_description")}</small>
      </label>
    `;
  }

  protected anchorSelector(
    key: keyof T,
    kind: "installation" | "zone",
    fallback?: string,
  ): TemplateResult {
    const choices = anchorChoices(this.hass, kind);
    return html`
      <label class="selector">
        <span>${localize(this.hass, kind)}</span>
        <select
          data-testid="anchor-selector"
          .value=${String(this._config[key] ?? fallback ?? "")}
          @change=${(event: Event) =>
            this.updateValue(key, (event.target as HTMLSelectElement).value)}
        >
          <option value="">${localize(this.hass, "missing")}</option>
          ${choices.map(
            (choice) => html`<option value=${choice.value}>${choice.label}</option>`,
          )}
        </select>
      </label>
    `;
  }

  protected choices(key: "visible_metrics" | "visible_actions", values: string[]): TemplateResult {
    const selected = this._config[key] ?? values;
    return html`
      <div class="checks">
        ${values.map(
          (value) => html`
            <label class="check">
              <input
                type="checkbox"
                .checked=${selected.includes(value)}
                @change=${(event: Event) => {
                  const checked = (event.target as HTMLInputElement).checked;
                  this.updateValue(
                    key,
                    checked ? [...selected, value] : selected.filter((item) => item !== value),
                  );
                }}
              />
              ${localize(this.hass, value as Parameters<typeof localize>[1])}
            </label>
          `,
        )}
      </div>
    `;
  }
}

export class IrrigationManagerOverviewCardEditor extends BaseEditor<OverviewCardConfig> {
  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    const mode = inferConfigurationMode(this._config, overviewEntityFields);
    return html`
      <div class="editor">
        <section>${this.configurationMode(overviewEntityFields)}</section>
        ${mode === "simple"
          ? html`<section>${this.anchorSelector("installation", "installation")}</section>`
          : html`
              <section>
                <h3>${localize(this.hass, "required_entity")}</h3>
                ${this.entitySelector("status_entity", overviewFields[0][1], true)}
              </section>
              <section>
                <h3>${localize(this.hass, "optional_entities")}</h3>
                ${overviewFields.slice(1).map(([key, label]) => this.entitySelector(key, label, false))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${localize(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", overviewMetrics)}
        </section>
        <section>
          <h3>${localize(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", overviewActions)}
        </section>
      </div>
    `;
  }
}

export class IrrigationManagerZoneCardEditor extends BaseEditor<ZoneCardConfig> {
  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    const mode = inferConfigurationMode(this._config, zoneEntityFields);
    return html`
      <div class="editor">
        <section>${this.configurationMode(zoneEntityFields)}</section>
        ${mode === "simple"
          ? html`<section>${this.anchorSelector("zone", "zone")}</section>`
          : html`
              <section>
                <h3>${localize(this.hass, "required_entity")}</h3>
                ${this.entitySelector("zone_entity", zoneFields[0][1], true)}
              </section>
              <section>
                <h3>${localize(this.hass, "optional_entities")}</h3>
                ${zoneFields.slice(1).map(([key, label]) => this.entitySelector(key, label, false))}
              </section>
            `}
        <section>${this.displayMode()}</section>
        <section>
          <h3>${localize(this.hass, "metrics")}</h3>
          ${this.choices("visible_metrics", zoneMetrics)}
        </section>
        <section>
          <h3>${localize(this.hass, "actions")}</h3>
          ${this.choices("visible_actions", zoneActions)}
        </section>
      </div>
    `;
  }
}
