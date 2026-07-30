# Bedienungsanleitung für IrrigationManager

Stand: `v0.1.0-rc30`, 30. Juli 2026

Diese Anleitung führt von der Installation über die minimale Konfiguration bis zum
beaufsichtigten ersten Bewässerungstest. Sie beschreibt die tatsächlich sichtbaren
deutschen Bezeichnungen von rc30. Die fachliche Spezifikation bleibt
`docs/17_Neukonzept.md`.

## Kennzeichnung

| Kennzeichnung | Bedeutung |
| --- | --- |
| **Pflicht** | Ohne diese Angabe kann keine minimale Anlage angelegt werden. |
| **Optional** | Kann leer oder ausgeschaltet bleiben; der Grundbetrieb funktioniert weiter. |
| **Bedingt** | Wird nur benötigt, wenn eine davon abhängige Funktion verwendet wird. |
| **Sicherheitsrelevant** | Kann reale Ventile betätigen oder eine Sperre verändern. |

## 1. Minimal benötigte Voraussetzungen

Für die kleinste funktionsfähige, rein zeitgesteuerte Anlage werden nur folgende Dinge
benötigt:

- **Pflicht:** Home Assistant 2026.7.2 oder neuer.
- **Pflicht:** die installierte Integration IrrigationManager.
- **Pflicht:** eine vorhandene `switch`- oder `valve`-Entity für das erste Zonenventil.
- **Pflicht:** ein Name für die Bewässerungsanlage und ein Name für die erste Zone.
- **Pflicht:** die Steuerungsart `Zeitsteuerung`.
- **Optional:** Hauptventil, Wasserzähler, Pflanzenprofile, Wetterdaten, Saisonkurve,
  Bodenfeuchte, Teilgaben und ein automatischer Wochenplan.

Ein Basissoll und ein Wochenplan sind für eine rein manuell bediente Zone nicht nötig.

## 2. Vor der Installation

1. Prüfe, dass jedes Ventil bei ausgeschaltetem Aktor geschlossen ist.
2. Notiere die Entity-ID jedes Zonenventils und gegebenenfalls des Hauptventils.
3. Prüfe die manuelle Schaltung der Aktoren zunächst ohne Wasser oder unter direkter
   Aufsicht.
4. Erstelle ein vollständiges Home-Assistant-Backup.
5. Plane den ersten realen Test so, dass du Hauptventil, Zonenventil und Wasserfluss vor
   Ort beobachten kannst.

Ein unabhängiger Hardware-Abschalttimer ist für einen späteren unbeaufsichtigten Betrieb
weiterhin empfohlen und Teil der noch offenen Feldqualifikation.

## 3. Installation über HACS

Wenn IrrigationManager bereits installiert ist, fahre mit Abschnitt 4 fort.

1. Öffne HACS in Home Assistant.
2. Öffne den Bereich für Integrationen.
3. Falls IrrigationManager noch nicht öffentlich gelistet ist, füge
   `https://github.com/aabegg/IrrigationManager` als benutzerdefiniertes Repository vom
   Typ `Integration` hinzu.
4. Öffne IrrigationManager und installiere die gewünschte Version.
5. Starte Home Assistant nach der Installation neu.
6. Prüfe unter **Einstellungen → System → Reparaturen**, dass keine neue Reparaturmeldung
   vorliegt.

## 4. Sicherer Minimal-Schnellstart

### Wichtiger Hinweis für rc30

Eine neu angelegte Anlage und eine neu angelegte Zone werden in rc30 zunächst mit
Betriebs- und Automatikfreigabe gespeichert. Lasse deshalb beim ersten Einrichten den
gesamten Wochenplan leer. Ohne automatisches Fenster entsteht kein automatischer Auftrag.
Deaktiviere die Freigaben unmittelbar nach Abschluss des Assistenten, bevor du einen
realen Test durchführst.

### 4.1 Integration hinzufügen

1. Öffne **Einstellungen → Geräte & Dienste**.
2. Wähle **Integration hinzufügen**.
3. Suche nach `Irrigation Manager`.
4. Öffne **Irrigation Manager einrichten**.
5. Wähle **Neue Bewässerungsanlage anlegen**.

### 4.2 Bewässerungsanlage anlegen

1. Im Schritt **Bewässerungsanlage anlegen** gibst du einen eindeutigen Namen ein,
   beispielsweise `Gartenbewässerung`. **Pflicht**
2. Im Schritt **Optionales Hauptventil** lässt du `Hauptventil` leer, wenn die Anlage kein
   gemeinsames Hauptventil besitzt. **Optional**
3. Im Schritt **Optionale Wassermessung** wählst du für den minimalen Einstieg
   `Keine Wassermessung`. **Optional**
4. Im Schritt **Optionale Erweiterungen** lässt du alle Module ausgeschaltet. **Optional**

Damit bleibt die Anlage vollständig zeitgesteuert und verwendet keine Zusatzmodule.

### 4.3 Erste Bewässerungszone anlegen

1. Gib unter **Name** einen verständlichen Zonennamen ein, beispielsweise `Rasen`.
   **Pflicht**
2. Wähle unter **Zonenventil** die Entity, die genau diese Zone öffnet und schliesst.
   **Pflicht**
3. Wähle unter **Steuerungsart** den Wert `Zeitsteuerung`. **Pflicht**
4. Lasse das **Gemeinsame Basissoll** leer. Für eine rein manuelle Zone ist es optional.
5. Im Schritt **Wochenplan** lässt du Montag bis Sonntag vollständig leer.
6. Schliesse den Assistenten ab.

Eine Ventil-Entity kann nur von einer IrrigationManager-Anlage oder -Zone verwendet
werden. Bei einer Doppelzuordnung wird die Konfiguration abgelehnt.

### 4.4 Freigaben unmittelbar deaktivieren

1. Öffne unter **Einstellungen → Geräte & Dienste → Irrigation Manager** die neue Anlage.
2. Öffne **Konfigurieren → Status und Steuerung**.
3. Wähle **Anlage deaktivieren**, falls diese Aktion angeboten wird.
4. Öffne **Konfigurieren → Status und Steuerung** erneut, weil jede ausgeführte Aktion den
   Dialog abschliesst.
5. Wähle **Automatische Bewässerung deaktivieren**, falls diese Aktion angeboten wird.
6. Öffne danach die Konfiguration der ersten Bewässerungszone.
7. Öffne dort **Status und Steuerung** und wähle **Zone deaktivieren**, falls angeboten.
8. Öffne den Punkt erneut und wähle **Automatische Bewässerung deaktivieren**, falls
   angeboten.

Die angebotenen Aktionen hängen vom aktuellen Zustand ab. Wird `Anlage aktivieren`
angezeigt, ist die Anlage bereits deaktiviert. Wird `Automatische Bewässerung aktivieren`
angezeigt, ist die Automatik bereits deaktiviert.

## 5. Dashboard-Karten einrichten

Die Integration registriert ihr Frontend-Modul automatisch. Es darf keine zweite
Lovelace-Ressource von Hand angelegt werden.

### 5.1 Anlagenübersicht

1. Öffne das gewünschte Dashboard.
2. Aktiviere **Dashboard bearbeiten**.
3. Wähle **Karte hinzufügen**.
4. Suche nach **Irrigation Manager Overview**.
5. Wähle als Bewässerungsanlage die Status-Entity der Anlage, beispielsweise
   `sensor.gartenbewasserung_status`.
6. Speichere die Karte.

Die Anlagenkarte zeigt Status, offene Aufträge, nächste Zone, erwarteten Start,
Tages-/Monatslaufzeit oder gemessertes Wasser und bei aktiver Messung den korrigierten
physischen Zähler. Der rote **Not-Aus** ist immer sichtbar und wirkt sofort ohne
Bestätigungsdialog.

### 5.2 Zonenkarte

1. Wähle erneut **Karte hinzufügen**.
2. Suche nach **Irrigation Manager Zone**.
3. Wähle die Status-Entity der gewünschten Zone, beispielsweise `sensor.rasen_status`.
4. Speichere die Karte.
5. Wiederhole die Schritte für jede weitere Zone.

Die Zonenkarte zeigt Status, Tages-/Monatswert, nächste Bewässerung und die Aktionen
**Manuell bewässern** und **Verlauf anzeigen**. Während einer laufenden Bewässerung wird
zusätzlich **Bewässerung stoppen** angeboten. Bei aktiven Teilgaben erscheinen Restziel,
Teilgabennummer und sichere Fortsetzungszeitpunkte.

## 6. Erster beaufsichtigter Funktionstest

Dieser Abschnitt ist **sicherheitsrelevant**. Bleibe während des gesamten Tests vor Ort.

1. Prüfe nochmals, dass kein offener Bewässerungsauftrag vorhanden ist.
2. Prüfe, dass Not-Aus und Anlagen-Sicherheitssperre aus sind.
3. Öffne die Anlageneinstellungen und aktiviere unter **Status und Steuerung** nur die
   Anlage. Lasse die Anlagenautomatik ausgeschaltet.
4. Aktiviere unter den Zoneneinstellungen nur die Testzone. Lasse auch deren Automatik
   ausgeschaltet.
5. Öffne die Zonenkarte und wähle **Manuell bewässern**.
6. Wähle `Zeitgesteuert` und beginne mit einer kurzen, vor Ort überwachbaren Dauer.
7. Halte den roten **Not-Aus** und die physische Wasserabsperrung erreichbar.
8. Prüfe die Reihenfolge: Hauptventil, falls vorhanden, danach Zonenventil; beim Ende
   zuerst Zonenventil, danach Hauptventil.
9. Prüfe nach Abschluss den **Bewässerungsverlauf** und die Home-Assistant-Protokolle.
10. Deaktiviere Anlage und Zone nach dem Test wieder.

Setze eine Sicherheitssperre niemals nur deshalb zurück, um weiterzutesten. Prüfe zuerst
den physischen Zustand und die protokollierte Ursache.

## 7. Vollständiger Anlagen-Assistent

Die folgenden Schritte ergänzen den Minimal-Schnellstart.

### 7.1 Optionales Hauptventil

Wähle ein gemeinsames Hauptventil nur, wenn es hydraulisch vor allen Zonen liegt. Die
Integration öffnet es vor dem Zonenventil und schliesst es danach. Ohne Auswahl werden nur
die einzelnen Zonenventile geschaltet.

### 7.2 Optionale Wassermessung

Es stehen drei Messarten zur Verfügung:

| Messart | Zusätzliche Angaben | Verwendung |
| --- | --- | --- |
| `Keine Wassermessung` | keine | Zeitsteuerung und Laufzeitstatistik |
| `Kumulativer Mengenzähler` | Zählerentität | gemessener Verbrauch und Mengensteuerung |
| `Impulszähler` | Zählerentität und Umrechnungsfaktor | Impulse werden dauerhaft in Liter umgerechnet |

Beim Impulszähler kann der Faktor als `Liter pro Impuls` oder `Impulse pro Liter`
eingegeben werden. Der physische Zählerstand kann später unter **Konfigurieren →
Zählerstand korrigieren** abgeglichen werden. Diese Korrektur verändert nicht den
gespeicherten Verbrauchsverlauf.

Eine Wassermessung kann nicht deaktiviert werden, solange eine Zone Mengensteuerung
verwendet. Stelle solche Zonen zuerst auf Zeitsteuerung um.

### 7.3 Optionale Erweiterungen

Die anlagenweite Checkbox macht ein Modul nur verfügbar. Saisonale Korrektur, gemessene
Wasserbilanz und Teilgaben werden zusätzlich je Zone ausdrücklich aktiviert. Das
Deaktivieren eines Moduls behält dessen Zoneneinstellungen, schränkt den Grundbetrieb aber
nicht ein.

Die vollständigen Voraussetzungen stehen in der
[Funktionsübersicht](21_Funktionsuebersicht.md).

### 7.4 Wetterdatenquellen

Die Rollen dürfen mit lokalen Sensoren oder externen, über Home Assistant eingebundenen
Wetterdiensten belegt werden. Rollen dürfen leer bleiben.

Für die gemessene Wasserbilanz sind insbesondere erforderlich:

- `Gemessene Niederschlagssumme`
- `Referenz-Evapotranspiration`

Weitere Rollen verbessern Diagnose oder optionale Funktionen:

- aktuelle Niederschlagsrate
- Lufttemperatur
- relative Luftfeuchtigkeit
- Taupunkt
- Windgeschwindigkeit
- Sonneneinstrahlung
- Wettervorhersage

Fehlen Niederschlagssumme oder Referenz-Evapotranspiration oder sind die Werte unbrauchbar,
behält die Planung sicher das saisonale Ziel bei.

## 8. Zonenkonfiguration

### 8.1 Zeit- oder Mengensteuerung

- **Zeitsteuerung:** Das Ziel ist eine Dauer. Sie funktioniert ohne Wasserzähler.
- **Mengensteuerung:** Das Ziel ist eine Wassermenge. Sie benötigt eine funktionierende
  Wassermessung und eine harte maximale Laufzeit, falls das Mengenziel nicht erreicht wird.

### 8.2 Gemeinsames Basissoll

Das Basissoll ist das normale Ziel der Zone. Es ist optional, solange die Zone nur manuell
verwendet wird. Sobald ein automatisches Wochenfenster gespeichert wird, ist ein positives
Basissoll erforderlich.

Ein Tagesziel im Wochenplan darf vom Basissoll abweichen. Die Abweichung gilt nur für den
betreffenden Wochentag.

### 8.3 Wochenplan

Für jeden verwendeten Wochentag werden Start, Ende und optional ein abweichendes Ziel
erfasst. Nicht verwendete Tage bleiben vollständig leer.

- Start und Ende müssen gemeinsam ausgefüllt sein.
- Das vollständige Ziel muss in das Zeitfenster passen.
- Benachbarte Zeitfenster dürfen sich nicht überschneiden.
- Ein Fenster darf über Mitternacht reichen.
- Ein Tagesziel ohne Zeitfenster ist ungültig.

Der Wochenplan allein bewässert noch nicht. Für einen automatischen Lauf müssen Anlage und
Zone sowohl betriebs- als auch automatikfreigegeben sein.

### 8.4 Weitere Zonen hinzufügen

1. Öffne den IrrigationManager-Konfigurationseintrag.
2. Wähle **Bewässerungszone hinzufügen**.
3. Durchlaufe denselben Zonenassistenten wie bei der ersten Zone.
4. Verwende eine noch nicht zugeordnete Ventil-Entity.
5. Lasse den Wochenplan beim ersten Hardwaretest leer.
6. Deaktiviere danach die neue Zone und ihre Automatik unter **Status und Steuerung**.

## 9. Optionale Zonenmodule

### 9.1 Pflanzen- und Standortmodell

Das Modul erfasst eine oder mehrere gleichzeitig bewässerte Teilflächen. Pro Teilfläche
können Fläche, Pflanzenprofil, Entwicklungszustand, Exposition, Bodenprofil und
Ausbringungsprofil gewählt werden. Hangneigung, Mulch und relative Ausbringungsrate liegen
unter **Erweiterte Angaben**.

Die Empfehlung ist qualitativ. Sie setzt das Basissoll niemals automatisch. Beim
Deaktivieren bleiben die Teilflächen gespeichert.

### 9.2 Saisonale Korrektur

Die Zone erhält zwölf Monatsfaktoren. `1,00` ist neutral; zwischen den Monatswerten wird
täglich interpoliert. Die Vorschau muss ausdrücklich bestätigt werden. Änderungen wirken
nur auf noch nicht begonnene automatische Aufträge.

### 9.3 Gemessene Wasserbilanz

Die Wasserbilanz verrechnet gemessenen Niederschlag und bestätigte Bewässerung. Sie
benötigt eine nachvollziehbare Umrechnung von Millimeter Wasserdefizit in das Zonen-Ziel.

Zur Auswahl stehen:

- `Nur bei Bedarf bewässern`: Ein fälliges Fenster kann unterhalb der Bedarfsgrenze
  ausgelassen werden.
- `Mindestens saisonales Ziel`: Das saisonale Ziel wird nicht unterschritten.

Pflanzenfaktor, wirksamer Regenfaktor, Bedarfsgrenze, maximales Defizit,
Ausbringungsrate, Fläche und Effizienz sind fachliche Werte. Übernimm sie nicht ungeprüft.

### 9.4 Prognosebasierte Verschiebung

Diese Funktion ist nur verfügbar, wenn die Zone die gemessene Wasserbilanz verwendet und
eine Wettervorhersage zugeordnet ist. Sie prüft wahrscheinlichen Regen unmittelbar vor
dem geplanten Start und verwendet feste Nachholfristen und Nachholfenster. Eine einmal
begonnene Nachholfrist wird nicht verlängert.

### 9.5 Bodenfeuchterückmeldung

Die Rückmeldung ist nur bei aktiver gemessener Wasserbilanz verfügbar. Eine Quelle kann
für die ganze Zone oder je Teilfläche zugeordnet werden. Der Sensor muss Bodenfeuchte in
Prozent liefern. Trocken- und Feuchtpunkt müssen kalibriert sein; der Feuchtpunkt liegt
mindestens fünf Prozentpunkte über dem Trockenpunkt.

Beim Deaktivieren bleiben Zuordnung und Kalibrierung erhalten. Veraltete, unplausible oder
nicht verfügbare Messwerte werden nicht als Null interpretiert.

### 9.6 Teilgaben und Sickerpausen

Das Modul benötigt zwei Opt-ins: anlagenweite Verfügbarkeit und zonenspezifische
Verwendung. Für die Zone werden vier Grenzen gespeichert:

- maximale Teilgabengrösse
- minimale Sickerpause
- maximale Anzahl Teilgaben
- maximale Gesamtlebensdauer

Das vollständige Ziel muss mit allen Teilgaben, Pausen und Sicherheitsbudgets in das
Bewässerungsfenster passen. Eine Teilgabe wird nie automatisch vergrössert. Andere Zonen
dürfen eine Pause nur nutzen, wenn der pausierende Vorgang danach sicher fortgesetzt
werden kann.

Änderungen gelten nur für neu angenommene Aufträge. Offene oder aktive Vorgänge behalten
ihren unveränderlichen Snapshot.

## 10. Einstellungen nach der Ersteinrichtung

### 10.1 Anlagenmenü

Unter **Konfigurieren** können abhängig vom Zustand folgende Punkte erscheinen:

- **Basisinformationen**
- **Hauptventil**
- **Wassermessung**
- **Optionale Erweiterungen**
- **Wetterdatenquellen**
- **Status und Steuerung**
- **Bewässerungsplanung neu berechnen**
- **Sicherheitssperre zurücksetzen**, nur bei aktiver Sperre
- **Zählerstand korrigieren**, nur mit Wassermessung
- **Anlage vollständig konfigurieren**, wenn eine Migration Neukonfiguration verlangt

### 10.2 Zonenmenü

Je nach aktivierten Anlagenmodulen erscheinen:

- **Vollständige Zone konfigurieren**
- **Pflanzen und Standort**
- **Saisonale Korrektur**
- **Gemessene Wasserbilanz**
- **Bodenfeuchterückmeldung**
- **Prognosebasierte Verschiebung**
- **Teilgaben und Sickerpausen**
- **Gemeinsames Basissoll**
- **Wochenplan**
- **Status und Steuerung**
- **Durchfluss kalibrieren**, nur mit Wassermessung

## 11. Bedienung der Karten

### 11.1 Offene Bewässerungsaufträge

Ein Klick auf **Offene Aufträge** öffnet die Aufträge eines lokalen Kalendertags. Mit den
Pfeilen oder dem Datumsfeld kann der Tag gewechselt werden. Gibt es an diesem Tag keine
Aufträge, führt eine Schaltfläche zum nächsten Tag mit offenen Aufträgen.

Ein Bewässerungsauftrag ist noch nicht gestartet. Nach dem Start erscheint sein Ergebnis
als Bewässerungsvorgang im Verlauf.

### 11.2 Manuell bewässern

Bei Zeitsteuerung wird eine Dauer eingegeben. Bei funktionierender Wassermessung kann
zusätzlich `Mengengesteuert` gewählt werden; dafür ist eine maximale Dauer Pflicht.

Ist bereits ein anderer Vorgang aktiv, stehen zwei Regeln zur Verfügung:

- aktiven Vorgang beenden und sofort starten
- aktiven Vorgang abschliessen und danach mit Priorität ausführen

### 11.3 Bewässerungsverlauf

Der Verlauf kann nach Quelle `Manuell` oder `Automatisch` und nach Ergebnis gefiltert
werden. Er zeigt lokalisiertes Datum und Uhrzeit, Ziel, Laufzeit, gemessene Liter und
Abschlussgrund. Teilgaben erscheinen aufklappbar unter dem gemeinsamen Vorgang.

### 11.4 Stop und Not-Aus

- **Bewässerung stoppen** beendet den aktiven Vorgang der Zone kontrolliert und verlangt
  eine Bestätigung.
- **Not-Aus** stoppt die gesamte Anlage sofort, setzt eine persistente Sperre und besitzt
  auf der Anlagenkarte bewusst keinen Bestätigungsdialog.
- **Sicherheitssperre zurücksetzen** ist eine getrennte, bestätigungspflichtige Aktion in
  den Anlageneinstellungen.

## 12. Diagnose und Fehlersuche

Prüfe bei einem unerwarteten Zustand in dieser Reihenfolge:

1. Anlagenstatus und Zonenstatus.
2. Not-Aus und Anlagen-Sicherheitssperre.
3. Betriebs- und Automatikfreigabe von Anlage und Zone.
4. offene Aufträge sowie erwarteten Start.
5. Bewässerungsverlauf und Abschlussgrund.
6. **Einstellungen → System → Protokolle** nach `irrigation_manager`.
7. **Einstellungen → System → Reparaturen**.
8. Integrationsdiagnose des IrrigationManager-Konfigurationseintrags.

Typische Statuswerte:

| Status | Bedeutung |
| --- | --- |
| `Bereit` | Betrieb ist möglich; kein Vorgang ist aktiv. |
| `Bewässerung` | Ein Ventilvorgang läuft. |
| `Sickerpause` | Ein Teilvorgang wartet bei geschlossenen Ventilen. |
| `Gesperrt` / `Anlage gesperrt` | Betriebsfreigabe fehlt. |
| `Automatik gesperrt` | Manuelle Bedienung kann möglich sein, automatische nicht. |
| `Sicherheitssperre` | Ursache vor einem Reset physisch und anhand der Diagnose prüfen. |
| `Not-Aus` | Anlage bleibt gesperrt, bis Ursache und Zustand geprüft wurden. |
| `Neukonfiguration erforderlich` | Anlage oder Zone muss vollständig über die UI bestätigt werden. |

## 13. Updates und Wiederherstellung

1. Erstelle vor jedem Release-Update ein Home-Assistant-Backup.
2. Prüfe die Release Notes und die Mindestversion.
3. Aktualisiere über HACS und starte Home Assistant neu, wenn das Update dies verlangt.
4. Prüfe danach Integrationsstatus, Repairs, Protokoll, offene Aufträge und Freigaben.
5. Führe nach einer Migration zuerst einen Trockenlauf und danach einen kurzen
   beaufsichtigten Hardwaretest durch.

Die private Feldtestabfolge für rc30 steht im
[Feldtest- und Freigabeprotokoll](19_Feldtest_rc30.md).
