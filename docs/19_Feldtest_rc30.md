# Feldtest- und Freigabeprotokoll für v0.1.0-rc30

Status: Restart-Nachweis mit Zone 2 bestanden; produktionsnaher Mehrwochen-Feldtest
vorbereitet, aber noch nicht abgeschlossen

Dieses Dokument ist ein nicht normativer Qualifikationsnachweis. Fachlich verbindlich
bleibt ausschließlich `docs/17_Neukonzept.md`.

## Release und Testumgebung

- Release: `v0.1.0-rc30`
- Commit: `458b390c16a2c14e6d52332f031617d94b929d38`
- Testdatum: 30. Juli 2026, Zeitzone Europe/Zurich
- Home Assistant: Core 2026.7.4 auf Home Assistant OS 18.1
- Config Entry: `Gartenbewässerung`
- reale Testzone: Zone 2 `Rasen`
- Backup vor Installation: `Before_IrrigationManager_v0.1.0-rc30`, ID `8cb23a19`

Backend-, Frontend-, HACS/Hassfest- und Release-Workflows des veröffentlichten Candidates
waren erfolgreich. Die Installation wurde danach auf der Referenzanlage geprüft.

## Ausgeführter Restart-Test

1. Anlage und Zone blieben zunächst ohne Betriebsfreigabe; der Trockenlauf öffnete kein
   Ventil.
2. Ein zusammenhängender manueller 10-Sekunden-Lauf öffnete und schloss `Rasen`
   erwartungsgemäss. Er lieferte 10,0 Sekunden und gemessene 7,00 Liter.
3. Für den Restart-Test wurden vorübergehend maximal 5 Sekunden pro Teilgabe, mindestens
   20 Sekunden Sickerpause, höchstens 3 Teilgaben und 180 Sekunden Gesamtlebensdauer
   gesetzt.
4. Der manuelle Auftrag `3d48047a867e48da815672f7b26992da` erzeugte den Vorgang
   `af2dce5a5fd04d889c89cef252768a3f`.
5. Die erste Teilgabe lieferte 5,0 Sekunden und 4,00 Liter. Während des persistenten
   Zustands `soaking` wurde Home Assistant neu gestartet.
6. Nach dem Neustart wurde die zweite Teilgabe genau einmal ausgeführt. Sie lieferte
   5,0 Sekunden und 3,00 Liter.
7. Der gemeinsame Vorgang endete mit 10,0 Sekunden, 7,00 Litern, zwei abgewickelten
   Teilgaben und `target_reached`. Die physische Betätigung wurde vor Ort bestätigt.

## Sicherheits- und Diagnosenachweis

- Anlagenstatus und Zonenstatus kehrten in einen inaktiven Zustand zurück.
- Der Dispatcher enthielt keinen `last_error` und keinen aktiven Vorgang.
- Anlagen-Sicherheitssperre und Not-Aus blieben aus.
- Der unzugeordnete Wasserverbrauch blieb bei 0,00 Litern.
- Home Assistants Konfigurationsprüfung war gültig; Repairs enthielt keine Probleme.
- Der Verlauf enthält einen gemeinsamen Vorgang mit genau zwei untergeordneten
  Teilgabennachweisen; Dauer und Wassermenge wurden genau einmal aggregiert.
- Nach dem Test wurden Anlagen- und Zonenbetriebsfreigabe deaktiviert. Anlagenweite
  Verfügbarkeit und zonenspezifische Verwendung des Sickerpausenmoduls wurden wieder
  deaktiviert; die Detailwerte blieben entsprechend dem Modulvertrag erhalten.

## Dokumentierte Protokollabweichung

Die 5-Sekunden-Grenze war ausschließlich für den kurzen Restart-Test bestimmt. Sie konnte
das reguläre Rasen-Ziel von 2700 Sekunden mit maximal drei Teilgaben nicht erfüllen.
Unmittelbar nach dem Neustart protokollierte die automatische Planung deshalb für dreizehn
zukünftige Tagesfenster `partial_irrigation_portion_limit_exceeded`. Das war eine korrekte
Ablehnung einer unmöglichen Planung, keine Recovery-Exception. Nach der Rückstellung
entstanden keine weiteren IrrigationManager-Warnungen.

Da das Freigabekriterium in `docs/18_Sicherheitsdesign_Teilgaben.md` streng keine neuen
Warnungen verlangt, gilt es erst nach einem erneuten Lauf mit produktionsnahen, vollständig
machbaren Grenzen als bestanden.

## Produktionsnahe Startkonfiguration für Rasen

Die erste Feldtestkonfiguration bleibt ausdrücklich ein sicherer technischer Startwert und
keine agronomisch validierte Empfehlung:

| Einstellung | Startwert | Begründung |
| --- | ---: | --- |
| Maximale Teilgabengrösse | 15 Minuten / 900 Sekunden | teilt das Tagesziel von 45 Minuten in drei gleich grosse, begrenzte Läufe |
| Minimale Sickerpause | 5 Minuten / 300 Sekunden | schafft eine hydraulikfreie Beobachtungspause zwischen den Läufen |
| Maximale Anzahl Teilgaben | 3 | entspricht exakt dem vollständigen Tagesziel |
| Maximale Gesamtlebensdauer | 2 Stunden / 7200 Sekunden | begrenzt den Vorgang auf das bestehende Fenster 06:00–08:00 Uhr |

Mit konservativ angenommenen 10 Sekunden hydraulischem Overhead je Teilgabe belegt der
vollständige Vorgang höchstens 3330 Sekunden beziehungsweise 55 Minuten 30 Sekunden. Im
zweistündigen Fenster verbleiben damit 64 Minuten 30 Sekunden Reserve. Ein Auftrag wird
vor der Persistenz dennoch erneut gegen das zu diesem Zeitpunkt gültige Fenster geprüft.

Das Pflanzen-, Boden- und Ausbringungsverhalten ist noch nicht fachlich kalibriert. Bei
sichtbarem Oberflächenwasser, Abfluss oder ungleichmässiger Aufnahme wird nicht die
Gesamtlebensdauer vergrössert, sondern die Teilgabengrösse reduziert und die Pause unter
erneuter Machbarkeitsprüfung angepasst.

## Stufenplan des privaten Feldtests

### Stufe A: Konfiguration ohne Ventilfreigabe

- Sickerpausenmodul anlagenweit verfügbar machen und nur für `Rasen` verwenden.
- Die vier produktionsnahen Startwerte speichern.
- Anlagen- und Zonenbetrieb sowie beide Automatikfreigaben ausgeschaltet lassen.
- Diagnose, geplante Aufträge und Protokolle auf Warnungsfreiheit prüfen.

Ergebnis am 30. Juli 2026: bestanden. Das Modul ist anlagenweit verfügbar und nur für
`Rasen` aktiviert. Die Werte 900 / 300 / 3 / 7200 Sekunden sind persistent gespeichert.
Anlagen- und Zonenbetrieb sowie Anlagen- und Zonenautomatik bleiben ausgeschaltet. Es
existiert kein offener Auftrag, kein aktiver Vorgang, keine Sicherheitssperre, kein
Not-Aus, kein unzugeordneter Verbrauch und keine Repair-Meldung. Die Integration ist
geladen, `last_error` ist leer und seit der produktionsnahen Konfiguration entstand keine
neue IrrigationManager-Warnung. Die älteren Warnungen des kurzen 5-Sekunden-Tests bleiben
als historische Protokollevidenz erhalten.

### Stufe B: Erster beaufsichtigter Produktionslauf Rasen

- Vor Ort stromlose Ventilstellung, Hauptventil und Zonenventil prüfen.
- Anlage und Zone erst unmittelbar vor dem Lauf freigeben.
- Einen vollständigen 45-Minuten-Auftrag mit drei Teilgaben beaufsichtigen.
- Für jede Teilgabe Öffnung, Schliessung, Wasseraufnahme, Abfluss, gemessene Liter und
  Zeitstempel protokollieren.
- Danach Betriebsfreigaben wieder ausschalten und Verlauf, Diagnose, Repairs und Logs
  prüfen. Neue Warnungen oder Exceptions stoppen die Feldfreigabe.

### Stufe C: Rasen über mindestens sieben aufeinanderfolgende Gelegenheiten

- Automatik erst nach bestandenem Stufe-B-Lauf bewusst aktivieren.
- Jede Gelegenheit auf vollständiges Ziel, genau drei Teilgaben, Sickerpausen,
  Messkontinuität und Warnungsfreiheit prüfen.
- Mindestens einen kontrollierten HA-Neustart in einer Sickerpause wiederholen.
- Grenzwerte nur anhand dokumentierter realer Beobachtungen ändern.

### Stufe D: Weitere Zonen einzeln anbinden

- Jeweils nur eine zusätzliche Zone freigeben und zunächst einen beaufsichtigten Lauf
  durchführen.
- Teilgaben bleiben je Zone deaktiviert, solange kein fachlicher Bedarf und keine
  passende, vollständig machbare Konfiguration bestätigt wurden.
- Kleine Mengen von Pflanztöpfen und Hochbeet besonders gegen Zählerauflösung und
  Messlatenz prüfen.
- Erst nach erfolgreicher Einzelprüfung dürfen zwei Zonen gemeinsam die Lückenplanung
  während einer Sickerpause erproben.

### Stufe E: Mehrwochen- und Release-Abschluss

- Alle sechs Zonen mehrere Wochen beaufsichtigt betreiben.
- Ventil-, Relais-, Zähler-, Durchfluss-, Impuls-, Nachlauf- und Messlatenznachweise
  abschliessen.
- Unabhängigen Hardware-Abschalttimer installieren und unter Last prüfen.
- Karten und Editoren auf unterstütztem Mobil- und Desktop-Browser visuell abnehmen.
- Eine gemeinsame Zeitachse aus Planung, Ausführung, Wetter, Messung und Fehlerereignissen
  auswerten.
- Erst danach `v0.1.0` als stabiles Release freigeben.

## Abbruchkriterien

Der Feldtest wird sofort angehalten und die Betriebsfreigabe entzogen, wenn mindestens
eines der folgenden Ereignisse eintritt:

- ein Ventil schliesst nicht sicher oder eine Rückmeldung widerspricht dem sichtbaren
  Zustand;
- zwei Zonen sind gleichzeitig hydraulisch aktiv;
- Not-Aus, Sicherheitssperre, unbekannte Lieferung oder unzugeordneter Verbrauch tritt
  ohne erklärten Testgrund auf;
- Laufzeit, Wassermenge, Teilgabenanzahl oder Gesamtlebensdauer wird überschritten;
- ein Vorgang wird nach Neustart doppelt ausgeführt oder verliert sein Restziel;
- Home Assistant oder IrrigationManager erzeugt eine neue unerwartete Warnung,
  Exception, Repair-Meldung oder einen wiederholten Fehlerlauf.

Ein abgebrochener Feldtest wird nicht durch Zurücksetzen einer Sicherheitssperre
fortgesetzt. Ursache, gespeicherter Vorgang, Diagnose und physischer Zustand werden zuerst
geprüft und dokumentiert.
