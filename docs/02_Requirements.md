# Funktionsanforderungen

> **Überholt für Version 2:** `docs/17_Neukonzept.md` ist der verbindliche Implementierungsvertrag. Dieses Dokument beschreibt den früheren Version-1-Umfang und gilt nur noch dort, wo es dem Neukonzept nicht widerspricht; insbesondere sind Bedarfsplanung, zonale Sicherheitssperren und geschätzte Verbrauchsbilanzen ohne Zähler keine bindenden Version-2-Anforderungen.

Dieses Dokument beschreibt den verbindlichen Funktionsumfang vor dem ersten realen Einsatz, mit Ausnahme des ausdrücklich als später markierten Abschnitts. Die Entwicklung darf intern in Stufen erfolgen; die reale Anlage wird erst nach vollständiger Simulation und Sicherheitsprüfung freigegeben.

## Bewässerungsanlage

- Ein Konfigurationseintrag bildet genau eine physische Bewässerungsanlage ab.
- Weitere unabhängige Wasserzufuhren werden als eigene Bewässerungsanlagen eingerichtet.
- Ein Hauptventil ist optional.
- Ein Wasserzähler ist optional; ohne ihn ist nur Zeitsteuerung möglich.
- Ohne Zähler oder Durchflusssensor entfallen Mengenbegrenzung, Leckage- und Durchflussüberwachung; Verbrauch und Bilanzgutschrift werden aus dem Durchflussprofil geschätzt und klar gekennzeichnet.
- Innerhalb einer Anlage darf immer nur eine Bewässerungszone gleichzeitig Wasser erhalten.
- Die gesamte Automatik kann dauerhaft oder zeitlich begrenzt ausgesetzt werden.
- Manuelle Bewässerung bleibt bei ausgeschalteter Automatik möglich.
- Stop finalisiert alle offenen Vorgänge einschließlich Sickerpausen und storniert wartende Aufträge ohne persistente Sperre.
- Not-Aus tut dasselbe und setzt zusätzlich eine persistente Sicherheitssperre.
- Optionale Tages- und Wochenbudgets begrenzen automatische Bewässerung.
- Manuelle Aufträge dürfen Budgets nach sichtbarer Warnung überschreiten.
- Ein optionaler Wassertarif berechnet Kosten pro Anlage und Zone.

## Bewässerungszonen

- Beliebig viele Zonen pro Anlage.
- Genau ein logisches Ventil je Zone; zunächst werden `valve` und `switch` unterstützt.
- Zone benennen, archivieren, automatisch freigeben oder zeitlich begrenzt aussetzen.
- Pflanzen-, Boden-, Standort- und Bewässerungsprofil je Zone.
- Mitgelieferte Profile können kopiert und angepasst werden.
- Saisonale Pflanzenfaktoren werden als Jahreskurve modelliert.
- Ein einfacher Modus verwendet ein gemeinsames Zonenprofil.
- Optional können Teilflächen mit Pflanzenprofil, Fläche und relativer Ausbringungsrate erfasst werden.
- Teilflächen werden zu einem gemeinsamen effektiven Zonenprofil zusammengeführt; sie führen keine eigene Wasserbilanz.
- Der berechnete Zonenfaktor kann manuell überschrieben werden.
- Regenexposition wird über einen zonenspezifischen Regenfaktor abgebildet.
- Bodenfeuchtesensoren können einer Zone oder Teilfläche zugeordnet werden.
- Mehrere Feuchtesensoren werden nach einer wählbaren Strategie zusammengeführt.
- Bodenfeuchte kann je Zone als Sperre, Korrektur oder primäre Bedarfsquelle dienen.
- Optionale Batterie-, Verbindungs- und Störungssensoren der Ventilhardware werden vor einem Start geprüft.

## Bewässerungsmodi und Rhythmus

- Bedarfsbewässerung führt einen Termin nur bei ausreichendem Wasserbedarf aus.
- Mindestbewässerung liefert am fälligen Termin das Maximum aus berechnetem Bedarf und konfigurierter Mindestmenge.
- Eine dauerhaft ausgeschaltete Automatikfreigabe entspricht einem rein manuellen Betrieb.
- Rhythmus über minimalen und maximalen Abstand zwischen wirksamen Bewässerungen.
- Der Abstand beginnt erst nach einer konfigurierbaren wirksamen Mindestmenge erneut.
- Fehlgeschlagene, übersprungene oder zu kleine Testläufe setzen den Abstand nicht zurück.
- Jede Zone besitzt ein oder mehrere Bewässerungsfenster.
- Fenster dürfen über Mitternacht reichen und je Wochentag abweichen.
- Fenster können feste Uhrzeiten oder Sonnenaufgang/-untergang mit Offset verwenden.
- Automatische Vorgänge starten nur, wenn mindestens eine wirksame Teilgabe in die Restzeit passt.
- Ist das vollständige Ziel zu groß, darf der Scheduler planmäßig eine verkleinerte Teilgabe bis zum Fensterende erzeugen.
- Das Fensterende ist eine harte Grenze; eine Teilmenge wird verbucht und der Restbedarf bleibt erhalten.
- Prognoseaufschub ist je Zone zeitlich begrenzt.
- Ein einmalig übersprungener Auftrag bleibt bis zur nächsten Gelegenheit unterdrückt.
- Diese Unterdrückung bleibt über Neustarts erhalten, obwohl automatische Aufträge neu geplant werden.

## Bewässerungsziele

- Jede Zone verwendet regulär Mengen- oder Zeitsteuerung.
- Mengensteuerung endet am gemessenen Zielvolumen und besitzt immer ein hartes Zeitlimit.
- Zeitsteuerung endet nach Dauer; ein vorhandener Zähler dokumentiert die reale Menge.
- Manuelle Aufträge dürfen unabhängig vom normalen Zonenmodus Menge oder Zeit vorgeben.
- Eine maximale Menge und Laufzeit je Vorgang begrenzt große Rückstände; Restbedarf bleibt erhalten.
- Die maximale Bewässerungslaufzeit zählt nur tatsächliche Wasserabgabe über alle Teilgaben.
- Eine separate maximale Vorgangsdauer begrenzt die gesamte verstrichene Zeit einschließlich Sicker- und Wartezeiten.
- Ziele werden auf die Messauflösung des Wasserzählers abgestimmt.
- Bei ungeeigneter Auflösung wird Zeitsteuerung empfohlen.
- Eine kalibrierte Vorabschaltung kann Ventil- und Messnachlauf kompensieren.
- Zielmenge berücksichtigt optional den erwarteten Bedarf bis zur nächsten erlaubten Bewässerung.
- Das Prioritätsziel nach Sicherheit ist je Zone zwischen Pflanzenschutz und Wassersparen wählbar.

## Teilgaben und Sickerpausen

- Eine Zone kann ihr Ziel in konfigurierbare Teilgaben aufteilen.
- Zwischen Teilgaben liegt eine Sickerpause.
- Während der Sickerpause sind Haupt- und Zonenventil geschlossen.
- Andere Zonen dürfen während einer Sickerpause ausgeführt werden.
- Alle Teilgaben gehören zu einem gemeinsamen Bewässerungsvorgang.
- Gelieferte Teilmengen werden sofort verbucht; der verbleibende Bedarf geht nicht verloren.

## Scheduler und Aufträge

- Automatische und manuelle Anforderungen werden als stornierbare Bewässerungsaufträge geführt.
- Wartende Aufträge zeigen Zone, Quelle, Ziel, erwarteten Start und Ablaufzeit.
- Mehrere manuelle Zonen können als sortierbare Auftragsliste zusammengestellt werden.
- Ein manueller Auftrag kann sofort oder einmalig für die Zukunft geplant werden.
- Manuelle Aufträge überleben Neustarts, werden danach neu validiert und verfallen nach ihrer konfigurierten Ablaufzeit.
- Ein manueller Auftrag erhält Vorrang vor weiteren automatischen Aufträgen, unterbricht aber keine aktive Teilgabe.
- Manueller und automatischer Auftrag derselben Zone bleiben getrennt; nach dem manuellen Vorgang wird der automatische Bedarf neu berechnet.
- Reihenfolge automatischer Aufträge: drohendes Fensterende, relative Bedürftigkeit, konfigurierte Zonenpriorität.
- Bei unzureichender Fensterzeit wird eine Teilmenge geliefert und der Rest neu geplant.
- Geplante Aufträge erscheinen in einem schreibgeschützten Home-Assistant-Kalender.
- Vorschau und Trockenlauf zeigen zukünftige Entscheidungen, ohne Ventile zu schalten.

## Manuelle Bedienung

- Manueller Start einer Zone mit Menge oder Dauer.
- Einmaliger Mehrzonenplan mit individuellen Zielen.
- Wartende manuelle Aufträge bearbeiten, sortieren und stornieren.
- Aktiven Vorgang stoppen, pausieren und fortsetzen.
- Pause schließt alle Ventile und bewahrt das Restziel.
- Eine nicht fortgesetzte Pause endet nach konfigurierbarer Frist; Restbedarf wird neu geplant.
- Zielmenge oder Restlaufzeit kann innerhalb aller Sicherheitsgrenzen verändert werden.
- Stop und Stop+Überspringen sind getrennte Aktionen.
- Manuelle Vorgänge dürfen außerhalb von Rhythmus und Bewässerungsfenster laufen.
- Tatsächlich gelieferte manuelle Bewässerung reduziert immer die Wasserbilanz; ohne Messquelle wird sie aus Laufzeit und Durchflussprofil geschätzt und als solche gekennzeichnet.
- Wetter-Komfortsperren wie Wind dürfen manuell übersteuert werden; Frost nicht.
- Start- und Bedienentities werden nicht automatisch für Sprachassistenten freigegeben.

## Wetter und Wasserbilanz

- Lokale Home-Assistant-Sensoren und Weather-Entities können pro Messgröße priorisiert werden.
- Open-Meteo wird als direkte optionale Standardquelle angeboten.
- Andere Wetterdienste werden generisch über Home-Assistant-Entities eingebunden.
- Temperatur, Luftfeuchtigkeit beziehungsweise Taupunkt, Wind, Luftdruck, Strahlung, Regen und Prognosen werden unterstützt.
- Direkte Referenzverdunstung kann als Primärquelle gewählt werden.
- Eigene Berechnung und direkte ET0-Quelle können zur Plausibilitätskontrolle verglichen werden.
- Bevorzugte Berechnung ist FAO-56 Penman-Monteith bei ausreichenden Daten.
- Definierte Fallbackkette verwendet datenärmere Modelle, bevor die Berechnung ausgesetzt wird.
- Jedes Ergebnis nennt verwendetes Modell, Datenquellen, Alter und Qualitätsstufe.
- Der Bilanzzeitraum wird wissenschaftlich passend zum Modell festgelegt.
- Nur das Aktualisierungsintervall vorläufiger Anzeigen kann als Expertenoption verändert werden.
- Gemessener Regen verändert die persistente Bilanz.
- Prognostizierter Regen verändert die Bilanz und Zielmenge nicht, kann aber anhand Menge und Wahrscheinlichkeit Aufträge verschieben.
- Wirksamer Regen berücksichtigt Regenfaktor, Bodenaufnahme, Speicherkapazität, Abfluss und Drainage.
- Wetterausfälle verwenden zeitlich begrenzt historische oder saisonale Ersatzwerte; danach wird die Bedarfsautomatik ausgesetzt.
- Wettersperren für Frost, Wind und aktuellen Regen stammen aus Profilen und sind zonenspezifisch überschreibbar.
- Einsetzender Regen beendet einen automatischen Vorgang ab konfigurierbarer Schwelle.
- Ausgangszustand einer neuen Zone wird als frisch bewässert, manuelles Defizit oder optionaler Recorder-Rückblick gewählt.
- Bilanz kann absolut gesetzt oder relativ korrigiert werden; Grund und Änderung werden historisiert.
- Aus Korrekturen und Sensorabweichungen werden nur Vorschläge abgeleitet; Parameter ändern sich nie selbstständig.
- Vergangene Berechnungen behalten die damals verwendeten Eingaben und werden nicht rückwirkend neu berechnet.
- Die UI zeigt eine vollständige Beitragsaufschlüsselung jeder Zielberechnung.

## Wasserzähler und Durchfluss

- Unterstützte Quellen: kumulatives Volumen, Durchflussrate und rohe Impuls-/Zählwerte mit Umrechnungsfaktor.
- Kumulatives Volumen ist die bevorzugte Verbrauchsquelle.
- Ein optionaler Durchflusssensor verbessert Reaktion und Plausibilität.
- Quellen werden unabhängig von Hersteller und Integration über Einheiten und Geräteklassen normalisiert.
- Der interne Gesamtverbrauch läuft über Quellen- und Gerätestarts hinweg fort.
- Fallende oder zurückgesetzte Quellwerte werden erkannt.
- Physischer Ist-Zählerstand kann jederzeit korrigiert werden.
- Eine Korrektur ändert nur den zukünftigen Offset und keine historischen Zonenverbräuche.
- Bei Ausfall des kumulativen Zählers kann integrierter Durchfluss als gekennzeichneter Fallback dienen.
- Weitere Fallbacks werden je Zone über die Zählerausfallstrategie bestimmt.
- Verbrauch wird für Anlage, jede Zone und unzugeordnete Mengen kumuliert.
- Kumulative Wasserentities sind mit Home-Assistant-Langzeitstatistik und Energie-Dashboard kompatibel.
- Tag-, Wochen-, Monats- und Jahreswerte werden über Statistiken dargestellt.
- Durchfluss wird direkt gelesen oder aus Zähleränderung und Zeit abgeleitet.
- Ungeordneter Durchfluss wird nach konfigurierbarer Schwelle als mögliche Leckage behandelt.

## Durchflussprofile und Kalibrierung

- Jede Zone besitzt erwarteten minimalen und maximalen Durchfluss.
- Werte können manuell eingegeben oder durch einen geführten Kalibrierungslauf bestimmt werden.
- Kalibrierung ist jederzeit außerhalb der Wintersperre wiederholbar.
- Neue Werte werden vor Übernahme angezeigt und bestätigt.
- Kalibrierungswasser zählt als Zonenverbrauch und reduziert die Wasserbilanz.
- Langsame Abweichungen erzeugen einen Vorschlag zur erneuten Kalibrierung.
- Durchflussprofile ändern sich nicht automatisch.

## Sicherheit

- Zugeordnete Ventile stehen unter exklusiver Kontrolle der Integration.
- Unerwartetes Öffnen wird geschlossen und sperrt die Anlage.
- Unerwartetes Schließen beendet den Vorgang, verbucht die Teilmenge und sperrt Zone beziehungsweise Anlage.
- Aktorzustand wird nach jedem Befehl geprüft.
- Optionales separates Feedback-Entity kann den realen Zustand bestätigen.
- Schalt-, Stabilisierungs- und Nachlaufzeiten sind pro Anlage und Zone konfigurierbar.
- Schließreihenfolge von Haupt- und Zonenventil ist pro Anlage konfigurierbar.
- Niedriger Durchfluss stoppt und sperrt die betroffene Zone.
- Hoher Durchfluss stoppt und sperrt die gesamte Anlage.
- Durchfluss ohne aktive Teilgabe wird ab Schwellwert als Leckage behandelt.
- Hauptventil wird zwischen allen Zonen und Teilgaben geschlossen.
- Maximale Zonen- und Gesamtlaufzeiten gelten immer; Maximalmengen gelten nur bei verfügbarer plausibler Mengenquelle.
- Ein Hardware-Abschalttimer wird dringend empfohlen und als Setup-Warnung behandelt, aber nicht technisch vorausgesetzt.
- Nach Neustart werden alle Ventile geschlossen, sämtliche offenen Vorgänge einschließlich Sickerpausen als unterbrochen verbucht und die Planung neu erstellt.
- Not-Aus und Wintersperre bleiben über Neustarts erhalten.
- Eine bestehende Gefahr darf im normalen automatischen oder manuellen Betrieb nicht übersteuert werden.
- Im Wartungstest dürfen Feedback-, Durchfluss-, Wetter- und externe Sensorprüfungen zeitlich begrenzt übersteuert werden.
- Not-Aus, Wintersperre, exklusive Ein-Zonen-Ausführung, Wartungstimeout und Benutzer-Stop sind niemals übersteuerbar.
- Ein Wartungstest verlangt regelmäßige Dead-Man-Bestätigung; ausbleibende Bestätigung schließt alle Ventile.
- Freie Wartungstests können Wasser wahlweise einer Zone oder unzugeordnet verbuchen.
- Externe Freigabe- und Sperrsensoren werden ohne freie Template-Bedingungen unterstützt.

## Winter und Wartung

- Wintererinnerung wird durch konfigurierbares Datum oder Frostprognose ausgelöst.
- Bestätigung „Anlage entleert“ setzt eine vollständige Wintersperre.
- Freigabe im Frühjahr erfolgt durch bewusste Bestätigung.
- Ein optionaler geführter Anlagenprüflauf wird bei Inbetriebnahme angeboten.
- Der Prüflauf bleibt außerhalb der Wintersperre jederzeit verfügbar.
- Wiederkehrende Wartungsaufgaben können aus Vorlagen oder frei angelegt werden.
- Wartungsaufgaben besitzen Fälligkeit, Bestätigung und Historie.

## UI und Integration

- Vollständiger Config Flow und Options Flow ohne YAML-Pflicht.
- Einfache Profile und Vorschläge mit Erklärungen; Expertenwerte bleiben einsehbar und überschreibbar.
- Geführte Schätzung für unbekannte Flächen und Ausbringungsraten.
- Plausibilitätsprüfung von Entities, Einheiten, Grenzwerten und erwarteten Laufzeiten.
- Ein Vorgang verwendet einen unveränderlichen, beim Preflight validierten Konfigurationssnapshot.
- Änderungen im Config/Options Flow werden erst im sicheren Leerlauf wirksam; Stop, Not-Aus und neue Sicherheitssperren wirken unmittelbar über die Laufzeitsteuerung, nicht durch Mutation des Snapshots.
- Eigene Übersichts- und Zonenkarte werden gemeinsam mit der Integration ausgeliefert.
- Karten besitzen einen grafischen Editor und funktionieren mobil sowie auf Desktop.
- Kernentities sind standardmäßig aktiv; technische Diagnoseentities standardmäßig deaktiviert.
- Vollständige Home-Assistant-Aktionen und strukturierte Ereignisse für Bedienung und Automationen.
- Persistente HA-Benachrichtigungen plus optionale Notify-Ziele je Ereignistyp.
- Konfiguration kann als portable Datei exportiert und importiert werden.
- Historie kann als CSV und JSON exportiert werden.
- Diagnoseexport enthält redigierte Konfiguration, Entscheidungen, Quellenqualität, Ventil- und Zählerdaten.
- Deutsch und Englisch werden vollständig unterstützt.
- Projekt und private Vorabversion verwenden die MIT-Lizenz; die öffentliche HACS-Veröffentlichung folgt erst nach dem Feldtest.

## Historie und Auswertung

- Konfigurierbar begrenzte interne Detailhistorie.
- Ein Vorgang enthält Auftrag, Teilgaben, Berechnungssnapshot, Ziele, Messungen, Quellen, Gründe, Warnungen und Ergebnis.
- Recorder und Langzeitstatistik speichern langfristige Messreihen und kumulative Mengen.
- Auswertungen zeigen Verbrauch und Bedarfsdeckung nach Tag, Woche, Monat und Jahr pro Anlage und Zone.
- Geplante, gelieferte, gemessene, geschätzte und unzugeordnete Mengen bleiben unterscheidbar.

## Spätere Erweiterung

- Wasserquellen wie Zisterne oder Brunnen mit Füllstand, Druck, Pumpe und Umschaltung sind architektonisch vorzubereiten, aber nicht Teil des ersten realen Einsatzes.
- Das öffentliche HACS-Release folgt erst nach privatem Feldtest des vollständigen Erstumfangs.
