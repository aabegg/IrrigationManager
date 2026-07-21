# Scheduler

## Grundregel

Der Scheduler erzeugt Bewässerungsaufträge, schaltet aber keine Ventile. Pro Bewässerungsanlage darf der Executor immer nur eine Teilgabe gleichzeitig ausführen. Weitere Bewässerungsvorgänge dürfen ausschließlich während ihrer Sickerpause offen warten.

## Planungsablauf

1. finale und vorläufige Wasserbilanzen aktualisieren
2. archivierte, nicht automatisch freigegebene und gesperrte Zonen ausschließen
3. externe Freigaben, Wettersperren, Budgets und Datenqualität prüfen
4. minimales und maximales Intervall je Zone auswerten
5. aktuelle und optional vorausschauende Ziele bestimmen
6. Mindestbewässerung als Maximum aus Bedarf und Mindestziel anwenden
7. Ziel durch Maximalgabe, Laufzeit und Budget begrenzen
8. Teilgaben und notwendige Sickerpausen bilden
9. passende Bewässerungsfenster suchen
10. Aufträge priorisieren und erwartete Startzeiten vergeben
11. schreibgeschützten Kalender und Vorschau aktualisieren

## Rhythmus

Eine Zone besitzt einen minimalen und maximalen Abstand zwischen wirksamen Bewässerungen.

- Vor Ablauf des Mindestabstands wird kein automatischer Auftrag erzeugt.
- Innerhalb des Intervalls entscheidet der Bedarf über den günstigsten Termin.
- Bei Bedarfsbewässerung kann auch der maximale Abstand ohne Lauf verstreichen, wenn kein Bedarf besteht.
- Bei Mindestbewässerung wird spätestens am maximalen Abstand mindestens das Mindestziel fällig.
- Nur eine gelieferte, zonenspezifisch konfigurierbare wirksame Mindestmenge setzt das Intervall zurück.

## Bewässerungsfenster

- mehrere Fenster pro Zone und Tag
- Standardfenster plus optionale Abweichungen je Wochentag
- feste Uhrzeit oder Sonnenaufgang/-untergang mit Offset
- Fenster über Mitternacht
- mindestens eine wirksame Teilgabe muss vor Ende hineinpassen
- ist das vollständige Ziel zu groß, wird planmäßig eine verkleinerte Teilgabe bis zum Fensterende erzeugt
- passt nicht einmal die wirksame Mindestteilgabe, startet die Zone nicht
- Fensterende beendet einen unerwartet längeren Vorgang hart
- Restbedarf bleibt für eine spätere Gelegenheit erhalten

## Priorisierung

Automatische Aufträge werden lexikografisch priorisiert:

1. frühestes drohendes Fensterende
2. höchste relative Bedürftigkeit beziehungsweise Ausschöpfung
3. konfigurierte Zonenpriorität
4. stabiler Tie-Breaker für reproduzierbare Pläne

Manuelle Aufträge erhalten Vorrang vor noch nicht gestarteten automatischen Aufträgen. Ein aktiver Vorgang wird dafür nicht abgebrochen.

## Manuelle Aufträge

- sofort oder einmalig terminiert
- einzelne Zone oder sortierbarer Mehrzonenplan
- Ziel als Menge oder Laufzeit
- außerhalb automatischer Fenster zulässig
- bis zum Beginn stornierbar
- persistiert über Neustarts
- nach Neustart vollständig neu validiert
- verfällt nach konfigurierbarer Ablaufzeit

Automatische Aufträge verfallen am Ende ihrer Bewässerungsgelegenheit oder werden bei einer Neuberechnung ersetzt. Eine einmalig übersprungene Gelegenheit wird separat persistiert, damit ein Neustart sie nicht erneut erzeugt.

Existieren ein manueller und automatischer Auftrag derselben Zone, bleiben beide getrennt. Nach dem manuellen Vorgang berechnet der Scheduler den automatischen Bedarf neu und verwirft oder reduziert den automatischen Auftrag entsprechend.

## Teilgaben

Ein Vorgang kann in mehrere Teilgaben aufgeteilt werden:

- maximale Menge oder Dauer je Teilgabe
- definierte Sickerpause
- Haupt- und Zonenventil während der Pause geschlossen
- andere Zonen dürfen die Pause nutzen
- der pausierende Vorgang bleibt fachlich offen, gibt aber keine Hardware-Ressource belegt
- verbleibende Teilgaben konkurrieren danach erneut anhand Fensterende und Priorität
- kumulierte Wasserabgabezeit und gesamte Vorgangsdauer besitzen getrennte Grenzen
- überschreitet die Vorgangsdauer ihre Frist, wird der Restbedarf neu geplant

## Prognosen

- Regenprognosen verändern keine persistente Wasserbilanz.
- Ein Auftrag darf nur bei ausreichender erwarteter wirksamer Menge und Wahrscheinlichkeit verschoben werden.
- Der maximale Prognoseaufschub ist je Zone begrenzt.
- Vorausschauende Zielmengen bis zur nächsten möglichen Bewässerung sind je Zone optional.
- Prognosebeiträge bleiben getrennt von gemessenen Daten sichtbar.
- Regenprognosen reduzieren weder persistentes Defizit noch aktuelles Zielvolumen.

## Budgets

- optionale Tages- und Wochenbudgets für Anlage und Zonen
- automatische Ziele werden begrenzt oder verschoben
- Restbedarf wird nicht verworfen
- manuelle Aufträge dürfen nach sichtbarer Warnung überschreiten

## Überspringen und Stoppen

- Auftrag löschen allein erlaubt eine sofortige Neuberechnung.
- „Einmal überspringen“ unterdrückt dieselbe Gelegenheit bis zum nächsten zulässigen Termin.
- Stop beendet den gezielt ausgewählten Vorgang unabhängig davon, ob seine Teilgabe aktiv ist oder er in einer Sickerpause wartet; Restbedarf bleibt planbar.
- Stop+Überspringen beendet den ausgewählten Vorgang und unterdrückt seine aktuelle Gelegenheit.
- Globaler Stop finalisiert alle offenen Vorgänge einschließlich Sickerpausen und storniert wartende Aufträge.
- Not-Aus tut dasselbe und setzt zusätzlich eine persistente Sicherheitssperre.

## Konfigurationsänderungen

Änderungen an Ventilen, Zielen, Profilen, Fenstern und Sicherheitsgrenzen werden während offener Vorgänge nur vorgemerkt. Nach sicherem Leerlauf werden sie atomar aktiviert und alle automatischen Aufträge neu berechnet.

## Trockenlauf

Ein Trockenlauf führt denselben Planungsweg ohne Aktorzugriffe aus und zeigt:

- einbezogene und ausgeschlossene Zonen
- Bedarf und Zielberechnung
- Wettersperren und Prognosewirkung
- Budgets und Begrenzungen
- Reihenfolge und erwartete Zeiten
- Gründe für Verschiebung oder Überspringen
