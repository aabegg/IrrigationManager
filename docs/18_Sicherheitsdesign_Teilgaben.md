# Sicherheitsdesign für Teilgaben und Sickerpausen

Status: Pakete 1–6 im Release Candidate implementiert. Automatisierte Release-Gates sind erfüllt; Installation sowie reale Trocken-, Hardware- und Neustarttests stehen vor der Veröffentlichung noch aus.

Geltungsbereich: Stufe 7 aus `docs/17_Neukonzept.md`

Fachliche und verbindliche Quelle: Ausschliesslich `docs/17_Neukonzept.md`. Dieses Dokument ist ein nicht normativer Implementierungsnachweis, spiegelt dessen Vorgaben und erweitert den Funktionsumfang nicht. Bei Widersprüchen gilt immer `docs/17_Neukonzept.md`.

## 1. Ziel und Nicht-Ziele

Das optionale Modul soll ein Bewässerungsziel in begrenzten Teilgaben liefern und dazwischen alle Ventile schliessen. Andere Zonen dürfen die freie Zeit nutzen, ohne den gemeinsamen Bewässerungsvorgang, sein Restziel oder seine Sicherheitsgrenzen zu verlieren.

Nicht Teil dieses Ausbaus sind:

- frei programmierbare oder von Drittanbietern geladene Teilgabenstrategien
- parallele Bewässerung mehrerer Zonen
- automatisch aus Pflanzen-, Boden- oder Ausbringungsprofilen aktivierte Teilgaben
- nachträgliche Aufteilung bereits offener Aufträge oder begonnener Vorgänge
- Änderungen am hydraulischen Sicherheitsverhalten des vorhandenen `IrrigationExecutor`

## 2. Analyse der heutigen Architektur

Der bestehende Dispatcher wählt einen `ManualIrrigationRequest`, persistiert einen `IrrigationExecutionState` und einen globalen `ActiveExecutionState`, ruft den `IrrigationExecutor` genau einmal auf und schliesst Auftrag und Ausführung danach terminal ab. Der Executor ist bereits ein tiefes Module: Sein kleines Interface kapselt exklusive Ventilbetätigung, Messung, Zeitlimit, Rückmeldung und sicheres Schliessen.

Eine Sickerpause innerhalb dieses Executors wäre ein falscher Seam. Sie würde den globalen Hardware-Checkpoint und den Dispatcher blockieren, obwohl kein Ventil geöffnet sein darf. Umgekehrt dürfen Teilgaben nicht als `ManualIrrigationRequest` in die bestehende Queue gelegt werden, weil dadurch Ziel, Abbruch, Wiederanlauf und Ergebnis des gemeinsamen Bewässerungsvorgangs auseinanderfallen würden.

Der neue Seam liegt deshalb zwischen Dispatcher und hydraulischem Executor:

```text
Bewässerungsauftrag
        |
        v
persistenter Bewässerungsvorgang -- Prozessmodul --> nächste sichere Aktion
        |                                             |
        |                                             +-- Sickerpause / Abschluss / fail-closed
        v
persistierte Teilgabe + ActiveExecutionState
        |
        v
bestehender IrrigationExecutor --> genau eine hydraulische Lieferung
```

## 3. Bewertete Designs

### A. Ein einziger Ereignis-Reducer

Ein `advance(state, event, now)` besitzt maximale Depth und Leverage und ist vollständig deterministisch testbar. Sein Risiko ist ein schwer lesbarer God Reducer, wenn Start, Recovery, Disposition und Abschluss ohne weitere Struktur in einer Funktion zusammenlaufen.

### B. Erweiterbare Strategie- und Regelmodule

Getrennte Portionierungsstrategien und Planungsregeln erleichtern spätere Varianten. Für die erste einzige Regel `fixed_cap` wären Registry, Strategieversionen und zusätzliche persistente Seams jedoch vorzeitige Abstraktion und eine grössere Wiederanlaufoberfläche.

### C. Früher Feature-Gate mit managerorientiertem Prozessmodul

Der bestehende Einmalpfad bleibt bei deaktiviertem Modul unverändert. Nur Aufträge mit aktivem Teilgabensnapshot betreten das neue Module. Das minimiert das Regressionsrisiko, kann langfristig aber zu zwei Orchestrierungspfaden führen.

### Entscheidung

Umgesetzt wird ein Hybrid aus A und C:

- ein reines, I/O-freies `IrrigationProcessModule` mit zwei Entry Points
- eine getrennte, reine Auswahlfunktion im Scheduler
- ein früher Feature-Gate, der den deaktivierten Legacy-Pfad unverändert lässt
- gemeinsame interne Persistenz-, Settlement-, Diagnose- und Safety-Primitiven für beide Pfade
- genau eine fest eingebaute `fixed_cap`-Regel ohne öffentliches Strategie-Interface

Diese Aufteilung erzielt hohe Depth für den mehrphasigen Vorgang, hohe Leverage für Start, Fortsetzung, Abbruch und Recovery sowie gute Locality der Teilgabenregeln. Home Assistant, Store und Hardware bleiben Adapter ausserhalb des reinen Kerns.

## 4. Vorgesehenes öffentliches Interface

Illustrative Python-Typen; Namen dürfen beim Implementieren nur aus technischen Gründen angepasst werden, nicht ihre Verantwortungsgrenzen:

```python
class IrrigationProcessModule:
    def start(
        self,
        order: OrderSnapshot,
        policy: PortionPolicySnapshot,
        *,
        now: datetime,
    ) -> ProcessTransition: ...

    def advance(
        self,
        process: IrrigationExecutionState,
        portions: tuple[IrrigationPortionState, ...],
        event: ProcessEvent,
        *,
        now: datetime,
    ) -> ProcessTransition: ...
```

`ProcessEvent` ist eine geschlossene Union aus:

- `PortionOpening`: unmittelbar vor einem möglichen Öffnungsbefehl persistierte Aktuierungsgrenze
- `PortionStarted`: bestätigte Ventilöffnung einer vorbereiteten Teilgabe
- `PortionSettled`: belastbares Ergebnis einer geschlossenen Teilgabe
- `ResumeDue`: Dispatcher prüft eine fällige Fortsetzung
- `CancelRequested`: Benutzer, Not-Aus oder entzogene Betriebsfreigabe
- `RecoveryObserved`: nach fail-closed Ventilschliessung rekonstruierte Fakten

`ProcessAction` ist eine geschlossene Union aus:

- `PreparePortion`: Zustand persistieren und danach eine begrenzte Teilgabe ausführen
- `WaitUntil`: keine Hardware belegen; Dispatcher zum angegebenen Zeitpunkt wecken
- `StopActivePortion`: Abbruchabsicht persistieren, laufenden Executor stoppen und erst nach seinem Schliessergebnis terminal abrechnen
- `CompleteProcess`: gemeinsamen Vorgang und Auftrag terminal abschliessen
- `CancelProcess`: einen Vorgang ohne aktive Hardware unmittelbar terminal beenden
- `FailClosed`: keine weitere Betätigung, Diagnose und gegebenenfalls Sicherheitssperre
- `NoOp`: idempotent bereits verarbeitete oder terminale Beobachtung ohne Seiteneffekt

Ein `ProcessTransition` enthält den vollständig aktualisierten Prozesszustand, neu angelegte oder aktualisierte Teilgabennachweise und genau eine Aktion. Das Module führt kein I/O aus, schläft nicht und kennt keine Home-Assistant-Entities.

Der Scheduler erhält separat:

```python
def select_dispatch_work(
    *,
    now: datetime,
    orders: Iterable[ManualIrrigationRequest],
    resumptions: Iterable[ResumeCandidate],
) -> DispatchDecision | None: ...
```

Das verhindert, dass der Prozesskern Verantwortung für konkurrierende Zonen übernimmt.

## 5. Persistentes Modell

### Bewässerungsauftrag

`ManualIrrigationRequest` bleibt der einzige Auftrag. Sein unveränderlicher Snapshot erhält optional eine `PortionPolicySnapshot` mit:

- aktiv beziehungsweise nicht vorhanden
- Steuerungsart und maximale Zielgrösse je Teilgabe
- minimale Sickerpause
- maximale Teilgabenanzahl
- maximale Gesamtlebensdauer

Ein Auftrag ohne Snapshot verwendet den Legacy-Pfad. Der bestehende anlagenweite Schalter alleine verändert keinen bereits erzeugten Auftrag.

### Bewässerungsvorgang

`IrrigationExecutionState` bleibt das einzige Aggregat und wird additiv erweitert:

- `portion_policy`: unveränderlicher Snapshot oder `None`
- `process_started_at`
- `process_deadline_at`
- `next_portion_at`
- `next_portion_sequence`
- `completed_portion_count`
- `cancellation_requested`
- bestehendes gemeinsames Ziel und Restziel
- bestehende kumulierte Liter und Ventilöffnungszeit
- Status zusätzlich `soaking`

`process_deadline_at` ist das Minimum aus dem zulässigen Ausführungsende und `process_started_at + maximum_lifetime_seconds`.

### Teilgabennachweis

`IrrigationPortionState` ist neu und enthält mindestens:

- `portion_id`, stabil aus `execution_id` und Sequenz abgeleitet
- `execution_id`, Sequenz, Steuerungsart und begrenztes Teilziel
- Status `prepared`, `watering`, `settled` oder `interrupted`
- Vorbereitung, bestätigte Öffnung und bestätigte Schliessung
- gelieferte Liter und tatsächliche Ventilöffnungszeit
- Ergebnis, Messqualität, Herkunft und Warnungen

Die Teilgaben werden als eigene Liste `irrigation_portions` im atomar gespeicherten `StoredInstallationState` geführt. Dadurch bleiben Aggregate klein und einzelne Settlements eindeutig adressierbar.

### Hardware-Checkpoint

`ActiveExecutionState` bleibt die einzige anlagenweite Hardware-Lease und erhält `portion_id` und `portion_sequence`. Er existiert nur für eine vorbereitete oder aktive hydraulische Teilgabe. Während `soaking` muss er `None` sein.

`WaterConsumptionRecord` erhält optional `portion_id`. Benutzeroberfläche und Verlauf gruppieren weiterhin über `execution_id`; `portion_id` dient der Idempotenz und Diagnose.

## 6. Zustandsautomat

```text
Auftrag pending
      |
      | start + atomarer Commit
      v
Teilgabe prepared --> watering --> settled
                              |        |
                              |        +-- Restziel = 0 ----------------> completed
                              |        |
                              |        +-- Grenze/Fehler ----------------> failed/cancelled
                              |        |
                              |        +-- Restziel > 0 --> soaking
                              |                                |
                              |                                | resume_not_before erreicht
                              |                                v
                              +-------------------------- nächste prepared

jeder Zustand ohne aktive Hardware -- CancelRequested -------> cancelled
watering -- CancelRequested --> StopActivePortion --> settled --> cancelled
jeder inkonsistente/unsichere Zustand -- RecoveryObserved ---> fail-closed
```

Der Auftrag bleibt ab dem ersten Commit bis zum terminalen Übergang `executing`. Nur der Bewässerungsvorgang wechselt zwischen `watering` und `soaking`.

## 7. Harte Invarianten

1. Ein Auftrag besitzt höchstens einen Bewässerungsvorgang.
2. Eine Teilgabe ist niemals ein Bewässerungsauftrag.
3. Ein Bewässerungsvorgang besitzt höchstens eine nicht abgewickelte Teilgabe.
4. Anlagenweit existiert höchstens ein `ActiveExecutionState` und damit höchstens eine physisch aktive Zone.
5. `soaking` impliziert bestätigte Ventilschliessung, keinen Executor-Task und keinen `ActiveExecutionState`.
6. Aggregat, Teilgabe und Hardware-Checkpoint werden vor jedem Öffnungsbefehl gemeinsam atomar gespeichert.
7. Ein Teilgabenergebnis wird anhand seiner `portion_id` höchstens einmal aggregiert und verbucht.
8. Das Restziel wird nur aus ursprünglichem Ziel und dauerhaft abgewickelten Teilgaben abgeleitet und nie negativ.
9. Eine Teilgabe überschreitet weder ihre maximale Zielgrösse noch das verbleibende Ziel.
10. Pausen zählen zur Gesamtlebensdauer, niemals zur kumulativen Lieferlaufzeit.
11. Einer mengengesteuerten Teilgabe wird höchstens das verbleibende kumulative Lieferlaufzeitbudget übergeben.
12. Keine weitere Teilgabe öffnet nach Ablauf einer Deadline, Erreichen einer Grenze, Sicherheitsverletzung oder inkonsistentem Zustand.
13. Während eines nichtterminalen Vorgangs darf kein neuer Auftrag derselben Zone beginnen.
14. Konfigurationsänderungen verändern den unveränderlichen Snapshot eines offenen oder begonnenen Vorgangs nicht.

Jede Verletzung von 3 bis 12 verhindert eine Aktorbetätigung. Eine mögliche unbekannte Wasserabgabe oder nicht bestätigte Ventilschliessung erzeugt zusätzlich eine Sicherheitssperre.

## 8. Berechnung der nächsten Teilgabe

Die erste Version verwendet ausschliesslich `fixed_cap`:

```text
portion_target = min(remaining_target, configured_maximum_portion_target)
```

Nach einer erfolgreich abgewickelten Teilgabe gilt:

```text
remaining_target = max(0, original_target - sum(settled_delivered_target))
```

Für Zeitsteuerung ist `settled_delivered_target` die bestätigte Ventilöffnungszeit. Für Mengensteuerung ist es die belastbar gemessene Wassermenge. Ein vom Executor gemeldetes nicht erreichtes Mengenziel ist kein normaler Teilfortschritt, sondern beendet den Vorgang nach den bestehenden Sicherheitsregeln.

Vor `PreparePortion` wird der gesamte verbleibende Tail erneut geprüft:

- benötigte Teilgaben `ceil(remaining_target / maximum_portion_target)`
- bereits verwendete plus benötigte Teilgaben höchstens `maximum_portions`
- alle noch notwendigen Mindestpausen
- verbleibende Lieferzeit und Ventil-/Rückmeldebudgets
- `process_deadline_at` und automatisches Bewässerungsfenster

Ist der Tail nicht vollständig zulässig, wird keine vergrösserte oder vermeintlich letzte Teilgabe erzeugt. Der Vorgang endet mit einem eindeutigen Fehlergrund.

## 9. Sichere Disposition während Pausen

Ein pausierender Vorgang liefert einen `ResumeCandidate` mit:

- `earliest_start = next_portion_at`
- `latest_safe_start`, rückwärts aus Deadline und konservativem Rest-Tail berechnet
- Zone, Vorgang und nächste begrenzte Teilgabe

Andere Zonen dürfen nur als Lückenfüller beginnen, wenn ihre konservative maximale Belegungsdauer spätestens zu `latest_safe_start` endet. Für Dauersteuerung wird die vollständige Laufzeit angesetzt, für Mengensteuerung das harte Zeitlimit; hinzu kommen alle Ventil- und Rückmeldebudgets. Ein Auftrag derselben Zone ist ausgeschlossen.

Die Auswahl erfolgt in zwei Schritten:

1. Sicherheitsfilter: entferne jeden Kandidaten, der Freigaben, Deadlines, Exklusivität oder einen reservierten Rest-Tail verletzt.
2. Bestehendes Ranking: manuell FIFO vor automatisch nach Fensterende. Eine Fortsetzung wird erzwungen, sobald jeder andere Kandidat ihren `latest_safe_start` verletzen würde.

Ein Kandidat, der nur nach einer optimistischen Durchflussschätzung passen würde, gilt nicht als passend. Falls keine sichere Arbeit existiert, wartet der Dispatcher ohne Busy-Loop bis zum nächsten relevanten Zeitpunkt.

## 10. Atomare Übergänge und Idempotenz

Vor einer Teilgabe wird in einem Store-Commit gespeichert:

- Vorgang `watering`
- neue Teilgabe `prepared`
- globaler `ActiveExecutionState` mit `portion_id`

Erst nach erfolgreichem Commit wird der bestehende Executor als Hardware-Adapter aufgerufen. Seine Öffnungs- und Schliesscallbacks aktualisieren Active-, Teilgaben- und Aggregatzeitpunkte gemeinsam.

Nach bestätigter Schliessung wird in einem weiteren Commit gespeichert:

- Teilgabe `settled` mit Ergebnis
- kumulierte Werte und Restziel des Vorgangs
- Verbrauchsnachweis mit `portion_id`
- entweder Vorgang `soaking`, terminaler Vorgang oder Sicherheitssperre
- `active_execution=None`

Ein erneut zugestelltes Ergebnis einer bereits `settled` Teilgabe ist ein idempotenter No-op. Ein anderes Ergebnis für dieselbe ID ist eine Inkonsistenz und öffnet keine weitere Teilgabe.

Ein Abbruch während `prepared` oder `watering` setzt zuerst `cancellation_requested` im persistenten Vorgang und liefert `StopActivePortion`. Der Manager bricht danach den Executor ab; dessen garantiertes Schliessen und belastbares Ergebnis werden als `PortionSettled` an das Module zurückgegeben. Erst dieser Übergang setzt Vorgang und Auftrag terminal. So kann ein Stop weder die Ventilschliessung noch die Zuordnung bereits gelieferter Wassermenge überspringen.

## 11. Wiederanlaufmatrix

Vor der Auswertung eines gespeicherten Zustands schliesst die Integration alle verwalteten Ventile und bestätigt die Schliessung.

| Persistenter Zustand | Belastbare Evidenz | Entscheidung |
|---|---|---|
| `soaking`, kein Active-Checkpoint | Pause und Deadline gültig | Bis `next_portion_at` warten oder fällige Fortsetzung disponieren |
| `prepared`, kein Öffnungsversuch gespeichert | Ventile bestätigt geschlossen | Teilgabe wieder disponierbar machen |
| Öffnungsversuch, aber keine bestätigte Öffnung | Zählerdifferenz beweist keine Lieferung | Teilgabe kontrolliert wieder disponieren; ohne belastbare Evidenz fail-closed |
| `watering` | Gültige Öffnungszeit und bestätigte Recovery-Schliessung für Zeitsteuerung oder belastbare Zählerdifferenz für Mengensteuerung | Lieferung genau einmal settlen; bei Restziel frühestens nach Mindestpause fortsetzen |
| bestätigte Schliessung, Settlement fehlt | Zeit-/Zählerdaten vollständig | Bestehende `portion_id` genau einmal settlen |
| widersprüchliche Zeitpunkte, fehlende Messbasis oder unbestätigte Schliessung | Lieferung möglicherweise unbekannt | Vorgang fail-closed beenden, Sicherheitssperre und Diagnose |
| terminaler Vorgang mit Active-Checkpoint | Persistenz widersprüchlich | Keine Betätigung, Sicherheitssperre und Diagnose |
| Legacy-Vorgang ohne Teilgabensnapshot | beliebig | Bestehende Legacy-Recovery unverändert verwenden |

Der Recovery-Adapter erzeugt nur Fakten. Die Entscheidung über Fortsetzung oder fail-closed trifft dasselbe reine Prozessmodul wie im Normalbetrieb.

## 12. Abbruch- und Fehlersemantik

- `prepared` oder `watering`: Abbruchabsicht persistieren, Executor abbrechen, Ventile schliessen, bekannte Lieferung settlen, gesamten Vorgang terminal setzen.
- `soaking`: ohne Hardwareaktion gesamten Vorgang terminal setzen.
- Not-Aus: vor jeder weiteren Aktion dauerhaft setzen, aktive Hardware schliessen, gesamten Vorgang beenden.
- Anlagen- oder Zonenbetriebsfreigabe entzogen: gesamten betroffenen Vorgang beenden, auch wenn er nur pausiert.
- Automatikfreigabe entzogen: bestehende Semantik des gewählten `stop_active` bleibt erhalten; ohne Stop läuft der unveränderliche Vorgang weiter.
- Sicherheitsverletzung oder nicht erreichtes Mengenziel einer Teilgabe: gesamter Vorgang `failed`, bestehende Sicherheitssperre anwenden.
- Ablauf von `process_deadline_at`, Lieferlaufzeit oder Teilgabenmaximum: keine weitere Öffnung; eindeutiges terminales Ergebnis und Diagnose.

## 13. Migration und Feature-Gate

Die Storage-Minor-Version und bei Einführung der neuen Konfigurationsfelder die Config-Entry-Minor-Version werden additiv erhöht. Fehlende Felder werden wie folgt interpretiert:

- `portion_policy=None`
- `irrigation_portions=[]`
- `portion_id=None` im `ActiveExecutionState` und `WaterConsumptionRecord`
- kein Status `soaking`

Bestehende Aufträge, Ausführungen und Verbrauchseinträge werden nicht umgedeutet. Ein beim Upgrade aktiver Legacy-Vorgang verwendet die heutige konservative Restartbehandlung. Die Konfiguration wird additiv erweitert; Modul- und Zonennutzung sind standardmässig `False`, gespeicherte Detailwerte bleiben beim Deaktivieren erhalten.

Der Dispatcher besitzt für den ersten Release einen frühen Gate:

```text
kein Auftrag/Vorgang mit aktivem Teilgabensnapshot
    -> vorhandener select -> prepare -> execute -> finish Pfad

aktiver Teilgabensnapshot oder fortzusetzender Vorgang vorhanden
    -> neuer ProcessTransition-/DispatchDecision-Pfad
```

Settlement, Wasserhistorie, Diagnose, Sicherheitssperre und atomare Store-Helfer werden vor Aktivierung des neuen Pfads in gemeinsame interne Primitiven extrahiert. Dadurch bleibt nur die äussere Orchestrierung getrennt.

Der UI-Schalter wird erst sichtbar beziehungsweise aktivierbar, wenn alle Release-Gates aus Abschnitt 16 erfüllt sind.

## 14. Diagnose und Benutzeroberfläche

Zusätzliche persistente Diagnosegründe:

- `soak_pause`
- `portion_ready`
- `portion_limit_reached`
- `process_lifetime_exceeded`
- `process_deadline_exceeded`
- `portion_state_inconsistent`
- `portion_recovery_unsafe`

Der Ausführungsstatus unterscheidet mindestens `watering`, `soaking` und `idle`; Betriebs-, Automatik-, Not-Aus- und Sicherheitssperrenstatus bleiben wie bisher getrennte Zustandsdimensionen. Während `soaking` werden Vorgang, Zone, Restziel, `next_portion_at`, aktuelle und maximale Teilgabennummer sowie `latest_safe_start` gezeigt. Auftragstabelle und Verlauf bleiben je Bewässerungsvorgang aggregiert; Teilgaben erscheinen nur als aufklappbare Details oder Diagnosefelder.

Logs enthalten stabile `request_id`, `execution_id` und gegebenenfalls `portion_id`, aber keine unbeschränkten Rohmessreihen. Jede Zustandsänderung und jeder fail-closed Grund ist in den bestehenden Dispatcher-Diagnosen nachvollziehbar.

## 15. Implementierbare vertikale Arbeitspakete

### Paket 1: Reiner Prozesskern, noch nicht aktivierbar

- `portioning.py` mit Snapshots, Ereignissen, Aktionen, `start` und `advance`
- Tabellen- und Property-Tests aller Invarianten
- keine Manager-, Store-, Config- oder UI-Verhaltensänderung

### Paket 2: Additive Persistenz und gemeinsame Primitiven

- `IrrigationPortionState` und additive Felder
- Storage-Minor-Migration und Roundtrip-Tests
- gemeinsame atomare Prepare-/Settlement-/Safety-Helfer extrahieren
- Golden-Trace für unveränderten Legacy-Pfad

### Paket 3: Dispatcher und hydraulischer Adapter hinter verborgenem Gate

- `ResumeCandidate` und `select_dispatch_work`
- Manager interpretiert `ProcessTransition`
- bestehender Executor führt genau eine Teilgabe aus
- Gate bleibt in Produktion deaktiviert
- Konkurrenz-, Deadline-, Abbruch- und Fault-Injection-Tests

### Paket 4: Wiederanlauf und Diagnose

- fail-closed Recovery-Adapter und Wiederanlaufmatrix
- idempotentes Settlement
- Diagnosegründe und Statusprojektion
- Neustarttests an jeder persistenten Grenze

Implementierungsnachweis: Beim Start schliesst und bestätigt der Adapter alle konfigurierten sowie im Active-Checkpoint gespeicherten Ventile, bevor er Fakten als `RecoveryObserved` an das reine Prozessmodul übergibt. Sichere Sickerpausen und nachweislich trockene vorbereitete Teilgaben bleiben disponierbar; bekannte Zeit- oder Mengenlieferungen werden über denselben atomaren Settlement-Helfer genau einmal verbucht. Unbestätigte Schliessung, unbekannte Lieferung und widersprüchliche Checkpoints beenden den Vorgang fail-closed. Persistente Diagnosegründe sowie die Statusprojektion `watering`/`soaking` mit Restziel, Fortsetzungszeitpunkt, Teilgabennummern und `latest_safe_start` sind implementiert. Lifecycle-Tests decken `prepared`, Öffnungsversuch, `watering`, bestätigte Schliessung, Settlement, `soaking`, unbestätigte Schliessung und terminale Widersprüche für Zeit- und Mengensteuerung ab; der Legacy-Recovery-Pfad bleibt ohne Teilgabensnapshot unverändert.

### Paket 5: Konfiguration und read-only UI

- anlagenweite Verfügbarkeit und zonenspezifische Verwendung
- bedingte, validierte Detailfelder ohne automatische Aktivierung
- Status und Verlauf zeigen Teilgaben aggregiert
- bestehende Anlagen migrieren mit beiden Schaltern `False`

Implementierungsnachweis: Die bestehende anlagenweite Konfiguration `soak_module_enabled` macht das Modul lediglich verfügbar; `use_soak_module` aktiviert seine Verwendung ausdrücklich je Zone. Der Zonen-Wizard sammelt alle verfügbaren Modulverwendungen kompakt in einem Schritt, danach nur die gewählten Moduldetails und erst anschliessend den Wochenplan. Die vier Teilgabengrenzwerte werden über native Home-Assistant-Selektoren erfasst, gemeinsam validiert und beim Deaktivieren nicht gelöscht. Migration und Neuanlage setzen beide Opt-ins standardmässig auf `False`. Erst eine vom Release-Gate freigegebene und doppelt bestätigte Konfiguration darf einen unveränderlichen `PortionPolicySnapshot` für einen neuen Auftrag erzeugen; bereits angenommene Aufträge bleiben unverändert. Dieselbe reine Machbarkeitsprüfung reserviert vor manueller Auftragsannahme und automatischer Planung Ziel, Mindestpausen und konservative hydraulische Budgets innerhalb Teilgabenanzahl, Lebensdauer und Ausführungsfenster. Unmögliche manuelle Aufträge werden vor dem Speichern abgelehnt, automatische Kandidaten mit einem stabilen Planungsgrund ausgewiesen. Status und Verlauf zeigen den gemeinsamen Bewässerungsvorgang weiterhin genau einmal und stellen aktuelle beziehungsweise abgewickelte Teilgaben nur als untergeordnete read-only Details dar.

### Paket 6: Kontrollierte Aktivierung und Release

- Feature-Gate für Testanlage aktivieren
- komplette HA-Integrationstests und reale Trocken-/Kurztests
- UI-Schalter erst nach bestandenen Gates freigeben
- Release Candidate ohne automatische Aktivierung bestehender Zonen

Implementierungsnachweis: `PARTIAL_IRRIGATION_RELEASED` ist das einzige codebasierte Release-Gate für neue Teilgabensnapshots und die zugehörigen Home-Assistant-Konfigurationsschritte. Der Release Candidate schaltet es frei, während Anlagen- und Zonen-Opt-in bei Migration und Neuanlage weiterhin `False` bleiben. Die Minor-Migration auf Version 9 setzt beide Opt-ins auch für bereits mit einem Vorabstand gespeicherte Konfigurationen erneut auf `False`, erhält aber alle Detailwerte; dadurch ist nach dem Release eine bewusste neue Doppelaktivierung erforderlich. Ein Rollback des Release-Gates blendet die UI-Schritte aus und leitet neue Aufträge über den unveränderten Legacy-Pfad, ohne gespeicherte Opt-ins oder Detailwerte zu löschen. Bereits angenommene Aufträge und begonnene Vorgänge mit Teilgabensnapshot bleiben unabhängig vom aktuellen Release-Gate disponierbar, abbrechbar und wiederherstellbar; damit kann ein Rollback keinen persistenten Vorgang stranden. Die automatisierte HA-Matrix deckt Kernzustände, Store-Commit vor Executor-Aufruf, Fault Injection, Recovery-Grenzen, Abbruchphasen, Lückenplanung, Busy-Loop-Schutz, Golden-Trace, Migration, Aggregation und Gate-Rollback ab.

Noch nicht als bestanden markiert werden die umgebungsabhängigen Freigaben: Installation des Candidates, Test ohne Ventilöffnung, beaufsichtigter kurzer Hardwaretest, echter Neustart während einer Sickerpause sowie die anschliessende Prüfung von Home-Assistant-Protokoll und Systemdiagnose. Diese Schritte erfolgen erst im ausdrücklich gestarteten Release-/Installationstest.

Die Pakete werden in dieser Reihenfolge integriert und jeder Release-Schritt bleibt durch den frühen Feature-Gate zurückrollbar. Bis Paket 6 aktiviert kein Paket das Teilgabenverhalten für bestehende Anlagen.

## 16. Prüf- und Release-Nachweise

Die nachfolgenden Nachweise konkretisieren die verbindlichen Abnahmekriterien aus `docs/17_Neukonzept.md`; sie sind keine eigenständige fachliche Quelle.

### Reiner Kern

- jeder erlaubte und verbotene Zustandsübergang tabellarisch getestet
- Zeit- und Mengenziel exakt und nicht exakt durch Teilgrösse teilbar
- maximale Teilgabenanzahl, Lieferlaufzeit und Lebensdauer an beiden Grenzseiten
- doppeltes Settlement ist No-op; widersprüchliches Settlement ist fail-closed
- Property-Tests: monotones Restziel, monotone Sequenz, nie mehr als eine offene Teilgabe

### Manager und Store

- nachweisbarer Store-Commit vor jedem Executor-Aufruf
- Fault Injection vor/nach Commit, Öffnung, bestätigter Öffnung, Schliessung und Settlement
- Restart in `prepared`, `watering`, nach Schliessung und in `soaking`
- Stop, Not-Aus, Anlagen- und Zonendeaktivierung in jeder Phase
- Safety-Verletzung einer Teilgabe beendet den ganzen Vorgang
- kumulative Liter und Laufzeit entsprechen der Summe genau einmal verbuchter Teilgaben

### Dispatcher und Planung

- eine andere Zone passt sicher in die Pause und wird ausgeführt
- ein zu langer Auftrag wird nicht als Lückenfüller begonnen
- kein zweiter Vorgang derselben Zone während der Pause
- mehrere pausierende Vorgänge verletzen keine späteste sichere Fortsetzung
- automatischer Gesamtvorgang passt vollständig in sein Fenster
- kein Busy-Loop bei Pause oder nicht passender Arbeit

### Regression und Migration

- Golden-Trace: deaktiviertes Modul erzeugt dieselben Auswahl-, Store-, Executor- und Ergebnisfolgen wie der Stand vor Stufe 7
- bestehende Konfiguration migriert deaktiviert und ohne Datenverlust
- aktiver Legacy-Vorgang wird nicht aufgeteilt
- Moduländerung beeinflusst offene manuelle und aktive Vorgänge nicht
- Auftragstabelle, Verlauf, Wasserverbrauch und Wasserbilanz bleiben aggregiert und idempotent

### Freigabe

- vollständige Unit-, Type-, Lint- und HA-Integrationstest-Suite erfolgreich
- kontrollierter Test ohne Ventilöffnung und beaufsichtigter Kurztest mit echter Hardware erfolgreich
- Neustarttest während echter Sickerpause erfolgreich
- keine neuen Warnungen oder Exceptions in Home-Assistant-Protokoll und Systemdiagnose
- Rollback auf Legacy-Pfad ohne Storage-Verlust geprüft

## 17. Vorbereitete Dateizuordnung

| Datei | Vorgesehene Änderung |
|---|---|
| `custom_components/irrigation_manager/portioning.py` | reines tiefes Prozessmodul |
| `models.py` | Snapshots, Teilgabennachweis und additive Aggregatfelder |
| `scheduler.py` | sichere Auswahl von Aufträgen und Fortsetzungen |
| `manager.py` | Adapter, Feature-Gate und Interpretation persistierter Übergänge |
| `storage.py` | additive Minor-Migration |
| `const.py` | zonenspezifische Verwendung und vier Grenzwerte |
| `config_flow.py` | bedingte, validierte Teilgabenkonfiguration |
| `diagnostics.py` | Prozess-, Teilgaben- und Recovery-Evidenz |
| Frontend-Quellen | aggregierter Status und Teilgabendetails |
| `tests/test_portioning.py` | öffentliche Testfläche des reinen Modules |
| Scheduler-/Manager-/Storage-Tests | Adapter, Migration, Konkurrenz und Fault Injection |

Damit sind fachliche Entscheidungen, Module-Seam, persistente Zustände, Migration, Recovery, Sicherheitsinvarianten und Release-Gates vor Beginn der Laufzeitimplementation festgelegt.
