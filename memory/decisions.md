# Decisions & Learnings

## 2026-08-16 — Panel + IR-Bibliothek (v1.2.0)

### Entscheidungen

1. **Custom Panel statt Options-Flow-Wildwuchs.** Vorbild war HAIR (Screenshots
   des Nutzers): eigener Sidebar-Eintrag mit Tabs. Registrierung über
   `panel_custom.async_register_panel` + `hass.http.async_register_static_paths`
   in `async_setup_entry`, idempotent über ein Flag in `hass.data`.
   Vanilla Web Component ohne Build-Toolchain — hält das Repo HACS-tauglich
   (keine node_modules, keine Build-Artefakte im Release).
2. **SmartIR als Bibliotheksformat**, statt eine eigene Code-Datenbank zu
   pflegen. SmartIR hat hunderte gepflegte Klima-Code-Sets; ein Adapter
   (`smartir_codeset.py`) macht daraus Protokolle. Deutlich mehr Nutzen pro
   Zeile Code als jedes selbst portierte Protokoll.
3. **Base64 → Raw-Timings dekodieren** statt Code-Sets auf Broadlink zu
   beschränken. Damit funktioniert jedes importierte Set auch mit ESPHome.
   Der Decoder ist die exakte Umkehrung des bestehenden Encoders — im Test
   gegen ihn verifiziert (Toleranz 1 Puls-Einheit ≈ 31 µs).
4. **Import validiert sofort und lehnt mit Begründung ab.** Gleiches Prinzip
   wie der v1.1.1-Fix: lieber früh laut scheitern als spät still.
5. **Update-sichere Ablage `/config/transcold_ir/`.** Der alte Ordner lag
   *innerhalb* der Integration und wurde bei jedem HACS-Update gelöscht —
   ein Datenverlust-Bug, der beim Bauen des Panels auffiel. Legacy-Pfad wird
   weiter gescannt, damit bestehende Setups nicht brechen.
6. **Registry gleicht mit der Platte ab.** Ohne Reconciliation blieb ein
   gelöschtes Protokoll bis zum Neustart wählbar — im Panel sichtbar
   widersprüchlich.

### Session-Retrospektive

1. **Was lief gut?** Die Reference-Datei `part3-ha-integration.md` enthielt
   nichts zu Custom Panels → Freshness-Regel gegriffen, Live-Doku gesucht,
   korrektes API-Trio (`panel_custom` + `StaticPathConfig` + `embed_iframe=False`)
   gefunden. Der bestehende Broadlink-Encoder war ein perfektes Test-Orakel
   für den neuen Decoder.
2. **Was war schwierig?** Der GitHub-App-Token kann weder Tags pushen noch
   Workflows dispatchen (403) — zwei Fehlversuche, bis der Release-Workflow
   auf `pull_request: closed` umgestellt wurde. Beim nächsten Repo direkt so.
3. **Neue/bestätigte Patterns:** Fremdformate (SmartIR) als Klasse *generieren*
   (`make_codeset_protocol` → `type(...)`) statt einer Wrapper-Instanz — so
   bleibt die bestehende `get_protocol()`-Registry unverändert nutzbar.
   Nutzerdaten gehören nach `/config/<domain>/`, niemals in `custom_components/`.
4. **Nächstes Mal anders:** Release-Automatik als Allererstes einrichten, bevor
   das erste Feature gebaut wird.
5. **Fehlender Agent/Fähigkeit:** Ein Frontend-/Panel-Agent wäre sinnvoll,
   falls das Panel weiter wächst (Lit statt Vanilla, Websocket-API).

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
