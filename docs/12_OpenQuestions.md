# Offene Punkte

Die funktionalen Grundsatzfragen wurden in der Grill-Session vom 20. Juli 2026 entschieden. Offen sind überwiegend zu validierende Standardwerte und Implementierungsdetails.

## Referenzanlage erfassen

- Entity IDs und Domains von Haupt- und sechs Zonenventilen
- Entity IDs von kumuliertem Volumen und Durchfluss
- Flächen beziehungsweise geführte Schätzungen je Zone
- Tropferanzahl, Tropferleistung und Tropfrohrverlegung
- aktuelle Bodenarten und Wurzeltiefen
- verfügbare Wetterstationssensoren
- gewünschte Mindest- und Maximalintervalle
- reale Bewässerungsfenster
- heutige typische Laufzeiten und Mengen

## Fachliche Standardwerte validieren

- erste mitgelieferte Pflanzenprofile und saisonale Kurven
- Bodenprofile, Speicherkapazitäten und Drainageparameter
- Standardwerte für Anwendungseffizienz
- Prognosewahrscheinlichkeit und maximaler Aufschub
- Frost-, Wind- und Regenschwellen
- Durchflusstoleranzen und Mindestbeobachtungsdauer
- Kalibrierungsdauer und empfohlene Grenzbandbreite
- Standardgröße und Dauer von Teilgaben und Sickerpausen
- Mindestmenge für eine wirksame Bewässerung

## Technische Entscheidungen

- konkrete unterstützte Home-Assistant-Mindestversion
- Bibliothek oder eigene geprüfte Implementierung für FAO-56
- Open-Meteo-Endpunkte, Rate Limits und Cache
- Config-Subentry- und Profilpersistenz im gewählten HA-Stand
- kanonische interne Einheiten
- Standardgröße der Detailhistorie
- Exportformat und Schemaversion
- sichere Bereitstellung der gebündelten Lovelace-Karten
- Mechanismus für portable Importdateien

## Vor Feldtest

- unabhängigen Hardware-Abschalttimer der realen Anlage klären
- Abschalt- und Rückmeldesemantik der vorhandenen Ventile prüfen
- Verhalten des ESPHome-Impulszählers bei Neustart messen
- Messauflösung von einem Liter gegen kleine Topfzonen bewerten
- kontrollierten Ablöseplan für bestehende Integrationen erstellen
