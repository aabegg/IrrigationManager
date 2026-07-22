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

Die mitgelieferten Lovelace-Karten, ihre grafischen Editoren und Beispiele sind unter
[`custom_components/irrigation_manager/frontend`](custom_components/irrigation_manager/frontend/README.md)
dokumentiert. Das Frontend-Modul wird von der Integration automatisch registriert.

## Projektstatus

Aktive Entwicklung. Backend, Config Flow und die ersten Lovelace-Karten sind implementiert und getestet; der in den Fachdokumenten beschriebene Gesamtumfang ist noch nicht vollständig umgesetzt.

Die Messschicht unterstützt kumulative Volumenzähler, explizit umgerechnete
Impuls-/Zählwerte und direkte Durchflussraten. Portable Konfigurationen können über
die Options Flow-Vorschau oder die Aktion `irrigation_manager.import_config`
geprüft und mit expliziter Zuordnung übernommen werden. Der physische Zählerstand
wird mit `irrigation_manager.correct_physical_meter` korrigiert.
