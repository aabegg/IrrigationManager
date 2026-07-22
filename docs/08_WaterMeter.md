# Wasserzähler und Durchfluss

## Unterstützte Quellen

- kumulatives Volumen mit erkannter Volumeneinheit
- momentane Durchflussrate
- roher Impuls- oder Zählwert mit konfiguriertem Umrechnungsfaktor
- kein Zähler für reine Zeitsteuerung

Die Integration ist nicht an ESPHome gebunden. Jede numerische HA-Entity kann verwendet werden, wenn Einheit, Geräteklasse oder ein expliziter Umrechnungsfaktor eine eindeutige Normalisierung erlauben.

Im Config Flow sind kumulatives Volumen und roher Impuls-/Zählwert gegenseitig
ausschließend. Ein Rohwert ist nur zusammen mit `Liter je Impuls oder Zählschritt`
gültig. Die optionale Auflösung wird in Litern gespeichert; bei einem Rohzähler ist
der Umrechnungsfaktor zugleich die kleinste Auflösung, sofern keine gröbere
Auflösung angegeben ist.

## Empfohlene Kombination

- kumulatives Volumen als maßgebliche Verbrauchsquelle
- direkte Durchflussrate für schnelle Sicherheitsreaktion
- abgeleiteter Durchfluss aus Zählerdifferenz als Plausibilitätsvergleich

Bei einem ESPHome-`pulse_meter` können deshalb dessen Rate und `total` gemeinsam ausgewählt werden.

## Betrieb ohne Messquelle

Ohne kumuliertes Volumen und ohne Durchflusssensor:

- ist ausschließlich Zeitsteuerung zulässig
- wird Liefermenge aus Dauer und Durchflussprofil geschätzt
- sind Mengenlimit, Unter-/Überdurchfluss und Leckageerkennung nicht verfügbar
- bleiben harte Laufzeitlimits und Ventilzustandsprüfungen aktiv
- zeigt die UI die reduzierte Sicherheits- und Messqualität dauerhaft an

## Fortlaufender Anlagenzähler

Die Integration führt einen eigenen fortlaufenden Verbrauch:

1. letzten gültigen Rohwert speichern
2. positive Differenz addieren
3. fallenden Quellwert als möglichen Reset klassifizieren
4. neue Baseline setzen, ohne den bisherigen internen Verbrauch zu verlieren
5. unplausible Sprünge nicht ungeprüft verbuchen

Die Quelle selbst wird niemals verändert.

Interner letzter Rohwert, fortlaufender normalisierter Stand, Resetanzahl und
Korrekturoffset werden atomar mit dem Anlagenzustand persistiert. Dadurch erzeugt
ein Home-Assistant-Neustart keinen neuen Zähleranfang.

## Physische Korrektur

Der Benutzer kann den abgelesenen physischen Ist-Zählerstand setzen:

```text
Korrekturoffset = physischer Stand - normalisierter interner Rohstand
```

Die Korrektur gilt nur für zukünftige Anzeigen. Bereits zugeordnete Verbräuche und historische Statistiken werden nicht rückwirkend verteilt.

## Verbrauchszuordnung

Da immer nur eine Zone aktiv ist:

```text
Zonenverbrauch = Endstand - Startstand
```

Vor dem Start wird eine Baseline erfasst. Nach Ventilschluss wartet die Integration die konfigurierte Nachlaufzeit ab und finalisiert dann die Menge. Kalibrierung und manuelle Vorgänge werden wie reguläre Bewässerung zugeordnet.

Mengen außerhalb eines zuordenbaren Vorgangs werden als unzugeordnet geführt. Dazu gehören Leckage, freie Wartungstests und Messlücken.

## Messqualität

Jede Menge trägt eine Herkunft:

- primär aus kumuliertem Zähler gemessen
- aus Durchflussrate integriert
- aus kalibriertem Durchfluss und Laufzeit geschätzt
- unbekannt

Bei Ausfall eines konfigurierten kumulativen Zählers darf eine gültige Durchflussrate integriert werden. Danach gilt die zonenspezifische Zählerausfallstrategie: Vorgang abbrechen oder auf Zeitsteuerung mit Schätzung wechseln. Ohne konfigurierten kumulativen Zähler sind Mengenziele unabhängig von der Zählerausfallstrategie unzulässig.

Die öffentliche Qualität lautet dabei `measured`, `integrated`, `estimated` oder
`unknown`. Nur eine gültige kumulative Differenz heißt `measured`. Eine Integration
direkter Durchflusswerte wird niemals nachträglich als gemessen bezeichnet.

## Messauflösung

- Zielmengen werden auf erfassbare Schritte gerundet.
- Rundungsrichtung und erwarteter Fehler werden angezeigt.
- Bei grober Auflösung gegenüber dem Ziel wird Zeitsteuerung empfohlen.
- Teilmengen zwischen Impulsen werden nicht als exakte Messung ausgegeben.

## Vorabschaltung und Nachlauf

Kalibrierung kann die nach Schaltbefehl noch gelieferte Menge bestimmen. Eine bestätigte konservative Vorabschaltung schließt vor dem rechnerischen Ziel. Maßgeblich für Bilanz und Historie bleibt die bestverfügbare Endmenge mit Herkunft und Qualitätskennzeichnung: gemessen, integriert oder geschätzt.

## Durchflussprofil

Pro Zone:

- erwarteter Minimaldurchfluss
- Normalbereich
- erwarteter Maximaldurchfluss
- Anlauf- und Stabilisierungszeit
- Nachlauf und Messlatenz

Werte werden manuell eingegeben oder in einem geführten Test gemessen. Langsame Trends erzeugen nur Vorschläge; automatische Grenzwertverschiebung ist verboten.

## Leckage und Abweichungen

- Durchfluss wird direkt gelesen oder aus Volumendifferenz und Zeit berechnet.
- Einzelne Impulse lösen ohne ausreichende Beobachtungsdauer keinen Alarm aus.
- Niedriger Durchfluss bei aktiver Zone stoppt und sperrt die Zone.
- Hoher Durchfluss stoppt und sperrt die gesamte Anlage.
- Durchfluss ohne aktive Teilgabe wird ab konfigurierbarer Rate und Dauer als Leckage behandelt.
- Nach manueller Quittierung führt eine weiterhin messbare Gefahr erneut zur Sperre.
- Übersteuerung ist ausschließlich in einem beaufsichtigten Wartungstest zulässig.

## Statistiken

Bereitgestellt werden fortlaufende Sensoren für:

- gesamte Anlage
- jede aktive oder archivierte Zone
- unzugeordneten Verbrauch

Die Sensoren verwenden eine kanonische interne Einheit und Home Assistants Einheitenkonvertierung. Sie sind für Recorder, Langzeitstatistik und Wasserverbrauch im Energie-Dashboard geeignet.

Die kumulativen Sensoren verwenden `device_class: water`, Liter und
`state_class: total_increasing`. Die Periodenwerte werden aus einer begrenzten,
persistierten Beitragsliste nach lokaler Zeitzone abgeleitet; sie führen keine
zweite Gesamtsumme. Zugeordneter unzugeordneter Verbrauch reduziert nur den
zuweisbaren Bestand, nie den kumulativen Statistikwert.
