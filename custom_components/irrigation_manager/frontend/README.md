# Irrigation Manager Lovelace cards

The integration serves and registers the compiled ES module automatically while at least one Irrigation Manager config entry is loaded. Do not add a duplicate Lovelace resource and do not edit `.storage`.

Add a card through the dashboard editor and select **Irrigation Manager Overview** or **Irrigation Manager Zone**. Both cards provide graphical editors for their entity set, compact/detailed layout, visible metrics, and visible actions.

## Overview card

The installation status entity is required. It supplies the `config_entry_id` used by the native `irrigation_manager.stop` and `irrigation_manager.emergency_stop` actions. Other metrics are optional because the integration does not currently expose dedicated daily/monthly consumption, next-installation request, or model-quality entities.

```yaml
type: custom:irrigation-manager-overview-card
status_entity: sensor.garden_irrigation_status
emergency_entity: binary_sensor.garden_irrigation_emergency_stop
lock_entity: binary_sensor.garden_irrigation_installation_safety_lock
active_zone_entity: sensor.garden_irrigation_active_zone
dose_entity: sensor.garden_irrigation_current_dose
pending_entity: sensor.garden_irrigation_pending_requests
display_mode: detailed
visible_metrics:
  - active
  - pending
visible_actions:
  - stop
  - emergency
```

## Zone card

The zone cumulative water entity is required. It supplies the `config_entry_id` and `zone_subentry_id` accepted by the native manual-irrigation actions. Select the other entities from the same zone device. Pause/resume/targeted stop require a queue entity exposing `request_id`, `execution_id`, and the same `zone_subentry_id`, normally the installation's current-dose or remaining-target sensor. Controls stay disabled when that ownership cannot be verified.

```yaml
type: custom:irrigation-manager-zone-card
zone_entity: sensor.lawn_water_total
automation_needed_entity: binary_sensor.lawn_automation_needed
safety_lock_entity: binary_sensor.lawn_zone_safety_lock
deficit_entity: sensor.lawn_water_deficit
target_entity: sensor.lawn_automatic_target
planning_reason_entity: sensor.lawn_planning_reason
next_window_entity: sensor.lawn_next_watering_window
active_zone_entity: sensor.garden_irrigation_active_zone
request_entity: sensor.garden_irrigation_current_dose
last_delivered_entity: sensor.lawn_last_delivered
last_duration_entity: sensor.lawn_last_duration
quality_entity: sensor.lawn_measurement_quality
display_mode: detailed
```

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
