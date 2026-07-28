# Changelog

## 0.1.0-rc24 - 2026-07-28

### Changed

- Simplify the weather-source options form by removing its redundant technical status summary.
- Clarify that suitable Home Assistant entities may originate from local sensors or external
  weather services while keeping detailed source quality in integration diagnostics.

## 0.1.0-rc23 - 2026-07-28

### Added

- Add explicit local weather-source assignment for precipitation, reference
  evapotranspiration, temperature, humidity, dew point, wind, solar irradiance, and
  forecasts.
- Normalize configured sources into canonical units and expose availability, age,
  plausibility, completeness, and forecast capabilities in settings and diagnostics.

### Changed

- Keep weather-source assignment observational: it neither enables weather correction nor
  reloads planning or an active irrigation execution.
- Add a neutral config-entry migration with no automatically selected sources and no change to
  existing irrigation behavior.

## 0.1.0-rc22 - 2026-07-28

### Changed

- Format irrigation-history timestamps in the Home Assistant time zone, display durations as
  hours, minutes, and seconds, round liter values to two decimal places, and present responsive
  localized pagination.
- Render malformed history values with a safe placeholder instead of exposing raw API values or
  failing the history dialog.

## 0.1.0-rc21 - 2026-07-28

### Fixed

- Persist a clean dispatcher shutdown from Home Assistant's core stop event so controlled
  restarts are not reported as unclean previous runtimes.
- Serialize overlapping stop and unload paths and retry a transient final diagnostics write
  before Home Assistant exits.

## 0.1.0-rc20 - 2026-07-28

### Added

- Add per-zone seasonal adjustment with twelve bounded monthly factors and daily local-date
  interpolation between month anchors.
- Add native Home Assistant configuration flows for global module availability, zone opt-in,
  curve editing, target preview, and explicit confirmation.
- Snapshot the baseline, applied seasonal factor, resulting target, resolution outcome,
  fallback strategy, quality, and warnings in every automatic irrigation order.
- Add the shared execute, skip, and defer target-resolution contract for later modules.

### Changed

- Replan only pending automatic orders atomically after seasonal configuration changes while
  retaining active executions, manual orders, and dormant curves.
- Report seasonally enlarged targets that no longer fit as `seasonal_target_does_not_fit`
  instead of shortening them or failing the complete planning pass, and persist the current
  rejections for diagnostics across restarts.
- Migrate existing zones to a disabled neutral seasonal curve without changing behavior.

### Fixed

- Align the Config Flow version with the rc20 migration target so Home Assistant executes the
  additive rc19-to-rc20 migration while preserving schedules, targets, releases, queued work,
  active executions, and safety state.

## 0.1.0-rc19 - 2026-07-28

### Added

- Persist dispatcher decision transitions, blockers, wake times, and lifecycle evidence in
  a versioned 100-entry diagnostic ring exposed through Home Assistant diagnostics.
- Detect and retain evidence of an unclean previous Irrigation Manager runtime without
  attributing the interruption to an unverified host cause.

### Fixed

- Back off exponentially after unexpected dispatcher failures so repeated exceptions cannot
  monopolize the Home Assistant event loop.
- Log blocked due orders once per reason transition and clean up terminal wait/error objects
  after requests finish.
- Wake the dispatcher after safety-lock reset and failed deferred reload completion.

## 0.1.0-rc18 - 2026-07-28

### Fixed

- Prevent the request dispatcher from spinning without delay when a due irrigation order
  remains pending because a release or configuration barrier temporarily blocks execution.

## 0.1.0-rc17 - 2026-07-27

### Added

- Add optional plant and site profiles with multiple subareas and transparent qualitative
  recommendations for water need, soil behavior, and partial-delivery suitability.
- Add one shared zone baseline with optional weekday overrides while retaining manual-only
  zones without an automatic target.

### Changed

- Split installation and zone configuration into focused settings areas for hardware,
  extensions, profiles, baseline, and weekly schedule.
- Migrate existing weekday targets losslessly to the shared-baseline model.
- Replan pending automatic orders after configuration changes without changing active
  irrigation executions or manual orders.

### Fixed

- Preserve dormant subareas when plant profiles are disabled and re-enabled.
- Reject baseline changes and invalid stored schedules whose complete target no longer fits
  inside the configured irrigation window.

## 0.1.0-rc16 - 2026-07-27

### Fixed

- Show a localized success message after saving an irrigation-zone configuration instead
  of the raw `reconfigure_successful` translation key.

## 0.1.0-rc15 - 2026-07-27

### Changed

- Replace `HH:MM:SS` text inputs with separate hour, minute, and second fields in config
  flows, Home Assistant actions, and the zone card.
- Keep hours unrestricted beyond 24 while continuing to store and process durations as
  seconds internally.
- Retain numeric seconds and legacy `HH:MM:SS` values for existing service callers.

## 0.1.0-rc14 - 2026-07-27

### Changed

- Replace every user-facing duration input with validated `HH:MM:SS` text while retaining
  numeric seconds in configuration, storage, scheduling, and execution.
- Apply the duration format consistently to weekly time targets, volume safety limits,
  flow calibration, manual card actions, and Home Assistant action fields.
- Keep numeric second values accepted by the service schema for existing automations and
  external callers.

## 0.1.0-rc13 - 2026-07-27

### Changed

- Use an accepted per-zone flow calibration to estimate the duration of automatic
  volume-controlled orders while retaining the configured maximum runtime as their hard
  execution limit.
- Keep configured liter targets unchanged for cumulative and pulse meters instead of
  rounding them to an artificial measurement resolution.
- Make `docs/17_Neukonzept.md` the only authoritative concept and implementation source;
  mark all older requirements, roadmaps, ADRs, and documents as historical archive material.

## 0.1.0-rc12 - 2026-07-27

### Changed

- Move installation operation and automatic-irrigation controls into a dedicated
  `Status and control` settings dialog with safety-lock-aware status text.
- Remove emergency stop from the installation settings while retaining it in the
  installation card and service API.

## 0.1.0-rc11 - 2026-07-27

### Added

- Add a confirmed zone-card action that safely stops only the currently active irrigation
  execution for that zone.

### Changed

- Split open irrigation orders into a localized daily view with date selection, day
  navigation, formatted start times, and a shortcut to the next day containing orders.

## 0.1.0-rc10 - 2026-07-26

### Changed

- Register the dashboard card bundle as one persistent Lovelace module resource and update
  its versioned URL in place so Companion clients load it reliably after upgrades.

### Fixed

- Request and unwrap Home Assistant action responses correctly for open orders, zone
  history, and manual irrigation.
- Show readable Home Assistant WebSocket error messages instead of `[object Object]`.

## 0.1.0-rc9 - 2026-07-25

### Changed

- Present installation and automatic-irrigation state independently with direct activate
  and deactivate actions for both installations and zones.
- Add complete zone labels, field descriptions, and native Next-step behavior.
- Group weekly schedules into translated weekday sections with labeled start, end, and
  time- or volume-target fields.

### Fixed

- Replace generic activation error dialogs with actionable reconfiguration explanations.
- Keep activation actions visible while reconfiguration is required so users can discover
  why the action is currently blocked.

## 0.1.0-rc8 - 2026-07-25

### Changed

- Replace separate installation settings with one atomic guided wizard for the name,
  optional main valve, and conditional water-meter configuration.
- Show installation actions according to the current operation, automatic-release, and
  safety-lock state, with concise localized status and result messages.
- Use native Home Assistant entity selectors in both card editors while limiting each
  picker to valid installation or zone status anchors.

### Fixed

- Handle the selector's native value-change event and empty preview configurations so
  installation and zone cards can be configured from the dashboard editor.
- Explain invalid card anchors immediately instead of silently rendering incomplete data.
- Require an explicit inspection confirmation with a visible warning before resetting an
  installation safety lock.

## 0.1.0-rc7 - 2026-07-25

### Changed

- Rebuild the integration around the authoritative v2 installation, zone, weekly-plan,
  manual-operation, water-meter, and calibration contracts.
- Reduce Home Assistant entities, actions, settings, diagnostics, and dashboard cards to
  their defined v2 surface and remove the old demand, weather, profile, maintenance,
  winter, archive, suspension, flow-sensor, and partial-delivery modules.
- Replace the incremental legacy storage chain with one destructive, fail-closed v2
  migration that preserves only valid releases, locks, measurements, and history.
- Store cards by one selected installation or zone anchor entity and clean stale rc5
  registry entities by stable unique ID.

### Fixed

- Make a disabled installation fully passive after active work has stopped, including
  during startup, so external valve changes are neither closed nor safety-locked.
- Make cancellation and calibration termination single-owner and idempotent to prevent
  duplicate water and runtime accounting.
- Enforce ordered, bounded valve closure independently of volume-target deadlines.
- Keep serial automatic work inside its windows, including cross-midnight windows, and
  wake the dispatcher at future requested start times.
- Allow timed irrigation to continue when its optional meter is unavailable while keeping
  volume irrigation and calibration fail-closed.
- Persist complete physical-meter correction records without changing consumption totals.

## 0.1.0-rc6 - 2026-07-24

### Added

- Introduce the authoritative v2 configuration model with a minimal installation wizard,
  one required first zone, and explicit seven-day time or volume schedules.
- Add independent installation and zone operation and automatic releases plus one
  persistent installation-wide safety lock.
- Add optional main-valve, cumulative-volume, and pulse-meter modules with corrected
  physical meter continuity and measured zone, installation, and unassigned consumption.
- Add Energy Dashboard-compatible water entities, runtime period sensors, fixed-weekly
  atomic replanning, and guided per-zone flow calibration.
- Add focused installation and zone cards with open-order and history dialogs, atomic
  manual conflict handling, adaptive runtime/water metrics, and immediate Not-Aus.

### Changed

- Existing v1 installations migrate fail-closed and must be explicitly reconfigured;
  legacy demand schedules are not guessed or silently converted into weekly targets.
- Runtime faults now set the installation-wide safety lock instead of a zone-local lock.
- Unchanged available meter values remain valid without artificial heartbeat updates;
  only volume targets and calibration require physical meter progress.
- Make automatic replanning idempotent, DST-aware, active-window aware, and atomic while
  preserving active executions and manual requests.

### Safety

- Block all actuator paths until migrated installations and zones are fully reconfigured.
- Enforce global actuator ownership across installations and fail closed on meter loss,
  volume timeout, invalid release transitions, and unconfirmed safety-lock reset.

## 0.1.0-rc5 - 2026-07-23

### Added

- Show effective zone and installation safety locks on every affected zone card with
  scope, understandable reason, persistent occurrence time, and a guarded reset button.
- Persist safety-lock timestamps across Home Assistant restarts.

### Changed

- Publish an installation safety lock as the effective `safety_lock` status of every
  non-archived zone instead of incorrectly leaving zone status at `idle`.
- Recommend a 60-second flow calibration, allow longer measurements within the configured
  hard test deadline, and require recurring dead-man confirmation for longer tests.

## 0.1.0-rc4 - 2026-07-22

### Added

- Add a native zone-subentry menu below Settings > Devices & services with guided,
  expert, and flow-calibration choices.
- Guide operators through an explicitly supervised measurement, bounded runtime,
  result review, and separate accept-or-discard decision.
- Keep measured flow limits unchanged until the operator explicitly accepts a fresh
  proposal for the same unchanged zone.

## 0.1.0-rc3 - 2026-07-22

### Changed

- Add simple card configuration that selects an irrigation installation or zone and
  resolves all matching entities automatically.
- Retain the individual entity selectors as an expert mode with explicit overrides.
- Keep automatic mappings stable across entity renames and isolated between zones and
  installations.

## 0.1.0-rc2 - 2026-07-22

### Fixed

- Allow Home Assistant's card picker to apply an empty preview configuration before
  the user selects installation and zone entities.
- Add a browser-like catalog regression test covering both bundled Lovelace cards.
- Remove a duplicate `execution_id` field from the action metadata.

## 0.1.0-rc1 - 2026-07-22

First private release candidate.

### Included

- Guided German and English setup for installations, zones, raised beds, profiles,
  metering, weather sources, and safety limits.
- Serialized time- and volume-controlled irrigation with main-valve ordering,
  split doses, soak pauses, persistent requests, restart recovery, and hard limits.
- Emergency stop, winter lock, supervised maintenance, calibration, leak detection,
  flow monitoring, external interlocks, actuator feedback, and weather interlocks.
- Recorder-, Weather-, and optional Open-Meteo-based evapotranspiration and water
  balances with researched, versioned plant, soil, and irrigation profiles.
- Scheduling windows, priorities, budgets, forecast deferral, manual plans, calendar,
  consumption statistics, portable import/export, diagnostics, and Lovelace cards.
- HACS and Hassfest validation plus backend and frontend CI.

### Release-candidate limitations

- Intended for simulation and supervised private field testing, not unattended use.
- Site-specific soil, root-depth, infiltration, flow, and application-rate values must
  be verified during commissioning.
- An independent hardware shutoff timer remains strongly recommended.
- Browser/mobile presentation and all six physical zones still require field validation.
