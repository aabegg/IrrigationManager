# Neukonzept

Status: Einzige verbindliche Konzept- und Implementierungsquelle; nicht in diesem Dokument festgelegte Erweiterungsmodule bleiben offen

Dieses Dokument ist die einzige maßgebliche Quelle für Funktionsumfang, Verhalten, Architekturentscheidungen und Weiterentwicklung des Irrigation Managers. Es ersetzt alle älteren Anforderungen, Roadmaps, ADRs sowie die Dokumente `01` bis `16` vollständig. Diese Unterlagen bleiben ausschließlich als historisches Archiv erhalten und sind fachlich irrelevant; aus ihnen dürfen auch bei fehlendem Widerspruch keine Anforderungen, Standardwerte oder Designentscheidungen übernommen werden.

Regelt dieses Dokument einen Sachverhalt nicht, gilt er als offen. Die Lücke darf nicht aus älteren Unterlagen, bestehendem Code oder bestehenden Tests geschlossen werden, sondern muss vor der Umsetzung hier entschieden und ergänzt werden. Bestehende Version-1-Einträge werden bewusst destruktiv in eine gesperrte Version-2-Hülle migriert und erst nach gültiger lokaler Neukonfiguration wieder freigegeben.

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
4. **Optionale Erweiterungen:** Kompakte Auswahl der verfügbaren Erweiterungsmodule. Die Detailkonfiguration erfolgt nur für ausgewählte Module im jeweils fachlich passenden Anlagen- oder Zonenschritt.
5. **Erste Bewässerungszone:** Erfassung der ersten Zone anhand des dynamisch aus den gewählten Modulen aufgebauten Zonen-Wizards.

Der Hauptventil-Schritt beginnt mit einem kurzen Text, der fragt, ob die Anlage ein Hauptventil besitzt, und dessen Verwendung erklärt. Darunter befindet sich ein optionales Entity-Auswahlfeld. Ein leeres Auswahlfeld bedeutet, dass die Anlage kein Hauptventil verwendet; ein zusätzliches Ja-/Nein-Feld ist nicht erforderlich.

Der Wassermessungs-Schritt bietet die Auswahl `Keine Wassermessung`, `Kumulativer Volumenzähler` und `Impulszähler`. Abhängig von der Messart werden nur die dazugehörenden Felder angezeigt. Beim Impulszähler weist ein Erklärungstext darauf hin, dass spätere Ablesungen des physischen Wasserzählers für eine Langzeitkalibrierung und einen verbesserten Umrechnungsfaktor verwendet werden können.

Spätere Einstellungen des Hauptventil-Moduls werden im selben Schritt ergänzt. Dazu können bei Bedarf eine Öffnungs- und eine Schliesswartezeit gehören, ohne die Basisinformationen oder andere Module mit technischen Details zu überladen.

Der Schritt `Optionale Erweiterungen` zeigt für jedes verfügbare Modul eine eigene Checkbox und einen kurzen Erklärungstext. Er enthält keine umfangreiche Detailkonfiguration. Ein Modul wird in diesem Schritt erst auswählbar, wenn seine jeweilige Ausbaustufe vollständig nutzbar ist. Dadurch zeigt der Wizard keine wirkungslosen oder nur teilweise implementierten Fähigkeiten an.

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

Bei dieser Messart wird genau eine Sensor-Entity ausgewählt, deren Zustand einen fortlaufenden Wasserzähler in einer unterstützten Volumeneinheit darstellt. Die Integration normalisiert den Wert intern auf Liter und übernimmt positive Zählerdifferenzen als gemessenen Verbrauch. Das konfigurierte Bewässerungsziel bleibt dabei der eingegebene Literwert; für einen kumulativen Volumenzähler wird keine künstliche Messauflösung und keine Rundung des Ziels abgeleitet.

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

Bei Zeitsteuerung besitzt die Zone eine gemeinsame Basisdauer. Eine konfigurierte Tageszeile enthält:

- ein Bewässerungsfenster
- optional eine ausdrücklich abweichende Bewässerungsdauer

Bei Mengensteuerung besitzt die Zone eine gemeinsame Basiswassermenge. Eine konfigurierte Tageszeile enthält:

- ein Bewässerungsfenster
- optional eine ausdrücklich abweichende Zielwassermenge

Eine mengengesteuerte Zone benötigt zusätzlich eine maximale Laufzeit als harte Sicherheitsgrenze. Ohne gültige Messung startet kein mengengesteuerter Auftrag. Fällt die Messung während des Vorgangs aus oder wird die maximale Laufzeit vor der Zielmenge erreicht, wird der Vorgang gestoppt und die gesamte Bewässerungsanlage gesperrt. Tatsächlich gelieferte Wassermenge und eine mögliche Überschreitung durch die Messauflösung werden protokolliert.

Zielwassermenge und maximale Laufzeit werden bei der Konfiguration auf Plausibilität geprüft. Beim Impulszähler bestimmt der Umrechnungsfaktor die Liter pro Impuls; das Ziel selbst wird nicht vorab gerundet. Ohne Durchflussprofil reserviert die Bewässerungsplanung für einen mengenbasierten Auftrag vorsichtshalber dessen vollständige maximale Laufzeit.

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

Mit einem Durchflussprofil bestimmt die Bewässerungsplanung die erwartete Dauer eines mengenbasierten Auftrags aus Zielwassermenge und erwartetem durchschnittlichem Durchfluss und prüft damit dessen Einpassung in ein Bewässerungsfenster. Die konfigurierte maximale Laufzeit bleibt unabhängig davon die harte Sicherheitsgrenze der Ausführung. Ohne Profil bleibt die Mengensteuerung möglich und verwendet für die Planung konservativ die konfigurierte maximale Laufzeit.

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

Jede Bewässerungszone kann optional einen Wochenplan erhalten. Der Wochenplan besteht in Datenhaltung und Benutzeroberfläche aus genau einer Zeile pro Wochentag. Die Zone besitzt ein gemeinsames Basissoll pro fälligem Termin. Eine Tageszeile kann dieses Basissoll ausdrücklich überschreiben.

Das Basissoll gehört zur Steuerungsart der Zone: Es ist eine Bewässerungsdauer bei Zeitsteuerung oder eine Zielwassermenge bei Mengensteuerung. Jede Tageszeile enthält optional ein Bewässerungsfenster sowie optional ein abweichendes Ziel derselben Steuerungsart.

Eine rein manuell verwendete Zone darf ohne Basissoll gespeichert werden. Sobald mindestens ein automatisches Bewässerungsfenster vorhanden ist, muss die Zone ein bestätigtes positives Basissoll besitzen; ein Tagesziel ersetzt diese Voraussetzung nicht.

Alle durch den Benutzer eingegebenen Dauern und maximalen Laufzeiten werden in der Oberfläche über getrennte Felder für Stunden, Minuten und Sekunden erfasst. Stunden sind nicht auf 24 begrenzt. Die Integration speichert und verarbeitet diese Werte intern weiterhin als Sekunden.

Dabei gelten folgende Regeln:

- Ist kein Bewässerungsfenster vorhanden, erfolgt an diesem Wochentag keine automatische Bewässerung.
- Ist ein Bewässerungsfenster vorhanden, wird für diesen Wochentag genau ein automatischer Bewässerungsauftrag mit dem Basissoll oder dem ausdrücklich abweichenden Tagesziel erzeugt.
- Ein abweichendes Tagesziel ohne Bewässerungsfenster ist ungültig.
- Basissoll und abweichende Tagesziele müssen größer als null sein.
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

Die Anlageneinstellungen trennen Konfiguration und Laufzeitsteuerung. Das Hauptmenü enthält `Anlage konfigurieren`, `Status und Steuerung`, die manuelle Neuberechnung der Bewässerungsplanung, bei aktiver Sicherheitssperre deren Zurücksetzen sowie bei vorhandener Wassermessung die Zählerstandskorrektur. `Status und Steuerung` öffnet einen eigenen Dialog, zeigt Betriebs- und Automatikfreigabe an und bietet abhängig vom aktuellen Zustand jeweils `Anlage aktivieren` oder `Anlage deaktivieren` sowie `Automatische Bewässerung aktivieren` oder `Automatische Bewässerung deaktivieren` an.

Der Not-Aus wird in der Benutzeroberfläche ausschließlich über die Anlagen-Card angeboten und erscheint nicht in den Anlageneinstellungen. Das Aufheben einer Sicherheitssperre verlangt immer eine Warnmeldung mit ausdrücklicher Bestätigung.

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

Eine Neuberechnung darf einen noch nicht begonnenen automatischen Bewässerungsauftrag
ersetzen, der ausschliesslich durch den vorherigen Entzug einer Automatikfreigabe, eine relevante
Konfigurationsänderung oder eine frühere Neuplanung storniert wurde. Eine ausdrückliche Rücknahme
durch den Benutzer sowie ein bereits abgeschlossener, abgelaufener, fehlgeschlagener oder nach
einem unterbrochenen Start beendeter Auftrag derselben deterministischen Termin-ID bleiben
endgültig und dürfen nicht erneut ausgeführt werden. Pro Termin-ID bleibt nach Persistenz und
Neustart genau ein wirksamer Auftragsdatensatz erhalten.

Bei vor dieser Unterscheidung gespeicherten Stornierungen ohne verlässlichen Grund gilt
standardmässig die sichere Annahme, dass sie endgültig sind. Nur eine ausdrücklich bestätigte
administrative Reparatur darf solche mehrdeutigen Altdaten einmalig durch die neu berechneten
Aufträge ersetzen; reguläre automatische Neuplanungen führen diese Migration nicht implizit aus.

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
Zeitbasierte Bewässerungsziele werden dabei aus den intern gespeicherten Sekunden als `HH:MM:SS` dargestellt; mengenbasierte Ziele behalten ihre Volumeneinheit.

Der Dialog zeigt jeweils die Aufträge eines lokalen Kalendertags und öffnet mit dem aktuellen Tag. Das ausgewählte Datum wird lokalisiert dargestellt und kann mit Pfeilen tageweise vor- und zurückgeschaltet werden. Gibt es am ausgewählten Tag keine offenen Aufträge, weist ein Sprungziel auf den nächsten Tag mit offenen Aufträgen. Innerhalb eines Tages werden die Aufträge nach ihrem erwarteten Start in der berechneten Ausführungsreihenfolge angezeigt.

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
- während einer laufenden Bewässerung dieser Zone die Aktion `Bewässerung stoppen`
- die Aktion `Verlauf anzeigen`

Die Aktion `Manuell bewässern` öffnet einen Dialog zur Eingabe des Bewässerungsziels. Eine Dauer kann immer eingegeben werden. Eine Wassermenge kann nur gewählt werden, wenn für die Anlage eine funktionsfähige Mengensteuerung verfügbar ist.

Die Aktion `Bewässerung stoppen` wird nur angezeigt, solange in dieser Zone ein Bewässerungsvorgang läuft. Nach einer Bestätigung beendet sie genau diesen Vorgang kontrolliert. Eine veraltete Card-Aktion darf keinen inzwischen neu gestarteten Bewässerungsvorgang stoppen.

Ist kein anderer Bewässerungsvorgang aktiv, wird der manuelle Auftrag sofort gestartet. Läuft bereits eine Bewässerung innerhalb der Anlage, entscheidet der Benutzer:

- Der aktive Bewässerungsvorgang wird kontrolliert beendet und der manuelle Auftrag sofort gestartet.
- Der aktive Bewässerungsvorgang wird abgeschlossen und der manuelle Auftrag direkt danach, vor wartenden automatischen Aufträgen, eingereiht.

Die Aktion `Verlauf anzeigen` öffnet einen Dialog oder eine eigene Ansicht mit den Bewässerungsvorgängen der Zone. Für längere Verläufe wird eine eigene Ansicht mit Pagination und Filtern bevorzugt. Jeder Eintrag zeigt mindestens Start, Ende, Quelle, Bewässerungsziel, Ergebnis, tatsächliche Laufzeit, verfügbare Wassermenge und Abschlussgrund.

## Aussagekraft ohne Wasserzähler

Ohne Wasserzähler arbeitet die Anlage zeitgesteuert. Wiederholte Bewässerungen verwenden dieselbe konfigurierte Dauer, liefern aufgrund möglicher Durchflussschwankungen aber nicht garantiert dieselbe Wassermenge.

Laufzeiten können erfasst und ausgewertet werden. Ein tatsächlicher Wasserverbrauch kann ohne eine Messquelle nicht angegeben werden. Wassermessung, Mengensteuerung und Wasserverbrauchsstatistiken gehören deshalb nicht zu den Startvoraussetzungen, sondern bleiben optionale Erweiterungen.

## Gemeinsamer Vertrag der Erweiterungsmodule

Die folgenden vier Erweiterungsmodule werden unabhängig voneinander in den Anlageneinstellungen geführt:

- Pflanzen- und Standortmodell
- saisonale Korrektur
- wetterabhängige Bewässerung
- Teilgaben und Sickerpausen

Jedes vollständig implementierte Modul besitzt genau eine anlagenweite Checkbox. Die Checkbox bestimmt, ob das Modul für die Anlage verfügbar ist. Jede Zone entscheidet zusätzlich, ob sie ein anlagenweit verfügbares Modul tatsächlich verwendet. Deaktivierte oder für eine Zone nicht verwendete Module dürfen den einfachen zeit- oder mengengesteuerten Grundbetrieb nicht voraussetzen oder einschränken.

Für alle vier Module gilt:

- Ein Modul ist standardmässig deaktiviert.
- Das Deaktivieren löscht weder die Anlagen- noch die Zonenkonfiguration des Moduls.
- Das erneute Aktivieren stellt die zuvor gespeicherte Konfiguration wieder bereit.
- Ein bereits aktiver Bewässerungsvorgang behält seinen beim Start festgelegten Berechnungs- und Ausführungssnapshot und wird durch eine Moduländerung weder umgerechnet noch gestoppt.
- Noch nicht begonnene automatische Bewässerungsaufträge werden nach einer Moduländerung anhand der dann wirksamen Konfiguration atomar neu geplant.
- Manuelle Bewässerungsaufträge werden nicht nachträglich durch Pflanzen-, Saison- oder Wetterdaten verändert.
- Ein fehlendes, deaktiviertes oder fehlerhaftes Komfortmodul setzt keine Sicherheitssperre und verhindert keine Bewässerung anhand des verbleibenden Basissolls.
- Modulfehler und verwendete Rückfallwerte werden sichtbar protokolliert und dürfen nicht stillschweigend verborgen werden.

Die Rückfallwirkung ist festgelegt:

| Deaktiviertes oder nicht verwendetes Modul | Rückfallverhalten |
|---|---|
| Pflanzen- und Standortmodell | Es wird keine Empfehlung erzeugt; das bestätigte Basissoll bleibt unverändert. |
| Saisonale Korrektur | Der wirksame saisonale Faktor ist `1,0`. |
| Wetterabhängige Bewässerung | Das saisonale Basissoll beziehungsweise ohne Saisonmodul das Basissoll wird verwendet. |
| Teilgaben und Sickerpausen | Das vollständige Bewässerungsziel wird zusammenhängend ausgeführt. |

Zwischen den Modulen bestehen keine harten Deaktivierungsabhängigkeiten. Eine saisonale Kurve kann manuell ohne Pflanzenmodell gepflegt werden. Das Wettermodul kann ein manuell festgelegtes Basissoll korrigieren. Teilgaben funktionieren unabhängig von Pflanzen- und Wetterdaten.

## Dynamische Konfigurationsführung der Zone

Der Zonen-Wizard bleibt auch mit Erweiterungsmodulen schrittweise und übersichtlich. Schritte eines anlagenweit deaktivierten Moduls werden nicht angezeigt. Umfangreiche oder erklärungsbedürftige Angaben erhalten einen kurzen Hilfetext; selten benötigte Fachwerte werden in einem ausdrücklich optionalen Bereich `Erweiterte Angaben` zusammengefasst.

Der vollständige Zielaufbau des Zonen-Wizards ist:

1. **Basis:** Bezeichnung, Zonenventil, Steuerungsart und bei Mengensteuerung die maximale Laufzeit.
2. **Pflanzen und Standort:** Optionale Erfassung einer oder mehrerer Teilflächen, wenn das Pflanzen- und Standortmodell anlagenweit verfügbar ist und für die Zone verwendet werden soll.
3. **Empfehlung und Basissoll:** Anzeige der aus den vorhandenen Daten ableitbaren Empfehlung sowie ausdrückliche Festlegung oder Bestätigung des gemeinsamen Basissolls.
4. **Modulverwendung:** Kompakte zonenspezifische Auswahl der anlagenweit verfügbaren Saison-, Wetter- und Teilgabenmodule.
5. **Moduldetails:** Je ein eigener, nur bei Verwendung angezeigter Schritt für saisonale Kurve, Wetterverhalten und Teilgaben.
6. **Wochenplan:** Bewässerungsfenster pro Wochentag und nur bei Bedarf ein vom gemeinsamen Basissoll abweichendes Tagesziel.

Der erste Basisschritt erklärt kurz, dass Zeit- und Mengensteuerung das Abschaltkriterium des Bewässerungsvorgangs festlegen. Bedarfs- und Mindestbewässerung sind davon getrennte Bewässerungsmodi und bestimmen, ob und in welchem Umfang ein zulässiger Termin tatsächlich genutzt wird.

Nach der Ersteinrichtung sind Basis, Pflanzen und Standort, Basissoll, saisonale Kurve, Wetterverhalten, Teilgaben und Wochenplan einzeln über die Zoneneinstellungen erreichbar. Die Änderung eines Bereichs erfordert nicht das erneute Durchlaufen des gesamten Zonen-Wizards.

## Optionales Pflanzen- und Standortmodell

Das Pflanzen- und Standortmodell dient zunächst der nachvollziehbaren Erfassung und Empfehlung. Es verändert ein bereits bestätigtes Basissoll niemals selbstständig. Ein Vorschlag wird erst durch ausdrückliche Bestätigung in die Zonenkonfiguration übernommen.

### Teilflächen

Eine homogene Zone besitzt genau eine Teilfläche. Bestehen innerhalb derselben hydraulisch nicht separat schaltbaren Zone deutlich unterschiedliche Pflanzenbestände, Flächen oder Ausbringungsraten, können mehrere Teilflächen erfasst werden. Der Wizard erfasst zunächst eine Teilfläche und bietet anschliessend wahlweise `Weitere Teilfläche hinzufügen` oder `Fortfahren` an.

Die grundlegenden Angaben einer Teilfläche sind:

- Bezeichnung
- bewässerte Fläche
- Pflanzenprofil
- Entwicklungszustand, beispielsweise neu angepflanzt oder etabliert
- Exposition, beispielsweise sonnig, halbschattig oder schattig
- Bodenprofil
- Ausbringungsprofil

Erweiterte optionale Angaben sind:

- Hangneigung in Prozent
- Mulch oder andere Bodenabdeckung als Ja-/Nein-Angabe
- relative Ausbringungsrate innerhalb der Zone als positiver Faktor

Eine bekannte absolute Ausbringungsrate und fachkundig überschriebene Pflanzen- oder Bodenwerte werden erst in einer späteren Ausbaustufe bearbeitbar. Sie benötigen zuvor festgelegte Einheiten, Wertebereiche und eine nachvollziehbare Abgrenzung von Katalogwerten.

Die Oberfläche erklärt mindestens:

- weshalb die Fläche für eine spätere Umrechnung von Millimeter Wasser in Liter benötigt wird
- dass alle Teilflächen derselben Zone gleichzeitig bewässert werden
- dass die Bodenart primär Wasserspeicherung und Versickerung beeinflusst und nicht beliebig als Verdunstungsmultiplikator verwendet wird
- dass Katalogwerte Empfehlungen und gemessene beziehungsweise kalibrierte Werte vorzuziehen sind
- dass stark unterschiedliche Teilflächen zu unvermeidbarer Über- oder Unterversorgung führen können

### Pflanzenprofile

Der erste Ausbau verwendet überschaubare, nachvollziehbare Pflanzenkategorien statt einer vermeintlich vollständigen botanischen Artendatenbank. Vorgesehen sind mindestens Rasen, Hecken und Gehölze, Stauden, Gemüse, Kübelpflanzen, Jungpflanzen, Bodendecker und ein benutzerdefiniertes Profil.

Ein Pflanzenprofil kann Vorschlagswerte liefern für:

- relativen Pflanzenfaktor
- typische Wurzeltiefe
- tolerierbare Ausschöpfung des pflanzenverfügbaren Bodenwassers
- Empfindlichkeit gegenüber Trockenstress
- eine spätere saisonale Monatskurve
- eine Tendenz zu häufigeren kleinen oder selteneren tieferen Bewässerungsgaben

Jeder Katalogwert benötigt eine dokumentierte Herkunft, eine Version und eine fachlich vertretbare Bandbreite. Benutzerdefinierte Überschreibungen bleiben als solche erkennbar und ersetzen den Katalog nicht global.

Die erste Katalogversion verwendet ausschliesslich die qualitativen Stufen `niedrig`, `mittel` und `hoch`. Sie ordnet Pflanzenkategorien relativen Wasserbedarf und Trockenheitsempfindlichkeit zu. Bodenprofile verwenden dieselben Stufen für Speicherfähigkeit und Versickerung. Ausbringungsprofile verwenden sie für Effizienz und Eignung für Sickerpausen. Die Stufen sind keine numerischen Faktoren und dürfen nicht zur automatischen Berechnung eines absoluten Bewässerungsziels verwendet werden.

Die fachliche Einordnung wird mit öffentlich nachvollziehbaren Quellen zu Pflanzenkoeffizienten, Wurzeltiefen, Bodenwasserspeicherung, Versickerung und Bewässerungseffizienz belegt. Die konkrete Quellenliste und Katalogversion werden gemeinsam mit dem Katalog im Repository geführt. Breite Sammelkategorien wie Stauden oder Gehölze bleiben ausdrücklich grobe Ausgangswerte und weisen auf mögliche Abweichungen einzelner Arten hin.

Die qualitative Katalogversion `1.0.0` stützt ihre grundsätzliche Einordnung auf:

- FAO Irrigation and Drainage Paper 56, `Crop evapotranspiration - Guidelines for computing crop water requirements`: https://www.fao.org/4/x0490e/x0490e00.htm
- US EPA WaterSense, `Watering Tips`: https://www.epa.gov/watersense/watering-tips

Die FAO-Quelle begründet die Trennung von Referenzverdunstung, Pflanzenfaktor, Entwicklungszustand, Bodenwasser und Bewässerungsplanung. Die EPA-Quelle begründet die qualitative Berücksichtigung von Pflanzenart, Sonne beziehungsweise Schatten, Boden, Ausbringungsart sowie die Eignung von Sickerpausen bei tonreichen oder geneigten Flächen. Die groben Sammelprofile ersetzen keine artspezifische oder lokale Fachberatung.

Katalogversion `1.0.0` verwendet folgende redaktionelle Einordnung. Die Werte sind ordinale Hinweise und keine Messwerte oder Berechnungsfaktoren:

| Pflanzenprofil | relativer Wasserbedarf | Trockenheitsempfindlichkeit | Gabetendenz |
|---|---|---|---|
| Rasen | hoch | hoch | klein und häufig |
| Hecke/Gehölz | mittel | niedrig | tief und selten |
| Stauden | mittel | mittel | ausgewogen |
| Gemüse | hoch | hoch | klein und häufig |
| Kübel | hoch | hoch | klein und häufig |
| Jungpflanzen | hoch | hoch | klein und häufig |
| Bodendecker | niedrig | niedrig | tief und selten |

| Bodenprofil | Speicherfähigkeit | Versickerung |
|---|---|---|
| sandig | niedrig | hoch |
| sandiger Lehm | mittel | hoch |
| lehmig | hoch | mittel |
| tonreich | hoch | niedrig |

| Ausbringungsprofil | Eignung für Teilgaben |
|---|---|
| Tropfschlauch | niedrig |
| Sprinkler/Regner | hoch |
| Mikrobewässerung | mittel |

Sonne erhöht und Schatten reduziert den relativen Wasserbedarf um jeweils eine Stufe. Ein neuer Bestand erhöht Wasserbedarf und Trockenheitsempfindlichkeit um eine Stufe; Mulch reduziert den Wasserbedarf um eine Stufe. Alle Verschiebungen bleiben auf die drei Katalogstufen begrenzt. Niedrige Bodenspeicherung verschiebt die Gabetendenz in Richtung kleiner und häufiger, hohe Speicherung in Richtung tiefer und seltener. Jede positive Hangneigung sowie niedrige Versickerung erhöhen die Eignung für Teilgaben um eine Stufe; hohe Versickerung reduziert sie um eine Stufe.

Für mehrere Teilflächen verwendet die Empfehlung jeweils die höchste Stufe für Wasserbedarf, Trockenheitsempfindlichkeit und Teilgabeneignung. Speicherfähigkeit, Versickerung und Gabetendenz werden als gerundete mittlere Ordinalstufe zusammengeführt. Ein Konflikt liegt vor, wenn Wasserbedarf oder Speicherfähigkeit zwischen niedrig und hoch streuen oder wenn angegebene relative Ausbringungsraten voneinander abweichen. Vollständige bekannte Katalogprofile ohne Konflikt ergeben hohe Empfehlungsqualität, Konflikte mittlere und fehlende, unbekannte, benutzerdefinierte oder ungültige Pflichtangaben niedrige Qualität. Diese Regeln erzeugen weiterhin kein absolutes Bewässerungsziel.

### Boden- und Ausbringungsprofile

Der erste Ausbau verwendet mindestens sandige, lehmig-sandige, lehmige, tonige und benutzerdefinierte Bodenprofile. Sie können Vorschlagswerte für pflanzenverfügbaren Wasserspeicher, Versickerung und Eignung für Sickerpausen liefern.

Das Ausbringungsprofil unterscheidet mindestens Tropfschlauch, Sprinkler beziehungsweise Regner, Mikrobewässerung und ein benutzerdefiniertes Profil. Es kann Vorschläge für Ausbringungseffizienz, Niederschlagsrate, Verteilungsqualität und sinnvolle Teilgabengrösse liefern. Ein gemessener oder kalibrierter Wert hat Vorrang vor einem Katalogwert.

### Erste relative Empfehlung

Die erste Ausbaustufe des Pflanzen- und Standortmodells verwendet noch keine Wetterdaten und keine manuell vorgegebene klimatische Referenzverdunstung. Sie darf deshalb keine vermeintlich genaue absolute Wassermenge, Laufzeit oder Anzahl Termine pro Woche behaupten.

Sie zeigt stattdessen:

- relative Pflanzenverdunstung
- relative Trockenheitsempfindlichkeit
- erwartete Speicherfähigkeit und Versickerung des Bodens
- Tendenz zu häufigeren kleinen oder selteneren tieferen Gaben
- Eignung für Sickerpausen
- Konflikte zwischen mehreren Teilflächen
- Vollständigkeit und Qualität der Eingaben

Die Empfehlungsqualität besitzt ebenfalls die drei Stufen `niedrig`, `mittel` und `hoch`. Ein vollständig mit bekannten Katalogprofilen beschriebenes homogenes Gebiet kann `hoch` erreichen. Benutzerdefinierte oder fehlende Profile, stark abweichende Teilflächen sowie nicht zur Ausbringungsart passende Angaben reduzieren die Qualität nachvollziehbar. Die Empfehlung nennt die Gründe ihrer Qualitätsstufe.

Der Benutzer legt das gemeinsame Basissoll weiterhin selbst fest. Die Oberfläche erklärt, dass eine spätere Referenzverdunstung und belastbare Ausbringungs- oder Durchflussdaten für eine absolute Empfehlung benötigt werden.

### Spätere absolute Empfehlung

Sobald eine geeignete Referenzverdunstung verfügbar ist, kann die Pflanzenverdunstung einer Teilfläche aus Referenzverdunstung, Pflanzenfaktor und Standortkorrektur abgeleitet werden. Ein Millimeter benötigtes Wasser auf einem Quadratmeter entspricht einem Liter. Eine Bruttowassermenge berücksichtigt zusätzlich die Ausbringungseffizienz.

Bodenprofil, Wurzeltiefe und tolerierbare Ausschöpfung bestimmen den nutzbaren Speicher und damit eine fachliche Empfehlung für Gabenhöhe und Abstand zwischen zulässigen Terminen. Bei mehreren Teilflächen muss die gleichzeitig erfolgende Wasserverteilung berücksichtigt werden. Die kritischste Teilfläche kann das notwendige Gesamtziel bestimmen; eine dadurch erwartete Überversorgung anderer Teilflächen wird sichtbar ausgewiesen.

Ohne Wasserzähler kann eine Wassermenge nur dann in eine Laufzeit umgerechnet werden, wenn ein belastbarer erwarteter Durchfluss oder eine absolute Ausbringungsrate vorhanden ist. Fehlt dieser Wert, zeigt die Oberfläche den geschätzten Wasserbedarf, erzeugt aber keine vermeintlich genaue Laufzeit.

## Optionale saisonale Korrektur

Die saisonale Korrektur besitzt pro verwendender Zone zwölf Monatsfaktoren. Zwischen den Monatsstützpunkten wird anhand des lokalen Datums täglich linear interpoliert, damit Monatsgrenzen keine sprunghaften Zieländerungen verursachen.

Jeder Monatsfaktor liegt zwischen `0,10` und `3,00` und wird mit höchstens zwei Nachkommastellen gespeichert. `1,00` ist neutral. Ein Faktor `0` ist nicht zulässig, weil ein fälliger Termin nicht stillschweigend vollständig unterdrückt werden darf; dafür werden die ausdrücklichen Betriebs- und Automatikfreigaben verwendet. Der Monatswert gilt jeweils am ersten lokalen Kalendertag des Monats. Für jeden weiteren Tag wird zwischen diesem Wert und dem Wert des folgenden Monats linear interpoliert; der Dezember interpoliert dabei auf den Januarwert derselben Kurve. Die Zielberechnung verwendet den ungerundeten interpolierten Faktor und rundet weder Zeit- noch Mengenziele künstlich.

Das saisonale Basissoll wird bestimmt als:

`Basissoll des fälligen Termins × interpolierter Monatsfaktor`

Dabei gelten folgende Regeln:

- Ohne konfigurierten Wert gilt für jeden Monat `1,0`.
- Das Pflanzenprofil kann eine Monatskurve vorschlagen, übernimmt sie aber niemals automatisch.
- Der aktuelle qualitative Pflanzenkatalog enthält keine numerisch begründeten Monatskurven und erzeugt deshalb noch keinen Profilvorschlag. Die neutrale Standardkurve gilt nicht als Empfehlung. Ein späterer Katalogvorschlag benötigt zwölf ausdrücklich dokumentierte Faktoren, Quelle und Katalogversion; die Oberfläche darf ihn lediglich vorbefüllen und muss weiterhin Zielvorschau und ausdrückliche Bestätigung verlangen.
- Eine vorgeschlagene oder geänderte Kurve wird mit einer Zielvorschau angezeigt und erst nach ausdrücklicher Bestätigung gespeichert.
- Faktor, Ausgangssoll und saisonales Basissoll werden im Berechnungssnapshot jedes automatischen Bewässerungsauftrags festgehalten.
- Ist das Modul anlagenweit deaktiviert oder für die Zone nicht verwendet, gilt Faktor `1,0`.
- Passt ein durch die saisonale Korrektur vergrössertes Ziel nicht vollständig in sein Bewässerungsfenster, wird kein stillschweigend verkürzter Auftrag erzeugt. Die Planung weist den Termin als nicht einplanbar aus und nennt die Ursache.

Die saisonale Korrektur kann ohne Pflanzenmodell manuell verwendet werden. Änderungen der Monatskurve lösen eine atomare Neuberechnung noch nicht begonnener automatischer Bewässerungsaufträge aus.

## Optionale wetterabhängige Bewässerung

Das Wettermodul umfasst sowohl die Erfassung geeigneter Wetterquellen der Anlage als auch deren optionale Berücksichtigung pro Zone. Es wird anlagenweit mit einer Checkbox deaktiviert oder aktiviert. Jede Zone besitzt zusätzlich die Auswahl `Wetterdaten für diese Zone berücksichtigen`.

### Einbindung über Home Assistant

Wetterdienste und lokale Wetterstationen werden im ersten Ausbau nicht direkt mit eigenen Anbieterzugängen in den Irrigation Manager integriert. Sie werden zuerst als Home-Assistant-Integration eingerichtet und anschliessend über ihre Entities ausgewählt.

Damit können insbesondere:

- lokale Ecowitt-Sensoren als gewöhnliche Regen-, Solar-, Wind-, Temperatur-, Feuchte- oder Bodenfeuchte-Entities verwendet werden
- Wetterdienste über standardisierte `weather`-Entities eingebunden werden
- Prognosen über die Home-Assistant-Schnittstelle für Wettervorhersagen abgerufen werden
- Anbieter ausgetauscht werden, ohne Pflanzen- oder Planungsmodell anzupassen

Ein direkter Anbieteradapter wird erst erwogen, wenn eine fachlich notwendige Information nachweislich nicht über Home Assistant bereitgestellt werden kann.

### Quellenrollen und Qualität

Die Anlagenkonfiguration ordnet Entities fachlichen Rollen zu. Vorgesehen sind mindestens:

- gemessene kumulierte Niederschlagsmenge
- aktuelle Niederschlagsrate
- direkte Referenzverdunstung
- Lufttemperatur
- relative Luftfeuchtigkeit
- Taupunkt
- Windgeschwindigkeit
- Solarstrahlung
- Wetterprognose

Bodenfeuchte gehört fachlich zur betroffenen Zone oder Teilfläche und wird dort optional zugeordnet.

Der erste Ausbau verwendet pro Rolle genau eine primäre Quelle. Mehrere Quellen können später als ausdrücklich priorisierte Fallback-Liste ergänzt werden. Prognosen verschiedener Anbieter werden nicht ungeprüft gemittelt.

Die Quellenzuordnung wird als Abbildung von Quellenrolle auf Entity-ID in der Bewässerungsanlage gespeichert. Es gibt keine automatische Auswahl nach Entity-Name, Gerät, Bereich oder Integrationsherkunft. Eine leere oder nur teilweise Zuordnung ist gültig und schränkt den bisherigen Bewässerungsbetrieb nicht ein. Dieselbe `weather`-Entity darf für mehrere aktuelle Attributrollen ausgewählt werden; kumulierte Niederschlagsmenge, Niederschlagsrate, direkte Referenzverdunstung und Solarstrahlung benötigen dagegen jeweils eine ausdrücklich ausgewählte `sensor`-Entity.

Stufe 3 verwendet folgende kanonische Einheiten, Aktualitätsgrenzen und harten Plausibilitätskorridore. Die Korridore sind bewusst breiter als ein erwarteter Normalbereich. Werte ausserhalb werden nicht begrenzt oder korrigiert, sondern als `unplausibel` abgelehnt.

| Quellenrolle | Zulässiger HA-Vertrag | Kanonische Einheit | Maximalalter | Harter Plausibilitätskorridor |
|---|---|---:|---:|---:|
| kumulierte Niederschlagsmenge | `sensor` mit Device-Class `precipitation`, State-Class `total` oder `total_increasing` | `mm` | 6 Stunden | endlich und `>= 0`; kein oberes Limit, da der Rücksetzzeitraum quellenabhängig ist |
| Niederschlagsrate | `sensor` mit Device-Class `precipitation_intensity` | `mm/h` | 30 Minuten | `0..1000 mm/h` |
| direkte Referenzverdunstung | ausdrücklich ausgewählter `sensor` mit Längeneinheit und State-Class `total` oder `total_increasing`; Wert gilt für den durch den Quellenzeitstempel bezeichneten lokalen Kalendertag | `mm/Tag` | 36 Stunden | `0..30 mm/Tag` |
| Lufttemperatur | `sensor` mit Device-Class `temperature` oder Attribut `temperature` einer `weather`-Entity | `°C` | 2 Stunden | `-90..60 °C` |
| relative Luftfeuchtigkeit | `sensor` mit Device-Class `humidity` oder Attribut `humidity` einer `weather`-Entity | `%` | 2 Stunden | `0..100 %` |
| Taupunkt | `sensor` mit Device-Class `temperature` oder Attribut `dew_point` einer `weather`-Entity | `°C` | 2 Stunden | `-100..60 °C`; bei gleichzeitig verfügbarer Lufttemperatur höchstens `2 °C` darüber |
| Windgeschwindigkeit | `sensor` mit Device-Class `wind_speed` oder Attribut `wind_speed` einer `weather`-Entity | `m/s` | 2 Stunden | `0..120 m/s` |
| Solarstrahlung | `sensor` mit Device-Class `irradiance` | `W/m²` | 2 Stunden | `0..1600 W/m²` |
| Wetterprognose | `weather`-Entity mit mindestens einer von HA ausgewiesenen Prognoseart | noch keine Wertnormalisierung in Stufe 3 | 6 Stunden | Entity verfügbar und mindestens `hourly`, `daily` oder `twice_daily` unterstützt |

Für die Aktualität wird der HA-Zeitstempel `last_reported` verwendet, der auch eine unveränderte, aber erneut gemeldete Messung abbildet. Nur falls er nicht verfügbar ist, wird `last_updated` verwendet. Alle Vergleiche erfolgen zeitzonenbewusst. Der Zustand einer `weather`-Entity wird nicht in eine Niederschlagsmenge oder -rate umgedeutet. Prognosedaten werden erst in Stufe 5 über die standardisierte HA-Wetteraktion abgerufen; Stufe 3 prüft Quelle, Verfügbarkeit und unterstützte Prognosearten und weist sie in der Home-Assistant-Integrationsdiagnose aus.

Jeder verwendete Wetterwert besitzt mindestens:

- normalisierte Einheit
- Mess- oder Prognosezeitpunkt
- Herkunft
- Aktualität
- Qualitätsstatus
- gegebenenfalls den Grund seiner Ablehnung

Die Quellenqualität unterscheidet `nicht konfiguriert`, `verfügbar`, `veraltet`, `nicht verfügbar`, `unplausibel` und `unvollständig`. Fehlende oder nicht unterstützte Einheit, Device-Class, State-Class oder benötigte `weather`-Attribute gelten als `unvollständig`; `unknown`, `unavailable` oder eine nicht mehr vorhandene Entity gelten als `nicht verfügbar`. Nicht endliche oder ausserhalb des Korridors liegende Werte gelten als `unplausibel`. Erst wenn diese Prüfungen bestanden sind, kann das Maximalalter zu `veraltet` führen.

`Ersatzwert verwendet` ist keine Quellenqualität, sondern eine spätere Zielauflösungsentscheidung. Stufe 3 verwendet noch keinen Wetterwert für die Planung und kann diesen Zustand daher noch nicht erzeugen. Ab Stufe 4 wird bei nicht belastbarer Wetterberechnung sichtbar auf das saisonale Basissoll zurückgefallen.

Die Quellenbeobachtungen werden beim Erstellen der Home-Assistant-Integrationsdiagnose aus dem aktuellen HA-Zustand erzeugt. Stufe 3 persistiert weder rohe Wetterwerte noch einen eigenen Messverlauf. Der Diagnoseexport enthält pro Rolle Auswahl, normalisierten Wert, kanonische Einheit, verwendeten Zeitstempel, Alter, Qualitätsstatus und stabilen Grundcode; sensible Entity-Namen werden mit dem bestehenden HA-Diagnosemechanismus redigiert. Der Einstellungsdialog bleibt auf die Quellenzuordnung beschränkt und zeigt keinen zusätzlichen technischen Statusblock. Sein Hinweis erklärt, dass fachlich passende Entities sowohl von lokalen Sensoren als auch von externen, über Home Assistant eingebundenen Wetterdiensten stammen dürfen. Die Quellenzuordnung kann unabhängig vom späteren Wettermodul bearbeitet werden. Ihr Speichern löst keine Neuplanung aus und verändert keine offenen oder aktiven Bewässerungsvorgänge.

Die Migration auf Stufe 3 ergänzt eine leere Quellenzuordnung und hält den anlagenweiten Wettermodulschalter ausdrücklich deaktiviert. Der reguläre Modulschalter und die zonenspezifische Wetterverwendung bleiben in Stufe 3 ausgeblendet. Damit ist die Quellenaufnahme und Diagnose vollständig prüfbar, ohne das bestehende Bewässerungsziel zu beeinflussen.

Normative technische Grundlage dieser Stufe sind die HA-Verträge für [Sensor-Entities](https://developers.home-assistant.io/docs/core/entity/sensor/), [Weather-Entities](https://developers.home-assistant.io/docs/core/entity/weather/) und den Zeitstempel [`State.last_reported`](https://developers.home-assistant.io/blog/2024/03/20/state_reported_timestamp/). Anbieter- oder gerätespezifische Attribute ausserhalb dieser Verträge werden nicht vorausgesetzt.

Für die Referenzverdunstung gilt folgende fachliche Priorität:

1. Ein geeigneter direkter Referenzverdunstungssensor wird verwendet.
2. Bei vollständig verfügbaren lokalen Messgrössen kann die Referenzverdunstung nach einem dokumentierten fachlichen Modell berechnet werden.
3. Eine vereinfachte Berechnung darf nur mit sichtbar geringerer Qualität verwendet werden.
4. Ist keine belastbare Bestimmung möglich, wird die Wetterkorrektur ausfallsicher ignoriert und das saisonale Basissoll verwendet.

Die konkrete Berechnungsmethode, erforderliche Messgrössen, Aktualitätsgrenzen und Plausibilitätsbereiche werden vor der entsprechenden Implementierungsstufe in diesem Dokument festgelegt. Sie dürfen nicht aus historischen Dokumenten oder bestehendem Altcode übernommen werden.

### Wasserbilanz

Eine wetterabhängig bewässerte Zone führt eine nachvollziehbare Wasserbilanz. Sie wird grundsätzlich fortgeschrieben als:

`bisheriges Wasserdefizit + Pflanzenverdunstung - wirksamer Niederschlag - wirksame Bewässerung`

Die Wasserbilanz speichert tägliche Beiträge, verwendete Quellen, Qualität und Korrekturen. Sie speichert nicht unbegrenzt sämtliche rohen Sensormeldungen. Negative oder unplausible Beiträge werden nicht stillschweigend akzeptiert.

Gemessener Niederschlag und tatsächlich zugeordnete Bewässerung sind gegenüber Prognosen vorrangig. Eine Prognose verändert den abgeschlossenen historischen Wasserhaushalt nicht, sondern beeinflusst ausschliesslich noch nicht begonnene automatische Bewässerungsaufträge.

Stufe 4 verwendet ausschliesslich eine ausdrücklich zugeordnete direkte Referenzverdunstung und die kumulierte gemessene Niederschlagsmenge. Eine eigene oder vereinfachte Referenzverdunstungsberechnung sowie Prognosen gehören noch nicht zu dieser Stufe. Damit eine Millimeterbilanz ohne Scheingenauigkeit in das vorhandene Zeit- oder Mengenziel umgerechnet werden kann, benötigt jede das Wettermodul verwendende Zone folgende ausdrücklich bestätigte Angaben:

- Bewässerungsmodus `Bedarfsbewässerung` oder `Mindestbewässerung`
- Pflanzenfaktor zwischen `0,10` und `2,00`; der neutrale Vorschlagswert `1,00` muss bestätigt werden und wird nicht aus dem qualitativen Pflanzenprofil abgeleitet
- Anteil wirksamen Niederschlags zwischen `0,00` und `1,00`; der Vorschlagswert `1,00` muss bestätigt werden
- Bedarfsschwelle zwischen `0,00` und `100,00 mm`, ab der eine Bedarfsbewässerung ausgeführt wird
- maximales fortgeführtes Wasserdefizit zwischen `1,00` und `500,00 mm`; es muss grösser als die Bedarfsschwelle sein
- bei Zeitsteuerung eine effektive Ausbringungsrate zwischen `0,10` und `500,00 mm/h`
- bei Mengensteuerung eine bewässerte Fläche zwischen `0,10` und `1 000 000,00 m²` und eine Ausbringungseffizienz zwischen `0,10` und `1,00`

Nur Pflanzenfaktor und Anteil wirksamen Niederschlags erhalten den ausdrücklich genannten neutralen Vorschlagswert `1,00`. Bewässerungsmodus, Bedarfsschwelle, maximales Defizit, Ausbringungsrate, Fläche und Effizienz haben keinen impliziten Vorschlagswert und müssen beim erstmaligen Aktivieren ausdrücklich eingegeben werden. Bereits gespeicherte gültige Werte werden beim Bearbeiten weiterhin angezeigt.

Diese Angaben gehören zum Wetterverhalten der Zone und sind unabhängig davon bearbeitbar, ob das Pflanzen- und Standortmodell verwendet wird. Ohne vollständige und gültige Umrechnungsangaben bleibt die zonenspezifische Wetterverwendung deaktiviert. Ein vorhandener kalibrierter Durchfluss ersetzt weder die effektive Ausbringungsrate einer zeitgesteuerten Zone noch Fläche und Effizienz einer mengengesteuerten Zone, weil er allein keine wirksame Wasserhöhe beschreibt.

Für einen lokalen Kalendertag gilt:

- `Pflanzenverdunstung = Referenzverdunstung × Pflanzenfaktor`
- `wirksamer Niederschlag = gemessener Niederschlag × Anteil wirksamen Niederschlags`
- bei Zeitsteuerung `wirksame Bewässerung = tatsächliche Ventilöffnungszeit in Stunden × effektive Ausbringungsrate`
- bei Mengensteuerung `wirksame Bewässerung = tatsächlich gelieferte Liter × Ausbringungseffizienz ÷ bewässerte Fläche in m²`
- das resultierende Defizit wird auf den Bereich von `0` bis zum konfigurierten maximalen Defizit begrenzt

Der Wert eines direkten Referenzverdunstungssensors ersetzt innerhalb desselben lokalen Kalendertags den zuvor gelesenen Tageswert und wird nicht bei jeder Aktualisierung erneut addiert. Eine kumulierte Niederschlagsquelle wird über einen persistenten Quellenfortschritt differenziert. Die erste Lesung setzt nur die Baseline. Ein regulärer Rücksetzer an einer lokalen Tagesgrenze verwendet den neuen Wert als Beitrag des neuen Tages. Ein Rückgang innerhalb desselben Tages, ein Quellenwechsel, ein nicht endlicher Wert oder eine Lücke von mindestens einem vollständigen lokalen Kalendertag machen die betroffene Fortschreibung nicht belastbar und erzwingen den sichtbaren Rückfall auf das saisonale Basissoll; negative Beiträge werden nie erzeugt.

Beim erstmaligen Aktivieren oder nach einer nicht belastbaren Fortschreibung wird die Bilanz einen vollständigen lokalen Kalendertag lang beobachtend initialisiert. Während dieses Initialisierungstags bleibt das automatische Ziel verhaltensgleich beim saisonalen Basissoll. Als Startdefizit wird dessen anhand der bestätigten Zonendaten umgerechnete Wasserhöhe verwendet. Dadurch kann die Wetteraktivierung einen bestehenden Termin nicht unmittelbar reduzieren. Erst ab dem folgenden lokalen Kalendertag darf eine vollständig belastbare Bilanz das Ziel verändern. Ein Deaktivieren erhält die Bilanz, eine Wiederaktivierung nach mindestens einem nicht beobachteten vollständigen Tag initialisiert erneut verhaltensgleich.

Eine Bedarfsbewässerung wird übersprungen, wenn das aktuelle Defizit die konfigurierte Bedarfsschwelle nicht erreicht. Andernfalls wird das Defizit vollständig in Zeit beziehungsweise Liter umgerechnet. Eine Mindestbewässerung verwendet das grössere Ziel aus umgerechnetem Defizit und saisonalem Basissoll. Das Ergebnis wird niemals stillschweigend auf ein Bewässerungsfenster gekürzt; passt es nicht vollständig, greift die vorhandene Nicht-einplanbar-Behandlung. Für zukünftige Kalendertage verwendet Stufe 4 mangels Prognose weiterhin das saisonale Basissoll. Eine stündliche Neuberechnung darf nur den noch nicht begonnenen Auftrag des aktuellen lokalen Tages ersetzen.

Tatsächliche Bewässerung wird nach Abschluss oder kontrollierter Wiederherstellung eines Vorgangs genau einmal anhand seiner stabilen Ausführungs-ID gutgeschrieben. Die bestätigten Öffnungs- und Schliesszeitpunkte des Zonenventils werden unmittelbar im dauerhaften Ausführungsdatensatz gespeichert; ein erst nach Ventilschluss, Absetzzeit oder Zählerablesung gesetzter Abschlusszeitpunkt darf diese Grenzen nicht ersetzen. Fehlt bei einer Wiederherstellung einer dieser Zeitpunkte oder ist ihre Reihenfolge ungültig, wird die Kalenderzuordnung mit `irrigation_timing_unavailable` als unzuverlässig behandelt und sichtbar neu initialisiert. Die Verbuchungsmarke besteht intern aus Ausführungs-ID, lokalem Kalendertag und Ergebnis `credited` oder `unreliable`, damit ein über Mitternacht laufender Vorgang genau einmal je betroffenem Tagesanteil berücksichtigt werden kann und eine verworfene unbekannte Lieferung nicht später als Nullbeitrag wiederholt wird. Die tatsächliche Ventilöffnungszeit wird an jeder lokalen Tagesgrenze exakt aufgeteilt. Eine belastbar gemessene Gesamtmenge wird bei einem solchen Vorgang proportional zu diesen tatsächlichen Laufzeitanteilen verteilt und mit `irrigation_split_across_midnight` gekennzeichnet; ohne belastbare Mengenmessung wird bei einer mengengesteuerten Zone kein vermeintlicher Nullbeitrag gebucht, sondern sichtbar neu initialisiert und als `unreliable` protokolliert. Auch eine abgebrochene oder fehlgeschlagene Ausführung wird nur mit ihrer belastbar bekannten tatsächlichen Lieferung berücksichtigt. Manuelle Vorgänge verändern die Wasserbilanz ebenso wie automatische, ihre eigenen Ziele werden durch die Bilanz jedoch niemals nachträglich verändert.

Persistiert werden pro Zone der aktuelle Quellenfortschritt, das fortgeführte Defizit, die bereits verbuchten datierten Ausführungsmarken und höchstens die letzten 90 abgeschlossenen oder laufenden Tagesbeiträge. Die Ausführungsmarken werden über denselben vollständigen 90-Tage-Horizont gehalten und nicht durch eine davon unabhängige Anzahlgrenze abgeschnitten. Die Migration ergänzt eine leere Bilanz, deaktiviert das Wettermodul der Anlage sowie die Wetterverwendung aller vorhandenen Zonen und verändert weder bestehende Aufträge noch laufende Vorgänge. Jede Zielauflösung hält Ausgangsdefizit, Tagesbeiträge, Ergebnis, Quellen und Zeitstempel, Umrechnungsangaben, Ziel, Qualität, Warnungen und Rückfallstrategie im unveränderlichen Auftragssnapshot fest.

### Bewässerungsmodi

Die wetterabhängige Planung ergänzt die von der Steuerungsart unabhängige Auswahl:

- **Bedarfsbewässerung:** Ein fälliger Wochenplantermin ist eine zulässige Gelegenheit. Liegt kein ausreichender Wasserbedarf vor, wird er mit protokolliertem Grund übersprungen. Liegt Bedarf vor, wird das Ziel anhand der Wasserbilanz bis zu den festgelegten Grenzen bestimmt.
- **Mindestbewässerung:** Ein fälliger Termin garantiert mindestens das konfigurierte Mindestziel. Wetter und Wasserbilanz können ein grösseres Ziel begründen, reduzieren es aber nicht unter das Mindestziel.

Zeit- und Mengensteuerung bleiben das jeweilige Abschaltkriterium. Beide Bewässerungsmodi können mit beiden Steuerungsarten kombiniert werden, sofern eine Mengensteuerung durch die Wassermessung der Anlage verfügbar ist.

Bei deaktiviertem Wettermodul, nicht optierter Zone, fehlenden Quellen oder einer nicht belastbaren Wetterberechnung wird das saisonale Basissoll verwendet. Die letzte erfolgreiche Wetterkorrektur darf nicht als eingefrorener Faktor weiterwirken.

### Wetterbedingte Aufschiebung und Nachholen

Eine Regenprognose löscht einen fälligen Bewässerungsauftrag nicht sofort endgültig. Ist ausreichend Regen angekündigt, wird der Auftrag wetterbedingt aufgeschoben und bis zu einer konfigurierten Nachholfrist wiederholt neu bewertet.

Die Zonenkonfiguration enthält dafür:

- Prognosen berücksichtigen
- maximale Nachholfrist
- Nachholfenster an den Folgetagen
- Mindestprognosemenge für eine Aufschiebung
- Mindestwahrscheinlichkeit für eine Aufschiebung
- maximale nachzuholende Zielmenge beziehungsweise Laufzeit

Die Prognoseverwendung ist nach der Migration und für jede neu angelegte Zone standardmässig deaktiviert. Sie kann nur aktiviert werden, wenn das Wettermodul der Anlage und die gemessene Wasserbilanz der Zone vollständig konfiguriert sind und eine verfügbare `weather`-Entity ausdrücklich der Quellenrolle `Wetterprognose` zugeordnet ist. Die Zuordnung allein aktiviert keine Aufschiebung.

Stufe 5 ruft Prognosen ausschliesslich über die Home-Assistant-Aktion `weather.get_forecasts` ab. Stündliche Prognosen werden bevorzugt, danach `twice_daily` und zuletzt tägliche Prognosen, sofern die zugeordnete Entity die jeweilige Art unterstützt. Ein Fehler einer bevorzugten Art erlaubt den Versuch der nächsten ausdrücklich unterstützten Art. Direkte Forecast-Attribute im Entity-Zustand, anbieterspezifische Dienste und eigene Providerzugänge werden nicht verwendet.

Für die zonenspezifischen Einstellungen gelten folgende Standardwerte und Grenzen:

- `Prognosen berücksichtigen`: standardmässig deaktiviert
- `maximale Nachholfrist`: Standard `2` lokale Kalendertage, zulässig `1` bis `7`
- `Mindestprognosemenge`: Standard `3,0 mm`, zulässig `0,1` bis `100,0 mm`
- `Mindestwahrscheinlichkeit`: Standard `70 %`, zulässig `1` bis `100 %`
- `maximales Nachholziel`: ein ausdrücklich bestätigtes positives Zeit- beziehungsweise Mengenziel innerhalb der allgemeinen Zielgrenzen der Zone; als Vorschlag wird bei Bedarfsbewässerung das grösste bestätigte Basissoll und bei Mindestbewässerung mindestens das grösste gegenwärtig mögliche saisonale Basissoll verwendet
- `Nachholfenster`: je lokalem Wochentag höchstens ein ausdrücklich konfiguriertes Start-/Endintervall; leere Tage sind zulässig, mindestens ein Intervall ist erforderlich und ein Intervall darf wie ein reguläres Bewässerungsfenster über Mitternacht reichen

Das maximale Nachholziel ist eine sichtbare Sicherheitsobergrenze für das bei einem nachgeholten Auftrag aus der Wasserbilanz abgeleitete Ziel. Ein darüberliegender Bedarf wird auf diese konfigurierte Obergrenze begrenzt, im Entscheidungssnapshot mit `make_up_target_capped` gekennzeichnet und bleibt über die tatsächlich gutgeschriebene Bewässerung als Defizit in der Wasserbilanz erhalten. Bei Mindestbewässerung darf die Obergrenze nicht kleiner als das grösste aktuell mögliche saisonale Basissoll eines konfigurierten regulären Termins sein; eine entsprechende Konfiguration oder spätere Saisonänderung wird abgelehnt und niemals durch eine stille Unterschreitung der Mindestbewässerung geheilt.

Eine Prognoseperiode wird nur berücksichtigt, wenn Zeitpunkt, Niederschlagsmenge und Niederschlagswahrscheinlichkeit vorhanden, endlich und plausibel sind, die Wahrscheinlichkeit mindestens der konfigurierten Mindestwahrscheinlichkeit entspricht und die vollständige Periode zwischen dem Bewertungszeitpunkt und dem Beginn der nächsten verfügbaren Nachholmöglichkeit liegt. Stündliche Perioden dauern eine Stunde, `twice_daily`-Perioden zwölf Stunden und tägliche Perioden einen vollständigen lokalen Kalendertag. Angebrochene Perioden werden nicht anteilig hoch- oder heruntergerechnet. Die Mengen aller so qualifizierten Perioden werden addiert. Nur wenn diese Summe die Mindestprognosemenge erreicht, darf aufgeschoben werden. Fehlende Felder, eine nicht aktuelle Quellenbeobachtung, eine leere Antwort, nicht unterstützte Prognosearten, Einheitenfehler oder ein Aktionsfehler führen ausfallsicher zu keiner neuen Aufschiebung und werden mit stabilem Grundcode protokolliert.

Eine Prognose wird erstmals unmittelbar vor der Ausführung des regulären Auftrags bewertet, nicht beim Erzeugen des bis zu zwei Wochen im Voraus sichtbaren Auftrags. Die Ausführung prüft atomar, dass diese Fälligkeitsbewertung erfolgt ist, bevor ein Ventil geöffnet werden darf. Eine ausreichende Prognose verschiebt den bestehenden Auftrag in das früheste vollständig innerhalb der festen Nachholfrist liegende Nachholfenster. Der ursprüngliche Auftragsbezug, die ursprüngliche Termin-ID, das saisonale Basissoll, die feste Nachholfrist und das maximale Nachholziel bleiben dabei erhalten. Die Frist endet zur lokalen Uhrzeit des ursprünglichen Fensterendes nach der konfigurierten Zahl lokaler Kalendertage und wird zeitzonen- sowie DST-sicher aufgelöst.

Zu Beginn jedes Nachholfensters werden zuerst gemessene Wetterwerte und tatsächliche Bewässerung in die Wasserbilanz übernommen. Bei Bedarfsbewässerung wird ein dadurch unter die Bedarfsschwelle gefallener Auftrag ohne Ventilöffnung mit `measured_rain_satisfied_need` abgeschlossen. Bei Mindestbewässerung bleibt das saisonale Mindestziel geschuldet; eine Prognose kann dessen Ausführung zeitlich verschieben, aber gemessener Regen reduziert es nicht. Besteht weiterhin Bedarf, darf nur dann erneut bis zum nächsten Nachholfenster aufgeschoben werden, wenn dieses vollständig innerhalb der unveränderten Frist liegt und die neu abgerufene Prognose erneut die Schwellwerte erreicht. Gibt es keine weitere Nachholmöglichkeit, wird die Prognose ignoriert und der Auftrag im aktuellen Fenster ausgeführt, sofern das vollständige Ziel hineinpasst.

Eine Aufschiebung wird im dauerhaften Bewässerungsauftrag mit ursprünglichem Fenster, aktueller Nachholmöglichkeit, fester Frist, Prognoseart, verwendeten vollständigen Perioden, qualifizierter Niederschlagssumme, Schwellwerten, Bewertungszeitpunkt, Qualität, Warnungen und Anzahl bisheriger Aufschiebungen gespeichert. Der Dispatcher darf einen fälligen prognosefähigen Auftrag nur starten, nachdem die Planung diesen Nachweis für die aktuelle Ausführungsmöglichkeit atomar erneuert hat. Damit bleiben Aufschiebung und erneute Bewertung über Neustarts erhalten, ohne ein Ventil auf Basis einer veralteten Vorhersage zu öffnen.

Wird das Wettermodul der Anlage, die Wetterverwendung der Zone oder nur die Prognoseverwendung während einer Aufschiebung deaktiviert, bleibt der Auftrag samt fester Frist erhalten. Er wird im nächsten bereits festgelegten beziehungsweise noch innerhalb der Frist verfügbaren Nachholfenster ohne weitere Prognose anhand des ursprünglichen saisonalen Basissolls und der weiterhin geltenden Bewässerungsmodus-Regeln bewertet. Eine Konfigurationsänderung darf die Frist weder verlängern noch den Auftrag löschen. Wird kein vollständiges Nachholfenster mehr erreicht, endet der Auftrag nachvollziehbar als `make_up_deadline_expired`.

Für eine freitags zwischen `05:00` und `08:00` geplante Heckenbewässerung mit zwei Tagen Nachholfrist gilt beispielhaft:

1. Am Freitag wird ausreichend Regen prognostiziert und der Auftrag wird als `wetterbedingt aufgeschoben` erhalten.
2. Tatsächlich gemessener Regen wird der Wasserbilanz gutgeschrieben.
3. Bleibt der Regen aus, wird der Bedarf im konfigurierten Nachholfenster am Samstag erneut geprüft.
4. Besteht weiterhin Bedarf, wird am Samstag bewässert.
5. Fällt genügend Regen, wird der Auftrag mit nachvollziehbarem Abschlussgrund ohne Bewässerung abgeschlossen.
6. Eine neue Prognose darf die Bewässerung nicht unbegrenzt über die Nachholfrist hinaus verschieben.

Die Abnahme erfolgt an den öffentlichen Schnittstellen der Prognosenormalisierung und -entscheidung, des Config Flow samt Migration, der atomaren automatischen Planung sowie der dauerhaften Auftragsspeicherung und Neustartwiederherstellung. Mindestens geprüft werden das vollständige Freitag-Regen-Samstag-Nachholen-Szenario, ausgebliebener und ausreichend gemessener Regen, Prognoseausfall, unvollständige Perioden, feste Frist, fehlendes Nachholfenster, Deaktivieren während einer Aufschiebung, Zielobergrenze und Neustart vor jeder erneuten Bewertung.

### Bodenfeuchterückmeldung

Ein Bodenfeuchtesensor ist eine optionale Eingabe des Wettermoduls pro Zone oder Teilfläche. Seine Verwendung besitzt die eigene zonenspezifische Checkbox `Bodenfeuchterückmeldung verwenden` und ist standardmässig deaktiviert. Sie kann nur aktiviert werden, wenn das Wettermodul der Anlage und die gemessene Wasserbilanz der Zone vollständig aktiviert und konfiguriert sind. Ein Deaktivieren erhält die Sensorzuordnung und Kalibrierung, beendet aber jede Wirkung auf die Wasserbilanz. Manuelle Bewässerungsaufträge und bereits begonnene Bewässerungsvorgänge werden niemals verändert.

Unterstützt werden ausschliesslich ausdrücklich ausgewählte `sensor`-Entities mit Device-Class `moisture`, State-Class `measurement` und Einheit `%`. Der Zustand muss endlich zwischen `0` und `100 %` liegen und darf höchstens zwei Stunden alt sein; wie bei anderen Quellen wird `last_reported` und ersatzweise `last_updated` verwendet. `unknown`, `unavailable`, eine fehlende Entity, ein abweichender Entity-Vertrag oder eine nicht unterstützte Einheit führen zu keiner Korrektur.

Jede Sensorzuordnung enthält zwei ausdrücklich bestätigte Kalibrierpunkte:

- `Trockenpunkt`: Sensorwert am für die Zone beziehungsweise Teilfläche festgelegten trockenen Referenzzustand, zulässig `0..95 %`
- `Feuchtpunkt`: Sensorwert nach vollständiger Bewässerung und Abtropfen bis zum feuchten Referenzzustand, zulässig `5..100 %` und mindestens fünf Prozentpunkte über dem Trockenpunkt

Zwischen beiden Punkten wird linear auf einen normierten verfügbaren Bodenwasservorrat von `0..100 %` abgebildet. Plausible Rohwerte ausserhalb der Kalibrierpunkte werden auf die jeweilige Grenze begrenzt und mit `soil_moisture_below_dry_calibration` beziehungsweise `soil_moisture_above_wet_calibration` gekennzeichnet; die Rohmessung selbst wird nicht verändert. Aus dem normierten Vorrat wird ein Sensor-Defizit zwischen `0` und dem konfigurierten maximalen Wasserdefizit der Zone abgeleitet.

Eine Zone verwendet entweder genau eine zonenweite Zuordnung oder je eine Zuordnung für jede konfigurierte Teilfläche mit positiver Fläche. Beide Varianten dürfen nicht gemischt werden. Teilflächenwerte werden nach ihrer bestätigten Fläche gewichtet. Fehlt bei der Teilflächenvariante eine Zuordnung oder eine belastbare Beobachtung, wird keine Teilkorrektur aus den verbleibenden Sensoren berechnet.

Eine neue Zuordnung, geänderte Kalibrierung, Reaktivierung oder erste belastbare Beobachtung initialisiert die Rückmeldung rein beobachtend. Eine Korrektur ist frühestens mit einer zweiten belastbaren Beobachtung zulässig, die mindestens 30 Minuten und höchstens sechs Stunden später liegt. Ändert sich der normierte Vorrat zwischen diesen Beobachtungen um mehr als 20 Prozentpunkte, wird die neuere Beobachtung mit `soil_moisture_jump_detected` zur neuen Referenz und noch nicht angewendet. Pro lokalem Kalendertag ist höchstens eine Korrektur zulässig.

Die Bodenfeuchte korrigiert ausschliesslich das für den aktuellen lokalen Kalendertag fortgeschriebene Wasserdefizit. Abweichungen bis zur Totzone von `max(1,0 mm; 5 % des maximalen Defizits)` werden nur protokolliert. Eine einzelne Tageskorrektur ist auf `min(5,0 mm; 25 % des maximalen Defizits)` in beide Richtungen begrenzt. Das korrigierte Defizit bleibt im Bereich `0` bis zum konfigurierten maximalen Defizit. Erst danach wird die bestehende Bedarfs- oder Mindestbewässerungsregel angewendet; eine Mindestbewässerung bleibt mindestens beim saisonalen Basissoll. Zukünftige Kalendertage verwenden weiterhin das saisonale Basissoll, und Prognosen verändern die Bodenfeuchtekorrektur nicht rückwirkend.

Bei fehlender, veralteter, unvollständiger oder unplausibler Bodenfeuchte wird die aus Verdunstung, gemessenem Regen und tatsächlicher Bewässerung fortgeschriebene Wasserbilanz unverändert verwendet. Der Sensor erzeugt weder eine Sicherheitssperre noch einen Rückfall auf ein früheres Ziel und kann den Betrieb nicht blockieren. Quellenqualität, Kalibriersignatur, normierter Vorrat, abgeleitetes Sensor-Defizit, Totzone, begrenzte Korrektur, Beobachtungszeitpunkte, Warnungen und der Grund einer Nichtanwendung werden im Wasserbilanzzustand, Auftragssnapshot und redigierten Diagnoseexport ausgewiesen.

Die Migration ergänzt für jede Zone eine deaktivierte Rückmeldung und eine leere Zuordnung. Sie verändert weder Wettermodul, Wasserbilanz, offene Bewässerungsaufträge noch laufende Bewässerungsvorgänge. Persistierte Beobachtungs- und Korrekturfortschritte werden bei deaktivierter Rückmeldung verworfen, die Konfiguration bleibt erhalten; eine spätere Reaktivierung beginnt dadurch erneut beobachtend.

## Optionales Modul für Teilgaben und Sickerpausen

Teilgaben und Sickerpausen sind insbesondere sinnvoll, wenn die Ausbringungsrate die Versickerungsfähigkeit des Bodens übersteigt, beispielsweise bei Regnern auf schwerem oder geneigtem Boden. Bei langsam ausbringenden Tropfschläuchen können sie unnötig sein. Pflanzen-, Boden- und Ausbringungsprofile dürfen eine Empfehlung erzeugen, aktivieren das Modul aber niemals automatisch.

Eine verwendende Zone konfiguriert mindestens:

- maximale Dauer oder Wassermenge einer Teilgabe passend zur Steuerungsart
- minimale Dauer der Sickerpause
- maximale Anzahl Teilgaben
- maximale Gesamtlebensdauer des Bewässerungsvorgangs einschliesslich Sickerpausen

Der Bewässerungsvorgang bleibt die gemeinsame fachliche Klammer aller Teilgaben. Ziel, Ergebnis, tatsächlich gelieferte Wassermenge und tatsächliche Laufzeit werden über alle Teilgaben gemeinsam geführt.

Für die Ausführung gelten:

- Während einer Sickerpause bleibt das Restziel erhalten.
- Zonen- und Hauptventil werden während der Sickerpause geschlossen.
- Andere Zonen derselben Anlage dürfen während der Sickerpause bewässert werden.
- Teilgaben werden nicht als voneinander unabhängige Bewässerungsaufträge dargestellt.
- Not-Aus, Anlagen- oder Zonendeaktivierung und ausdrücklicher Abbruch beenden den gesamten Bewässerungsvorgang kontrolliert.
- Ein Neustart stellt offene Teilgaben, Restziel und laufende Sickerpause aus dem persistenten Zustand wieder her, ohne ein Ventil ungeprüft geöffnet zu lassen.
- Die harte maximale Lieferlaufzeit einer Mengensteuerung begrenzt die aufsummierte Ventilöffnungszeit und schliesst bewässerungsfreie Sickerpausen nicht ein.
- Die maximale Gesamtlebensdauer begrenzt den gesamten Vorgang einschliesslich Sickerpausen.
- Der vollständige Vorgang muss einschliesslich Teilgaben und Sickerpausen innerhalb seines zulässigen Ausführungszeitraums liegen.

Sickerpausen werden nicht als blockierendes Warten innerhalb des vorhandenen Ventil-Executors umgesetzt. Die Ausführungssteuerung benötigt einen persistenten übergeordneten Bewässerungsvorgang mit einzeln disponierbaren Teilgaben, damit andere Zonen während der Pause weiterarbeiten können.

### Verbindliches Sicherheits- und Ablaufmodell

Das Modul ist anlagenweit verfügbar und wird zusätzlich je Zone ausdrücklich verwendet. Beide Schalter sind standardmässig deaktiviert. Das Deaktivieren löscht keine Teilgabeneinstellungen. Die bei Annahme eines Bewässerungsauftrags gültige Verwendung und alle vier zonenspezifischen Grenzwerte werden in dessen unveränderlichen Ausführungssnapshot übernommen. Eine spätere Konfigurationsänderung verändert weder einen offenen manuellen Auftrag noch einen begonnenen Bewässerungsvorgang. Bestehende und neue Aufträge ohne aktiven Teilgabensnapshot verwenden unverändert die zusammenhängende Einmalausführung.

Die maximale Teilgabengrösse und die minimale Sickerpause müssen endlich und grösser als null sein. Die maximale Teilgabenanzahl ist eine positive ganze Zahl, die maximale Gesamtlebensdauer ist endlich und grösser als null. Für jeden noch nicht begonnenen Auftrag wird vor der Annahme beziehungsweise automatischen Planung geprüft, ob das vollständige Ziel mit Teilgaben, den dazwischenliegenden Mindestpausen und den konservativen hydraulischen Zeitbudgets innerhalb der maximalen Teilgabenanzahl, der maximalen Gesamtlebensdauer und des zulässigen Ausführungszeitraums liegt. Ist dies nicht möglich, wird der Auftrag abgelehnt beziehungsweise als nicht planbar ausgewiesen; eine Teilgabe wird niemals stillschweigend über ihren konfigurierten Höchstwert vergrössert.

Mit Beginn der ersten Teilgabe entsteht genau ein persistenter Bewässerungsvorgang. Der ursprüngliche Bewässerungsauftrag bleibt bis zum terminalen Ergebnis dieses Vorgangs im Zustand `executing`. Jede Teilgabe besitzt lediglich eine stabile, dem Vorgang untergeordnete Identität. Während einer Sickerpause befindet sich der Vorgang im Zustand `soaking`, besitzt einen frühesten Fortsetzungszeitpunkt und keinen aktiven Hardware-Checkpoint. Ein weiterer Bewässerungsvorgang derselben Zone darf bis zum terminalen Ende nicht beginnen.

Der Dispatcher darf während einer Sickerpause nur einen anderen Vorgang beginnen, dessen konservativ angesetzte maximale Belegungsdauer die späteste sichere Fortsetzung des pausierenden Vorgangs nicht überschreitet. Dafür werden bei zeitgesteuerten Aufträgen die vollständige verbleibende Laufzeit und bei mengengesteuerten Aufträgen die verbleibende harte Lieferlaufzeit einschliesslich der jeweiligen Ventil- und Rückmeldebudgets angesetzt. Passt kein anderer Vorgang sicher in die verfügbare Lücke, bleibt die Anlage bis zur nächsten Teilgabe im Leerlauf. Unter den so zugelassenen Kandidaten bleibt die bestehende Priorität manueller vor automatischen Aufträgen erhalten; eine fällige Fortsetzung hat Vorrang, sobald ein anderer Kandidat ihre späteste sichere Fortsetzung verletzen würde.

Vor jedem möglichen Öffnungsbefehl werden Bewässerungsvorgang, vorbereitete Teilgabe und der globale aktive Hardware-Checkpoint gemeinsam atomar gespeichert. Ein Teilgabenergebnis wird anhand seiner stabilen Teilgaben-ID höchstens einmal dem Restziel, den kumulierten Ergebnissen und dem Verbrauch zugeordnet. Die harte Lieferlaufzeit einer Mengensteuerung wird jeder Teilgabe nur als noch verfügbares kumulatives Budget übergeben. Ein nicht erreichtes Mengenziel, eine Sicherheitsverletzung, eine überschrittene Grenze oder ein widersprüchlicher persistenter Zustand beendet den gesamten Bewässerungsvorgang; es wird keine weitere Teilgabe geöffnet.

Beim Wiederanlauf werden vor jeder fachlichen Wiederherstellung alle der Anlage zugeordneten Ventile geschlossen und ihre Schliessung geprüft. Eine persistierte Sickerpause wird danach ohne Hardwareaktion fortgeführt. Eine unterbrochene Teilgabe darf nur weitergeführt werden, wenn ihre tatsächliche Lieferung anhand bestätigter Öffnungs- und Schliesszeitpunkte beziehungsweise einer belastbaren Zählerdifferenz eindeutig rekonstruiert und genau einmal verbucht werden kann. Bei möglicher, aber nicht zuverlässig bestimmbarer Wasserabgabe oder nicht bestätigter Ventilschliessung wird der gesamte Vorgang fail-closed beendet und die Anlage sicherheitsgesperrt. Ein beim Upgrade bereits aktiver Vorgang ohne Teilgabensnapshot behält die bisherige konservative Wiederanlaufbehandlung und wird nicht nachträglich aufgeteilt.

Abbruch, Not-Aus sowie entzogene Anlagen- oder Zonenbetriebsfreigabe adressieren stets den ganzen Bewässerungsvorgang. Während einer aktiven Teilgabe werden zuerst die Ventile kontrolliert geschlossen und die belastbar bekannte Lieferung verbucht; während einer Sickerpause kann der Vorgang ohne Hardwarebetätigung terminal gespeichert werden. Verlauf und Bewässerungsaufträge zeigen weiterhin genau einen gemeinsamen Vorgang beziehungsweise Auftrag. Teilgaben und Pausen sind untergeordnete Diagnose- und Statusdetails. Die Wasserbilanz berücksichtigt die belastbar bekannten Lieferungen aller Teilgaben genau einmal unter der stabilen Ausführungs-ID des gemeinsamen Vorgangs.

## Berechnungs- und Planungsschnittstelle

Pflanzenmodell, saisonale Korrektur und Wettermodul bestimmen das Ziel eines noch nicht begonnenen automatischen Bewässerungsauftrags über eine gemeinsame fachliche Zielauflösung. Diese kann genau eines der Ergebnisse liefern:

- ausführen mit einem festgelegten Zeit- oder Mengenziel
- mit nachvollziehbarem Grund überspringen
- bis zu einem festgelegten Zeitpunkt und einer festen Nachholfrist aufschieben

Jeder erzeugte automatische Bewässerungsauftrag besitzt einen unveränderlichen Berechnungssnapshot. Dieser enthält, soweit verfügbar:

- Basissoll oder abweichendes Tagesziel
- saisonalen Faktor und saisonales Basissoll
- verwendete Wetterquellen und deren Zeitstempel
- Referenz- und Pflanzenverdunstung
- wirksamen Niederschlag
- vorheriges und resultierendes Wasserdefizit
- endgültiges Bewässerungsziel
- verwendete Rückfallstrategie
- Qualitätsstufe und Warnungen

Die Zielauflösung wird vor der Queue- und Fenstereinteilung durchgeführt. Die anschliessende Bewässerungsplanung prüft, ob das aufgelöste Ziel beziehungsweise alle Teilgaben vollständig in den zulässigen Zeitraum passen. Aktive Bewässerungsvorgänge werden von einer Neuberechnung niemals verändert.

## Stufenweise Umsetzung der Erweiterungsmodule

Jede Ausbaustufe muss für sich vollständig nutzbar, migrierbar, testbar und deaktivierbar sein. Ein Modulschalter wird im regulären Wizard erst auswählbar, wenn die zugehörige Stufe den beschriebenen Grundvertrag erfüllt.

### Stufe 1: Modulgrundlage, Profile und relatives Basissoll

- gemeinsamen Modul- und Deaktivierungsvertrag in Konfiguration und Planung abbilden
- Anlagenwizard um den kompakten Schritt `Optionale Erweiterungen` ergänzen
- Anlagen- und Zoneneinstellungen in direkt erreichbare Fachbereiche aufteilen
- gemeinsames Basissoll pro Zone und optionale Tagesabweichungen einführen
- bestehende Tagesziele verhaltensgleich migrieren, indem sie als ausdrückliche Tagesabweichungen erhalten bleiben
- Pflanzen-, Boden-, Standort- und Ausbringungsprofile erfassen
- eine oder mehrere Teilflächen pro Zone unterstützen
- relative Empfehlungen mit Qualitätsangabe und Hilfetexten anzeigen
- keine automatische Änderung des Basissolls und keine absolute Empfehlung ohne klimatische Grundlage vornehmen

Für die Migration bestehender Version-2-Zonen wird das erste vorhandene positive Tagesziel in Wochentagsreihenfolge als gemeinsames Basissoll übernommen. Sämtliche bisherigen Tagesziele bleiben unabhängig von Gleichheit oder Wiederholung als ausdrückliche Tagesabweichungen erhalten, sodass sich kein bestehender Auftrag ändert. Besitzt eine bestehende Zone kein einziges Tagesziel, bleibt ihr Basissoll zunächst leer; sie kann weiterhin manuell verwendet werden und benötigt erst vor dem Speichern eines neuen automatischen Bewässerungsfensters ein positives Basissoll. Die Migration erfindet für eine leere Zone keinen Wert und setzt allein deshalb keine Sicherheitssperre.

### Stufe 1.1: Persistente Ausführungsdiagnose (umgesetzt ab rc19)

Vor der saisonalen Korrektur ist die Ablaufdiagnose von Planung und Dispatcher so erweitert, dass ein nicht gestarteter oder blockierter Bewässerungsauftrag nach einem unsauberen Neustart nachvollzogen werden kann. Die Diagnose ist rein beobachtend und verändert weder Priorisierung noch Freigaben, Ziele oder Ausführung.

- Die bisherige boolesche Ausführungsfreigabe wird intern als strukturierte Entscheidung mit einem stabilen Grundcode dargestellt. Mindestens unterschieden werden `waiting_for_start`, `ready`, `operation_disabled`, `zone_disabled`, `automation_disabled`, `zone_automation_disabled`, `safety_lock`, `emergency_stop`, `reconfiguration_required`, `config_reload_pending`, `automatic_planning_in_progress`, `actuator_snapshot_mismatch`, `window_no_longer_fits` und `expired`.
- Persistiert werden ausschliesslich Zustandsübergänge, nicht jeder Dispatcher-Durchlauf. Ein Eintrag enthält Zeitstempel, Auftrags-ID, Zonen-ID, alten und neuen Grundcode, die für die Entscheidung relevanten Freigaben und Sperren sowie den nächsten geplanten Weckzeitpunkt.
- Pro Bewässerungsanlage werden die letzten 100 Diagnoseeinträge als begrenzter Ringpuffer im versionierten Laufzeitspeicher geführt. Die Migration ergänzt einen leeren Puffer und verändert keine bestehenden Aufträge oder Bewässerungsvorgänge.
- Die Home-Assistant-Integrationsdiagnose zeigt den aktuellen Dispatcherzustand, den gegebenenfalls blockierenden Auftrag, den Grund, den Beginn der Blockierung, den nächsten Weckzeitpunkt und den Ringpuffer. Entity-Zustände, Zugangsdaten und andere nicht benötigte Nutzdaten werden nicht kopiert.
- Ein fälliger blockierter Auftrag erzeugt beim Wechsel in einen Blockierungsgrund genau einen gedrosselten Systemprotokolleintrag. Erst ein Wechsel des Grundes oder die erneute Blockierung nach zwischenzeitlichem `ready` darf einen weiteren Eintrag erzeugen; eine Warteschleife darf das Protokoll nicht füllen.
- Ein erfolgreicher Start, Ablauf, Abbruch, Konfigurationsreload und Neustart schliesst beziehungsweise überführt den letzten Diagnosezustand ausdrücklich. Nach einem unsauberen Neustart bleibt dadurch erkennbar, welcher Zustand zuletzt dauerhaft erreicht wurde.
- Für den Integrationslebenszyklus ergänzen `startup`, `clean_shutdown`, `config_reload` und `unclean_restart` die auftragsbezogenen Grundcodes; `completed` und `cancelled` schliessen einen Auftrag ausdrücklich ab. Unerwartete Dispatcher- und Planungsfehler werden als `dispatcher_error` beziehungsweise `automatic_planning_error` mit Fehlerklasse und nächstem Retry-Zeitpunkt erfasst; die vollständige Ausnahme mit Stacktrace bleibt im Home-Assistant-Systemprotokoll.
- Jeder Dispatcher-Durchlauf muss entweder einen Auftrag dauerhaft voranbringen oder warten. Bei einem unerwarteten Fehler verhindert ein exponentieller, auf 60 Sekunden begrenzter Backoff einen Fehler- oder Busy-Loop. Ein Fehler beim Schreiben der optionalen Diagnose wird protokolliert, darf den Bewässerungsbetrieb aber nicht selbst sperren.
- Kurzlebige In-Memory-Warteobjekte und zugehörige Fehler werden nach Abschluss oder Abbruch entfernt, damit die Zahl früherer Aufträge den Arbeitsspeicher nicht unbegrenzt belastet.
- Die Diagnose benennt nur Zustände innerhalb des Irrigation Managers. Stromausfall, Kernel-Panik, OOM oder andere HAOS-Ursachen werden nicht behauptet, sondern bleiben mit den Host- und Supervisor-Protokollen zu korrelieren.

Abnahmekriterien sind ein reproduzierter fälliger, aber blockierter Auftrag ohne Busy-Loop, korrekte Grundcodes für alle Freigabe- und Sperrpfade, gedrosselte Protokollierung, Begrenzung des Ringpuffers, Migration ohne Verhaltensänderung sowie der Erhalt des letzten Diagnosezustands über einen simulierten unsauberen Neustart.

### Stufe 2: Saisonale Korrektur (umgesetzt ab rc20)

- zwölf Monatsfaktoren und tägliche lineare Interpolation implementieren
- manuelle Kurve unabhängig vom Pflanzenmodell erlauben
- Vorschlagskurven aus Pflanzenprofilen nur nach Bestätigung übernehmen
- Zielvorschau, Berechnungssnapshot und atomare Neuplanung ergänzen
- deaktivierte Saisonkorrektur nachweislich als Faktor `1,0` behandeln

### Stufe 3: Wetterquellen und Diagnose

- Home-Assistant-Sensoren und `weather`-Entities nach Quellenrollen auswählen
- Einheiten, Aktualität, Plausibilität und Qualitätsstatus normalisieren
- Quellenzustand in der Home-Assistant-Integrationsdiagnose anzeigen und den Einstellungsdialog auf die fachliche Quellenzuordnung beschränken
- leere Quellenzuordnung verhaltensgleich migrieren und Teilkonfiguration ausdrücklich zulassen
- keine Rohwert-Historie und keine automatische Quellenauswahl einführen
- den anlagenweiten Laufzeit-Modulschalter und die zonenspezifische Wetterverwendung bis zur vollständigen Wasserbilanz der Stufe 4 noch nicht freigeben
- noch keine automatische Zielkorrektur aktivieren, bevor Wasserbilanz und Ausfallregeln vollständig implementiert sind

### Stufe 4: Gemessener Niederschlag und Wasserbilanz

- tägliche Wasserbilanz pro optierter Zone persistent führen
- gemessenen Niederschlag und zugeordnete Bewässerung verrechnen
- Bedarfs- und Mindestbewässerung ohne prognosebedingte Aufschiebung einführen
- Wetterausfall auf das saisonale Basissoll zurückfallen lassen
- alle Berechnungsgrundlagen im Auftragssnapshot protokollieren

### Stufe 5: Prognosen und Nachholstrategie

- Wetterprognosen über die Home-Assistant-Wetterschnittstelle beziehen
- Aufschieben, erneute Bewertung und Abschluss innerhalb einer Nachholfrist implementieren
- separate Nachholfenster berücksichtigen
- wetterbedingt aufgeschobene Aufträge persistent und neustartsicher führen
- das Freitag-Regen-Samstag-Nachholen-Szenario vollständig abdecken

### Stufe 6: Bodenfeuchterückmeldung (umgesetzt ab rc27)

- optionale Sensorzuordnung pro Zone oder Teilfläche einführen
- Kalibrierung, Aktualität und Plausibilität festlegen
- Bodenfeuchte nur als nachvollziehbare Rückmeldung oder Korrektur der Wasserbilanz verwenden
- ein unabhängiges Deaktivieren der Bodenfeuchterückmeldung ohne Verlust der Sensorkonfiguration ermöglichen

### Stufe 7: Teilgaben und Sickerpausen (umgesetzt ab rc30)

- persistenten Bewässerungsvorgang mit disponierbaren Teilgaben modellieren
- andere Zonen während Sickerpausen ausführen
- Restziel, Gesamtmessung, Abbruch und Wiederanlauf über mehrere Teilgaben sicherstellen
- Planungsprüfung um Pausen und maximale Gesamtlebensdauer erweitern
- Cards und Verlauf um aktuellen Teilgaben- beziehungsweise Sickerzustand ergänzen

## Übergreifende Abnahmekriterien der Erweiterungen

Jede Ausbaustufe prüft mindestens:

- Aktivieren und Deaktivieren ohne Verlust der Modulkonfiguration
- unveränderten Grundbetrieb bei deaktiviertem Modul
- unveränderte aktive Bewässerungsvorgänge bei Moduländerungen
- atomare Neuberechnung ausschliesslich noch nicht begonnener automatischer Bewässerungsaufträge
- unveränderte manuelle Bewässerungsaufträge
- verständliche Hilfetexte und Ausblendung nicht benötigter Wizard-Schritte
- stabile Einheiten und Ablehnung ungültiger oder nicht endlicher Werte
- nachvollziehbare Qualität, Quellen und Rückfallstrategie
- verhaltensgleiche Migration vorhandener Anlagen und Wochenpläne
- Neustartverhalten aller persistenten Zwischenzustände
- Einhaltung von Betriebsfreigabe, Automatikfreigabe, Sicherheitssperre und Not-Aus

Für die Wetterstufen kommen mindestens Tests für veraltete, fehlende und unplausible Quellen, Wetterausfall während einer Aufschiebung, lokale Tagesgrenzen und das Nachholen nach ausgebliebenem Regen hinzu. Für Teilgaben kommen mindestens Konkurrenz mit anderen Zonen, Neustart während einer Sickerpause, kumulierte Mengen- und Laufzeitgrenzen sowie Abbruch in jeder Phase hinzu.

## Noch nicht festgelegt

Offen bleiben alle Eigenschaften der Bewässerungsanlage und Bewässerungszone, die in diesem Dokument nicht ausdrücklich geregelt sind. Für spätere Erweiterungsstufen sind insbesondere numerische Katalogwerte und Wertebereiche, Aktualitätsgrenzen, Prognoseschwellen, Standard-Nachholfristen, Bodenfeuchte-Kalibrierung und die genaue vereinfachte Referenzverdunstungsberechnung vor ihrer jeweiligen Implementierungsstufe noch verbindlich festzulegen.
