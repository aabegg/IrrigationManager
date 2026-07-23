# Changelog

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
