# IrrigationManager

IrrigationManager ist eine geplante Home-Assistant-Integration für intelligente, vollständig über die Benutzeroberfläche konfigurierbare Bewässerung privater Gärten.

## Projektziele

- Einrichtung vollständig über die Home-Assistant-UI
- ein Konfigurationseintrag je physischer Bewässerungsanlage
- beliebig viele sequenziell ausgeführte Bewässerungszonen
- Hauptventil-Unterstützung
- intelligenter Scheduler
- wissenschaftlich nachvollziehbare Wetter- und Wasserbilanz
- zeit- oder mengengesteuerte Bewässerung
- Wasserverbrauch pro Zone
- Historie vergangener Bewässerungsvorgänge
- Integration in das Home-Assistant-Energie-Dashboard
- fertige Dashboard-Karten und offene Rohdaten
- sichere und nachvollziehbare Ventilsteuerung

## Geplante Architektur

- Backend: Python als Home-Assistant-Custom-Integration
- Frontend: TypeScript für eigene Lovelace-Karten
- Installation: HACS-kompatibel
- Konfiguration: Config Flow und Options Flow
- Datenhaltung: Home-Assistant-Storage plus Recorder-/Statistik-Entitäten

## Dokumentation

Die fachliche und technische Planung befindet sich im Ordner [`docs`](docs/).

## Projektstatus

Spezifikationsphase. Der funktionale Zielumfang wurde in einer Grill-Session konkretisiert; Implementierung und Tests stehen noch aus.
