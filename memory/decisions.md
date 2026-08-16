# Decisions & Learnings

## 2026-08-16 — Bugfix "Steuerung geht nicht" (v1.1.1)

### Entscheidungen

1. **Remote-Auswahl auf Broadlink beschränkt** (Selector `integration="broadlink"`
   + serverseitige Validierung). Begründung: `remote.send_command` mit
   b64-Payload funktioniert nur bei Broadlink; alle anderen remote-Plattformen
   (Android TV, Apple TV, …) akzeptieren den Call, senden aber kein IR.
   Andere IR-Sender laufen über den ESPHome-Service-Pfad.
2. **Fehler werfen statt loggen**: Bei Assumed-State-Entities ist stilles
   Fehlschlagen fatal — die UI zeigt "an", real passiert nichts. Jetzt
   `HomeAssistantError` + Rollback des internen States.

### Session-Retrospektive

1. **Was lief gut?** Fehlerlog (`ha_get_logs(source="error_log", search=...)`)
   lieferte die Root Cause in einem Schritt. ULID-Timestamps der Config-Einträge
   halfen bei der Timeline-Rekonstruktion.
2. **Was war schwierig?** Config-Entry-Daten (.storage) sind per MCP nicht
   lesbar — Ziel-Remote musste aus Fehlermeldungen erschlossen werden.
   MCP-Löschung von Config-Einträgen wird vom Permission-System blockiert.
3. **Neue/bestätigte Patterns:** "Es hat mal funktioniert" immer gegen
   Zeitstempel prüfen (Commit-Daten vs. Gerätehistorie) — hier lag der
   vermeintliche Erfolg VOR der Installation. Broadlink-Sendungen lassen sich
   über die `infrared.*`-Emitter-Entities und Debug-Log verifizieren.
4. **Nächstes Mal anders:** Bei One-Way-Protokollen (IR) von Anfang an
   Fehler sichtbar machen statt loggen — das hätte dem Nutzer sofort gezeigt,
   dass nie gesendet wurde.
5. **Fehlender Agent/Fähigkeit:** Keiner — HA-Integration-Agent + Validator
   reichten aus.
