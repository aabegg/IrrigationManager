# UI und Config Flow

## Leitlinien

- keine YAML-Pflicht
- verständliche Fragen statt agronomischer Fachbegriffe
- Vorschläge mit Begründung
- sichere Standardwerte
- progressive Offenlegung von Expertenoptionen
- Plausibilitätsprüfung vor Aktivierung
- dieselbe Konfiguration ist niemals parallel in Karte und Config Flow editierbar

## Einrichtung einer Anlage

### Schritt 1: Anlage

- Name
- optionales Hauptventil
- Aktortyp `valve` oder `switch`
- optionales Feedback-Entity
- maximale Gesamtlaufzeit
- optionale Budgets und Tarif
- Schaltreihenfolge und globale Verzögerungen

### Schritt 2: Wasserzähler

- kumulatives Volumen
- optionaler Durchflusssensor
- alternativ Rohimpuls-/Zähl-Entity und Umrechnungsfaktor
- erkannte Einheiten, Geräteklasse und Auflösung
- aktueller physischer Zählerstand
- Betrieb ohne Zähler mit sichtbaren Einschränkungen

### Schritt 3: Wetter

- lokale Sensoren und Weather-Entity
- optional Open-Meteo
- Quelle und Priorität je Messgröße
- direkte ET0-Quelle oder eigene Berechnung
- Fallbackdauer und Datenalter
- Vergleichsansicht verfügbarer Quellen

### Schritt 4: Zonen

Wiederholbarer Subentry-Flow:

- Name und Ventil
- optionales Feedback und Gerätesensoren
- Pflanzen-, Boden-, Standort- und Bewässerungsprofil
- Fläche oder geführte Schätzung
- optionale Teilflächen
- Regenfaktor
- Bewässerungsmodus
- Mengen- oder Zeitsteuerung
- Mindest- und Maximalintervall
- Bewässerungsfenster
- Grenzen, Teilgaben und Sickerpause
- Zählerausfallstrategie
- Wettersperren und Prognoseregeln
- optionale Bodenfeuchtesensoren

### Schritt 5: Sicherheit

- Maximalzeiten und Maximalmengen
- Ventil- und Stabilisierungstimeouts
- Durchflussgrenzen
- Leckageschwelle
- externe Freigabe-/Sperrsensoren
- Notification-Ziele
- Hinweis und Bestätigung zum empfohlenen Hardware-Abschalttimer

### Schritt 6: Prüfung

- vollständige Zusammenfassung
- fehlende oder inkonsistente Entities
- Einheiten- und Auflösungsprüfung
- geschätzte Zielmengen und Laufzeiten
- mögliche Fensterkonflikte
- Sicherheitswarnungen
- optionaler Trockenlauf
- optionaler Kalibrierungs- und Anlagenprüflauf

## Profile

- Mitgelieferte Profile bleiben unverändert und versioniert.
- Benutzer kann ein Profil kopieren und anpassen.
- Profiländerungen zeigen betroffene Zonen.
- Historische Vorgänge behalten ihren Berechnungssnapshot.
- Zusammengesetzte Teilflächen erzeugen ein gemeinsames effektives Zonenprofil.

## Options Flow

- Anlage und Quellen bearbeiten
- Zonen hinzufügen, bearbeiten, archivieren und wiederherstellen
- Profile verwalten
- Zählerstand korrigieren
- Durchfluss kalibrieren
- Bilanz setzen oder relativ korrigieren
- Automatik zeitlich aussetzen
- Winterstatus verwalten
- Wartungsaufgaben verwalten
- Notify-Ziele und Exporte konfigurieren
- Expertenmodus aktivieren

Jeder Vorgang verwendet seinen beim Preflight validierten Konfigurationssnapshot. Änderungen während offener Vorgänge werden vorgemerkt und erst im vollständigen Leerlauf wirksam. Unmittelbare Eingriffe erfolgen über Stop, Not-Aus oder eine Sicherheitssperre.

## Geführte Kalibrierung

1. Zone und Testdauer auswählen
2. Sicherheitsprüfung und ausdrückliche Bestätigung
3. Haupt- und Zonenventil kontrolliert schalten
4. Durchfluss, Volumen, Latenz und Nachlauf messen
5. Normalbereich und Vorabschaltung vorschlagen
6. Wasser als reale Bewässerung verbuchen
7. Werte prüfen und explizit übernehmen oder verwerfen

## Wartungsmodus

- zeitlich begrenzt und deutlich sichtbar
- keine automatische Bewässerung
- genau ein beaufsichtigter Test
- Übersteuerung von Feedback-, Durchfluss-, Wetter- und externen Sensorprüfungen nur innerhalb dieses Tests
- Not-Aus, Wintersperre, Ein-Zonen-Ausführung, Wartungstimeout und Benutzer-Stop bleiben wirksam
- regelmäßige Dead-Man-Bestätigung in der UI
- ausbleibende Bestätigung oder verlorene Verbindung beendet den Test und schließt alle Ventile
- Wasser wahlweise einer Zone oder unzugeordnet verbuchen
- automatisches Ende und sichere Ventilschließung

## Karten

### Übersichtskarte

- Anlagenzustand und Sperren
- aktive Teilgabe, Fortschritt und weitere offene Vorgänge
- wartende und geplante Aufträge
- nächste Bewässerungen
- heutiger und monatlicher Verbrauch
- Wetter- und Modellqualität
- Stop und Not-Aus
- Winter- und Wartungshinweise

### Zonenkarte

- Automatikfreigabe und zeitliche Aussetzung
- Wasserbedarf und vollständige Berechnungserklärung
- nächster Auftrag und zulässige Fenster
- manuelle Menge oder Dauer
- Start, Pause, Fortsetzen, Stop und Stop+Überspringen
- Verbrauch und Bedarfsdeckung
- Durchflussprofil und Warnungen
- letzte Vorgänge

### Grafischer Karteneditor

- Anlage beziehungsweise Zone auswählen
- sichtbare Kennzahlen und Aktionen wählen
- kompakte und ausführliche Darstellung
- responsive Vorschau

## Import und Export

- Konfiguration als versionierte portable Datei
- Vorschau und Entity-Neuzuordnung vor Import
- CSV- und JSON-Export der Historie
- kein automatischer Import konkurrierender Integrationen

Der Import steht als Aktion und im Options Flow zur Verfügung. Er führt zuerst
immer einen Trockenlauf mit Vorschau aus. Entity-IDs und Zonen müssen ausdrücklich
neu zugeordnet werden. Das Überschreiben einer vorhandenen Anlage benötigt eine
Bestätigung und den Hash genau der zuvor geprüften Konfiguration; bei zwischenzeitlicher
Änderung wird abgebrochen. Der Import erzeugt oder übernimmt keine Konfiguration
anderer Integrationen.

Der Historienexport ist auf höchstens 1000 Vorgänge begrenzt. JSON und CSV enthalten
den bereinigten Auftrag, Vorgang, persistierte Teilgaben, Berechnungssnapshot,
Quelle, Messherkunft, Messqualität und Warnungen. Ventil-Entities und Zonennamen
werden nicht exportiert.

## Sprache und Barrierearmut

- vollständige deutsche und englische Übersetzung
- SI- und Home-Assistant-Einheitenkonvertierung
- keine Farbe als einziges Statussignal
- verständliche Fehlertexte mit konkreter Handlungsempfehlung
