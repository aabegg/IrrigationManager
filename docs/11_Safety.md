# Sicherheit

## Sicherheitsprinzipien

- Sicherheit hat Vorrang vor Pflanzenschutz, Wassersparen und Komfort.
- Pro Anlage darf immer nur eine Teilgabe Wasser erhalten; andere Vorgänge dürfen ausschließlich in einer Sickerpause warten.
- Der Executor besitzt exklusiven Schreibzugriff auf zugeordnete Ventile.
- Jeder Vorgang besitzt harte Zeitbegrenzungen; Mengenbegrenzungen gelten bei plausibler Mengenquelle.
- Die Bewässerungslaufzeit begrenzt die kumulierte Ventilöffnungszeit; eine separate Vorgangsdauer begrenzt die gesamte Lebensdauer einschließlich Sicker- und Wartezeiten.
- Fehler führen zu einem bekannten geschlossenen Zustand, soweit die Hardware erreichbar ist.
- Ein Neustart setzt keinen unklaren Vorgang fort.
- Gemessene Teilmengen werden auch bei Fehlern korrekt verbucht.
- Ein unabhängiger Hardware-Abschalttimer wird dringend empfohlen.

## Ausführungszustände

Ein Vorgang durchläuft explizite Zustände:

```text
waiting
preflight
opening_main
opening_zone
watering
closing_zone
settling
closing_main
soaking
paused
completed
cancelled
failed
interrupted
```

Jeder Übergang besitzt Timeout, erlaubte Eingangszustände und definierte Fehlerreaktion.

`soaking` ist ein fachlich offener Vorgang ohne geöffnete Ventile. Währenddessen darf der Executor eine Teilgabe eines anderen Vorgangs ausführen. Es bleibt trotzdem immer nur eine Teilgabe hydraulisch aktiv.

## Preflight

Vor jedem automatischen oder manuellen Vorgang:

- keine Not-Aus-, Sicherheits- oder Wintersperre
- kein anderer aktiver Vorgang
- alle fremden Zonenventile geschlossen
- Hauptventil in erwartbarem Zustand
- Zielventil und optionales Feedback verfügbar
- Zähler- und Durchflussqualität passend zur Zielart oder erlaubtem Fallback
- keine harte Frostsperre
- externe Freigaben erfüllt
- Maximalgrenzen gültig
- manueller Auftrag noch nicht abgelaufen

Der Vorgang übernimmt danach einen unveränderlichen Konfigurationssnapshot. Spätere Config-/Options-Änderungen verändern ihn nicht; Stop, Not-Aus und laufende Sensorprüfungen bleiben davon unabhängig wirksam.

Automatik prüft zusätzlich Fenster, Rhythmus, Wetter, Budgets und Automatikfreigabe.

## Reguläre Schaltfolge

1. Zählerbaseline erfassen
2. Hauptventil öffnen und bestätigen, sofern vorhanden
3. konfigurierte Stabilisierung abwarten
4. Zonenventil öffnen und bestätigen
5. Durchfluss innerhalb der Anlaufzeit prüfen
6. Ziel, Fenster, Durchfluss und Zeitlimit überwachen
7. Ventile in konfigurierter Reihenfolge schließen
8. Durchflussende und Nachlauf abwarten
9. Endmenge und Ergebnis finalisieren

Das Hauptventil wird zwischen Zonen und Teilgaben geschlossen.

## Ventilabweichungen

### Unerwartetes Öffnen

- betroffene Ventile und Hauptventil schließen
- Anlage sperren
- unzugeordnete Menge erfassen
- Benutzer alarmieren

### Unerwartetes Schließen

- nicht automatisch wieder öffnen
- Vorgang als Teilbewässerung beenden
- gemessene Menge verbuchen
- bei Zonenventil Zone sperren
- bei Hauptventil Anlage sperren

### Befehl ohne erwartete Rückmeldung

- begrenzte, konfigurierte Wiederholungsversuche
- optional separates Feedback-Entity auswerten
- nach Fehlschlag sicher schließen und sperren

## Durchflussfehler

### Zu niedriger Durchfluss

- Zone und Hauptventil schließen
- Vorgang als fehlerhaft beenden
- Zone sperren
- mögliche Blockade, geschlossenes Ventil oder fehlende Versorgung melden

### Zu hoher Durchfluss

- alle Ventile schließen
- Vorgang als fehlerhaft beenden
- gesamte Anlage sperren
- möglichen Leitungsbruch melden

### Durchfluss ohne Vorgang

- Messartefakte und Nachlauf innerhalb konfigurierter Grenzen tolerieren
- ab Rate und Mindestdauer Hauptventil erneut schließen
- gesamte Anlage sperren
- Menge als unzugeordnet verbuchen

## Sensor- und Wetterausfall

- keine stille Umdeutung ungültiger Werte zu null
- Datenalter und Plausibilität prüfen
- festgelegte Modell- oder Zählerfallbacks verwenden
- verwendeten Fallback sichtbar kennzeichnen
- nach Ablauf erlaubter Fallbackdauer automatische Bedarfsbewässerung aussetzen
- kritische Gerätesensoren können Starts blockieren

## Betrieb ohne Wasserzähler oder Durchflusssensor

- nur Zeitsteuerung
- Liefermenge aus Laufzeit und Durchflussprofil schätzen
- keine Mengenabschaltung
- keine Unter-/Überdurchfluss- oder Leckageerkennung
- harte Laufzeitgrenzen und Ventilzustandsprüfung bleiben aktiv
- reduzierte Sicherheitsqualität dauerhaft anzeigen

## Mengensteuerung

- ohne plausible Mengenquelle gilt die zonenspezifische Zählerausfallstrategie
- harter Zeit-Timeout bleibt immer aktiv
- das harte Laufzeitlimit bestimmt den Zeitpunkt, an dem die Schließbefehle ausgelöst werden; die anschließende Rückmeldeprüfung aller Schließbefehle verwendet ein gemeinsames, separat begrenztes Bestätigungsbudget und verlängert keine Wasserabgabe absichtlich
- das gemeinsame Bestätigungsbudget ist eine feste Sicherheitsgrenze und wird nicht durch ein kurzes Bewässerungslimit verkürzt; alle erforderlichen Schließbefehle werden zu Beginn dieses Budgets parallel ausgelöst
- kalibrierte Vorabschaltung darf das Ziel nicht über Sicherheitsgrenzen hinaus verlängern
- tatsächliche Endmenge ist maßgeblich, nicht das Soll

## Pause, Stop und Fensterende

- Pause schließt Haupt- und Zonenventil und bewahrt Restziel
- Pausentimeout beendet den Vorgang und gibt Restbedarf an den Scheduler zurück
- Stop beendet den ausgewählten aktiven oder in Sickerpause wartenden Vorgang ohne automatische Sperre
- Stop+Überspringen unterdrückt zusätzlich dessen aktuelle Gelegenheit
- Fensterende und Maximalgrenzen schließen hart und verbuchen die Teilmenge
- globaler Stop und Not-Aus finalisieren auch alle in Sickerpause wartenden Vorgänge

## Neustart und Shutdown

- bei kontrolliertem Shutdown bestmöglich alle Ventile schließen
- beim Start unabhängig vom gespeicherten Zustand alle zugeordneten Ventile schließen
- alle offenen Vorgänge einschließlich Sickerpausen als unterbrochen markieren
- noch erfassbare Menge der zuletzt aktiven Teilgabe verbuchen
- bei geschätztem Zählerfallback den zuletzt persistent bestätigten Mengenfortschritt verwenden; nur bei beobachtetem möglichen Durchfluss darf ab diesem Checkpoint begrenzt weitergeschätzt werden
- automatische Aufträge neu planen
- manuelle Aufträge laden und auf Ablauf prüfen
- persistente Sperren beibehalten

## Not-Aus und Sperren

- Not-Aus schließt alle Ventile, finalisiert alle offenen Vorgänge, storniert Aufträge und bleibt persistent
- Quittierung entfernt den gespeicherten Zustand, sofern kein aktueller Check sofort erneut sperrt
- normale manuelle Bedienung umgeht keine aktive Sicherheitsgefahr
- Frost bleibt auch für manuelle Vorgänge hart

## Wartungstest und Übersteuerung

Feedback-, Durchfluss-, Wetter- und externe Sensorprüfungen dürfen ausschließlich übersteuert werden, wenn:

- Wartungsmodus bewusst gestartet wurde
- genau ein Testziel ausgewählt ist
- eine kurze feste Ablaufzeit gilt
- Benutzer auf die aktive Übersteuerung hingewiesen wird
- keine Automatik läuft
- der Test durch regelmäßige Dead-Man-Bestätigung aktiv beaufsichtigt wird
- ausbleibende Bestätigung oder Verbindungsverlust den Test sofort beendet
- nach Ende alle Ventile geschlossen und die Übersteuerung entfernt werden

Nicht übersteuerbar bleiben Not-Aus, Wintersperre, exklusive Ein-Zonen-Ausführung, der feste Wartungstimeout und ein ausdrücklicher Benutzer-Stop.

Wartungswasser wird nach Benutzerentscheidung einer Zone oder unzugeordnet verbucht.

## Winterbetrieb

- Datum oder Frostprognose erzeugt eine Entleerungserinnerung
- Bestätigung der Entleerung setzt eine vollständige Wintersperre
- Wintersperre verhindert Automatik, manuelle Aufträge, Kalibrierung und Wartungstests
- Freigabe erfolgt nur durch bewusste Bestätigung
- optionaler Anlagenprüflauf wird angeboten, aber nicht erzwungen

## Hardwaregrenze

Software kann ein mechanisch klemmendes Ventil, Stromausfall, Netzwerkverlust oder einen vollständigen HA-Ausfall nicht garantiert beherrschen. Die Integration warnt deshalb, solange kein unabhängiger Hardware-Abschalttimer bestätigt ist, blockiert den Betrieb aber nicht allein deshalb.
