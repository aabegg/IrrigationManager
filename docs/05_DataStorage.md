# Datenhaltung

## Ziele

- Konfiguration dauerhaft und versioniert speichern
- Wasserbilanzen und Zählerkontinuität verlustfrei erhalten
- laufende Zustände nach Neustart sicher behandeln
- Entscheidungen und tatsächliche Bewässerung nachvollziehbar machen
- Energie- und Langzeitstatistiken ermöglichen
- Migrationen zwischen Versionen unterstützen

## Config Entries und Subentries

Ein Config Entry speichert eine Bewässerungsanlage:

- Anlagenname und globale Grenzen
- Hauptventil und Feedback
- Wasserzähler- und Wetterquellen
- Schalt- und Sicherheitsparameter
- Benachrichtigungen, Tarif und Wartung

Jede Bewässerungszone wird als Config Subentry geführt. Wiederverwendbare benutzerdefinierte Profile erhalten stabile IDs und werden referenziert statt kopiert, sofern Home Assistants Config-Entry-Modell dies sauber unterstützt.

## Versionierter Integrationsspeicher

Persistiert werden:

- finale Wasserbilanz je Zone
- Wetterquellenfortschritt, kumulative Regenbaselines und erkannte Quellen-Resets
- fortlaufender interner Anlagen- und Zonenverbrauch
- Rohzähler-Baselines, Quellen-Resets und Korrekturoffset
- Not-Aus, Sicherheits- und Wintersperren
- aktive und wartende manuelle Aufträge einschließlich Ablaufzeit
- manuelle Mehrzonenpläne und stabile Auftragsreihenfolge
- persistente Unterdrückung einmalig übersprungener Bewässerungsgelegenheiten
- alle offenen Vorgänge einschließlich Sickerstatus und aktuell aktiver Teilgabe bis zur sicheren Wiederherstellung
- begrenzte Detailhistorie
- Kalibrierungen und Durchflusstrends
- Wartungsaufgaben und Bestätigungen
- archivierte Zonenmetadaten

Jeder gespeicherte Datensatz besitzt eine Schemaversion. Migrationen sind vor jeder Änderung an persistierten Strukturen verpflichtend.

## Nicht persistent oder neu berechnet

- automatische Aufträge werden nach Neustart aus aktueller Bilanz und Konfiguration neu geplant
- einmalig übersprungene Gelegenheiten bleiben dabei unterdrückt
- vorläufige Wetterberechnungen werden aus den verfügbaren Daten neu erstellt
- kurzfristige Entity-Anzeigewerte werden nicht als zweite Wahrheitsquelle gespeichert

## Recorder und Langzeitstatistik

Reguläre HA-Sensoren liefern:

- kumulativen Anlagenverbrauch
- kumulativen Verbrauch je Zone
- unzugeordneten Verbrauch
- Laufzeiten
- Wasserbedarf und Bedarfsdeckung
- Referenz- und Pflanzenverdunstung
- Regen und Durchfluss
- optionale Kosten

Kumulative Anlagen- und Zonenverbräuche verwenden `device_class: water` und `state_class: total_increasing`. Der durch nachträgliche Zuordnung fallende unzugeordnete Verbrauch verwendet `state_class: total`. Periodische Tages-, Wochen-, Monats- und Jahresansichten werden aus Statistiken abgeleitet und nicht als konkurrierende Summen persistiert.

## Detailhistorie

Die Integration hält eine konfigurierbar begrenzte Anzahl vollständiger Bewässerungsvorgänge. Jeder Eintrag enthält Berechnungssnapshot, Auftrag, Teilgaben, Messquellen, Ziel, bestverfügbare Liefermenge mit Qualitätsstatus, Ergebnis, Gründe und Warnungen.

Änderungen an Profilen oder Formeln verändern alte Einträge nicht. CSV-Export enthält tabellarische Kerndaten; JSON-Export die vollständige Struktur.

## Zählerkorrektur

Eine manuelle Korrektur setzt den aktuellen physischen Anlagenzählerstand über einen neuen Offset. Bereits verbuchte Anlagen- und Zonenverbräuche bleiben unverändert. Quellen-Resets werden als neue Rohbaseline behandelt und reduzieren den fortlaufenden internen Verbrauch nicht.

## Neustartverhalten

Nach einem Neustart:

1. alle verwalteten Haupt- und Zonenventile schließen
2. Ventilzustände und Durchfluss prüfen
3. alle offenen Vorgänge einschließlich Sickerpausen als unterbrochen markieren
4. noch erfassbare Zählerdifferenz der zuletzt aktiven Teilgabe verbuchen
5. wartende manuelle Aufträge laden, neu validieren und auf Ablauf prüfen
6. automatische Aufträge verwerfen und neu planen
7. Not-Aus, Sicherheits- und Wintersperren beibehalten
8. Benutzer über alle Unterbrechungen und Ergebnisse informieren

Ein unterbrochener Vorgang wird niemals blind fortgesetzt.

## Export und Import

- Portabler Konfigurationsexport ohne Geheimnisse
- Import mit Schemamigration, Entity-Validierung und Vorschau
- Kein automatischer Import aus Irrigation Unlimited, Smart Irrigation oder NeverDry
- Vollständige Home-Assistant-Backups bleiben der systemweite Wiederherstellungsweg
