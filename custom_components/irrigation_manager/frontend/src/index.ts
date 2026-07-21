import {
  IrrigationManagerOverviewCardEditor,
  IrrigationManagerZoneCardEditor,
} from "./editors";
import { IrrigationManagerOverviewCard } from "./overview-card";
import { IrrigationManagerZoneCard } from "./zone-card";

const elements: Array<[string, CustomElementConstructor]> = [
  ["irrigation-manager-overview-card", IrrigationManagerOverviewCard],
  ["irrigation-manager-zone-card", IrrigationManagerZoneCard],
  ["irrigation-manager-overview-card-editor", IrrigationManagerOverviewCardEditor],
  ["irrigation-manager-zone-card-editor", IrrigationManagerZoneCardEditor],
];

for (const [name, constructor] of elements) {
  if (!customElements.get(name)) customElements.define(name, constructor);
}

window.customCards = window.customCards ?? [];
for (const card of [
  {
    type: "irrigation-manager-overview-card",
    name: "Irrigation Manager Overview",
    description: "Installation status, progress, consumption and safety actions.",
    preview: true,
  },
  {
    type: "irrigation-manager-zone-card",
    name: "Irrigation Manager Zone",
    description: "Water balance, planning details and native zone controls.",
    preview: true,
  },
]) {
  if (!window.customCards.some((registered) => registered.type === card.type)) {
    window.customCards.push(card);
  }
}
