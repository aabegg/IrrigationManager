# Prüfcheckliste für Konfiguration und Benutzeroberfläche

Stand: `v0.1.0-rc30`, 30. Juli 2026

Diese Checkliste hilft bei der manuellen Beurteilung, ob Einrichtung und Bedienung ohne
Vorwissen verständlich sind. Sie ergänzt die Bedienungsanleitung, soll aber keine
unverständliche UI entschuldigen.

Referenzen:

- [Schritt-für-Schritt-Bedienungsanleitung](20_Bedienungsanleitung.md)
- [Funktionsübersicht](21_Funktionsuebersicht.md)

## Grundsatz der Prüfung

Bewerte zuerst ohne Bedienungsanleitung. Verwende die Anleitung erst, wenn du nicht
weiterkommst. So wird sichtbar, welche Information tatsächlich in der UI fehlt.

Ein Basisschritt gilt als unzureichend verständlich, wenn nur eine lange Erklärung in der
Anleitung verhindert, dass eine sicherheitsrelevante Fehlentscheidung getroffen wird.

## Vorbereitung

- [ ] Home-Assistant-Backup erstellt
- [ ] installierte IrrigationManager-Version notiert
- [ ] Desktop-Browser und Mobilgerät oder schmale Browseransicht verfügbar
- [ ] Entity-IDs von Hauptventil, Zonenventilen und Wasserzähler notiert
- [ ] physische Absperrung und Not-Aus erreichbar
- [ ] keine unbeaufsichtigte automatische Bewässerung während der Prüfung geplant
- [ ] bestehende Screenshots oder Konfigurationswerte gesichert

Eine zweite Testanlage darf nicht dieselben Ventil-Entities wie die bestehende Anlage
verwenden. IrrigationManager lehnt diese Doppelzuordnung korrekt ab. Für einen vollständigen
Neuanlage-Test sind daher freie Test-Entities, eine geplante Wiederherstellung oder eine
separate Testinstanz nötig.

## Bewertungsskala

| Wert | Bedeutung |
| ---: | --- |
| 1 | nicht verständlich oder sicherheitsgefährdend |
| 2 | nur mit Ausprobieren oder externer Hilfe verständlich |
| 3 | verständlich, aber unnötig umständlich oder mehrdeutig |
| 4 | klar und mit kleinen Verbesserungsmöglichkeiten |
| 5 | unmittelbar verständlich, konsistent und sicher |

## 1. Installation und Auffindbarkeit

- [ ] Ist die erforderliche Home-Assistant-Mindestversion sichtbar?
- [ ] Ist klar, ob ein Neustart nach der Installation nötig ist?
- [ ] Ist IrrigationManager unter **Integration hinzufügen** leicht auffindbar?
- [ ] Ist `Neue Bewässerungsanlage anlegen` als nächster Schritt eindeutig?
- [ ] Ist der Unterschied zwischen HACS-Installation und HA-Integrationseinrichtung klar?

Bewertung 1–5: ___

Notizen: ___

## 2. Erster Anlagen-Assistent

- [ ] Ist `Name` als Name der gesamten physischen Anlage verständlich?
- [ ] Ist ohne Dokumentation klar, dass das Hauptventil optional ist?
- [ ] Ist verständlich, was ein leeres Hauptventilfeld bewirkt?
- [ ] Sind `Keine Wassermessung`, `Kumulativer Mengenzähler` und `Impulszähler` eindeutig?
- [ ] Werden nur die Felder der gewählten Messart angezeigt?
- [ ] Ist der Impulsfaktor einschließlich Einheit verständlich?
- [ ] Sind alle Erweiterungsmodule klar als optional gekennzeichnet?
- [ ] Ist verständlich, dass ein Anlagenmodul nur die Verfügbarkeit freischaltet?
- [ ] Ist erkennbar, dass Einstellungen beim Deaktivieren erhalten bleiben?

Bewertung 1–5: ___

Notizen: ___

## 3. Erste Zone

- [ ] Ist `Zone` als gemeinsam geschaltete Bewässerungsfläche verständlich?
- [ ] Ist klar, welche Ventil-Entity ausgewählt werden muss?
- [ ] Ist der Unterschied zwischen Zeit- und Mengensteuerung verständlich?
- [ ] Erscheint die maximale Laufzeit nur bei Mengensteuerung?
- [ ] Erklärt die UI, warum Mengensteuerung ohne Wasserzähler nicht angeboten wird?
- [ ] Ist das gemeinsame Basissoll von einem Tagesziel unterscheidbar?
- [ ] Ist klar, dass das Basissoll bei rein manueller Nutzung leer bleiben darf?
- [ ] Ist klar, dass ein automatischer Wochenplan ein Basissoll benötigt?

Bewertung 1–5: ___

Notizen: ___

## 4. Sicherheitskritische Freigaben

- [ ] Ist nach dem Anlegen sichtbar, ob Anlage und Zone betriebsfreigegeben sind?
- [ ] Ist sichtbar, ob die Automatik aktiv ist?
- [ ] Ist der Unterschied zwischen Betriebs- und Automatikfreigabe verständlich?
- [ ] Ist erkennbar, dass vier Freigaben für einen automatischen Zonenlauf zusammenwirken?
- [ ] Ist die angebotene Aktion eindeutig, beispielsweise `Anlage deaktivieren` statt nur
      `Umschalten`?
- [ ] Warnt der Assistent ausreichend davor, dass neue Einträge in rc30 zunächst aktiviert
      angelegt werden?
- [ ] Kann ein neuer Benutzer sicher ohne Wochenplan und ohne Ventilöffnung starten?

Bewertung 1–5: ___

Notizen: ___

Wenn die Aktivierung nach dem Erstellen überraschend war oder ein automatisches Fenster
ungewollt einen realen Auftrag erzeugen konnte, ist dies unabhängig von der restlichen
Bewertung als sicherheitsrelevantes UI-Thema zu erfassen.

## 5. Wochenplan

- [ ] Ist sofort erkennbar, dass leere Tage nicht verwendet werden?
- [ ] Sind Start, Ende und Ziel je Wochentag eindeutig gruppiert?
- [ ] Ist ein über Mitternacht laufendes Fenster verständlich?
- [ ] Ist der Unterschied zwischen Basissoll und Tagesabweichung sichtbar?
- [ ] Sind Validierungsfehler einem konkreten Feld oder Wochentag zuordenbar?
- [ ] Erklärt die Fehlermeldung verständlich, warum ein Ziel nicht ins Fenster passt?
- [ ] Ist erkennbar, wann eine Änderung neue automatische Aufträge erzeugt?

Bewertung 1–5: ___

Notizen: ___

## 6. Optionale Module

Prüfe jedes Modul zunächst ausgeschaltet und danach, falls fachlich möglich, aktiviert.

### Pflanzen und Standort

- [ ] Ist klar, dass mehrere Teilflächen gleichzeitig bewässert werden?
- [ ] Sind Katalogwerte als grobe Empfehlungen und nicht als Messwerte erkennbar?
- [ ] Ist die qualitative Empfehlung vom bestätigten Basissoll getrennt?
- [ ] Sind seltene Felder sinnvoll unter **Erweiterte Angaben** eingeordnet?

### Saisonale Korrektur

- [ ] Ist `1,00` als neutral verständlich?
- [ ] Ist die monatliche Interpolation erklärt?
- [ ] Ist die Zielvorschau vor der Bestätigung verständlich?
- [ ] Ist klar, dass nur noch nicht begonnene automatische Aufträge geändert werden?

### Wetterdaten und Wasserbilanz

- [ ] Ist klar, dass Quellen lokal oder von externen Wetterdiensten stammen dürfen?
- [ ] Sind Niederschlagssumme und Niederschlagsrate klar unterschieden?
- [ ] Sind die wirklich benötigten Quellen von Diagnosequellen unterscheidbar?
- [ ] Ist der sichere Rückfall bei fehlenden Daten verständlich?
- [ ] Sind Bedarfs- und Mindestmodus unterscheidbar?
- [ ] Ist erkennbar, welche Werte fachlich kalibriert werden müssen?

### Prognose und Nachholen

- [ ] Ist klar, dass nur wahrscheinlicher Regen vor einem Start geprüft wird?
- [ ] Sind Nachholfrist und Nachholfenster unterscheidbar?
- [ ] Ist verständlich, dass eine Frist nicht später verlängert wird?
- [ ] Bleibt die Funktion unsichtbar, wenn keine Prognosequelle verfügbar ist?

### Bodenfeuchte

- [ ] Ist eine zonenweite Quelle von Teilflächenquellen unterscheidbar?
- [ ] Sind Trocken- und Feuchtpunkt verständlich?
- [ ] Werden falsche Einheit, veraltete Quelle und unplausibler Wert klar erklärt?
- [ ] Ist sichtbar, dass die Zuordnung beim Deaktivieren erhalten bleibt?

### Teilgaben und Sickerpausen

- [ ] Ist die doppelte Aktivierung auf Anlagen- und Zonenebene verständlich?
- [ ] Sind Teilgabengrösse, Pause, Anzahl und Gesamtlebensdauer unterscheidbar?
- [ ] Ist klar, dass alle Grenzen für den vollständigen Vorgang gelten?
- [ ] Erklärt die UI verständlich, wenn Ziel und Zeitfenster nicht machbar sind?
- [ ] Ist klar, dass bestehende Aufträge durch spätere Änderungen nicht verändert werden?

Bewertung der optionalen Module 1–5: ___

Notizen: ___

## 7. Anlagenkarte

- [ ] Ist der Anlagenstatus ohne technisches Vorwissen verständlich?
- [ ] Sind offene Aufträge anklickbar erkennbar?
- [ ] Sind nächste Zone und erwarteter Start plausibel?
- [ ] Wechselt die Karte nachvollziehbar zwischen Laufzeit und gemessenem Wasser?
- [ ] Ist der physische Zählerstand korrekt formatiert?
- [ ] Ist der rote Not-Aus eindeutig und nicht mit einem normalen Stop verwechselbar?
- [ ] Ist bewusst erkennbar, dass Not-Aus ohne Bestätigung sofort wirkt?
- [ ] Funktioniert der Auftragsdialog auf Desktop und Mobilgerät ohne horizontales
      Abschneiden?

Bewertung 1–5: ___

Notizen: ___

## 8. Zonenkarte und manuelle Bewässerung

- [ ] Sind Status, Tages-/Monatswert und nächste Bewässerung übersichtlich?
- [ ] Ist `Manuell bewässern` deaktiviert, wenn eine erforderliche Freigabe fehlt?
- [ ] Sind Zeit- und Mengenziel klar auswählbar?
- [ ] Wird bei Mengensteuerung eine maximale Dauer verlangt?
- [ ] Sind Stunden, Minuten und Sekunden klar beschriftet und begrenzt?
- [ ] Ist die Konfliktwahl bei einem aktiven Vorgang verständlich?
- [ ] Erscheint `Bewässerung stoppen` nur während eines aktiven Vorgangs?
- [ ] Besitzt der normale Stop einen verständlichen Bestätigungsdialog?
- [ ] Sind Teilgabenstatus, Restziel und Fortsetzungszeiten verständlich?

Bewertung 1–5: ___

Notizen: ___

## 9. Auftrags- und Verlaufsdialoge

- [ ] Werden Datum und Uhrzeit lokal und lesbar dargestellt?
- [ ] Funktionieren Tagesnavigation und Datumsfeld erwartungsgemäss?
- [ ] Führt der Hinweis bei einem leeren Tag zum nächsten Auftragstag?
- [ ] Sind Zone, Quelle, Ziel, Start und Status eines Auftrags erkennbar?
- [ ] Sind Quelle und Ergebnis im Verlauf verständlich filterbar?
- [ ] Werden Liter auf zwei Nachkommastellen dargestellt?
- [ ] Wird die Laufzeit als Stunden, Minuten und Sekunden dargestellt?
- [ ] Sind Teilgaben unter einem gemeinsamen Vorgang aufklappbar?
- [ ] Ist die Seitennavigation mit Seite und Eintragsbereich verständlich?
- [ ] Bleiben Dialoge auf kleiner Bildschirmhöhe vollständig bedienbar und scrollbar?

Bewertung 1–5: ___

Notizen: ___

## 10. Fehler, Diagnose und Wiederherstellung

- [ ] Ist eine Fehlermeldung konkret genug, um den falschen Wert zu finden?
- [ ] Bleiben bereits eingegebene Werte nach einer Validierung erhalten?
- [ ] Ist `Neukonfiguration erforderlich` mit einem klaren nächsten Schritt verbunden?
- [ ] Ist der Grund einer Sicherheitssperre auffindbar?
- [ ] Verlangt das Zurücksetzen eine ausdrückliche Bestätigung der Anlagenprüfung?
- [ ] Bleibt Not-Aus nach einem Neustart sichtbar?
- [ ] Sind Integrationsdiagnose und Protokolle für Supportfälle auffindbar?
- [ ] Entstehen bei normalen, gültigen Einstellungen keine wiederholten Warnungen?

Bewertung 1–5: ___

Notizen: ___

## 11. Konsistenz und Sprache

- [ ] Werden `Bewässerungsauftrag` und `Bewässerungsvorgang` konsistent verwendet?
- [ ] Werden `Anlage`, `Zone`, `Teilfläche`, `Teilgabe` und `Sickerpause` nicht vermischt?
- [ ] Sind gleiche Aktionen in Einstellungen und Cards gleich benannt?
- [ ] Sind optionale Felder und Module überall als optional erkennbar?
- [ ] Sind Einheiten direkt am Feld sichtbar?
- [ ] Sind Hilfetexte kurz genug, ohne wichtige Sicherheitsinformation zu verlieren?
- [ ] Sind Texte in Deutsch und de-CH vollständig lokalisiert?

Bewertung 1–5: ___

Notizen: ___

## 12. Barrierefreiheit und responsive Darstellung

- [ ] Sind alle Funktionen mit Tastatur erreichbar?
- [ ] Ist der Tastaturfokus sichtbar?
- [ ] Besitzen Icon-Schaltflächen verständliche zugängliche Namen?
- [ ] Bleiben Kontrast und Status auch ohne Farberkennung verständlich?
- [ ] Werden Fehlermeldungen als solche angekündigt und nicht nur farbig markiert?
- [ ] Funktionieren Dialoge mit Browserzoom 200 Prozent?
- [ ] Funktionieren Cards auf Mobilbreite ohne überlappende Texte oder abgeschnittene
      Aktionen?
- [ ] Sind Touch-Ziele ausreichend gross und voneinander getrennt?

Bewertung 1–5: ___

Notizen: ___

## Ergebnisübersicht

| Bereich | Bewertung 1–5 | Kritischer Befund? |
| --- | ---: | --- |
| Installation und Auffindbarkeit |  |  |
| Anlagen-Assistent |  |  |
| Zone und Wochenplan |  |  |
| Sicherheitsfreigaben |  |  |
| Optionale Module |  |  |
| Anlagenkarte |  |  |
| Zonenkarte |  |  |
| Aufträge und Verlauf |  |  |
| Fehler und Diagnose |  |  |
| Sprache und Konsistenz |  |  |
| Barrierefreiheit und Mobilansicht |  |  |

## Vorlage für einen Befund

```text
Titel:
Version und Home-Assistant-Version:
Gerät/Browser und Bildschirmgrösse:
UI-Pfad:
Ausgangszustand:
Erwartetes Verhalten:
Tatsächliches Verhalten:
Warum war es unklar oder riskant?:
Screenshot/Protokollzeitpunkt:
Sicherheitsrelevant: ja/nein
Vorgeschlagene Formulierung oder Änderung:
```

## Abnahmeregel

Vor einem stabilen Release sollten alle sicherheitsrelevanten Punkte mit mindestens 4
bewertet sein. Kein kritischer Befund darf offen bleiben. Ein Durchschnittswert darf eine
unklare Freigabe, einen nicht erkennbaren Not-Aus oder eine missverständliche
Ventilbetätigung nicht ausgleichen.
