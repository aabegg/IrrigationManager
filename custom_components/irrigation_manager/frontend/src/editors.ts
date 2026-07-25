import { LitElement, html, nothing, type TemplateResult } from "lit";

import { anchorEntityIds, DOMAIN, fireConfigChanged, isAnchor } from "./helpers";
import { localize } from "./localize";
import { editorStyles } from "./styles";
import type { HomeAssistant, OverviewCardConfig, ZoneCardConfig } from "./types";

type CardConfig = OverviewCardConfig | ZoneCardConfig;

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
    const next = { ...this._config, [key]: value };
    if (value === undefined || value === "") delete next[key];
    this._config = next;
    fireConfigChanged(this, next);
  }

  private valueChanged(event: CustomEvent<{ value: unknown }>): void {
    const value = event.detail?.value;
    this.updateValue("entity", typeof value === "string" ? value : undefined);
  }

  protected anchorSelector(
    kind: "installation" | "zone",
  ): TemplateResult {
    const selected = this._config.entity
      ? this.hass.states[this._config.entity]
      : undefined;
    const invalid = Boolean(this._config.entity && !isAnchor(selected, kind));
    return html`
      <label class="selector">
        <span>${localize(this.hass, kind)}</span>
        <ha-selector
          data-testid="anchor-selector"
          .hass=${this.hass}
          .value=${this._config.entity ?? ""}
          .selector=${{
            entity: {
              include_entities: anchorEntityIds(this.hass, kind),
              filter: {
                integration: DOMAIN,
                domain: "sensor",
                device_class: "enum",
              },
            },
          }}
          @value-changed=${this.valueChanged}
        ></ha-selector>
        ${invalid
          ? html`<span class="error" role="alert">${localize(
              this.hass,
              kind === "installation" ? "invalid_installation_anchor" : "invalid_zone_anchor",
            )}</span>`
          : nothing}
      </label>
    `;
  }

}

export class IrrigationManagerOverviewCardEditor extends BaseEditor<OverviewCardConfig> {
  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    return html`
      <div class="editor">
        <section>${this.anchorSelector("installation")}</section>
      </div>
    `;
  }
}

export class IrrigationManagerZoneCardEditor extends BaseEditor<ZoneCardConfig> {
  render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    return html`
      <div class="editor">
        <section>${this.anchorSelector("zone")}</section>
      </div>
    `;
  }
}
