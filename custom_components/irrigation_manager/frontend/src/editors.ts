import { LitElement, html, nothing, type TemplateResult } from "lit";

import { anchorChoices, fireConfigChanged } from "./helpers";
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
    const next = { ...this._config, [key]: value || undefined };
    if (!value) delete next[key];
    this._config = next;
    fireConfigChanged(this, next);
  }

  protected anchorSelector(
    kind: "installation" | "zone",
  ): TemplateResult {
    const choices = anchorChoices(this.hass, kind);
    return html`
      <label class="selector">
        <span>${localize(this.hass, kind)}</span>
        <ha-selector
          data-testid="anchor-selector"
          .hass=${this.hass}
          .value=${this._config.entity ?? ""}
          .selector=${{ entity: { include_entities: choices.map((choice) => choice.value) } }}
          @value-changed=${(event: CustomEvent<{ value?: string }>) =>
            this.updateValue("entity", event.detail.value)}
        ></ha-selector>
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
