# IrrigationManager

IrrigationManager ist eine Home-Assistant-Integration für eine vollständig über die Benutzeroberfläche konfigurierbare Bewässerung privater Gärten.

- Repository: <https://github.com/aabegg/IrrigationManager>
- Fehler und Vorschläge: <https://github.com/aabegg/IrrigationManager/issues>

Unterstützte Mindestversion: **Home Assistant 2026.7.2**. Die Grenze steht in
`hacs.json`; Home Assistants `manifest.json` besitzt kein zulässiges Feld für eine
Mindestversion. Dort wird deshalb bewusst kein nicht standardkonformer Schlüssel ergänzt.

## Projektziele

- Einrichtung vollständig über die Home-Assistant-UI
- ein Konfigurationseintrag je physischer Bewässerungsanlage
- beliebig viele sequenziell ausgeführte Bewässerungszonen
- optionales Hauptventil
- einfache Wochenpläne mit gemeinsamem Basissoll, einem Bewässerungsfenster pro Wochentag und optionalen Tagesabweichungen
- getrennte Betriebs- und Automatikfreigaben für Anlage und Zonen
- zeit- oder mengengesteuerte Bewässerung
- optionale kumulative oder impulsbasierte Wassermessung
- Laufzeit- beziehungsweise gemessene Wasserstatistiken für Anlage und Zonen
- Historie vergangener Bewässerungsvorgänge
- anlagenweiter Not-Aus und persistente Sicherheitssperre
- optionale Durchflusskalibrierung aus der Wassermessung
- optionales Pflanzen- und Standortmodell mit Teilflächen und qualitativer Empfehlung
- fertige Dashboard-Karten und offene Rohdaten
- sichere und nachvollziehbare Ventilsteuerung

## Architektur

- Backend: Python als Home-Assistant-Custom-Integration
- Frontend: TypeScript für eigene Lovelace-Karten
- Installation: HACS-kompatibel
- Konfiguration: Config Flow und Options Flow
- Datenhaltung: Home-Assistant-Storage plus Recorder-/Statistik-Entitäten

## Dokumentation

Die fachliche und technische Planung befindet sich im Ordner [`docs`](docs/).

Für Einrichtung und Bedienung stehen folgende deutschsprachige Benutzerunterlagen zur
Verfügung:

- [Schritt-für-Schritt-Bedienungsanleitung](docs/20_Bedienungsanleitung.md)
- [Funktionsübersicht mit Pflicht- und optionalen Funktionen](docs/21_Funktionsuebersicht.md)
- [Prüfcheckliste für Konfiguration und UI](docs/22_UI_Pruefcheckliste.md)

Die mitgelieferten Lovelace-Karten, ihre grafischen Editoren und Beispiele sind unter
[`custom_components/irrigation_manager/frontend`](custom_components/irrigation_manager/frontend/README.md)
dokumentiert. Das Frontend-Modul wird von der Integration automatisch registriert.

## Projektstatus

Release Candidate. Ausschließlich [`docs/17_Neukonzept.md`](docs/17_Neukonzept.md)
definiert den verbindlichen Umfang und die weitere Entwicklung. Alle älteren
Anforderungen, Roadmaps, ADRs und Dokumente `01` bis `16` sind fachlich irrelevantes
Archivmaterial und dürfen nicht zur Ergänzung des Neukonzepts verwendet werden.
Bestehende Einträge aus dem früheren Funktionsmodell werden absichtlich deaktiviert und
müssen in den Einstellungen neu validiert werden. Alte Wetter-, Bedarfs-, Profil-,
Wartungs-, Winter-, Archiv- und Sickerpausenkonfigurationen werden nicht übernommen.
Das neue Pflanzen- und Standortmodell ist davon unabhängig, rein optional und verändert
ein bestätigtes Basissoll niemals automatisch.

Die Messschicht unterstützt kumulative Volumenzähler und explizit umgerechnete
Impulszähler. Der abgeglichene physische Zählerstand kann in den Anlageneinstellungen
oder über `irrigation_manager.correct_physical_meter` korrigiert werden. Jede Korrektur
wird getrennt vom Verbrauch mit altem und neuem Stand, Differenz, Zeitpunkt und
optionalem Grund protokolliert.

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
