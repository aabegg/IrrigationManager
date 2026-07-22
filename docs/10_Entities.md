# Entitäten und Schnittstellen

Exakte Entity IDs werden aus stabilen Unique IDs erzeugt und sind nicht Teil des fachlichen Vertrags. Kernwerte sind standardmäßig aktiv; technische Diagnosewerte standardmäßig deaktiviert.

## Gerätetopologie

- ein Home-Assistant-Gerät pro Bewässerungsanlage
- ein untergeordnetes Gerät pro Bewässerungszone
- archivierte Zonen bleiben für Historie und Verbrauch identifizierbar

## Anlage

### Status

- Anlagenstatus
- Automatikfreigabe
- Not-Aus
- Sicherheitssperre
- Wintersperre
- Wartungsmodus
- aktuelle Zone
- aktive Teilgabe
- offene Bewässerungsvorgänge
- nächste Zone
- nächster geplanter Start
- Restziel und Restlaufzeit
- Anzahl wartender Aufträge

### Wasser

- fortlaufender Gesamtverbrauch
- unzugeordneter Verbrauch
- heutiger, wöchentlicher, monatlicher und jährlicher Verbrauch
- aktueller Durchfluss
- Messqualität
- physischer korrigierter Zählerstand
- optionale Kosten

Gesamt-, Zonen- und unzugeordnete Verbrauchssensoren sind monotone
`total_increasing`-Wassersensoren in Litern. `Heute`, `Woche`, `Monat` und `Jahr`
sind abgeleitete Periodensensoren. Aktueller Durchfluss, korrigierter physischer
Zählerstand und Messqualität werden separat veröffentlicht.

### Bedienung

- globaler Stop
- Not-Aus
- Not-Aus quittieren
- neu planen
- Trockenlauf
- Winterstatus setzen beziehungsweise freigeben
- Anlagenprüflauf starten

## Zone

### Status und Planung

- Automatikfreigabe
- zeitliche Aussetzung bis
- archiviert
- Status
- aktuelle oder nächste Teilgabe
- nächster Auftrag
- erwarteter Start
- erlaubtes Intervall
- aktuelle Priorität
- Bewässerung erforderlich

### Wasserbilanz

- finales und vorläufiges Defizit
- Referenzverdunstung
- Pflanzenverdunstung
- wirksamer Regen
- erwarteter Regenaufschub
- Zielmenge
- Zieldauer
- Modell und Qualitätsstatus
- letzte Bilanzaktualisierung

### Verbrauch

- fortlaufender Zonenverbrauch
- letzte gelieferte Menge
- letzte Dauer
- letzte wirksame Bewässerung
- Bedarfsdeckung
- erwarteter und tatsächlicher Durchfluss
- Durchflussabweichung

### Bedienung

- manuellen Auftrag mit Menge oder Zeit erstellen
- Pause und Fortsetzen
- den zugehörigen aktiven oder in Sickerpause wartenden Vorgang stoppen
- Vorgang stoppen und aktuelle Gelegenheit überspringen
- einmal überspringen
- Bilanz korrigieren
- Kalibrierung starten

## Technische Diagnoseentities

Standardmäßig deaktiviert:

- einzelne Wettereingänge und Datenalter
- ET0-Vergleichswerte je Modell
- Rohzählerstände und Baselines
- integrierte und geschätzte Ersatzmengen
- Ventillatenzen
- Vorabschaltung und Nachlauf
- Teilflächenbeiträge zum effektiven Profil
- Sperr- und Preflight-Details

## Kalender

Ein schreibgeschützter Kalender zeigt automatische und terminierte manuelle Aufträge. Kalenderänderungen sind nicht die Konfigurationsschnittstelle.

## Aktionen

Mindestens:

- manuellen Einzel- oder Mehrzonenauftrag erstellen
- Auftrag bearbeiten, sortieren und stornieren
- Vorgang pausieren, fortsetzen und gezielt stoppen, auch während einer Sickerpause
- Stop+Überspringen
- global stoppen und Not-Aus auslösen
- Sperre quittieren
- Automatik zeitlich aussetzen
- neu planen und Trockenlauf ausführen
- Bilanz setzen, erhöhen oder reduzieren
- Zählerstand korrigieren
- Kalibrierung und Wartungstest starten
- Winterstatus setzen und Anlagenprüflauf starten
- Konfiguration und Historie exportieren
- Konfigurationsimport prüfen und mit Hash ausdrücklich übernehmen

Alle schreibenden Aktionen validieren Ziel, Einheiten, Grenzen und aktuellen Anlagenzustand.

`correct_physical_meter` setzt ausschließlich den zukünftigen Anzeigeoffset.
`import_config` ist standardmäßig ein Trockenlauf und benötigt für das Anwenden
`confirm_overwrite`, den Vorschau-`config_hash` sowie explizite Entity- und
Zonenzuordnungen.

## Ereignisse

Strukturierte Ereignisse für:

- Auftrag erzeugt, geändert, storniert oder verfallen
- Vorgang gestartet, pausiert, fortgesetzt und beendet
- Teilgabe gestartet und beendet
- automatische Bewässerung übersprungen oder verschoben
- Ventilbefehl und Rückmeldefehler
- Durchflussabweichung und Leckage
- Sicherheits-, Not-Aus- und Wintersperre
- Kalibrierungs- und Wartungsergebnis
- Bilanz- und Zählerkorrektur

Eventdaten enthalten stabile IDs, Gründe, Ziel, Messwerte, Qualitätsstatus und Kontext. Zugangsdaten oder genaue Standortdaten werden nicht veröffentlicht.

## Benachrichtigungen

- persistente HA-Benachrichtigung für relevante Fehler und Wartung
- optionale Notify-Ziele je Ereignistyp und Schweregrad
- Deduplizierung wiederholter identischer Meldungen
- konkrete Ursache, betroffene Zone und empfohlene Handlung

## Statistik

Kumulative Anlagen-, Zonen- und unzugeordnete Wassersensoren sind für Home-Assistant-Langzeitstatistik und Energie-Dashboard ausgelegt. Abgeleitete Periodenwerte werden nicht als konkurrierende manuell geführte Gesamtsummen gespeichert.
