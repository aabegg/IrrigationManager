# Irrigation Manager

Dieser Kontext beschreibt die fachlichen Begriffe einer intelligenten Gartenbewässerung und grenzt zusammengehörige Anlagen, Zonen und Bewässerungsvorgänge voneinander ab.

## Language

**Bewässerungsanlage**:
Ein physisch zusammengehöriger Bewässerungsverbund mit gemeinsamer Wasserzufuhr sowie optional gemeinsamem Hauptventil und Wasserzähler. Eine weitere unabhängig versorgte Installation ist eine eigene Bewässerungsanlage.
_Avoid_: System, Installation, Controller

**Bewässerungszone**:
Ein gemeinsam schaltbarer Bewässerungsbereich hinter genau einem Zonenventil. Alle enthaltenen Pflanzen werden gleichzeitig bewässert und können nicht unabhängig geplant werden.
_Avoid_: Kreis, Kanal, Station

**Teilfläche**:
Ein hydraulisch nicht separat schaltbarer Bereich innerhalb einer Bewässerungszone mit eigenem Pflanzenprofil, eigener Fläche und eigener relativer Ausbringungsrate.
_Avoid_: Unterzone

**Teilgabe**:
Ein begrenzter Abschnitt der Zielmenge oder Zieldauer einer Bewässerungszone. Mehrere Teilgaben können durch Sickerpausen getrennt werden, ohne den verbleibenden Wasserbedarf zu verwerfen.

**Sickerpause**:
Eine bewässerungsfreie Zeit zwischen zwei Teilgaben derselben Zone, in der Wasser in den Boden eindringen kann und andere Zonen bewässert werden dürfen.

**Bewässerungsauftrag**:
Eine noch nicht begonnene Anforderung, eine Zone mit einem bestimmten Bewässerungsziel zu versorgen. Ein Auftrag kann automatisch geplant oder manuell angefordert und bis zu seinem Beginn zurückgenommen werden.
_Avoid_: Job, Queue-Eintrag

**Bewässerungsvorgang**:
Die Ausführung eines angenommenen Bewässerungsauftrags für genau eine Zone. Ein Vorgang kann mehrere Teilgaben umfassen und besitzt ein gemeinsames Ziel sowie ein abschließendes Ergebnis.
_Avoid_: Zyklus, Lauf, Session

**Bewässerungsmodus**:
Die zonenspezifische Entscheidung, ob ein zulässiger Termin nur bei errechnetem Wasserbedarf ausgeführt wird oder eine garantierte Mindestbewässerung auslöst.
_Avoid_: Zeitmodell, Schedule-Typ

**Bedarfsbewässerung**:
Ein Bewässerungsmodus, bei dem der Rhythmus lediglich zulässige Termine vorgibt und die Zone ohne ausreichenden Wasserbedarf übersprungen wird.

**Mindestbewässerung**:
Ein Bewässerungsmodus, bei dem jeder fällige Termin mindestens die für die Zone festgelegte Mindestmenge erhält.
_Avoid_: Pflichtlauf

**Bewässerungsziel**:
Das zonenspezifische Abschaltkriterium eines Bewässerungsvorgangs. Es ist entweder eine zu liefernde Wassermenge oder eine auszuführende Laufzeit.

**Mengensteuerung**:
Eine Bewässerung, die beim Erreichen der am Wasserzähler gemessenen Zielmenge endet. Ein maximales Zeitlimit begrenzt den Vorgang unabhängig vom Messwert.

**Zeitsteuerung**:
Eine Bewässerung, die nach der festgelegten Laufzeit endet. Der Wasserzähler dokumentiert die gelieferte Menge, bestimmt aber nicht das reguläre Ende.

**Zählerausfallstrategie**:
Die zonenspezifische Festlegung, ob eine Mengensteuerung bei fehlender plausibler Zählermessung ausfällt oder ersatzweise zeitgesteuert mit geschätzter Wassermenge läuft.

**Bewässerungsfenster**:
Die zonenspezifische Menge täglicher Zeitintervalle, innerhalb derer automatische Bewässerungsvorgänge zulässig sind. Ein einzelnes Intervall darf über Mitternacht reichen.

**Automatikfreigabe**:
Die zonenspezifische Erlaubnis für automatische Bewässerungsvorgänge. Eine fehlende Automatikfreigabe verhindert keine ausdrücklich angeforderte manuelle Bewässerung.
_Avoid_: Aktiv, eingeschaltet

**Sicherheitssperre**:
Eine Sperre, die automatische und manuelle Bewässerungsvorgänge verhindert, bis ihre Ursache behoben und die Sperre zurückgesetzt wurde.
_Avoid_: Deaktiviert

**Durchflussprofil**:
Der für eine Zone erwartete normale Durchflussbereich. Er wird manuell erfasst oder durch einen wiederholbaren Kalibrierungslauf bestimmt und dient der Mengenplanung sowie der Erkennung von Abweichungen.

**Referenzverdunstung**:
Der wetterabhängig geschätzte Wasserverlust einer standardisierten Referenzfläche. Sie ist noch keinem konkreten Pflanzenbestand oder einer Zone zugeordnet.
_Avoid_: Verdunstung, Wasserbedarf

**Pflanzenverdunstung**:
Der aus Referenzverdunstung und zonenspezifischen Pflanzen- sowie Standortfaktoren abgeleitete Wasserverlust einer Zone.
_Avoid_: ET-Wert
