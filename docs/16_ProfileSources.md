# Built-in profile catalog sources

## Scope and status

Catalog version 1 contains researched planning defaults, not measurements or locally validated
values.
Every researched profile has `confirmation_required=true`, source metadata, an interpretation
confidence, explicit assumptions, and ranges where the supplied research defines them. The
unchanged neutral v1 profiles remain available for migration and retain their legacy precedence.

The catalog never infers soil texture, rooting depth, plant establishment, irrigation uniformity,
hemisphere, or crop dates. Those are external observations that the user must confirm.

## FAO-56 crop and water-balance model

- [FAO-56 Chapter 6, ETc and single crop coefficient](https://www.fao.org/4/X0490E/x0490e0b.htm)
  defines `ETc = Kc * ETo`, growth stages, the Kc curve, and Table 12 crop coefficients.
- [FAO-56 Chapter 8, soil water stress](https://www.fao.org/4/X0490E/x0490e0e.htm)
  defines total available water and readily available water. Table 19 supplies broad soil-water
  properties; Table 22 supplies crop rooting-depth ranges and depletion fractions.
- Total available water (TAW) is the physical root-zone storage clamp:
  `AWC [mm/m] * effective root depth [m]`.
- Readily available water (RAW) is the demand-irrigation trigger:
  `p * TAW`. A zone may retain a deficit above RAW up to TAW while waiting or being blocked.
- Table 19 texture classes do not exactly equal every catalog label or field soil. Catalog AWC
  defaults and supplied ranges are coarse texture-class interpretations and must not replace a
  measured field-capacity-minus-wilting-point result.
- Table 22 root depths are maximum effective ranges under stated conditions. Catalog root depths
  are conservative effective planning assumptions from the supplied research summary, not claims
  that roots at a site reach that depth. Compaction, containers, layering, groundwater, and recent
  planting can reduce effective depth.
- Table 22 `p` is stated around ETc of 5 mm/day and FAO documents climate and soil-texture
  adjustments. Catalog v1 intentionally keeps the supplied fixed `p`; it does not silently apply
  those adjustments.
- Table 12 Kc values describe standard, unstressed conditions. Landscape plant factors are not
  interchangeable with crop Kc measurements. Profiles declare `coefficient_basis`; a
  `landscape_pf` already incorporates plant and location effects, so the resolver does not
  multiply it by another exposure/location factor.

## Seasons and phenology

FAO-56 Chapter 6 requires local growth-stage lengths and explicitly notes dependence on planting
period, climate, and region. The mixed-vegetable profile therefore stores stages (`initial=0.60`,
`mid=1.05`, `late=0.85`) rather than universal calendar months. The user supplies an explicit
recurring `season_start` plus stage durations, or explicit recurring stage-boundary dates. The
resolver interpolates coefficient and effective root depth during development and late season.
Outside the configured season it reports `inactive`. Without a schedule it uses the mid-stage Kc
and 0.45 m root depth as a conservative fallback and emits `phenology_mapping_required`; it does
not infer a hemisphere.

The mature deciduous orchard profile uses the same explicit local schedule for the supplied
`0.45 -> 0.90 -> 0.65` sequence. It assumes no active groundcover. Budbreak, canopy, harvest, and
leaf-fall dates are not inferred. Turf Kc values apply to active growth only; dormancy behavior is
not inferred.

## Landscape plant factors

- [WUCOLS IV](https://ccuh.ucdavis.edu/wucols) classifies landscape species water use by region.
- [California Model Water Efficient Landscape Ordinance](https://water.ca.gov/Programs/Water-Use-And-Efficiency/Urban-Water-Use-Efficiency/Model-Water-Efficient-Landscape-Ordinance)
  provides the regulatory landscape-water-budget context and links WUCOLS.
- WUCOLS ratings and MWELO plant factors are regional landscape planning tools. They are not
  universal species Kc values, do not establish root depth or depletion fraction, and do not prove
  performance at a particular site. The annual-flower profile is therefore explicitly low
  confidence; other mixed landscape categories remain assumptions requiring confirmation.
- Landscape profiles store their coefficients as `seasonal_plant_factor` with
  `coefficient_basis=landscape_pf`. Any separate location factor is ignored with an explicit
  warning to prevent counting the site effect twice.

## Soil infiltration

- [FAO Irrigation Water Management, Annex 2, Table 7](https://www.fao.org/4/S8684E/s8684e0a.htm)
  gives broad basic infiltration ranges by texture and describes a field ring-infiltrometer test.
- Catalog values `25, 15, 8, 4, 2 mm/h` are deliberately provisional application-rate ceilings
  from the supplied research summary. They are not substitutions for Table 7's ranges and are not
  measurements. Structure, crusting, compaction, slope, antecedent moisture, organic matter, and
  emitter concentration can dominate texture. At least two site tests are needed according to the
  cited annex.
- Catalog v1 exposes the ceiling in resolved metadata. It does not silently change maximum dose,
  current deficit, or the configured Teilgabe limits.

## Irrigation application efficiency

- [FAO Annex I, Irrigation efficiencies, Table 8](https://www.fao.org/4/T7202E/t7202e08.htm)
  gives indicative field application efficiencies of 90% for drip and 75% for sprinkler.
- [FAO Irrigation Water Management, Chapter 7](https://www.fao.org/4/S8684E/s8684e08.htm)
  stresses that application efficiency depends on operation and local conditions as well as method.
- Catalog defaults/ranges are drip `0.90 [0.80, 0.95]`, microspray `0.80 [0.75, 0.90]`, fixed
  spray `0.70 [0.65, 0.80]`, and rotor `0.75 [0.65, 0.85]`. FAO Table 8 directly supports only the
  broad drip/sprinkler reference points; the method-specific ranges are supplied research-summary
  interpretations and remain medium-confidence planning defaults.
- Application efficiency converts net deficit to gross target (`gross = net / efficiency`). It
  does not alter current net deficit, maximum net deficit, or maximum Teilgabe configuration.

## Establishment and extension context

- [Colorado State University Extension: Watering established lawns](https://extension.colostate.edu/topic-areas/yard-garden/watering-established-lawns-7-199/)
  is contextual guidance for active turf and local scheduling. It is not the numerical source for
  the catalog Kc, root depth, or depletion fraction and may redirect as CSU reorganizes content.
- [University of Minnesota Extension: Watering newly planted trees and shrubs](https://extension.umn.edu/planting-and-growing-guides/watering-newly-planted-trees-and-shrubs)
  documents frequent establishment watering, expanding wetted area, and establishment periods.
  It does not support treating `Kc=0.50`, `root=0.70 m`, or `p=0.40` as exact for a young fruit
  tree. The catalog profile is an explicitly approximate, low-confidence bridge and carries an
  establishment warning.

## Operational interpretation

- Researched profiles derive TAW from AWC and effective root depth, then RAW from `p * TAW`.
  Demand irrigation becomes eligible at RAW; water-balance accumulation remains clamped at TAW.
- Legacy zones retain their previous one-limit behavior with TAW and RAW both equal to
  `maximum_deficit_mm`. An explicit `profile_overrides.maximum_deficit_mm` is treated the same way
  and recorded as a legacy override in resolved inputs.
- For multiple Teilflächen, each local TAW and RAW is divided by that Teilfläche's net-depth factor
  before the minimum common zone limit is selected.
- `max_dose_amount` and `max_dose_duration` continue to cap individual Teilgaben only.
- Historical requests and executions retain their immutable resolved input snapshot; a future
  catalog version or profile change does not rewrite history.
- Portable imports never trust exported `agronomic_values_confirmed` or
  `confirmation_required` flags. Every referenced researched profile, including references in
  Teilflächen and custom `based_on` ancestry, requires a new explicit local confirmation.
- The guided UI labels TAW as usable water storage and RAW as water available before plant stress;
  the expert terms remain visible in the review. Expected liters use the resolved gross liters per
  deficit millimeter. Runtime is shown only from a measured flow range or explicitly marked as an
  estimate.
- For a raised bed, usable soil depth caps the selected plant profile's effective root depth. The
  resulting TAW and RAW are persisted as explicit profile overrides with their assumptions shown in
  review. Drainage layers and empty space are excluded. Soil-mix age, organic richness, and observed
  drainage are uncertainty prompts, not invented measurements.
- Unknown raised-bed soil uses the researched sand profile as a conservative bounded default; it
  is explicitly disclosed and still requires local profile confirmation. Catalog v1 has no sourced
  sun/exposure reduction factors, so exposure answers remain descriptive and do not automatically
  reduce demand.
