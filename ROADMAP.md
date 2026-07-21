# Roadmap

Die Implementierung erfolgt in vertikalen, simulierbaren Stufen. Keine Zwischenstufe wird für unbeaufsichtigten Betrieb an der realen Anlage freigegeben. Der private Feldtest beginnt erst, wenn der vollständige vereinbarte Erstumfang implementiert und qualifiziert ist.

## Phase 0: Spezifikation

- [x] Zielgruppe und Produktgrenze festlegen
- [x] Topologie und Zweck der persönlichen Referenzanlage dokumentieren
- [x] Funktionsumfang konsolidieren
- [x] Domänensprache festlegen
- [x] zentrale Architekturentscheidungen dokumentieren
- [x] Scheduler-, Wetter-, Zähler- und Sicherheitsverhalten spezifizieren
- [ ] konkrete Profilwerte und Standardgrenzen fachlich validieren
- [ ] unterstützte Home-Assistant-Mindestversion festlegen
- [ ] Akzeptanzszenarien aus den Anforderungen ableiten

## Phase 1: Fundament und Simulation

- Custom-Integration-Grundgerüst und HACS-Struktur
- Config Entry pro Bewässerungsanlage
- Zonen als Config Subentries
- versionierter Integrationsspeicher und Migrationstest
- stabile Unique IDs und Gerätetopologie
- Simulator für Ventile, Zähler, Wetter und Fehler
- Config Flow für Anlage, Quellen und einfache Zonen
- Trockenlauf ohne Aktorzugriffe

## Phase 2: Sichere Ausführung und Messung

- exklusiver Executor-Zustandsautomat
- Hauptventil sowie `valve`- und `switch`-Zonen
- optionales Feedback-Entity
- Zeitsteuerung und harte Laufzeitgrenzen
- kumulatives Volumen, Durchfluss und Rohimpulse
- Zählerkontinuität und physische Korrektur
- eindeutige Zonen- und unzugeordnete Verbrauchsbilanz
- Mengensteuerung mit Fallbacks
- geführte Durchfluss- und Nachlaufkalibrierung
- Unter-/Überdurchfluss und Leckage
- Stop, Not-Aus, Pause und Neustartverhalten
- Fehler- und Ausfalltests ohne reale Hardware

## Phase 3: Scheduler und Wasserbilanz

- minimale und maximale Bewässerungsintervalle
- mehrere zonenspezifische Fenster einschließlich Sonnenzeiten
- Bedarfs- und Mindestbewässerung
- automatische und persistente manuelle Aufträge
- Priorisierung, Verfall, Überspringen und Kalender
- Teilgaben und Sickerpausen
- Budgets und Prognoseaufschub
- lokale Wetterquellen und Weather-Entities
- direkter optionaler Open-Meteo-Zugriff
- direkte ET0-Quelle und Vergleich
- FAO-56 sowie validierte Fallbackmodelle
- Pflanzen-, Boden-, Standort- und Bewässerungsprofile
- saisonale Kurven und zusammengesetzte Zonenprofile
- Bodenfeuchterollen
- finale und vorläufige Wasserbilanz
- vollständige Berechnungserklärung

## Phase 4: Bedienung und Betrieb

- vollständiger Options Flow und Expertenmodus
- Auftragsliste und einmalige Mehrzonenpläne
- Aktionen und strukturierte Ereignisse
- persistente und optionale mobile Benachrichtigungen
- Übersichtskarte mit grafischem Editor
- Zonenkarte mit grafischem Editor
- Recorder- und Langzeitstatistiken
- Energie-Dashboard-Wassersensoren
- Verbrauchs- und Bedarfsdeckungsansichten
- Konfigurationsimport und -export
- CSV- und JSON-Historienexport
- vollständiger Diagnoseexport
- Wintererinnerung, Wintersperre und Wiederinbetriebnahme
- konfigurierbare Wartungsaufgaben und Wartungstest
- Deutsch und Englisch

## Phase 5: Qualifikation vor realer Anlage

- Referenztests für ET-Modelle und Einheiten
- deterministische Langzeitsimulation trockener und regnerischer Perioden
- Fault Injection für alle Ventil-, Zähler-, Sensor- und Neustartfehler
- Tests für Zeitfenster über Mitternacht und Zeitumstellung
- Tests für Quellen-Reset, grobe Impulse und Messlatenz
- Tests für konkurrierende manuelle und automatische Aufträge
- Tests für Teilgaben, Pausen, Budgets und Prognoseaufschub
- Tests für Config/Options Flow, verzögerte Konfigurationsaktivierung und Migrationen
- Tests für Aktionen, Ereignisse, Kalender und persistente manuelle Aufträge
- Tests für Karten-Grundfunktionen und grafische Editoren
- Tests für Benachrichtigungen, Winter-, Wartungs- und Dead-Man-Abläufe
- Tests für Statistik, Energie-Dashboard-Sensoren, Import und Exporte
- Prüfung der deutschen und englischen Benutzertexte
- Sicherheitsreview gegen `docs/11_Safety.md`
- vollständige Abnahme aller Anforderungen aus `docs/02_Requirements.md`
- vollständiger Abnahmelauf mit simulierten sechs Referenzzonen
- keine bekannten Fehler mit Risiko für unbegrenzten Wasserfluss

## Phase 6: Privater Feldtest

- vorhandene Irrigation-Unlimited-/Smart-Irrigation-Steuerung kontrolliert ablösen
- reale Entities erfassen und vor Umschaltung alle Verbraucher prüfen
- Hauptventil und eine Zone unter Aufsicht anbinden
- Durchfluss, Nachlauf und Vorabschaltung kalibrieren
- alle sechs Zonen nacheinander anbinden
- Hardware-Abschalttimer einrichten oder verbleibende Warnung bewusst akzeptieren
- mehrere Wochen beaufsichtigt betreiben
- Profil- und Grenzwertvorschläge anhand Messungen verbessern

## Phase 7: Öffentliches HACS-Release

- Ergebnisse des Feldtests einarbeiten
- MIT-Lizenz und Repository-Metadaten
- Benutzer-, Installations- und Entwicklerdokumentation
- Release- und Migrationsprozess
- HACS- und Hassfest-Validierung
- öffentliche stabile Version 1.0

## Spätere Erweiterung

- Zisterne und Brunnen
- Pumpenfreigabe
- Füllstands- und Druckbedingungen
- Umschaltung zwischen Wasserquellen
