# Wasser- und Wettermodell

## Ziel

Das Modell liefert eine reproduzierbare Schätzung des zonenspezifischen Wasserbedarfs. Die gelieferte Wassermenge kann mit einem geeigneten Zähler innerhalb seiner Auflösung gemessen werden; ohne Messquelle wird auch sie geschätzt. Verdunstung, wirksamer Regen und Pflanzenbedarf bleiben Modelle mit sichtbarer Qualitätsangabe.

## Einrichtungsmodi

### Einfach

Der Benutzer wählt:

- Pflanzenprofil oder Pflanzenmischung
- Bodenprofil
- Sonne/Schatten und Regenexposition
- Bewässerungsart
- Fläche beziehungsweise geführte Flächenschätzung
- gewünschtes Intervall

Die Integration schlägt nachvollziehbare Werte vor.

### Experte

Alle zugrunde liegenden Faktoren können eingesehen und überschrieben werden, insbesondere Pflanzenkurve, Wurzeltiefe, Bodenparameter, Anwendungseffizienz, Regenfaktor, Prognoseschwellen und Speicherkapazität.

## Wetterquellen

Jede Messgröße besitzt eine priorisierte Quellenliste:

- lokale HA-Sensoren
- Weather-Entity
- optional direkter Open-Meteo-Wert
- zeitlich begrenzter historischer oder saisonaler Ersatzwert

Lokale Sensoren sind standardmäßig primär. Andere Wetterdienste werden über vorhandene HA-Entities eingebunden. Werte werden nicht ungefragt gemittelt.

## Referenzverdunstung

### Direkte Quelle

Ein vorhandener ET0-Sensor oder Wetterdienstwert kann als Primärquelle gewählt werden. Eine eigene Berechnung darf parallel als Plausibilitätsvergleich laufen.

### FAO-56 Penman-Monteith

Bei ausreichenden Daten wird für abgeschlossene Tage die standardisierte tägliche FAO-56-Gleichung verwendet:

```text
ET0 =
  [0.408 * Delta * (Rn - G)
   + gamma * 900 / (T + 273) * u2 * (es - ea)]
  /
  [Delta + gamma * (1 + 0.34 * u2)]
```

Benötigt werden insbesondere Temperatur, Luftfeuchtigkeit beziehungsweise Taupunkt, Wind auf zwei Meter Höhe, Strahlung, Luftdruck beziehungsweise Standorthöhe und Zeitraum.

Die dargestellte Konstante `900` und die Energieterme gelten für die tägliche Auswertung in passenden FAO-56-Einheiten. Eine spätere stündliche Berechnung benötigt die dafür definierte FAO-56-Variante mit anderen Konstanten und wird nicht durch bloß häufigeres Ausführen dieser Tagesformel simuliert.

### Fallbackkette

Wenn Eingangsdaten fehlen, wird eine definierte und getestete Modellkette verwendet, beispielsweise:

1. direkte konfigurierte ET0-Quelle
2. vollständige FAO-56-Berechnung
3. datenärmeres temperaturbasiertes Modell wie Hargreaves-Samani
4. begrenzter saisonaler Ersatzwert
5. Aussetzen der Bedarfsautomatik nach Ablauf der erlaubten Ersatzdauer

Die endgültige Reihenfolge richtet sich nach der gewählten Primärquelle. Methode, Eingaben, Datenalter und Qualitätsstufe werden gespeichert.

## Bilanzzeitraum

Das Modell legt seinen fachlich korrekten Bilanzzeitraum fest. Häufigere Sensorupdates erzeugen vorläufige Anzeigen, verbuchen aber denselben Zeitraum nicht mehrfach. Ein manuell einstellbares Aktualisierungsintervall beeinflusst nur Aktualität und Systemlast, nicht das finale Ergebnis.

## Pflanzenverdunstung

Vereinfacht:

```text
ETc = ET0 * Kc * Standortfaktor
```

- `Kc` stammt aus der saisonalen Pflanzenkurve.
- Standortfaktoren beschreiben Sonne, Mikroklima und weitere begründete Korrekturen.
- Teilflächen werden anhand Profil und Fläche zu einem effektiven Zonenprofil kombiniert.
- Die Zone führt genau eine gemeinsame Wasserbilanz.
- Ein manueller Zonenfaktor kann das kombinierte Ergebnis überschreiben.

Für Teilflächen `i` wird der effektive saisonale Pflanzen- und Standortfaktor flächengewichtet:

```text
Faktor_effektiv(t) =
  Summe(Fläche_i * Kc_i(t) * Standortfaktor_i)
  / Summe(Fläche_i)
```

Die relative Ausbringungsrate verändert nicht den Pflanzenbedarf. Sie wird mit dem relativen Bedarfsanteil verglichen und als Verteilungsabweichung angezeigt. Weil Teilflächen keine eigenen Bilanzen führen, korrigiert die Integration diese Abweichung nicht automatisch; der Benutzer kann Anwendungseffizienz oder Zonenfaktor begründet anpassen.

## Wasserbilanz

```text
Defizit_neu = clamp(
  Defizit_alt
  + Pflanzenverdunstung
  - wirksamer_Regen
  - wirksame_Bewässerung,
  0,
  maximal_speicherbares_Defizit
)
```

- `0` bedeutet kein auszugleichendes Defizit.
- Das maximale Defizit leitet sich aus Boden, Wurzeltiefe und zulässiger Ausschöpfung ab.
- Überschüssiges Wasser wird nicht als negativer Bedarf gespeichert.
- Drainage und Abfluss werden separat ausgewiesen.

## Wirksamer Regen

- Gemessener Regen wird mit dem zonenspezifischen Regenfaktor gewichtet.
- Bodenaufnahme, Intensität, freie Speicherkapazität und Drainage begrenzen den wirksamen Anteil.
- Prognostizierter Regen wird niemals als bereits gefallen verbucht.
- Prognose darf nur den Ausführungszeitpunkt verschieben, nicht persistentes Defizit oder Zielmenge reduzieren.

## Bewässerungsbedarf und Zielmenge

```text
Netto_Wassertiefe = auszugleichender Anteil des Defizits
Brutto_Wassertiefe = Netto_Wassertiefe / Anwendungseffizienz
Zielvolumen_Liter = Brutto_Wassertiefe_mm * Fläche_m2
Zieldauer_Minuten = Zielvolumen_Liter / Durchfluss_Liter_pro_Minute
```

Es gilt `1 mm * 1 m² = 1 Liter`.

Das Ziel wird anschließend durch Mindestbewässerung, maximale Gabe, Fenster, Budget, Messauflösung, Teilgaben und Sicherheitsgrenzen angepasst. Jede Anpassung erscheint in der Beitragsaufschlüsselung.

Bei Zeitsteuerung ohne Zähler wird die tatsächlich ausgeführte Dauer mit dem bestätigten Durchflussprofil in eine geschätzte Liefermenge umgerechnet. Diese Menge reduziert die Wasserbilanz unter Kennzeichnung ihrer geringeren Messqualität.

## Bodenfeuchte

Je Zone wählbare Rolle:

- Sperre bei ausreichend feuchtem Boden
- begrenzte Korrektur der modellierten Bilanz
- primäre Bedarfsquelle mit Wasserbilanz als Fallback

Sensoren können Zone oder Teilfläche zugeordnet werden. Mehrere Sensoren verwenden eine wählbare Aggregation wie Minimum, Median oder Mittelwert. Unplausible, stale oder nicht verfügbare Sensoren werden nicht stillschweigend als gültig behandelt.

## Wetterbedingte Ausführungssperren

- Frost ist für automatische und normale manuelle Vorgänge hart.
- Windgrenzen gelten besonders für oberirdische Beregnung und können manuell bewusst übersteuert werden.
- Einsetzender Regen kann einen automatischen Vorgang ab einer zonenspezifischen Schwelle beenden.
- Profile liefern Standardwerte; Benutzer kann Zonenwerte anpassen.

## Initialisierung und Korrektur

Neue Zone:

- frisch bewässert
- manuell gesetztes Defizit
- optional aus vorhandenen Recorder-Wetterdaten rückgerechnet

Spätere Korrekturen können den Bedarf setzen, erhöhen oder reduzieren. Sie benötigen einen Grund und verändern keine historischen Berechnungssnapshots.

## Validierung

- Referenztests gegen veröffentlichte FAO-56-Beispiele
- Einheiten- und Zeitzonentests
- Tests für fehlende, stale und unplausible Werte
- Tests für Regenzähler-Resets und Tageswechsel
- deterministische Ergebnisse bei identischer Eingangsdatenreihe
- Vergleich direkter und selbst berechneter ET0-Werte
- Simulation trockener, regnerischer und ausfallbehafteter Zeiträume
