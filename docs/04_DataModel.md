# Datenmodell

Die Namen beschreiben fachliche Modelle. Konkrete Python-Typen und Storage-Schemas werden während der Implementierung versioniert festgelegt.

## Bewässerungsanlage

- ID und Name
- optionales Hauptventil mit Feedback
- optionale Zählerquellen
- Automatikfreigabe und zeitliche Aussetzung
- Not-Aus, Sicherheitssperre und Wintersperre
- maximale Gesamtlaufzeit
- optionale Tages- und Wochenbudgets
- optionaler Wassertarif
- Schaltreihenfolge und Anlagenverzögerungen
- optionale Freigabe- und Sperrsensoren
- Notification-Ziele
- Status, aktive Teilgabe und Menge aller offenen Vorgänge

## Bewässerungszone

- ID, Name und Archivstatus
- genau ein logisches Ventil mit optionalem Feedback
- Automatikfreigabe und zeitliche Aussetzung
- Bewässerungsmodus: Bedarf oder Minimum
- normales Bewässerungsziel: Menge oder Zeit
- Zählerausfallstrategie
- minimales und maximales Intervall
- Mindestmenge für eine wirksame Bewässerung
- ein oder mehrere Bewässerungsfenster
- konfigurierte Zonenpriorität
- minimale und maximale Menge beziehungsweise Laufzeit
- Standardwerte für manuelle Aufträge
- Teilgabenlimit und Sickerpause
- Wettersperren und maximaler Prognoseaufschub
- aktueller Wasserbedarf und Ausgangszustand
- Pflanzen-, Boden-, Standort- und Bewässerungsprofil
- effektives zusammengesetztes Zonenprofil
- Regenfaktor und optionale vorausschauende Planung
- Durchflussprofil und Nachlaufkompensation
- optionale Bodenfeuchte- und Gerätesensoren
- optionale Mengenbudgets
- Priorität zwischen Pflanzenschutz und Wassersparen

## Teilfläche

Eine optionale Teilfläche zur Herleitung des gemeinsamen Zonenprofils:

- Pflanzenprofil
- Fläche oder Flächenanteil
- relative Ausbringungsrate
- optionaler Bodenfeuchtesensor

Teilflächen besitzen keine unabhängigen Aufträge, Vorgänge oder Wasserbilanzen.

## Bewässerungsfenster

- betroffene Wochentage oder Standard für alle Tage
- feste Start-/Endzeit oder Sonnenereignis mit Offset
- Unterstützung eines Intervalls über Mitternacht

## Pflanzenprofil

- Name und Herkunft: mitgeliefert oder benutzerdefiniert
- saisonale Pflanzenfaktorkurve
- empfohlene Wurzeltiefe
- empfohlene Ausschöpfungsgrenze
- optionale Hinweise und Gültigkeitsbereich

## Bodenprofil

- Name
- Feldkapazität
- Welkepunkt beziehungsweise nutzbare Speicherkapazität
- Infiltrations- und Drainageparameter
- empfohlene Ausschöpfungsgrenze

## Bewässerungsprofil

- Bewässerungsart
- Anwendungseffizienz
- empfohlene Teilgabe und Sickerpause
- Wind- und Regenempfindlichkeit

## Wetterquellenzuordnung

- Messgröße
- priorisierte HA-Sensoren beziehungsweise Weather-Entity
- optional Open-Meteo
- Einheiten- und Plausibilitätsgrenzen
- maximale Datenalter
- Fallbackregeln

## Wetterprognose

- Quelle und Ausgabezeitpunkt
- Gültigkeitsbeginn und -ende
- Akkumulationszeitraum der Niederschlagsmenge
- erwartete Menge und Wahrscheinlichkeit
- räumliche Herkunft beziehungsweise Standort
- Qualitäts- und Aktualitätsstatus

Prognosen sind Planungsdaten und keine bereits verbuchten Messungen.

## Wetterquellenfortschritt

- Quelle und Messgröße
- letzte eindeutig verbuchte Beobachtung beziehungsweise Zeitgrenze
- letzter kumulativer Rohwert
- Reset- und Quellenwechselstatus

Der Fortschritt verhindert doppelte oder verlorene Regen- und Wetterbeiträge nach Neustart, Quellenwechsel oder Zählerreset.

## Wasserbilanz

- Zone
- finales Defizit und Zeitpunkt
- vorläufiges Defizit
- maximal speicherbares Defizit
- letzter finalisierter Bilanzzeitraum
- letzte Beiträge aus ET, Regen und Bewässerung
- verwendete Modell- und Profilversionen
- Qualitätsstatus

## Bewässerungsauftrag

- ID, Zone und Quelle: automatisch oder manuell
- Erzeugungs-, Wunsch- und Ablaufzeit
- Zielart und Zielwert
- Priorität und Status
- Begründung und Berechnungssnapshot
- verbleibendes Ziel
- geplante Teilgaben
- Unterdrückung bis zur nächsten Gelegenheit

Automatische Aufträge verfallen am Ende der zugehörigen Bewässerungsgelegenheit oder werden durch eine Neuberechnung ersetzt. Die einmalige Unterdrückung einer Gelegenheit ist ein eigener persistenter Zustand und hängt nicht an der Lebensdauer des Auftrags.

## Manueller Bewässerungsplan

- ID und Name
- geordnete Liste zugehöriger Bewässerungsaufträge
- Erzeugungs-, Wunsch- und Ablaufzeit
- Status

Die Plan-ID und Reihenfolge bleiben über Neustarts stabil und erlauben gemeinsames Bearbeiten, Sortieren und Stornieren.

## Bewässerungsvorgang

- ID und zugehöriger Auftrag
- Zone und gemeinsames Ziel
- geplanter und tatsächlicher Start
- geplantes und tatsächliches Ende
- Status und Ergebnis
- Liste ausgeführter Teilgaben
- kumulierte Wasserabgabezeit
- maximale verstrichene Lebensdauer und Ablaufzeitpunkt
- gemessene und geschätzte Wassermenge
- Start- und Endwerte der Zählerquellen
- Qualitätsstatus der Messung
- Start-, Stop- und Fehlergründe
- verwendete Sicherheits- und Konfigurationsversion

## Teilgabe

- laufende Nummer innerhalb des Vorgangs
- Zielmenge beziehungsweise Zieldauer
- Start und Ende
- Ventil- und Zählerwerte
- gemessene, integrierte oder geschätzte Menge
- Ende durch Ziel, Fenster, Stop, Regen oder Fehler

## Zählerzustand

- konfigurierte Quellen und Umrechnungsfaktoren
- letzter Rohwert je Quelle
- fortlaufender interner Gesamtverbrauch
- physischer Korrekturoffset
- erkannte Quellen-Resets
- aktuelle Messqualität
- unzugeordneter Gesamtverbrauch

## Durchflussprofil

- Zone
- erwarteter Minimal-, Normal- und Maximaldurchfluss
- Messauflösung
- Nachlauf und Vorabschaltung
- Herkunft: manuell oder Kalibrierung
- Zeitpunkt und Messdaten der letzten Kalibrierung

## Sicherheitssperre

- Geltungsbereich: Zone oder Anlage
- Ursache und Schweregrad
- ausgelöst und quittiert am
- aktueller Zustand der Ursache
- Verweis auf Vorgang oder Wartungstest

## Wartungsaufgabe

- Anlage oder Zone
- Vorlage oder eigener Titel
- Intervall beziehungsweise Fälligkeit
- letzte Bestätigung
- nächste Fälligkeit
- Historie

## Konfigurationssnapshot

- Schemaversion
- fachlich relevante Konfiguration zum Zeitpunkt einer Berechnung oder Ausführung
- keine Zugangsdaten oder unredigierten Standortdetails
