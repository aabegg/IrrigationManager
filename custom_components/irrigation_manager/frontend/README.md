# Irrigation Manager Lovelace cards

The integration serves and registers the compiled ES module automatically while at least one Irrigation Manager config entry is loaded. Do not add a duplicate Lovelace resource and do not edit `.storage`.

Add a card through the dashboard editor and select **Irrigation Manager Overview** or **Irrigation Manager Zone**. Each editor selects exactly one Home Assistant anchor entity. The card resolves its defined sibling entities and action identifiers from that anchor.

## Overview card

Select the installation status entity. Its bounded `card_entities` attribute maps semantic card roles to current entity-registry IDs. The card shows the effective operating status, open orders, queue-adjusted next irrigation, the aligned physical meter when available, and either runtime or measured-water period values according to the current metering capability.

```yaml
type: custom:irrigation-manager-overview-card
entity: sensor.garden_irrigation_status
```

## Zone card

Select the zone status entity. This anchor exists for installations with and without water metering. Its `card_entities` map contains only that zone's runtime, measured-water, next-irrigation, and status roles. Controls stay disabled when required identifiers are unavailable.

```yaml
type: custom:irrigation-manager-zone-card
entity: sensor.lawn_status
```

`Manually water` opens a dialog. Duration is always available; amount and its required maximum duration appear only while volume metering is functional. If another irrigation execution is active, the dialog submits exactly one `start_manual_from_card` action with either `stop_active` or `priority_next`; the card never issues a race-prone stop-then-create sequence.

The overview card's red emergency-stop action is always visible and executes immediately without confirmation. Resetting a safety lock remains a separate confirmed action. Clicking the open-order metric calls `list_card_orders`; zone history uses the filtered, paginated `list_zone_history` presentation service. The canonical UI terms are **irrigation order** (`Bewässerungsauftrag`) for work not yet started and **irrigation execution** (`Bewässerungsvorgang`) for accepted execution history.

## Development

```bash
cd custom_components/irrigation_manager/frontend
npm ci
npm run check
npm run build
```

`npm run build` writes the checked-in production bundle to `dist/irrigation-manager.js`. The integration appends its manifest version to the served URL for cache invalidation.
