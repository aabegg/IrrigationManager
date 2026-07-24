# Neukonzept

Status: Verbindlicher Implementierungsvertrag für Version 2; weitere Erweiterungsmodule bleiben offen

Dieses Dokument ist der maßgebliche Implementierungsvertrag für Version 2. Bei Widersprüchen ersetzt es die älteren Anforderungs-, Sicherheits-, UI- und Qualifikationsdokumente. Bestehende Version-1-Einträge werden bewusst destruktiv in eine gesperrte Version-2-Hülle migriert und erst nach gültiger lokaler Neukonfiguration wieder freigegeben.

## Leitidee

Eine Bewässerungsanlage soll mit möglichst wenigen Angaben in Betrieb genommen werden können. Zusätzliche Fähigkeiten werden später durch optionale Einstellungen und Module ergänzt, ohne das Grundmodell unnötig zu vergrößern.

## Initialer Minimalumfang

Die Abschnitte zu Startvoraussetzungen, einfacher automatischer Bewässerung, Anlagen- und Zonenzuständen sowie Dashboard-Cards bilden den initialen Minimalumfang des neuen Irrigation Managers. Dieser Umfang soll für eine sinnvolle Verwendung vollständig ausreichen und darf keine späteren Erweiterungsmodule voraussetzen.

Der initiale Minimalumfang ermöglicht:

- die Erfassung einer Bewässerungsanlage mit einer oder mehreren Bewässerungszonen
- den Betrieb ausschließlich mit den Zonenventilen, ohne Hauptventil und Wasserzähler
- die manuelle zeitgesteuerte Bewässerung einzelner Zonen
- die automatische zeitgesteuerte Bewässerung anhand eines Wochenplans pro Zone
- die geordnete, aufeinanderfolgende Ausführung offener Bewässerungsaufträge
- getrennte Betriebs- und Automatikfreigaben für Anlage und Zonen
- einen anlagenweiten Not-Aus mit persistenter Sicherheitssperre
- Laufzeitstatistiken für Anlage und Zonen
- eine Anlagen-Card und eine Zonen-Card für Anzeige und Bedienung im Home-Assistant-Dashboard

Nicht zum initialen Minimalumfang gehören insbesondere:

- Hauptventil und Pumpe
- Wasserzähler, Durchflussmessung und Mengensteuerung
- gemessene Wasserverbrauchsstatistiken
- Wetterdaten, Prognosen und Wasserbedarfsberechnung
- Pflanzen-, Boden- und Standortprofile
- Regen- und Bodenfeuchtesensoren
- Durchflussüberwachung und Kalibrierung
- Teilgaben und Sickerpausen

Diese Fähigkeiten können später als optionale Module ergänzt werden. Eine Anlage ohne solche Module bleibt vollständig manuell und automatisch zeitgesteuert verwendbar.

## Konfigurationsführung der Anlage

Die erstmalige Erfassung einer Bewässerungsanlage erfolgt als mehrstufiger Wizard. Jeder Schritt behandelt einen fachlich zusammengehörenden Bereich und bleibt dadurch auch bei späteren Erweiterungen übersichtlich.

Der Wizard beginnt mit:

1. **Basisinformationen:** Erfassung der Bezeichnung der Bewässerungsanlage.
2. **Hauptventil:** Erklärung des optionalen Hauptventils und optionale Auswahl seiner Home-Assistant-Entity.
3. **Wassermessung:** Erklärung der optionalen Wassermessung und Auswahl der Messart sowie ihrer Home-Assistant-Entity.

Der Hauptventil-Schritt beginnt mit einem kurzen Text, der fragt, ob die Anlage ein Hauptventil besitzt, und dessen Verwendung erklärt. Darunter befindet sich ein optionales Entity-Auswahlfeld. Ein leeres Auswahlfeld bedeutet, dass die Anlage kein Hauptventil verwendet; ein zusätzliches Ja-/Nein-Feld ist nicht erforderlich.

Der Wassermessungs-Schritt bietet die Auswahl `Keine Wassermessung`, `Kumulativer Volumenzähler` und `Impulszähler`. Abhängig von der Messart werden nur die dazugehörenden Felder angezeigt. Beim Impulszähler weist ein Erklärungstext darauf hin, dass spätere Ablesungen des physischen Wasserzählers für eine Langzeitkalibrierung und einen verbesserten Umrechnungsfaktor verwendet werden können.

Spätere Einstellungen des Hauptventil-Moduls werden im selben Schritt ergänzt. Dazu können bei Bedarf eine Öffnungs- und eine Schliesswartezeit gehören, ohne die Basisinformationen oder andere Module mit technischen Details zu überladen.

Nach der Ersteinrichtung sind die einzelnen Konfigurationsbereiche direkt über die Anlageneinstellungen erreichbar. Eine Änderung des Hauptventils soll nicht das erneute Durchlaufen des gesamten Einrichtungs-Wizards erfordern.

## Startvoraussetzungen

Eine physische Bewässerungsanlage besitzt eine gemeinsame Wasserzuleitung. Die Wasserzuleitung wird im Irrigation Manager nicht konfiguriert.

Für die Erfassung im Irrigation Manager benötigt eine Bewässerungsanlage lediglich:

- eine Bezeichnung
- mindestens eine Bewässerungszone

Eine Bewässerungszone benötigt lediglich:

- eine Bezeichnung
- genau ein schaltbares Ventil

Ein Hauptventil und ein Wasserzähler sind keine Startvoraussetzungen. Eine so konfigurierte Anlage kann mehrere Zonen besitzen und bereits manuell betrieben werden.

## Optionales Hauptventil-Modul

Das Hauptventil-Modul wird aktiviert, sobald in den Anlageneinstellungen eine Hauptventil-Entity ausgewählt ist. Unterstützt werden Home-Assistant-Entities der Domains `valve` und `switch`. Die ausgewählte Entity muss bereits die korrekte Offen-/Geschlossen- beziehungsweise Ein-/Aus-Semantik besitzen.

Das Verhalten des Hauptventils ist fest vorgegeben:

- Vor dem Start der ersten Zone wird das Hauptventil geöffnet.
- Erst nach dem Öffnen des Hauptventils wird das Zonenventil geöffnet.
- Die Wiederverwendung eines bereits geöffneten Hauptventils für unmittelbar aufeinanderfolgende Bewässerungsaufträge ist aufgeschoben. Bis zu dieser Optimierung wird es ausfallsicher nach jedem Auftrag geschlossen und vor dem nächsten Auftrag erneut geöffnet.
- Nach dem Ende der letzten aktiven Zone wird zuerst das Zonenventil und danach das Hauptventil geschlossen.
- Bei Pause, Abbruch, Deaktivierung, Fehler und Not-Aus wird das Hauptventil geschlossen.
- Nach einem Neustart darf das Hauptventil ohne aktiven Bewässerungsvorgang nicht geöffnet bleiben.
- Ist die Hauptventil-Entity nicht verfügbar oder kann sie nicht zuverlässig geschaltet werden, startet keine Zone und die gesamte Bewässerungsanlage wird gesperrt.
- Das Hauptventil wird nicht unabhängig manuell bedient, sondern ausschliesslich als Teil eines Bewässerungsvorgangs gesteuert.

Für den ersten Ausbau besitzt das Modul keine weiteren Einstellungen. Eine optionale Öffnungswartezeit zwischen Haupt- und Zonenventil sowie eine optionale Schliesswartezeit zwischen Zonen- und Hauptventil können später im bestehenden Hauptventil-Schritt ergänzt werden. Beide Werte verwenden dann standardmässig `0 Sekunden`.

## Optionales Wassermengen-Modul

Das Wassermengen-Modul wird im Schritt `Wassermessung` des Anlagen-Wizards konfiguriert. Die Auswahl `Keine Wassermessung` lässt die Anlage vollständig zeitgesteuert und aktiviert das Modul nicht.

### Kumulativer Volumenzähler

Bei dieser Messart wird genau eine Sensor-Entity ausgewählt, deren Zustand einen fortlaufenden Wasserzähler in einer unterstützten Volumeneinheit darstellt. Die Integration normalisiert den Wert intern auf Liter und übernimmt positive Zählerdifferenzen als gemessenen Verbrauch.

### Impulszähler

Bei dieser Messart wird genau eine fortlaufende Zähler-Entity ausgewählt. Zusätzlich wird eine der beiden Eingabeformen gewählt:

- Wassermenge pro Impuls
- Impulse pro Liter

Der Umrechnungswert muss grösser als null sein. Intern wird unabhängig von der gewählten Eingabeform ein einheitlicher Umrechnungsfaktor in Liter pro Impuls verwendet.

Der Wizard erklärt, dass der anfängliche Umrechnungsfaktor später durch eine Langzeitkalibrierung überprüft werden kann. Hierzu werden bestätigte physische Zählerstände über einen ausreichend langen Messzeitraum mit der inzwischen erfassten Impulsmenge verglichen.

### Interne Zähler

Die Integration führt zwei getrennte Werte:

- **Kumulativer Anlagenverbrauch:** Die Summe aller akzeptierten gemessenen Verbrauchsdifferenzen. Dieser Wert bleibt monoton steigend und bildet die Grundlage für Anlagen- und Zonenverbräuche sowie Tages-, Monats- und Home-Assistant-Langzeitstatistiken.
- **Abgeglichener Zählerstand:** Der fortgeführte Stand des physischen Wasserzählers. Dieser Wert kann durch eine bestätigte physische Ablesung korrigiert werden.

Eine Zählerstandskorrektur verändert keine vergangenen Verbräuche und wird nicht selbst als Wasserverbrauch gewertet.

Der abgeglichene Zählerstand wird bei aktiver Wassermessung in der Anlagen-Card angezeigt. Während einer Bewässerung wird er automatisch mit jeder akzeptierten Änderung der Messquelle aktualisiert:

- Beim kumulativen Volumenzähler wird jede positive Zählerdifferenz übernommen.
- Beim Impulszähler wird jeder neu gemeldete Impuls mit dem Umrechnungsfaktor addiert.

Die Card aktualisiert sich über die Zustandsänderungen der zugehörenden Home-Assistant-Entity. Die Anzeige kann deshalb abhängig von Aktualisierungsrate und Messauflösung schrittweise steigen. Zwischen zwei Messwerten werden keine vermeintlich exakten Zwischenstände erzeugt.

### Zählerkontinuität

Die Integration erhält ihren internen Zählerstand auch bei Änderungen der Messquelle. Sie berücksichtigt insbesondere:

- eine plötzliche Zurücksetzung oder einen Neustart des Quellzählers
- einen Gerätewechsel oder Wechsel der ausgewählten Entity
- einen Zahlenüberlauf
- kurzfristige negative Schwankungen
- nicht verfügbare oder ungültige Werte
- eine Änderung der von der Entity gemeldeten Einheit

Ein fallender Quellwert erzeugt keinen negativen Verbrauch. Eine als Reset erkannte Änderung setzt einen neuen Bezugspunkt für zukünftige Differenzen, ohne den bisherigen kumulativen Anlagenverbrauch zu verlieren. Mehrdeutige oder unplausible Änderungen werden nicht stillschweigend als Verbrauch übernommen.

### Zählerstand korrigieren

Die Einstellungen des Wassermengen-Moduls bieten die Aktion `Zählerstand korrigieren`. Der Benutzer gibt den aktuell am physischen Wasserzähler abgelesenen Stand ein. Eine Korrektur speichert mindestens:

- den bisherigen abgeglichenen Zählerstand
- den neuen physischen Zählerstand
- die Differenz
- den Zeitpunkt
- einen optionalen Grund

Nach der Korrektur wird der abgeglichene Zählerstand vom bestätigten Wert aus mit neuen Messdifferenzen fortgeführt. Der kumulative Anlagenverbrauch und bereits zugeordnete Zonenverbräuche bleiben unverändert.

### Protokoll und Langzeitkalibrierung

Das Wassermengen-Modul protokolliert akzeptierte Verbrauchsdifferenzen, erkannte Resets, verworfene Messwerte, Wechsel der Messquelle, Änderungen des Impulsfaktors und manuelle Zählerstandskorrekturen.

Im Impulszählermodus können zwei bestätigte physische Ablesungen als Kalibrierungspunkte dienen. Die Integration vergleicht die physische Verbrauchsdifferenz mit der anhand der Impulse berechneten Verbrauchsdifferenz und kann daraus einen verbesserten Umrechnungsfaktor vorschlagen.

Ein Vorschlag wird nur erzeugt, wenn zwischen den Ablesungen genügend Wasser verbraucht wurde und keine ungeklärten Ausfälle, Resets oder unplausiblen Messwerte vorliegen. Alter Faktor, vorgeschlagener Faktor, Messzeitraum und Abweichung werden angezeigt. Ein vorgeschlagener Faktor wird niemals automatisch übernommen, sondern muss vom Benutzer ausdrücklich bestätigt werden.

Ein direkter Durchflusssensor ist nicht Bestandteil dieses ersten Wassermengen-Moduls und kann später als zusätzliche Mess- und Sicherheitsquelle ergänzt werden.

### Verbrauchszuordnung und Home-Assistant-Entities

Jede akzeptierte Verbrauchsdifferenz wird genau einer Verbrauchsgruppe zugeordnet:

- der eindeutig aktiven Bewässerungszone
- dem nicht zugeordneten Anlagenverbrauch, wenn keine eindeutige Zone bestimmt werden kann

Überspannt das Messintervall eines verzögert aktualisierten Zählers mehrere Zonenwechsel, wird die Menge nicht geschätzt aufgeteilt. Sie bleibt als nicht zugeordneter Anlagenverbrauch erhalten. Die Integration weist darauf hin, wenn Aktualisierungsrate oder Auflösung der Messquelle für eine zuverlässige Zonenzuordnung ungeeignet sind.

Jeder Bewässerungsvorgang speichert unabhängig von seiner Steuerungsart mindestens das geplante Bewässerungsziel, die tatsächliche Laufzeit, die zugeordnete gemessene Wassermenge und deren Zuordnungsqualität.

Das Wassermengen-Modul stellt kumulative Wasser-Entities bereit für:

- den gesamten Anlagenverbrauch
- den Verbrauch jeder Bewässerungszone
- den nicht zugeordneten Anlagenverbrauch

Die Entities verwenden stabile Unique IDs, eine unterstützte Volumeneinheit, die Home-Assistant-Geräteklasse `water` und eine für kumulative Werte geeignete Zustandsklasse. Sie unterstützen Home-Assistant-Langzeitstatistiken und können im Energie-Dashboard als individuelle Wasserverbraucher verwendet werden.

Werden Anlagen- und Zonenverbrauch gemeinsam im Energie-Dashboard verwendet, wird die Anlage als übergeordnete Quelle der Zonen berücksichtigt, damit keine Doppelzählung entsteht. Die Integration stellt geeignete Entities und Einrichtungshinweise bereit, verändert die Konfiguration des Energie-Dashboards aber nicht ungefragt.

## Optionale Mengensteuerung

Die Mengensteuerung ist eine optionale Fähigkeit pro Bewässerungszone und setzt eine aktive, geeignete Wassermessung der Anlage voraus. Eine vorhandene Wassermessung rapportiert auch für weiterhin zeitgesteuerte Zonen die tatsächlich gemessene Wassermenge; sie zwingt keine Zone zur Mengensteuerung.

Bei aktiver Wassermessung erhält die Zonenkonfiguration die Auswahl:

- Zeitsteuerung
- Mengensteuerung

Die gewählte Steuerungsart gilt für die automatische Bewässerung der gesamten Zone und wird nicht pro Wochentag gewechselt. Dadurch behält der Wochenplan seine einfache Struktur.

Bei Zeitsteuerung enthält eine konfigurierte Tageszeile:

- ein Bewässerungsfenster
- eine Bewässerungsdauer

Bei Mengensteuerung enthält eine konfigurierte Tageszeile:

- ein Bewässerungsfenster
- eine Zielwassermenge

Eine mengengesteuerte Zone benötigt zusätzlich eine maximale Laufzeit als harte Sicherheitsgrenze. Ohne gültige Messung startet kein mengengesteuerter Auftrag. Fällt die Messung während des Vorgangs aus oder wird die maximale Laufzeit vor der Zielmenge erreicht, wird der Vorgang gestoppt und die gesamte Bewässerungsanlage gesperrt. Tatsächlich gelieferte Wassermenge und eine mögliche Überschreitung durch die Messauflösung werden protokolliert.

Zielwassermenge, Messauflösung und maximale Laufzeit werden bei der Konfiguration auf Plausibilität geprüft. Ohne Durchflussprofil reserviert die Bewässerungsplanung für einen mengenbasierten Auftrag vorsichtshalber dessen vollständige maximale Laufzeit.

Bei aktiver Wassermessung kann ein manueller Bewässerungsauftrag unabhängig von der automatischen Steuerungsart der Zone eine Dauer oder eine Wassermenge als Ziel verwenden.

Das Wassermengen-Modul kann nicht entfernt oder deaktiviert werden, solange mindestens eine Zone Mengensteuerung verwendet. Die betroffenen Zonen müssen zuvor ausdrücklich auf Zeitsteuerung umgestellt werden; eine stille Rückfalllogik ist nicht zulässig.

## Optionales Durchflussprofil

Eine Zone kann bei aktiver Wassermessung ein optionales Durchflussprofil erhalten. Es beschreibt den für diese Zone erwarteten normalen Durchfluss und verbessert Planung, Prognose und Plausibilitätsprüfung, ist aber keine Voraussetzung für die gemessene Mengensteuerung.

Das Durchflussprofil enthält:

- erwarteten durchschnittlichen Durchfluss
- erwarteten minimalen Durchfluss
- erwarteten maximalen Durchfluss
- Zeitpunkt der letzten Kalibrierung
- Herkunft und Qualität der Werte

Mit einem Durchflussprofil kann die Bewässerungsplanung die erwartete Dauer eines mengenbasierten Auftrags genauer bestimmen, dessen Einpassung in ein Bewässerungsfenster prüfen und eine geeignete maximale Laufzeit vorschlagen. Ohne Profil bleibt die Mengensteuerung möglich und verwendet für die Planung konservativ die konfigurierte maximale Laufzeit.

### Durchfluss kalibrieren

Die Durchflusskalibrierung ist keine gewöhnliche Zoneneinstellung, sondern ein bewusst ausgelöster physischer Bewässerungsvorgang. Bei aktiver Wassermessung steht deshalb im Drei-Punkte-Menü der Zone die Aktion `Durchfluss kalibrieren` beziehungsweise bei vorhandenem Profil `Erneut kalibrieren` bereit.

Die Aktion ist nur ausführbar, wenn:

- Anlage und Zone aktiviert sind
- keine Sicherheitssperre besteht
- die Wassermessung verfügbar und plausibel ist
- kein anderer Bewässerungsvorgang läuft

Die Aktion öffnet einen geführten Dialog oder eine eigene Ansicht. Nach Bestätigung erfasst die Integration den Ausgangszählerstand, öffnet Haupt- und Zonenventil über den regulären Ausführungspfad, misst über eine ausreichende Zeit oder Wassermenge und schliesst danach alle Ventile regulär.

Die Kalibrierung:

- bleibt jederzeit durch den Not-Aus abbrechbar
- besitzt eine harte maximale Dauer und Wassermenge
- wird als besonderer manueller Bewässerungsvorgang protokolliert
- ordnet die gelieferte Wassermenge der kalibrierten Zone zu
- erscheint im Zonenverlauf
- bricht bei Messausfällen oder unplausiblen Werten ab

Nach der Messung werden bisheriges Profil, vorgeschlagener Durchschnitts-, Minimal- und Maximaldurchfluss, Messdauer, Wassermenge und Messqualität angezeigt. Die neuen Werte werden erst nach ausdrücklicher Bestätigung übernommen; ein verworfenes Ergebnis verändert das bestehende Profil nicht.

Das gespeicherte Durchflussprofil wird in den Zonendetails schreibgeschützt angezeigt. Seine erneute Bestimmung erfolgt über die separate Aktion im Drei-Punkte-Menü und nicht beim Bearbeiten der Zoneneinstellungen.

Ein direkter Durchflusssensor ist für die Kalibrierung nicht erforderlich. Der Durchfluss kann aus der Änderung des kumulativen Volumenzählers beziehungsweise der Impulse und der gemessenen Zeit bestimmt werden. Reguläre Bewässerungsvorgänge dürfen spätere Abweichungen erkennen und eine erneute Kalibrierung vorschlagen, verändern das Profil jedoch niemals automatisch.

## Einfache automatische Bewässerung

Jede Bewässerungszone kann optional einen Wochenplan erhalten. Der Wochenplan besteht in Datenhaltung und Benutzeroberfläche aus genau einer Zeile pro Wochentag.

Jede Tageszeile enthält optional ein Bewässerungsfenster und genau das zur Steuerungsart der Zone gehörende Bewässerungsziel: eine Bewässerungsdauer bei Zeitsteuerung oder eine Zielwassermenge bei Mengensteuerung.

Dabei gelten folgende Regeln:

- Sind beide Angaben leer, erfolgt an diesem Wochentag keine automatische Bewässerung.
- Sind Bewässerungsfenster und Bewässerungsziel vorhanden, wird für diesen Wochentag genau ein automatischer Bewässerungsauftrag erzeugt.
- Ist nur eine der beiden Angaben vorhanden, ist die Konfiguration ungültig.
- Das Bewässerungsziel muss größer als null sein.
- Der vollständige Bewässerungsvorgang muss innerhalb des Bewässerungsfensters ausgeführt werden können.
- Ein Bewässerungsfenster darf über Mitternacht reichen und gehört zu dem Wochentag, an dem es beginnt.
- Bewässerungsfenster benachbarter Wochentage derselben Zone dürfen sich nicht überschneiden.

Die geplanten Bewässerungsaufträge werden durch die Bewässerungsanlage geordnet und nacheinander ausgeführt.

## Anlagenzustand und Aktionen

Der Zustand einer Bewässerungsanlage besteht aus drei voneinander unabhängigen Dimensionen:

- **Betriebsfreigabe:** aktiviert oder deaktiviert
- **Automatikfreigabe:** aktiviert oder deaktiviert
- **Sicherheitssperre:** frei oder gesperrt

Aus diesen Dimensionen wird der für den Benutzer sichtbare Anlagenstatus abgeleitet. Die getrennte Speicherung verhindert, dass eine Aktion unbeabsichtigt einen anderen Zustand verändert. Insbesondere hebt das Aktivieren der Anlage keine Sicherheitssperre auf und das Aufheben einer Sicherheitssperre aktiviert keine zuvor deaktivierte Anlage.

Die Bewässerungsanlage bietet folgende Aktionen:

| Aktion | Wirkung |
|---|---|
| Anlage deaktivieren | Entzieht die Betriebsfreigabe, stoppt eine laufende automatische oder manuelle Bewässerung kontrolliert und verhindert jeden weiteren Start. Die Automatikfreigabe bleibt gespeichert. |
| Anlage aktivieren | Erteilt die Betriebsfreigabe wieder. Eine bestehende Sicherheitssperre bleibt wirksam. |
| Anlagenautomatik deaktivieren | Entzieht die Automatikfreigabe und verhindert weitere automatische Starts. Läuft gerade eine automatische Bewässerung, entscheidet der Benutzer nach einer Rückfrage, ob sie kontrolliert gestoppt oder noch abgeschlossen wird. Eine laufende manuelle Bewässerung bleibt unberührt. Manuelle Bewässerung bleibt bei erteilter Betriebsfreigabe und ohne Sicherheitssperre weiterhin möglich. |
| Anlagenautomatik aktivieren | Erteilt die Automatikfreigabe wieder. Die automatischen Bewässerungsaufträge werden anhand der aktuellen Wochenpläne neu bestimmt. |
| Not-Aus | Stoppt die gesamte Anlage sofort und setzt eine persistente Sicherheitssperre. Automatische und manuelle Bewässerung sind danach gesperrt. |
| Sperre aufheben | Hebt die Sicherheitssperre nach ausdrücklicher Bestätigung einer Warnmeldung auf. Betriebs- und Automatikfreigabe werden dabei nicht verändert. |

Für die Freigabe einer Bewässerung gelten damit folgende Bedingungen:

| Zustand | Manuelle Bewässerung | Automatische Bewässerung |
|---|---:|---:|
| Anlage deaktiviert | nein | nein |
| Anlage aktiviert, Automatik deaktiviert, keine Sperre | ja | nein |
| Anlage aktiviert, Automatik aktiviert, keine Sperre | ja | ja |
| Sicherheitssperre gesetzt | nein | nein |

Der angezeigte Anlagenstatus macht mindestens `deaktiviert`, `aktiv mit deaktivierter Automatik`, `aktiv mit aktivierter Automatik` und `gesperrt` unterscheidbar. Eine Sicherheitssperre besitzt in der Anzeige und bei der Ausführungsfreigabe Vorrang vor den anderen Zuständen.

Alle Anlagenaktionen sind in der Einstellungsoberfläche erreichbar, beispielsweise über das Drei-Punkte-Menü der Anlage oder über deren Zahnradsymbol. Das Aufheben einer Sicherheitssperre verlangt immer eine Warnmeldung mit ausdrücklicher Bestätigung.

### Automatische Aufträge neu planen

Das Drei-Punkte-Menü der Bewässerungsanlage bietet zusätzlich die administrative Aktion `Automatische Aufträge neu planen`. Sie ermöglicht jederzeit eine manuell ausgelöste Neuberechnung der Bewässerungsplanung, ist im normalen Betrieb aber nicht erforderlich.

Die Aktion:

- berechnet alle noch nicht begonnenen automatischen Bewässerungsaufträge anhand der aktuellen Wochenpläne und Freigaben neu
- entfernt abgelaufene automatische Bewässerungsaufträge
- verändert keinen aktiven Bewässerungsvorgang
- verändert keine manuellen Bewässerungsaufträge
- umgeht weder eine Deaktivierung noch eine Sicherheitssperre
- erzwingt keinen unmittelbaren Start einer Bewässerung

Die neue Planung wird zuerst vollständig berechnet und validiert und erst danach atomar übernommen. Schlägt die Berechnung fehl, bleibt die bisherige Planung unverändert.

Nach erfolgreicher Ausführung zeigt die Einstellungsoberfläche eine kurze Zusammenfassung der erstellten, ersetzten und entfernten automatischen Bewässerungsaufträge.

Die Bewässerungsplanung wird unabhängig von dieser manuellen Aktion automatisch aktuell gehalten. Eine Neuberechnung erfolgt mindestens nach relevanten Konfigurationsänderungen, nach dem Aktivieren einer Automatikfreigabe, nach einem Neustart und nach dem Abschluss eines Bewässerungsvorgangs.

## Zonenzustand und Aktionen

Der Zustand einer Bewässerungszone besteht aus zwei voneinander unabhängigen Dimensionen:

- **Betriebsfreigabe:** aktiviert oder deaktiviert
- **Automatikfreigabe:** aktiviert oder deaktiviert

Eine Bewässerungszone besitzt keine eigene Sicherheitssperre. Ein während des Betriebs erkannter Fehler sperrt und stoppt immer die gesamte Bewässerungsanlage. Die Betriebs- und Automatikfreigaben der einzelnen Zonen bleiben dabei gespeichert und gelten nach dem Aufheben der Anlagensperre unverändert weiter.

Eine Bewässerungszone bietet folgende Aktionen:

| Aktion | Wirkung |
|---|---|
| Zone deaktivieren | Entzieht die Betriebsfreigabe, stoppt eine laufende automatische oder manuelle Bewässerung dieser Zone kontrolliert und verhindert jeden weiteren Start der Zone. Die Automatikfreigabe bleibt gespeichert. |
| Zone aktivieren | Erteilt die Betriebsfreigabe wieder. Die übergeordneten Zustände der Bewässerungsanlage bleiben wirksam. |
| Zonenautomatik deaktivieren | Entzieht die Automatikfreigabe und verhindert weitere automatische Starts dieser Zone. Läuft gerade eine automatische Bewässerung der Zone, entscheidet der Benutzer nach einer Rückfrage, ob sie kontrolliert gestoppt oder noch abgeschlossen wird. Eine laufende manuelle Bewässerung bleibt unberührt. |
| Zonenautomatik aktivieren | Erteilt die Automatikfreigabe wieder. Die automatischen Bewässerungsaufträge der Zone werden anhand ihres aktuellen Wochenplans neu bestimmt. |

Eine Zone darf nur manuell bewässert werden, wenn Anlage und Zone aktiviert und die Anlage nicht gesperrt sind. Eine automatische Bewässerung erfordert zusätzlich die Automatikfreigabe der Anlage und der Zone.

Der angezeigte Zonenstatus macht mindestens `deaktiviert`, `aktiv mit deaktivierter Automatik` und `aktiv mit aktivierter Automatik` unterscheidbar. Eine übergeordnete Deaktivierung oder Sicherheitssperre der Anlage wird bei der Zone zusätzlich sichtbar gemacht, ohne ihren gespeicherten Zonenzustand zu verändern.

Alle Zonenaktionen sind in der Einstellungsoberfläche erreichbar, beispielsweise über das Drei-Punkte-Menü der Zone oder über deren Zahnradsymbol.

## Dashboard-Cards

Die Dashboard-Cards zeigen den aktuellen Zustand kompakt an und stellen die häufig benötigten Bedienaktionen bereit. Umfangreiche Listen und Detailinformationen werden in Dialogen oder eigenen Ansichten dargestellt, damit die Cards übersichtlich bleiben.

### Anlagen-Card

Im Card-Editor wird genau eine Anlagen-Entity ausgewählt.

Die Anlagen-Card zeigt:

- den Betriebsstatus der Bewässerungsanlage
- die Anzahl offener Bewässerungsaufträge
- die nächste Bewässerung mit erwartetem Startzeitpunkt und Zone
- die Laufzeit heute und im aktuellen Monat, solange keine Mengenmessung verfügbar ist
- die gemessene Wassermenge heute und im aktuellen Monat, sobald eine Mengenmessung verfügbar ist
- einen deutlich sichtbaren roten Not-Aus-Button

Ein Klick auf die Anzahl offener Bewässerungsaufträge öffnet einen Dialog oder eine eigene Ansicht. Die Liste zeigt für jeden Auftrag mindestens Zone, Quelle, Bewässerungsziel, erwarteten Start und aktuellen Status. Das Bewässerungsziel wird je nach Steuerungsart als Dauer oder Wassermenge dargestellt.

Der Not-Aus wird ohne vorgeschalteten Bestätigungsdialog sofort ausgeführt. Er stoppt die gesamte Bewässerungsanlage und setzt deren persistente Sicherheitssperre. Erst das separate Aufheben der Sperre verlangt eine Warnmeldung mit ausdrücklicher Bestätigung.

Die zeitbasierten Kennzahlen werden als `Laufzeit` und nicht als `Verbrauch` bezeichnet. Der Begriff Wasserverbrauch wird nur für gemessene Wassermengen verwendet.

### Zonen-Card

Im Card-Editor wird genau eine Zonen-Entity ausgewählt.

Die Zonen-Card zeigt:

- den Betriebsstatus der Bewässerungszone einschließlich einer wirksamen Deaktivierung oder Sicherheitssperre der Anlage
- die Laufzeit oder gemessene Wassermenge heute
- die Laufzeit oder gemessene Wassermenge im aktuellen Monat
- die nächste Bewässerung
- die Aktion `Manuell bewässern`
- die Aktion `Verlauf anzeigen`

Die Aktion `Manuell bewässern` öffnet einen Dialog zur Eingabe des Bewässerungsziels. Eine Dauer kann immer eingegeben werden. Eine Wassermenge kann nur gewählt werden, wenn für die Anlage eine funktionsfähige Mengensteuerung verfügbar ist.

Ist kein anderer Bewässerungsvorgang aktiv, wird der manuelle Auftrag sofort gestartet. Läuft bereits eine Bewässerung innerhalb der Anlage, entscheidet der Benutzer:

- Der aktive Bewässerungsvorgang wird kontrolliert beendet und der manuelle Auftrag sofort gestartet.
- Der aktive Bewässerungsvorgang wird abgeschlossen und der manuelle Auftrag direkt danach, vor wartenden automatischen Aufträgen, eingereiht.

Die Aktion `Verlauf anzeigen` öffnet einen Dialog oder eine eigene Ansicht mit den Bewässerungsvorgängen der Zone. Für längere Verläufe wird eine eigene Ansicht mit Pagination und Filtern bevorzugt. Jeder Eintrag zeigt mindestens Start, Ende, Quelle, Bewässerungsziel, Ergebnis, tatsächliche Laufzeit, verfügbare Wassermenge und Abschlussgrund.

## Aussagekraft ohne Wasserzähler

Ohne Wasserzähler arbeitet die Anlage zeitgesteuert. Wiederholte Bewässerungen verwenden dieselbe konfigurierte Dauer, liefern aufgrund möglicher Durchflussschwankungen aber nicht garantiert dieselbe Wassermenge.

Laufzeiten können erfasst und ausgewertet werden. Ein tatsächlicher Wasserverbrauch kann ohne eine Messquelle nicht angegeben werden. Wassermessung, Mengensteuerung und Wasserverbrauchsstatistiken gehören deshalb nicht zu den Startvoraussetzungen, sondern bleiben optionale Erweiterungen.

## Noch nicht festgelegt

Alle weiteren Eigenschaften der Bewässerungsanlage und der Bewässerungszone sowie zusätzliche Module werden in den folgenden Schritten festgelegt.
