# Changelog

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
