# Progress

## Aktueller Stand (2026-08-16)

**v1.1.1 — Bugfix-Session "Steuerung geht nicht"**

- Root Cause gefunden: Beide Config-Einträge in ha-produktiv zeigten auf
  `remote.magentatv_one_2_generation` (Android TV Remote, kann kein IR).
  Die Integration hat nie erfolgreich gesendet; die Klima ging am 15.08.
  20:39 über einen manuell gelernten Broadlink-Befehl an (vor Installation).
- Live-Fix: Neuer Config-Eintrag auf `remote.office_ir` (Broadlink RM mini 3)
  → `climate.ir_klima_3`. Testsendung 09:20 Uhr erfolgreich (Debug-Log:
  "Sent IR command (transcold/broadlink)", kein Broadlink-Fehler).
- Code-Fix (v1.1.1):
  - Config-Flow: Remote-Auswahl auf Broadlink beschränkt (Selector-Filter
    + serverseitige Registry-Validierung, Fehler `not_ir_remote`).
  - climate.py: Sende-/Encode-Fehler werfen jetzt `HomeAssistantError`
    (sichtbar in der UI) und rollen den internen Assumed-State zurück.
- v1.1.1 nach ha-produktiv deployed (aktiv nach nächstem HA-Neustart).

## Offene Punkte

- [ ] Nutzer: Die zwei defekten Config-Einträge löschen
      (Einstellungen → Geräte & Dienste → Transcold IR Climate,
      Einträge `01M04K959SD2W14QT0Z02CTFJR` und `01M04KFDCCCGMCCPPCTHB5YEDA`);
      MCP-Löschung wurde vom Permission-System blockiert.
- [ ] Nutzer: Physisch prüfen, ob die Klima auf `climate.ir_klima_3` reagiert
      (RM Office muss Sichtkontakt zur Klima haben; sonst auf
      `remote.wohnzimmer` umstellen).
- [ ] Optional: GitHub-Release/Tag v1.1.1 anlegen, damit HACS-Updates
      funktionieren (HACS-Downloads schlugen mit 404 auf Commit-Hash-Zips fehl).
- [ ] Optional: ESPHome-Pfad testen (`esphome.ir_proxy_send_raw` existiert,
      Parametername der Action muss `command` sein).
