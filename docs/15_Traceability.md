# Anforderungs- und Sicherheitsrückverfolgbarkeit

Stand: 2026-07-22

## Leseregel

Jeder normative Aufzählungspunkt in `02_Requirements.md` erhält innerhalb seines
Abschnitts fortlaufend eine ID. Ein Bereich wie `REQ-WEA-01..04` gilt für **jeden** der
vier Punkte, nicht nur für den Abschnitt als Ganzes. Damit sind alle 177 Anforderungen
vor dem Abschnitt „Spätere Erweiterung“ erfasst. Sicherheitsanforderungen aus
`11_Safety.md` werden zusätzlich als `SAFE-*` geführt.

Status:

- **V**: durch Code und automatisierten Test verifiziert
- **P**: Softwarepfad vorhanden, Abnahme oder Teilaspekt noch offen
- **A**: Agronomie-Gate; fachliche Werte müssen extern validiert werden
- **H**: Hardware-/Feld-Gate; Simulation kann den Nachweis nicht liefern
- **R**: Release-/Remote-Gate; externes System oder veröffentlichter Lauf fehlt

Die Matrix ist ein Evidenzindex, kein Ersatz für die Tests. Ein grüner Softwaretest hebt
kein `A`, `H` oder `R` auf.

## Funktionsanforderungen

| IDs | MUST aus `02_Requirements.md` | Code | Tests/Nachweis | Status |
| --- | --- | --- | --- | --- |
| REQ-INS-01..02 | Config Entry je physischer Anlage; unabhängige Zufuhren getrennt | `config_flow.py`, `__init__.py` | `test_config_flow.py`, `test_init.py` | V |
| REQ-INS-03..06 | optionales Hauptventil/Zähler, zeitbasierter Ersatz, exklusive Zone | `executor.py`, `manager.py`, `adapters.py` | `test_executor.py`, `test_phase5_multiweek.py` | V |
| REQ-INS-07..10 | Automatik aussetzen, manuell weiterarbeiten, Stop und Not-Aus | `manager.py`, `services.py`, `binary_sensor.py` | `test_operational_scope.py`, `test_operations.py`, `test_safety_modes.py` | V |
| REQ-INS-11..13 | Tages-/Wochenbudget, manuelle Überschreitung, Tarif | `manager.py`, `sensor.py` | `test_automatic_scheduling.py`, `test_operations.py`, `test_phase5_multiweek.py` | V |
| REQ-ZON-01..03 | beliebige Zonen, genau ein Ventil, Archiv/Freigabe/Aussetzung | `config_flow.py`, `manager.py` | `test_config_flow.py`, `test_operational_scope.py` | V |
| REQ-ZON-04..10 | Profile, Kopien, Saisonkurven, einfacher Modus, Teilflächen und Aggregation | `profiles.py`, `manager.py` | `test_profiles.py`, `test_profile_operations.py`, `test_profile_migrations.py` | V/A |
| REQ-ZON-11..14 | Regenfaktor und Bodenfeuchtesensoren/Rollen | `manager.py`, `profiles.py` | `test_soil_moisture.py`, `test_water_balance.py` | V/A |
| REQ-ZON-15 | Batterie-, Verbindung- und Störungssensoren | `manager.py`, `config_flow.py` | `test_safety_inputs.py` | V/H |
| REQ-MOD-01..07 | Bedarfs-/Mindestmodus, manuell, Intervalle und wirksame Menge | `scheduler.py`, `manager.py` | `test_scheduler.py`, `test_automatic_scheduling.py` | V/A |
| REQ-MOD-08..12 | mehrere feste/Wochentag-/Sonnenfenster, Teilziel und harte Grenze | `scheduler.py`, `manager.py` | `test_scheduler.py`, `test_phase5_multiweek.py` | V |
| REQ-MOD-13..15 | begrenzter Prognoseaufschub und restartfeste Unterdrückung | `manager.py`, `storage.py` | `test_automatic_scheduling.py` | V/A |
| REQ-TGT-01..04 | Mengen-/Zeitsteuerung, harte Frist, manuelle Zielart | `executor.py`, `manager.py` | `test_executor.py`, `test_manual_requests.py` | V |
| REQ-TGT-05..09 | maximale Menge/Laufzeit/Lebensdauer und Messauflösung | `manager.py`, `executor.py`, `meter.py` | `test_executor.py`, `test_meter.py`, `test_qualification_scenarios.py` | V/H |
| REQ-TGT-10 | kalibrierte Vorabschaltung | `executor.py`, `manager.py` | `test_executor.py`, `test_operations.py` | V/H |
| REQ-TGT-11..12 | Bedarf bis nächste Gelegenheit und Zielpriorität | `manager.py`, `scheduler.py` | `test_automatic_scheduling.py` | P/A |
| REQ-DOSE-01..06 | Teilgaben, Sickerpause, geschlossene Ventile, Interleaving, gemeinsame Ausführung, Rest | `manager.py`, `scheduler.py`, `executor.py` | `test_manual_requests.py`, `test_executor.py` | V |
| REQ-SCH-01..04 | stornierbare Aufträge, Anzeige, Mehrzonenplan, Zukunftsauftrag | `models.py`, `manager.py`, `services.py` | `test_manual_requests.py`, `test_operations.py` | V |
| REQ-SCH-05..09 | Persistenz, Priorität, getrennte Quellen, automatische Sortierung, Teilziel | `scheduler.py`, `storage.py`, `manager.py` | `test_scheduler.py`, `test_automatic_scheduling.py`, `test_phase5_multiweek.py` | V |
| REQ-SCH-10..11 | Kalender, Vorschau und Trockenlauf | `calendar.py`, `manager.py` | `test_calendar.py`, `test_automatic_scheduling.py` | V |
| REQ-MAN-01..08 | Start/Plan/Bearbeiten/Sortieren/Stop/Pause/Ändern/Überspringen | `services.py`, `manager.py` | `test_manual_requests.py`, `test_operations.py` | V |
| REQ-MAN-09..12 | außerhalb Automatikregeln, Bilanz, Wetterrichtlinie, keine Sprachexposition | `manager.py`, `entity.py` | `test_manual_requests.py`, `test_safety_inputs.py`, `test_init.py` | V |
| REQ-WEA-01..06 | priorisierte HA-/Weather-/Open-Meteo-Quellen und Messgrößen | `weather.py`, `config_flow.py` | `test_weather.py` | V |
| REQ-WEA-07..12 | direkte ET0, Vergleich, FAO-56, Modellfallback, Metadaten, Zeitraum | `weather.py`, `water_balance.py` | `test_weather.py`, `test_water_balance.py` | V/A |
| REQ-WEA-13..16 | Vorschauintervall, gemessener/prognostizierter Regen, wirksamer Regen | `manager.py`, `weather.py`, `water_balance.py` | `test_automatic_scheduling.py`, `test_phase5_multiweek.py` | V/A |
| REQ-WEA-17 | zeitlich begrenzter Wetterersatz und Aussetzung | `manager.py`, `weather.py` | `test_seasonal_weather_fallback_is_degraded_then_expires` | V/A |
| REQ-WEA-18..19 | Frost/Wind/Regen-Sperren und Regenabbruch | `manager.py` | `test_safety_inputs.py`, `test_qualification_scenarios.py` | V/H |
| REQ-WEA-20..22 | Initialzustand, begründete Korrektur, keine Selbstanpassung | `manager.py`, `services.py`, `models.py` | `test_operations.py`, `test_water_balance.py` | V/A |
| REQ-WEA-23..24 | unveränderliche historische Inputs und Beitragsaufschlüsselung | `models.py`, `manager.py`, `sensor.py` | `test_automatic_scheduling.py`, `test_operations.py` | V |
| REQ-MET-01..05 | kumulativ/Durchfluss/Impulse, Präferenz, Normalisierung, Kontinuität | `adapters.py`, `meter.py` | `test_adapters.py`, `test_meter.py` | V/H |
| REQ-MET-06..08 | Reset, physische Korrektur, unveränderte Historie | `meter.py`, `manager.py` | `test_meter.py`, `test_operations.py` | V/H |
| REQ-MET-09..10 | Durchfluss- und zonaler Zählerfallback | `executor.py`, `manager.py` | `test_executor.py`, `test_qualification_scenarios.py` | V/H |
| REQ-MET-11..15 | Anlagen-/Zonen-/unzugeordnet, Statistik/Energie, Perioden und Leck | `sensor.py`, `leak_monitor.py`, `manager.py` | `test_leak_monitor.py`, `test_operations.py`, `test_init.py` | V/H |
| REQ-FLO-01..07 | Durchflussprofil, Kalibrierung, Wintersperre, Bestätigung, Bilanz, Vorschläge | `manager.py`, `services.py` | `test_operations.py`, `test_safety_modes.py` | V/H |
| REQ-SAF-01..05 | exklusive Kontrolle, unerwartetes Öffnen/Schließen, Befehlsprüfung/Feedback | `executor.py`, `manager.py`, `adapters.py` | `test_executor.py`, `test_qualification_scenarios.py`, `test_phase5_multiweek.py` | V/H |
| REQ-SAF-06..12 | Zeiten, Reihenfolge, Unter-/Überfluss, Leck, Hauptventil, Grenzen | `executor.py`, `leak_monitor.py`, `manager.py` | `test_executor.py`, `test_leak_monitor.py`, `test_phase5_multiweek.py` | V/H |
| REQ-SAF-13 | unabhängiger Hardware-Abschalttimer | Setup-Warnung/Dokumentation | Feldprüfung erforderlich | H |
| REQ-SAF-14..18 | Neustart, persistente Sperren, keine normale Übersteuerung, begrenzte Wartung | `__init__.py`, `manager.py`, `storage.py` | `test_safety_modes.py`, `test_qualification_scenarios.py` | V/H |
| REQ-SAF-19..21 | nicht übersteuerbare Grenzen, Dead-Man, Wasserzuordnung | `manager.py` | `test_safety_modes.py`, `test_operations.py` | V/H |
| REQ-WIN-01..07 | Erinnerung, Wintersperre, Freigabe, Prüflauf und Wartungsaufgaben | `manager.py`, `services.py`, `sensor.py` | `test_safety_modes.py`, `test_operations.py` | V/H |
| REQ-UI-01..05 | Config/Options Flow, einfache/Expertenwerte, Schätzung, Plausibilität, Snapshot | `config_flow.py`, `profiles.py`, `manager.py` | `test_config_flow.py`, `test_profiles.py`, `test_qualification_scenarios.py` | P/A |
| REQ-UI-06 | verzögerte Aktivierung und unmittelbare Laufzeitsicherheit | `manager.py` | `test_config_reload_waits_for_idle_and_unload_cleans_runtime_tasks` | V |
| REQ-UI-07..09 | Karten, Editoren, mobil/Desktop, Entity-Defaults | `frontend/`, `sensor.py`, `binary_sensor.py` | `test_frontend.py`, `npm run check`, `npm run build` | P/R |
| REQ-UI-10..11 | Aktionen/Ereignisse und Benachrichtigungen | `services.py`, `events.py` | `test_operations.py` | V |
| REQ-UI-12 | portable Datei importieren/exportieren | `manager.py`, `config_flow.py`, `services.py` | `test_operations.py`, `test_config_flow.py` | V |
| REQ-UI-13..15 | Historie, Diagnose, Deutsch/Englisch | `manager.py`, `diagnostics.py`, `translations/` | `test_operations.py`, `test_frontend.py`, `test_init.py` | V |
| REQ-UI-16 | MIT intern; öffentlich erst nach Feldtest | `LICENSE`, Roadmap | Feldtest und Release fehlen | H/R |
| REQ-HIS-01..05 | begrenzte Detailhistorie, vollständiger Vorgang, Recorder, Auswertungen, Qualitätsarten | `models.py`, `manager.py`, `sensor.py` | `test_operations.py`, `test_init.py` | V |

## Sicherheitsanforderungen

| IDs | MUST aus `11_Safety.md` | Code | Tests/Nachweis | Status |
| --- | --- | --- | --- | --- |
| SAFE-PRI-01..09 | Priorität, Exklusivität, harte Grenzen, fail-closed, Neustart und Verbuchung | `executor.py`, `manager.py`, `storage.py` | `test_qualification_scenarios.py`, `test_phase5_multiweek.py` | V/H |
| SAFE-STA-01..02 | explizite Zustände und begrenzte Übergänge | `models.py`, `executor.py`, `manager.py` | `test_executor.py`, `test_manual_requests.py` | V |
| SAFE-PRE-01..13 | vollständiger Preflight einschließlich frischer Sensoren und Ablauf | `manager.py`, `adapters.py` | `test_safety_inputs.py`, `test_qualification_scenarios.py` | V/H |
| SAFE-SEQ-01..09 | Baseline, Haupt-/Zonenfolge, Stabilisierung, Überwachung, Abschluss | `executor.py` | `test_executor.py`, `test_phase5_multiweek.py` | V/H |
| SAFE-VAL-01..15 | unerwartete Zustände, Schließen, Sperren, Feedback und Alter | `executor.py`, `manager.py` | `test_qualification_scenarios.py`, `test_safety_inputs.py` | V/H |
| SAFE-FLO-01..13 | Unter-/Überfluss und Leerlaufleck | `executor.py`, `leak_monitor.py` | `test_executor.py`, `test_leak_monitor.py`, `test_phase5_multiweek.py` | V/H |
| SAFE-SEN-01..09 | keine Nullumdeutung, Fallback/Alter, Wetter- und Hardwareinterlocks | `adapters.py`, `weather.py`, `manager.py` | `test_adapters.py`, `test_weather.py`, `test_safety_inputs.py` | V/H/A |
| SAFE-NOM-01..06 | Betrieb ohne Messquellen nur zeitbasiert und sichtbar reduziert | `manager.py`, `executor.py`, `sensor.py` | `test_executor.py`, `test_operations.py` | V/H |
| SAFE-VOL-01..06 | Mengenfallback, harter Timeout, Schließbudget, Vorabschaltung, Istmenge | `executor.py` | `test_executor.py`, `test_qualification_scenarios.py` | V/H |
| SAFE-CTL-01..06 | Pause, Timeout, Stop, Überspringen, Fenster und globaler Stop | `manager.py`, `services.py` | `test_manual_requests.py`, `test_operations.py` | V |
| SAFE-RST-01..08 | Shutdown/Start schließen, unterbrechen, checkpointen, neu planen, Sperren halten | `__init__.py`, `manager.py`, `storage.py` | `test_init.py`, `test_qualification_scenarios.py` | V/H |
| SAFE-EST-01..04 | Not-Aus persistent, Quittierung geprüft, keine normale Umgehung, Frost hart | `manager.py`, `services.py` | `test_safety_modes.py`, `test_safety_inputs.py` | V/H |
| SAFE-MNT-01..10 | bewusstes Einzelziel, Frist, Hinweis, Dead-Man, keine Automatik, Cleanup | `manager.py`, `services.py` | `test_safety_modes.py`, `test_operations.py` | V/H |
| SAFE-WIN-01..05 | Wintererinnerung, Sperre, bewusste Freigabe und optionaler Prüflauf | `manager.py`, `services.py` | `test_safety_modes.py` | V/H |
| SAFE-HW-01 | mechanische/elektrische Grenze und unabhängiger Abschalttimer | Dokumentation/Setup-Warnung | realer Nachweis fehlt | H |

## Offene externe Gates

| Gate | Betroffene IDs | Abnahmekriterium |
| --- | --- | --- |
| AGR-01 Profilwerte | REQ-ZON-04..15, REQ-MOD-01..15, REQ-WEA-07..22, REQ-UI-01..05 | Profile, Schwellen, Kurven, Bodenparameter und Prognosewerte fachlich prüfen und freigeben |
| HW-01 Ventile/Relais | REQ-SAF-01..21, SAFE-VAL/FLO/RST/EST/MNT/HW | stromlose Stellung, Rückmeldung, Klemm-/Relaisfehler und Schließzeit an realer Hardware prüfen |
| HW-02 Messung | REQ-TGT-05..08, REQ-MET-01..15, REQ-FLO-01..07 | Auflösung, Impulsverlust, Reset, Latenz, Durchfluss und Nachlauf kalibrieren |
| HW-03 unabhängige Abschaltung | REQ-SAF-13, SAFE-HW-01 | unabhängigen Hardware-Abschalttimer installieren und mit Ventil unter Last prüfen |
| FIELD-01 beaufsichtigter Betrieb | alle H-markierten Anforderungen | sechs Zonen nacheinander anbinden und mehrere Wochen beaufsichtigt betreiben |
| UI-01 Browsergeräte | REQ-UI-07..09 | visuelle Bedienprüfung auf unterstütztem Mobil- und Desktop-Browser |
| REL-01 Validatoren | REQ-UI-16 | tatsächliche erfolgreiche HACS-/Hassfest-GitHub-Actions-Läufe; lokal nicht behauptet |
| REL-02 Feldtest vor HACS | REQ-UI-16 | privater Feldtest abgeschlossen und Ergebnisse eingearbeitet |

## Mindestversion und Manifestgrenze

Die freigegebene Mindestversion ist Home Assistant **2026.7.2**. `hacs.json`, README,
Roadmap und offene Punkte nennen denselben Wert. Das standardisierte HA-`manifest.json`
kennt kein Mindestversionsfeld. Ein Schlüssel wie `"homeassistant": "2026.7.2"` wäre dort
nicht schema-konform und würde gerade die Hassfest-Konsistenz verletzen; die maschinenlesbare
Installationsgrenze bleibt daher ausschließlich in `hacs.json`.
