import { LitElement, html, nothing, type TemplateResult } from "lit";

import { fireConfigChanged } from "./helpers";
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
  ["today_consumption_entity", "Today's consumption"],
  ["month_consumption_entity", "Monthly consumption"],
  ["model_quality_entity", "Model quality"],
] as const;

const zoneFields = [
  ["zone_entity", "Zone total / action identity"],
  ["automation_needed_entity", "Automatic demand"],
  ["safety_lock_entity", "Zone safety lock"],
  ["deficit_entity", "Water deficit"],
  ["target_entity", "Automatic target"],
  ["planning_reason_entity", "Planning explanation"],
  ["next_window_entity", "Next watering window"],
  ["active_zone_entity", "Active zone / progress"],
  ["request_entity", "Current request / dose"],
  ["last_delivered_entity", "Last delivered amount"],
  ["last_duration_entity", "Last duration"],
  ["quality_entity", "Measurement quality"],
] as const;

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

const overviewMetrics = ["active", "pending", "next", "today", "month", "quality"];
const overviewActions = ["stop", "emergency"];
const zoneMetrics = ["balance", "next", "total", "recent", "quality"];
const zoneActions = ["create", "start", "pause", "resume", "stop", "stop_skip"];

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
    return html`
      <div class="editor">
        <section>
          <h3>${localize(this.hass, "required_entity")}</h3>
          ${this.entitySelector("status_entity", overviewFields[0][1], true)}
        </section>
        <section>
          <h3>${localize(this.hass, "optional_entities")}</h3>
          ${overviewFields.slice(1).map(([key, label]) => this.entitySelector(key, label, false))}
        </section>
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
    return html`
      <div class="editor">
        <section>
          <h3>${localize(this.hass, "required_entity")}</h3>
          ${this.entitySelector("zone_entity", zoneFields[0][1], true)}
        </section>
        <section>
          <h3>${localize(this.hass, "optional_entities")}</h3>
          ${zoneFields.slice(1).map(([key, label]) => this.entitySelector(key, label, false))}
        </section>
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
