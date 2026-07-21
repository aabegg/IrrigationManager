# Architektur

## Systemgrenze

Irrigation Manager ist eine eigenständige Home-Assistant-Custom-Integration. Ein Config Entry besitzt genau eine Bewässerungsanlage mit optionalem Hauptventil, optionalem Wasserzähler und beliebig vielen Zonen als Config Subentries.

Irrigation Unlimited, Smart Irrigation und NeverDry sind keine Laufzeitabhängigkeiten. Vorhandene Aktoren, Sensoren und Weather-Entities werden über ihre Home-Assistant-Schnittstellen eingebunden.

## Backend

Python-Custom-Integration unter:

```text
custom_components/irrigation_manager/
```

Geplante Verantwortungsbereiche:

- `__init__.py`: Config-Entry-Lebenszyklus und Plattformweiterleitung
- `manifest.json`: Integrationsmetadaten und Abhängigkeiten
- `const.py`: technische Konstanten
- `config_flow.py`: Einrichtung einer Anlage
- `options_flow.py`: spätere Anlagen- und Experteneinstellungen
- `models.py`: unveränderliche Konfiguration und fachliche Laufzeitmodelle
- `coordinator.py`: Entity-Zustände und Aktualisierungen koordinieren
- `scheduler.py`: Aufträge erzeugen, priorisieren, verschieben und verfallen lassen
- `executor.py`: genau einen Bewässerungsvorgang sicher ausführen
- `safety.py`: Preflight, Sperren, Ventil- und Durchflussüberwachung
- `water_balance.py`: persistente Wasserbilanz pro Zone
- `evapotranspiration.py`: ET0-Modelle und Qualitätsbewertung
- `weather.py`: HA-Quellen, Open-Meteo und Quellenprioritäten
- `meter.py`: Zählernormalisierung, Kontinuität, Durchfluss und Zuordnung
- `calibration.py`: geführte Durchfluss- und Nachlaufkalibrierung
- `maintenance.py`: Winterstatus, Prüfläufe und Wartungsaufgaben
- `history.py`: begrenzte Detailhistorie und Exporte
- `storage.py`: versionierter persistenter Zustand und Migrationen
- `calendar.py`: schreibgeschützte Planansicht
- `sensor.py`, `binary_sensor.py`, `switch.py`, `number.py`, `select.py`, `button.py`: Home-Assistant-Entities
- `diagnostics.py`: redigierter Diagnoseexport

Die konkrete Dateiaufteilung darf beim Implementieren kleiner beginnen. Maßgeblich sind die Verantwortungsgrenzen, nicht eine Datei pro Begriff.

## Verantwortungsregeln

### Scheduler

- erzeugt und priorisiert Bewässerungsaufträge
- besitzt keine direkten Aktorzugriffe
- berücksichtigt Fenster, Intervalle, Prognosen, Budgets und Sperren
- plant nach jeder relevanten Änderung deterministisch neu

### Executor

- ist die einzige Komponente, die Haupt- und Zonenventile schaltet
- führt zu jeder Zeit höchstens eine aktive Teilgabe aus
- bildet einen expliziten Zustandsautomaten
- meldet jede Teilgabe und jedes Ergebnis an Bilanz, Zähler und Historie

Ein Bewässerungsvorgang darf während einer Sickerpause ruhen, während der Executor eine Teilgabe eines anderen Vorgangs ausführt. Mehrere Vorgänge können deshalb fachlich offen sein, aber nie gleichzeitig Wasser abgeben.

### Safety

- prüft Voraussetzungen vor und während jeder Ausführung
- besitzt Vorrang vor Scheduler und manuellen Anforderungen
- verwaltet persistente Sicherheits- und Wintersperren
- erlaubt die Übersteuerung ausdrücklich benannter Beobachtungsprüfungen nur in einem beaufsichtigten Wartungstest

### Water Balance

- berechnet ohne Seiteneffekte aus validierten Eingaben
- trennt finale Bilanzwerte von vorläufigen Prognosen
- verändert historische Berechnungssnapshots niemals rückwirkend
- erzeugt eine vollständige Beitragsaufschlüsselung

### Meter

- normalisiert kumuliertes Volumen, Durchfluss und Rohimpulse
- hält einen fortlaufenden internen Anlagenzähler über Quellen-Resets hinweg
- ordnet gemessene Mengen genau einem Vorgang oder „unzugeordnet“ zu
- stellt Messqualität und verwendeten Fallback explizit bereit

## Frontend

TypeScript-Projekt unter:

```text
frontend/
```

Übersichts- und Zonenkarte werden mit derselben HACS-Installation ausgeliefert. Beide Karten besitzen einen grafischen Editor. Die Konfiguration der Anlage bleibt im Config/Options Flow; Karten sind Bedien- und Anzeigeoberflächen, keine zweite Konfigurationsquelle.

## Externe Schnittstellen

- Home-Assistant-Entities für alle stabilen Kernwerte
- standardmäßig deaktivierte Diagnoseentities für technische Details
- Aktionen für vollständige Bedienung und kontrollierte Korrekturen
- strukturierte Ereignisse für Start, Ende, Teilgabe, Überspringen und Fehler
- schreibgeschützter Kalender für geplante Aufträge
- Recorder und Langzeitstatistiken für Messreihen
- optional direkter Open-Meteo-Zugriff
- generische Wetter- und Sensorquellen über Home Assistant

## Nebenläufigkeit

- Pro Bewässerungsanlage läuft höchstens eine Teilgabe gleichzeitig; weitere Vorgänge dürfen ausschließlich in einer Sickerpause warten.
- Mehrere unabhängige Config Entries dürfen parallel arbeiten.
- Jeder Vorgang verwendet einen unveränderlichen Konfigurationssnapshot.
- Konfigurationsänderungen werden während offener Vorgänge vorgemerkt und erst im vollständigen Leerlauf aktiviert.
- Schaltbefehle laufen ausschließlich seriell über den Executor.

## Erweiterungsgrenze

Zisterne, Brunnen, Pumpenfreigabe und Quellenumschaltung sind später als eigener Wasserquellenbereich ergänzbar. Der Erstumfang modelliert eine verfügbare Wasserzufuhr mit optionalem Hauptventil.
