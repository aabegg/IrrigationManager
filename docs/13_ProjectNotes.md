# Projektnotizen

## Ausgangslage

Die Referenzanlage wird aktuell grundlegend mit Irrigation Unlimited und Smart Irrigation aufgebaut. Die Kombination ist leistungsfähig, verteilt Konfiguration, Zustände und Fehlerdiagnose aber über mehrere Integrationen und zusätzliche Automationen.

Irrigation Manager wird deshalb als eigenständige Integration entwickelt. Es gibt keine automatische Migration aus bestehenden Lösungen; die reale Umschaltung erfolgt nach vollständiger Simulation und kontrollierter Bestandsaufnahme aller HA-Verbraucher.

## Persönliche Referenzanlage

- ein ausschließlich für Bewässerung verwendeter Wasserzähler
- ein Hauptventil
- sechs sequenziell betriebene Zonenventile

### Zone 1: Hecken

- Eiben und Thuja
- eher seltene Bewässerung mit minimalem und maximalem Abstand

### Zone 2: Rasen

- häufige, grundsätzlich tägliche Gelegenheit
- Kandidat für Teilgaben und Sickerpausen

### Zone 3: Pflanztöpfe

- verschiedene Kübel und Töpfe
- Einzeltropfer und Mikrobewässerung
- kleine Zielmengen erfordern besondere Beachtung der Zählerauflösung

### Zone 4: Beet mit geringerer Sonne

- Gräser, Ahorn, Farn und weitere Pflanzen
- Tropfschlauch
- unterschiedliche Rohrdichte wird als Verteilungsabweichung ausgewiesen und über Anwendungseffizienz oder Zonenfaktor manuell berücksichtigt

### Zone 5: Sonnigeres Beet

- ähnliche Bepflanzung wie Zone 4
- höhere Sonneneinstrahlung
- eigenes Standortprofil

### Zone 6: Hochbeet

- Mikro-Tropfbewässerungsschlauch
- saisonal veränderliche Bepflanzung

## Abgrenzung zu Wettbewerbern

- Irrigation Unlimited ist Referenz für flexible Zeitplanung und Sequenzen.
- Smart Irrigation ist Referenz für ET- und Wetterberechnung.
- NeverDry ist Referenz für Wasserbilanz, Pflanzenprofile und Ventilsicherheit.
- OpenSprinkler ist Referenz für lokale Programme, Cycle-and-Soak und Durchflussdiagnose.
- Keines dieser Projekte wird zur Laufzeit benötigt.

## Differenzierung

- eine gemeinsame UI für Planung, Berechnung, Messung und Sicherheit
- ein Config Entry je physischer Anlage
- exakte Zuordnung eines gemeinsamen Wasserzählers durch strikt sequenzielle Zonen
- vollständige Berechnungserklärung statt undurchsichtiger Laufzeitkorrektur
- generische HA-Hardware statt proprietärem Controller
- direkte Energie-Dashboard-fähige Zonenverbräuche
- sicherer Wartungs-, Winter- und Wiederanlaufprozess
- einfache Profile mit vollständigen Expertenoptionen

## Arbeitsweise

1. Entscheidungen zuerst dokumentieren.
2. Domänensprache in `CONTEXT.md` konsistent verwenden.
3. Schwer umkehrbare Entscheidungen als kurze ADRs festhalten.
4. Vertikale Funktionen gegen simulierte Entities implementieren.
5. Sicherheits- und Fehlerpfade vor Komfortfunktionen testen.
6. Reale Hardware erst nach vollständiger Qualifikation anbinden.
7. Öffentliches HACS-Release erst nach privatem Feldtest.
