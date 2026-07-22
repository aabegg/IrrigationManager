# IrrigationManager

IrrigationManager ist eine geplante Home-Assistant-Integration für intelligente, vollständig über die Benutzeroberfläche konfigurierbare Bewässerung privater Gärten.

- Repository: <https://github.com/aabegg/IrrigationManager>
- Fehler und Vorschläge: <https://github.com/aabegg/IrrigationManager/issues>

Unterstützte Mindestversion: **Home Assistant 2026.7.2**. Die Grenze steht in
`hacs.json`; Home Assistants `manifest.json` besitzt kein zulässiges Feld für eine
Mindestversion. Dort wird deshalb bewusst kein nicht standardkonformer Schlüssel ergänzt.

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

Private Release-Vorbereitung. Backend, geführter Config Flow, Sicherheitslogik,
Wetter- und Wasserbilanz, Scheduler sowie Lovelace-Karten sind implementiert und
simuliert. Die noch offenen Agronomie-, Hardware- und Feldtest-Gates sind in
[`docs/15_Traceability.md`](docs/15_Traceability.md) dokumentiert.

Die Messschicht unterstützt kumulative Volumenzähler, explizit umgerechnete
Impuls-/Zählwerte und direkte Durchflussraten. Portable Konfigurationen können über
die Options Flow-Vorschau oder die Aktion `irrigation_manager.import_config`
geprüft und mit expliziter Zuordnung übernommen werden. Der physische Zählerstand
wird mit `irrigation_manager.correct_physical_meter` korrigiert.

Ein portabler Export kann weiterhin mit Vorschau in eine bestehende Anlage übernommen
werden. Der normale Einrichtungsdialog bietet außerdem „Neue Anlage“ oder „Import“ an.
Der Import validiert Export und Entity-Neuzuordnung, prüft die exklusive Aktor- und
Rückmeldungszuordnung gegen alle vorhandenen Anlagen erneut unter einer Importsperre und
erzeugt den neuen Config Entry samt aller Zonen-Subentries atomar über Home Assistants
öffentliche Config-Flow-API. Für Anlage und Zonen entstehen neue Unique IDs.

## Lokale Validierung

```bash
uv sync --frozen --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest

npm --prefix custom_components/irrigation_manager/frontend ci
npm --prefix custom_components/irrigation_manager/frontend run check
npm --prefix custom_components/irrigation_manager/frontend run build
```

HACS- und Hassfest-Prüfungen laufen in `.github/workflows/home-assistant.yml`. Für diese
Repository-Validatoren existiert hier kein gleichwertiger installierter lokaler Runner;
ein erfolgreicher Remote-Lauf wird deshalb erst nach einem tatsächlichen GitHub-Actions-
Ergebnis behauptet.
