# Software-Qualifikation

Stand: 2026-07-21

## Umfang

Diese Qualifikation prüft die deterministisch simulierbaren Sicherheits-, Speicher-,
Scheduler-, Wasserzähler- und Wetterpfade vor einem Feldtest. Die wiederverwendbare
Testanlage `tests/irrigation_plant.py` stellt kontrollierbare monotone Zeit und Wandzeit,
Ventile und Rückmeldungen, kumulatives Volumen, Durchfluss, Wetterzustand sowie einen
Home-Assistant-Config-Entry mit echtem Integrationsspeicher bereit.

Die Tests ersetzen keinen beaufsichtigten Test mit realen Ventilen, Relais, Leitungen und
einem unabhängigen Hardware-Abschalttimer. Eine Freigabe für unbeaufsichtigten Feldbetrieb
wird aus diesem Bericht ausdrücklich nicht abgeleitet.

## Sicherheitsnachweis

| Invariante aus `docs/11_Safety.md` | Nachweis |
| --- | --- |
| Sicherheit hat Vorrang und Fehler führen soweit erreichbar zum geschlossenen Zustand | `test_valve_feedback_faults_fail_closed_when_hardware_is_reachable`, `test_cleanup_attempts_main_close_when_zone_close_fails` |
| Höchstens eine hydraulisch aktive Bewässerungszone | `test_serialized_plant_never_opens_two_zones_and_orders_main_valve`, `test_monitor_closes_a_second_zone_that_opens_during_watering`, Preflight-Tests in `test_init.py` |
| Hauptventil öffnet vor und schließt nach dem Zonenventil; zwischen Teilgaben ist es geschlossen | `test_serialized_plant_never_opens_two_zones_and_orders_main_valve`, `test_execute_timed_waters_one_zone_and_attributes_meter_delta`, `test_split_request_persists_one_execution_across_soak_doses` |
| Bewässerungslaufzeit und gesamte Vorgangsdauer sind getrennt begrenzt | `test_execution_hard_runtime_is_consumed_across_split_volume_doses`, `test_active_request_stops_at_expiry_and_never_continues`, `test_soaking_request_expires_without_another_dose` |
| Harte Mengenvorgänge enden auch bei Wandzeitsprung am monotonen Deadline | `test_volume_deadline_ignores_backward_wall_clock_jump`, alle `test_volume_deadline_*` in `test_executor.py` |
| Stop, Pause und Abbruch schließen Ventile und erhalten nur den tatsächlich gelieferten Fortschritt | `test_cancellation_race_uses_monotonic_progress_and_closes_every_valve`, `test_pause_and_resume_preserve_the_remaining_target`, `test_stop_actions_close_active_valves_and_account_partial_water` |
| Eine konkurrierende Änderung darf keinen veralteten Auftrag starten | `test_stale_selected_request_cannot_overwrite_concurrent_change` für Cancel, Pause und Ersetzung |
| Sickerpausen belegen keine Hydraulik; andere Zonen dürfen laufen | `test_other_zone_runs_during_soak_and_soaking_request_can_be_cancelled`, Scheduler-Tests für dieselbe Zone |
| Neustart schließt Ventile, unterbricht aktive und sickernde Vorgänge und setzt sie nicht blind fort | `test_restart_interrupts_active_dose_and_replans_unexpired_remainder`, `test_soaking_state_is_interrupted_before_remainder_is_replanned`, Recovery-Tests in `test_init.py` |
| Gemessene oder geschätzte Teilmengen werden auch bei Abbruch und Neustart verbucht | `test_cancellation_preserves_measured_and_estimated_fallback_progress`, `test_setup_recovers_interrupted_execution_from_meter_baseline`, `test_setup_caps_durable_fallback_recovery_after_long_downtime` |
| Unerwartetes Öffnen oder Schließen und fehlende Rückmeldung werden erkannt | `test_monitor_closes_a_second_zone_that_opens_during_watering`, `test_valve_feedback_faults_fail_closed_when_hardware_is_reachable`, `test_volume_deadline_closes_zone_when_open_feedback_never_confirms` |
| Unterdurchfluss sperrt die Zone, Überdurchfluss die Anlage | `test_flow_faults_stop_with_the_required_lock_scope`, `test_flow_fault_stops_and_applies_correct_safety_scope` |
| Durchfluss im Leerlauf wird zeitlich bestätigt, geschlossen, unzugeordnet verbucht und persistent gesperrt | `test_idle_leak_and_weather_idempotency_survive_restart`, `test_persistent_idle_flow_closes_valves_and_sets_installation_lock`, Artefakt- und Unload-Tests in `test_init.py` |
| Ungültige Sensorwerte werden nicht als null oder gültig umgedeutet | `test_meter_adapter_rejects_non_finite_and_negative_values`, `test_meter_adapter_rejects_stale_samples`, `test_invalid_flow_breaks_continuous_leak_observation`, `test_finalized_weather_rejects_nan_without_mutating_balance` |
| Zählerreset erhält Kontinuität; Regression und unplausibler Sprung während einer Teilgabe brechen ab | `test_meter_adapter_rejects_small_regression_without_corrupting_baseline`, `test_meter_adapter_preserves_continuity_for_conservative_reset`, `test_executor_uses_production_meter_reset_classification`, `test_volume_control_rejects_regressing_and_jumping_meter_samples` |
| Zählerausfall bricht ab oder verwendet nur den expliziten, gekennzeichneten Schätzfallback | `test_volume_meter_loss_aborts_or_uses_explicit_estimated_fallback`, Fallback- und Checkpoint-Tests in `test_executor.py` und `test_init.py` |
| Automatische Planung ist bei doppelten Ereignissen und Neustarts idempotent | `test_duplicate_planning_events_create_one_stable_request`, `test_restart_does_not_duplicate_a_persisted_window_opportunity`, Wetterperioden-Test in `test_automatic_scheduling.py` |
| Alte Speicherversionen werden additiv migriert; korrupte Sicherheitsdaten brechen den Start ab | `test_storage_migration_is_additive_and_corruption_fails_closed`, alle Migrationsfälle in `test_init.py` |
| Konfigurationsänderungen werden erst im vollständigen Leerlauf aktiviert | `test_config_reload_waits_for_idle_and_unload_cleans_runtime_tasks`, `test_options_update_during_watering_reloads_only_after_complete_idle`, Snapshot-Tests in `test_automatic_scheduling.py` |
| Unload entfernt Listener und beendet oder erwartet alle eigenen Tasks | `test_config_reload_waits_for_idle_and_unload_cleans_runtime_tasks`, `test_short_idle_flow_artifact_is_ignored_and_unload_cancels_monitoring`, `test_unload_awaits_an_already_confirmed_leak_application` |
| Not-Aus ist persistent und nicht durch normale manuelle Bedienung übersteuerbar | `test_stop_actions_close_active_valves_and_account_partial_water`, `test_emergency_stop_blocks_manual_watering` |
| Frost-, Winter- und Wartungssperren sowie der Wartungs-Dead-Man sind nicht übersteuerbar | Noch kein vollständiger ausführbarer Nachweis; bleibt Freigabesperre für den vollständigen Erstumfang. |

## Speicher- und Wetterannahmen

- Korrupte sicherheitskritische Datensätze führen absichtlich zu einem fehlgeschlagenen Setup statt zu stillen Standardwerten.
- `meter_max_age_seconds` ist im Config/Options Flow konfigurierbar und beträgt standardmäßig 300 Sekunden.
- Finalisierte Wetterwerte müssen endlich und nicht negativ sein. Eine Perioden-ID ist idempotent; abweichende Wiederholung wird abgelehnt.
- Ein Rückgang wird nur als Zählerreset akzeptiert, wenn der neue Rohwert höchstens 10 L beträgt, der Rückgang mindestens 5 L groß ist und mindestens dem Fünffachen des neuen Rohwerts entspricht. Kleinere oder mehrdeutige Rückgänge werden abgelehnt, ohne die letzte gültige Baseline zu verändern. Ein anhand von Maximaldurchfluss und harter Laufzeit unmöglicher Sprung wird ebenfalls als Anlagenfehler behandelt.

## Nicht simulierte Hardware-Risiken

- mechanisch klemmendes Ventil oder verschweißter Relaiskontakt, der trotz bestätigtem Befehl offen bleibt
- Leitungsbruch oder Leck vor dem Hauptventil, das durch kein verwaltetes Ventil isoliert werden kann
- Stromausfall mit einer Ventilbauart, die nicht selbsttätig schließt
- vollständiger Ausfall von Home Assistant, Host, Netzwerk oder Funkverbindung nach dem Öffnen
- falsche oder verzögerte Ventilrückmeldung, die nicht den tatsächlichen hydraulischen Zustand abbildet
- Wasserzählerstillstand, grobe Impulsauflösung, verlorene Impulse und herstellerspezifische Messlatenz außerhalb der simulierten Werte
- falsch kalibrierte Durchflussgrenzen oder ein Sensorfehler, der plausible, aber physisch falsche Werte liefert
- hydraulische Kopplung, Rückfluss oder Druckschläge außerhalb der modellierten Ventiltopologie
- Ausfall des unabhängigen Hardware-Abschalttimers selbst

Diese Risiken erfordern beaufsichtigte Inbetriebnahme, Prüfung der stromlosen Ventilstellung,
reale Durchfluss- und Nachlaufkalibrierung sowie einen unabhängig geprüften Hardware-Abschalttimer.

## Verbleibende Software-Lücken

- Frost-, Winter- und Wartungs-Dead-Man-Abläufe besitzen noch keinen vollständigen Abnahmepfad.
- Eine deterministische Mehrwochen-Simulation mit sechs Referenzzonen ist nicht Teil dieses Slices.
- Reale Zeitzonen-/DST-Übergänge und Sonnenfenster sind nicht vollständig qualifiziert; feste Fenster über Mitternacht sind getestet.
- Wetterquellen-Fallbackketten, Prognoseaufschub und lang andauernde Wetterausfälle sind nur teilweise implementiert und getestet.
- Der Test der grafischen Karten erfolgt als Build/Registrierungsprüfung, nicht als visueller Browser- oder Hardware-End-to-End-Test.
