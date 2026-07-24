# Irrigation Manager Lovelace cards

The integration serves and registers the compiled ES module automatically while at least one Irrigation Manager config entry is loaded. Do not add a duplicate Lovelace resource and do not edit `.storage`.

Add a card through the dashboard editor and select **Irrigation Manager Overview** or **Irrigation Manager Zone**. New cards use simple configuration: select one installation or zone by its configured name and the card resolves its metrics and action identifiers automatically. Compact/detailed layout, visible metrics, and visible actions remain available in both configuration modes.

Expert mode exposes every individual entity selector. Explicit entity selections override automatic resolution, and switching modes does not delete them. Existing card configurations containing individual entity fields are inferred as expert configurations and continue to work unchanged.

## Overview card

In simple mode, select the installation. The card stores its stable `config_entry_id` in `installation`, then finds the canonical status entity at runtime. Its bounded `card_entities` attribute maps semantic card roles to current entity-registry IDs, so renaming either the anchor or a sibling entity is followed automatically. The card shows the effective operating status, queue-adjusted next irrigation, and either runtime or measured-water period values according to the currently effective metering capability.

```yaml
type: custom:irrigation-manager-overview-card
configuration_mode: simple
installation: 01JEXAMPLECONFIGENTRY
display_mode: detailed
visible_metrics:
  - active
  - pending
visible_actions:
  - stop
```

## Zone card

In simple mode, select the zone. The card stores a stable `config_entry_id:zone_subentry_id` value in `zone`, then finds the canonical effective-status entity at runtime. This anchor exists for installations with and without water metering. Its `card_entities` map contains only that zone's runtime, measured-water, next-irrigation, and status roles; `installation_card_entities` supplies shared installation roles. Controls stay disabled when required identifiers are unavailable.

```yaml
type: custom:irrigation-manager-zone-card
configuration_mode: simple
zone: 01JEXAMPLECONFIGENTRY:01JEXAMPLEZONESUBENTRY
display_mode: detailed
```

Advanced configurations may continue using `status_entity`, `zone_entity`, and all optional `*_entity` fields. These fields remain the expert-mode overrides and always take precedence over an automatically resolved role.

`Manually water` opens a dialog. Duration is always available; amount and its required maximum duration appear only while volume metering is functional. If another irrigation execution is active, the dialog submits exactly one `start_manual_from_card` action with either `stop_active` or `priority_next`; the card never issues a race-prone stop-then-create sequence.

The overview card's red emergency-stop action is always visible and executes immediately without confirmation. Resetting a safety lock remains a separate confirmed action. Clicking the open-order metric calls `list_card_orders`; zone history uses the filtered, paginated `list_zone_history` presentation service. The canonical UI terms are **irrigation order** (`Bewässerungsauftrag`) for work not yet started and **irrigation execution** (`Bewässerungsvorgang`) for accepted execution history.

Compact mode only reduces secondary card metrics. Interactive form fields live in dialogs, so compact mode never hides required inputs while leaving their submit action visible.

## Development

```bash
cd custom_components/irrigation_manager/frontend
npm ci
npm run check
npm run build
```

`npm run build` writes the checked-in production bundle to `dist/irrigation-manager.js`. The integration appends its manifest version to the served URL for cache invalidation.
