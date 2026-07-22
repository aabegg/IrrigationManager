# Irrigation Manager Lovelace cards

The integration serves and registers the compiled ES module automatically while at least one Irrigation Manager config entry is loaded. Do not add a duplicate Lovelace resource and do not edit `.storage`.

Add a card through the dashboard editor and select **Irrigation Manager Overview** or **Irrigation Manager Zone**. New cards use simple configuration: select one installation or zone by its configured name and the card resolves its metrics and action identifiers automatically. Compact/detailed layout, visible metrics, and visible actions remain available in both configuration modes.

Expert mode exposes every individual entity selector. Explicit entity selections override automatic resolution, and switching modes does not delete them. Existing card configurations containing individual entity fields are inferred as expert configurations and continue to work unchanged.

## Overview card

In simple mode, select the installation. The card stores its stable `config_entry_id` in `installation`, then finds the canonical status entity at runtime. Its bounded `card_entities` attribute maps semantic card roles to current entity-registry IDs, so renaming either the anchor or a sibling entity is followed automatically.

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
  - emergency
```

## Zone card

In simple mode, select the zone. The card stores a stable `config_entry_id:zone_subentry_id` value in `zone`, then finds the canonical cumulative-water entity at runtime. Its `card_entities` map contains only that zone's roles; `installation_card_entities` supplies the shared active-zone and current-request entities from the owning installation. Pause/resume/targeted stop still verify that the active request exposes the selected zone's `zone_subentry_id`. Controls stay disabled when required identifiers are unavailable.

```yaml
type: custom:irrigation-manager-zone-card
configuration_mode: simple
zone: 01JEXAMPLECONFIGENTRY:01JEXAMPLEZONESUBENTRY
display_mode: detailed
```

Advanced configurations may continue using `status_entity`, `zone_entity`, and all optional `*_entity` fields. These fields remain the expert-mode overrides and always take precedence over an automatically resolved role.

Amount-controlled requests also ask for a maximum duration because `services.yaml` requires `hard_time_limit` whenever `amount` is used. Stop and emergency stop always require confirmation.

Both **Create request** and **Start now** submit through `create_manual`, whose service handler returns after accepting the request. The scheduler starts an accepted runnable request immediately; the card never waits for the complete irrigation operation. `services.yaml` currently has no separate `start_now` field.

## Development

```bash
cd custom_components/irrigation_manager/frontend
npm ci
npm run check
npm run build
```

`npm run build` writes the checked-in production bundle to `dist/irrigation-manager.js`. The integration appends its manifest version to the served URL for cache invalidation.
