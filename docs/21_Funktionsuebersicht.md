# Funktionsübersicht

Stand: `v0.1.0-rc30`, 30. Juli 2026

Diese Übersicht zeigt, was zum Grundbetrieb gehört, welche Funktionen optional sind und
welche Voraussetzungen gelten. Detailanweisungen stehen in der
[Schritt-für-Schritt-Bedienungsanleitung](20_Bedienungsanleitung.md).

## Legende

- **Pflicht:** Bestandteil jeder Anlage oder Zone.
- **Optional:** Kann vollständig deaktiviert bleiben.
- **Bedingt:** Nur nötig, wenn eine abhängige Funktion verwendet wird.
- **Erweitert:** Für Diagnose, Automationen oder fachlich kalibrierte Nutzung.

## Mindestkonfiguration

| Funktion oder Angabe | Einstufung | Voraussetzung | Verhalten ohne Funktion |
| --- | --- | --- | --- |
| Name der Anlage | **Pflicht** | keine | Anlage kann nicht angelegt werden |
| Erste Bewässerungszone | **Pflicht** | freie Ventil-Entity | Anlage kann nicht angelegt werden |
| Name der Zone | **Pflicht** | keine | Zone kann nicht angelegt werden |
| Zonenventil | **Pflicht** | `switch` oder `valve` | keine reale Bewässerung möglich |
| Steuerungsart | **Pflicht** | Zeit oder bei Messung Menge | Zone kann nicht angelegt werden |
| Zeitsteuerung | Grundfunktion | Zonenventil | funktioniert ohne Wasserzähler |
| Gemeinsames Basissoll | **Bedingt** | positives Ziel | darf bei rein manueller Zone leer bleiben |
| Wochenplan | **Optional** | Basissoll für automatische Fenster | rein manuelle Bedienung bleibt möglich |

## Hardware und Messung

| Funktion | Einstufung | Voraussetzung | Wirkung und Rückfall |
| --- | --- | --- | --- |
| Gemeinsames Hauptventil | **Optional** | freie `switch`- oder `valve`-Entity | ohne Auswahl werden nur Zonenventile geschaltet |
| Kumulativer Mengenzähler | **Optional** | kumulative Wasser-Entity | ermöglicht gemessene Liter und Mengensteuerung |
| Impulszähler | **Optional** | Impuls-Entity und positiver Faktor | Impulse werden in Liter umgerechnet |
| Mengensteuerung | **Bedingt** | funktionierende Wassermessung und maximale Laufzeit | Zeitsteuerung bleibt verfügbar |
| Korrigierter physischer Zähler | **Bedingt** | Wassermessung | gleicht Zählerstand ab, ohne Verbrauch umzuschreiben |
| Durchflusskalibrierung | **Bedingt**, sicherheitsrelevant | Wassermessung, freigegebene Anlage/Zone, Aufsicht | Vorschlag kann übernommen oder verworfen werden |
| Wasserstatistik für Anlage und Zonen | **Bedingt** | funktionierende Messung | Cards zeigen sonst Laufzeitstatistik |
| Unzugeordneter Verbrauch | automatisch bei Messung | Wassermessung | erfasst nicht sicher einer Zone zuordenbare Liter |

## Betrieb und Planung

| Funktion | Einstufung | Voraussetzung | Bemerkung |
| --- | --- | --- | --- |
| Anlagen-Betriebsfreigabe | **Pflicht für jeden Lauf** | gültige Konfiguration, keine Sperre | sperrt oder erlaubt den gesamten Betrieb |
| Zonen-Betriebsfreigabe | **Pflicht für jeden Zonenlauf** | Anlagenfreigabe | wirkt nur auf die betreffende Zone |
| Anlagen-Automatikfreigabe | **Pflicht für Automatik** | Anlagenbetrieb | manuelle Bedienung kann bei deaktivierter Automatik möglich bleiben |
| Zonen-Automatikfreigabe | **Pflicht für Zonenautomatik** | Anlagen- und Zonenbetrieb, Anlagenautomatik | automatische Aufträge dieser Zone |
| Wochenplan | **Optional** | Basissoll, vollständiges Fenster | höchstens ein Fenster je Wochentag |
| Tagesabweichendes Ziel | **Optional** | Wochenfenster | überschreibt das Basissoll nur an diesem Tag |
| Automatische Neuplanung | Bedienaktion | gültige Wochenpläne | ersetzt nur noch nicht begonnene automatische Aufträge atomar |
| Manueller Sofortstart | Grundfunktion | Betriebsfreigaben | Dauer immer, Menge nur mit funktionierender Messung |
| Manueller Auftrag für später | **Erweitert** | Service-Aufruf, Ziel und Gültigkeit | wird in die Dispatcher-Reihenfolge eingereiht |
| Konfliktbehandlung | automatisch/auswählbar | bereits aktiver Vorgang | stoppen und sofort starten oder danach priorisieren |
| Bewässerung stoppen | Sicherheitsfunktion | aktiver Vorgang | schliesst kontrolliert und verbucht bekannte Lieferung |
| Not-Aus | Sicherheitsfunktion | keine weitere Voraussetzung | stoppt sofort und setzt persistente Sperre |
| Sicherheitssperre zurücksetzen | Sicherheitsfunktion | physische Prüfung und Bestätigung | darf keine ungeklärte Ursache übergehen |

## Optionale Erweiterungsmodule

| Modul | Einstufung | Anlagenweite Voraussetzung | Zonenspezifische Voraussetzung | Verhalten bei Deaktivierung |
| --- | --- | --- | --- | --- |
| Pflanzen- und Standortmodell | **Optional** | Modul verfügbar | `Pflanzen- und Standortmodell verwenden` | Teilflächen bleiben gespeichert; Basissoll unverändert |
| Saisonale Korrektur | **Optional** | Anlagenmodul aktiviert | Zonen-Opt-in, zwölf Faktoren und Bestätigung | Faktor 1,0; Kurve bleibt gespeichert |
| Gemessene Wasserbilanz | **Optional** | Wettermodul und Quellenzuordnung | Zonen-Opt-in und vollständige Umrechnung | Rückfall auf saisonales Basissoll; Werte bleiben gespeichert |
| Prognosebasierte Verschiebung | **Optional** | zugeordnete Wettervorhersage | aktive Wasserbilanz, Grenzen und Nachholfenster | keine neue Verschiebung; Einstellungen bleiben erhalten |
| Bodenfeuchterückmeldung | **Optional** | Wettermodul | aktive Wasserbilanz, gültige Prozentquelle und Kalibrierung | Zuordnung bleibt erhalten; Bilanz arbeitet ohne Rückmeldung |
| Teilgaben und Sickerpausen | **Optional** | Sickerpausenmodul aktiviert | Zonen-Opt-in und vier positive Grenzen | neue Aufträge laufen zusammenhängend; Werte bleiben gespeichert |

## Pflanzen- und Standortmodell

| Teilfunktion | Einstufung | Hinweis |
| --- | --- | --- |
| Mehrere Teilflächen | **Optional** | alle Teilflächen einer Zone werden gleichzeitig bewässert |
| Flächengrösse | **Bedingt** | für Umrechnung von Millimeter in Liter relevant |
| Pflanzenprofil | **Optional** | Rasen, Gehölze, Stauden, Gemüse, Kübel, Jungpflanzen, Bodendecker oder benutzerdefiniert |
| Entwicklungszustand | **Optional** | neu angepflanzt oder etabliert |
| Exposition | **Optional** | sonnig, halbschattig oder schattig |
| Bodenprofil | **Optional** | sandig, lehmig-sandig, lehmig, tonig oder benutzerdefiniert |
| Ausbringungsprofil | **Optional** | Tropfschlauch, Sprinkler/Regner, Mikrobewässerung oder benutzerdefiniert |
| Erweiterte Angaben | **Optional** | Hangneigung, Mulch und relative Ausbringungsrate |
| Qualitative Empfehlung | automatisch bei Profildaten | verändert das bestätigte Basissoll niemals automatisch |

## Wetter und Wasserbilanz

| Quellenrolle | Einstufung | Verwendung |
| --- | --- | --- |
| Gemessene Niederschlagssumme | **Bedingt für Wasserbilanz** | täglicher Niederschlagsbeitrag |
| Referenz-Evapotranspiration | **Bedingt für Wasserbilanz** | täglicher klimatischer Bedarf |
| Wettervorhersage | **Bedingt für Verschiebung** | wahrscheinlicher Regen und Nachholstrategie |
| Aktuelle Niederschlagsrate | **Optional** | Diagnose und aktueller Zustand |
| Lufttemperatur | **Optional** | Diagnose/erweiterte Wetterbeobachtung |
| Relative Luftfeuchtigkeit | **Optional** | Diagnose/erweiterte Wetterbeobachtung |
| Taupunkt | **Optional** | Diagnose/erweiterte Wetterbeobachtung |
| Windgeschwindigkeit | **Optional** | Diagnose/erweiterte Wetterbeobachtung |
| Sonneneinstrahlung | **Optional** | Diagnose/erweiterte Wetterbeobachtung |

Quellen dürfen lokal oder von einem externen Wetterdienst stammen. Unbrauchbare oder
fehlende Pflichtquellen werden nicht als Null gewertet; die Planung fällt sichtbar auf
das saisonale Basissoll zurück.

## Teilgaben und Sickerpausen

| Teilfunktion | Einstufung | Sicherheitswirkung |
| --- | --- | --- |
| Maximale Teilgabengrösse | **Pflicht bei Modulnutzung** | begrenzt jede einzelne Öffnung |
| Minimale Sickerpause | **Pflicht bei Modulnutzung** | garantiert eine ventilfreie Pause |
| Maximale Anzahl Teilgaben | **Pflicht bei Modulnutzung** | begrenzt Schaltzyklen und Vorgang |
| Maximale Gesamtlebensdauer | **Pflicht bei Modulnutzung** | beendet einen zu lange dauernden Vorgang |
| Restart während Sickerpause | automatisch | setzt Restziel aus persistentem Zustand genau einmal fort |
| Andere Zone während Pause | automatisch und konservativ | nur wenn die sichere Fortsetzung nicht gefährdet wird |
| Teilgabendetails im Verlauf | automatisch | gemeinsamer Vorgang bleibt einmalig aggregiert |

## Cards und sichtbare Bedienung

| Oberfläche | Einstufung | Funktionen |
| --- | --- | --- |
| Anlagenkarte | **Optional, empfohlen** | Status, Aufträge, nächste Zone, Start, Laufzeit/Wasser, Zähler, Not-Aus |
| Zonenkarte | **Optional, empfohlen** | Status, nächste Bewässerung, manuell starten, stoppen, Verlauf, Teilgabenstatus |
| Auftragsdialog | Bestandteil der Anlagenkarte | lokaler Tag, Datumsnavigation, Reihenfolge und Ziele |
| Verlaufsdialog | Bestandteil der Zonenkarte | Filter, lokalisierte Zeit, Laufzeit, Liter, Ergebnis, Pagination, Teilgaben |
| Grafischer Karteneditor | Bestandteil beider Cards | Auswahl genau einer Status-Entity als Anker |
| Rohentitäten | **Erweitert** | eigene Dashboards und Automationen ohne Custom Card |

## Entitäten und Diagnose

| Entitätstyp | Verfügbarkeit | Zweck |
| --- | --- | --- |
| Anlagenstatus | immer | effektiver Betriebszustand und Card-Anker |
| Zonenstatus | je Zone | effektiver Zonenstatus und Card-Anker |
| Not-Aus | immer | persistenter Not-Aus-Zustand |
| Anlagen-Sicherheitssperre | immer | persistente Sicherheitsstörung |
| Offene Aufträge | immer | Anzahl noch nicht gestarteter Aufträge |
| Nächste Zone / nächster Start | immer | queue-berechnete Planung |
| Laufzeit heute/Monat | immer | Zeitstatistik ohne notwendige Messung |
| Wasser heute/Monat/gesamt | mit Messung | gemessene Verbrauchsstatistik |
| Korrigierter physischer Zähler | mit Messung | kontinuierlicher abgeglichener Zählerstand |
| Nächste Bewässerung | je Zone | nächster berechneter Start |
| Integrationsdiagnose | immer | Konfiguration, Quellenqualität, Dispatcher, Recovery und Teilgaben; sensible IDs redigiert |

## Home-Assistant-Aktionen für fortgeschrittene Nutzung

Die Cards verwenden validierte Integrationsaktionen. Dieselben Aktionen können in
Home-Assistant-Skripten oder Automationen eingesetzt werden:

- manuelle Bewässerung starten oder als Auftrag speichern
- offenen Auftrag stornieren
- aktiven Vorgang stoppen
- Not-Aus auslösen
- Anlagen- und Zonenbetrieb setzen
- Anlagen- und Zonenautomatik setzen
- Sicherheitssperre zurücksetzen
- automatische Aufträge neu planen
- physischen Zähler korrigieren
- offene Aufträge und Zonenverlauf als Antwortdaten abfragen

Diese Aktionen sind **erweitert** und ersetzen nicht die Sicherheitsprüfung vor Ort.
Not-Aus und das Zurücksetzen einer Sperre sollten nicht in Komfortautomationen versteckt
werden.

## Bewusst nicht automatisch

Folgende Entscheidungen trifft IrrigationManager nicht stillschweigend:

- keine automatische Auswahl von Wetter- oder Bodenfeuchtequellen
- keine automatische Änderung des bestätigten Basissolls durch Pflanzenprofile
- keine automatische Aktivierung optionaler Module für bestehende Anlagen
- keine stille Umstellung einer Mengen- auf Zeitsteuerung
- keine Vergrösserung einer unpassenden Teilgabe
- kein Zurücksetzen einer Sicherheitssperre ohne bestätigte Prüfung
- keine parallele hydraulische Bewässerung mehrerer Zonen
