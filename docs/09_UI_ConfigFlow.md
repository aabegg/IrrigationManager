# UI und Config Flow

## Leitlinien

- keine YAML-Pflicht
- verständliche Fragen statt agronomischer Fachbegriffe
- Vorschläge mit Begründung
- sichere Standardwerte
- progressive Offenlegung von Expertenoptionen
- Plausibilitätsprüfung vor Aktivierung
- dieselbe Konfiguration ist niemals parallel in Karte und Config Flow editierbar

## Implementierter Bedienmodus

Config Flow, Zonen-Subentry-Flow und Options Flow bieten einen geführten und einen
ausdrücklichen Expertenpfad. Der geführte Pfad verwendet ausschließlich Home-Assistant-Formulare
und Selektoren. Er sammelt Antworten in kleinen Schritten und übersetzt sie erst bei der Prüfung in
dasselbe persistierte Datenmodell wie der Expertenpfad. Dadurch bleiben bestehende Exporte,
Migrationen und Expertenfelder kompatibel. Bei einer geführten Bearbeitung werden nicht sichtbare
Expertenfelder aus dem vorhandenen Config Entry beziehungsweise Subentry übernommen und nicht
zurückgesetzt.

Unbekannte Antworten bleiben konservativ: Eine unbekannte Fläche verwendet sichtbar 1 m² als
vorläufigen Platzhalter, eine geschätzte Ausbringungsrate dient nur der Vorschau, und beides erteilt
keine Automatikfreigabe. Automatik benötigt bestätigte Profilannahmen und einen gemessenen
Durchflussbereich. Zusätzlich muss bei geführten Anlagen der Hinweis bestätigt werden, dass
eine unabhängige Hardware-Abschaltung den Wasserfluss auch bei Software-, Funk- oder
Home-Assistant-Ausfall begrenzt. Importierte und migrierte Anlagen erhalten diese Bestätigung
niemals automatisch; ihre globale und zonenspezifische Automatikfreigabe wird entfernt, bis die
Sicherheitsbestätigung lokal erfolgt und die gewünschte Freigabe erneut gesetzt wird.

## Einrichtung einer Anlage

### Schritt 1: Anlage

- Zweck und Name
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
- erkannte Geräteklasse und Einheit werden verständlich zusammengefasst

### Schritt 3: Wetter

- lokale Sensoren und Weather-Entity
- optional Open-Meteo
- Quelle und Priorität je Messgröße
- direkte ET0-Quelle oder eigene Berechnung
- Fallbackdauer und Datenalter
- Vergleichsansicht verfügbarer Quellen
- Empfehlung: geeignete lokale Quelle, sonst Open-Meteo, saisonale Werte nur als Ersatz

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

Der einfache Zonenpfad fragt zuerst nach erkennbaren Kategorien wie Hochbeet, Gemüse, Rasen,
Sträucher, Stauden oder jungem Obstbaum. Flächen können direkt oder aus Länge und Breite bestimmt
werden. Bei Hochbeeten begrenzt die nutzbare Bodentiefe den abgeleiteten Wurzelspeicher;
Drainageschichten werden nicht mitgerechnet. Bodenmischung, Alter, organischer Anteil und
beobachteter Ablauf dokumentieren die Unsicherheit, ohne daraus eine nicht belegte Messung zu
erfinden. Bei unbekannter Bodenart verwendet die einfache Einrichtung konservativ das
Sandprofil mit dem niedrigsten erforschten AWC-Standardwert. Die Sonnen-/Expositionsangabe bleibt
in Katalogversion 1 beschreibend; ohne lokal belegten Faktor reduziert sie den Wasserbedarf nicht.

Pflanzen-, Boden- und Bewässerungsprofile stammen aus dem versionierten Katalog. Die Vorschau
zeigt Profilnamen, Begründung, Annahmen, erwartete Liter und Laufzeit. TAW und RAW werden im
einfachen Text als „nutzbarer Wasserspeicher“ und „Wasser vor Pflanzenstress“ erklärt; die
Fachbegriffe bleiben für den Expertenkontext sichtbar. Bei schweren Böden oder Regnern wird eine
Teilgaben-/Sickerpausen-Empfehlung angeboten.

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

Der Modus wird beim Einstieg gewählt und nicht als parallele zweite Konfiguration gespeichert.
Geführte Profiländerungen zeigen vor dem Speichern die neu berechneten Speicher-, Mengen- und
Laufzeitwerte. Der Expertenpfad bleibt für alle gespeicherten Felder, Profilkopien, Teilflächen und
Sicherheitsdetails verfügbar. Beim Wechsel eines Profils werden nur davon abhängige agronomische
Überschreibungen entfernt, beispielsweise TAW/RAW, maximales Defizit, Wurzeltiefe,
Pflanzenkoeffizient oder Anwendungseffizienz. Sicherheitsgrenzen, Zeitfenster, Prioritäten und
unabhängige Expertenwerte bleiben erhalten. Der Hochbeetpfad baut seine begrenzten TAW-/RAW-Werte
anschließend ausdrücklich aus gewähltem Bodenprofil und nutzbarer Bodentiefe neu auf.

Jeder Vorgang verwendet seinen beim Preflight validierten Konfigurationssnapshot. Änderungen während offener Vorgänge werden vorgemerkt und erst im vollständigen Leerlauf wirksam. Unmittelbare Eingriffe erfolgen über Stop, Not-Aus oder eine Sicherheitssperre.

## Geführte Kalibrierung

Die Kalibrierung wird direkt am Untereintrag der Bewässerungszone gestartet:
**Einstellungen > Geräte & Dienste > Irrigation Manager > Zahnrad der Zone >
Durchfluss kalibrieren**. Home Assistant erlaubt Integrationen keine eigenen Einträge im
nativen Drei-Punkte-Kontextmenü; der Reconfigure-Flow des Zonen-Untereintrags ist daher die
native Konfigurationsschnittstelle.

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

- Neue Karten starten im einfachen Modus mit genau einer Auswahl der Bewässerungsanlage
  beziehungsweise Bewässerungszone nach ihrem konfigurierten Namen.
- Die kanonische Status- beziehungsweise Zonenverbrauchs-Entity dient als stabiler Anker. Ihre
  begrenzten semantischen `card_entities`-Zuordnungen werden aus der Home-Assistant-Entity-Registry
  ermittelt und folgen daher Entity-Umbenennungen. Zonenanker trennen zonenspezifische Rollen von
  den gemeinsam genutzten Rollen der zugehörigen Anlage.
- Der Expertenmodus behält alle einzelnen Entity-Selektoren als Überschreibungen. Explizite
  Überschreibungen gewinnen immer und werden beim Moduswechsel nicht gelöscht. Bestehende Karten
  mit einzelnen Entity-Feldern werden ohne Migration als Expertenkonfiguration behandelt.
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

Der normale Config-Flow-Einstieg bietet für eine neue Anlage die Auswahl zwischen
manueller Einrichtung und portablem Import. Nach Schema- und Entity-Neuzuordnung zeigt
der Import eine Bestätigung. Unmittelbar vor dem Erstellen prüft er unter einer
prozessweiten Importsperre alle vorhandenen Irrigation-Manager-Entries und Subentries:
Haupt-/Zonenaktoren und separate Rückmeldungen dürfen auch rollenübergreifend nicht
doppelt besessen werden. Danach erzeugt Home Assistants öffentliche atomare
`async_create_entry(..., subentries=...)`-Operation den Config Entry und alle Zonen;
dadurch kann kein halber Entry mit nur einem Teil der Zonen persistiert werden.
Installation und Zonen erhalten neue Unique IDs. Es werden weder `.storage`-Dateien
geschrieben noch Einträge anderer Integrationen angelegt.

Der Historienexport ist auf höchstens 1000 Vorgänge begrenzt. JSON und CSV enthalten
den bereinigten Auftrag, Vorgang, persistierte Teilgaben, Berechnungssnapshot,
Quelle, Messherkunft, Messqualität und Warnungen. Ventil-Entities und Zonennamen
werden nicht exportiert.

## Sprache und Barrierearmut

- vollständige deutsche und englische Übersetzung
- SI- und Home-Assistant-Einheitenkonvertierung
- keine Farbe als einziges Statussignal
- verständliche Fehlertexte mit konkreter Handlungsempfehlung
