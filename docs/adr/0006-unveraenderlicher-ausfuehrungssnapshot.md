# Laufende Vorgänge verwenden einen unveränderlichen Snapshot

Ein gestarteter Bewässerungsvorgang läuft mit dem beim Preflight validierten Konfigurations- und Sicherheitsgrenzen-Snapshot weiter. Änderungen im Config oder Options Flow werden erst im Leerlauf aktiviert; unmittelbare Eingriffe erfolgen stattdessen über Stop, Not-Aus oder eine Sicherheitssperre. Dadurch ändern halbfertige UI-Eingaben nicht unvorhersehbar einen aktiven Vorgang.
