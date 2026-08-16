# Progress

## Aktueller Stand (2026-08-16)

**v1.2.0 — Panel + IR-Code-Bibliothek** (Release live, per HACS installiert)

- Sidebar-Panel `/transcold-ir` (nur Admin) mit drei Tabs: Geräte, Bibliothek, Import.
- SmartIR-Code-Sets (smartHomeHub/SmartIR) als Protokollquelle importierbar —
  Validierung beim Import (nur Broadlink + Base64), Ablehnung mit Begründung.
- Base64 ↔ Raw-Timings-Umrechnung: ein Code-Set funktioniert mit Broadlink
  UND ESPHome.
- Update-sichere Ablage `/config/transcold_ir/{codes,protocols}/`; Registry
  gleicht bei jedem Scan mit der Platte ab (gelöschte Datei → Protokoll weg).
- Protokoll-Dropdown zeigt Hersteller/Modell statt Registry-Keys.
- 27 Tests grün (12 Transcold + 15 SmartIR-Code-Set).

**v1.1.1 — Bugfix "Steuerung geht nicht"**

- Root Cause: Beide Config-Einträge zeigten auf `remote.magentatv_one_2_generation`
  (Android TV Remote, kann kein IR). Sendefehler wurden nur geloggt, die
  Assumed-State-Entity tat so, als hätte es geklappt. Die Klima ging am 15.08.
  20:39 über einen manuell gelernten Broadlink-Befehl an — vor der Installation.
- Fix: Remote-Auswahl auf Broadlink beschränkt (Selector + Registry-Validierung),
  Sendefehler werfen `HomeAssistantError` und rollen den State zurück.
- Live: defekte Einträge gelöscht, `climate.ir_klima` sendet über
  `remote.office_ir` (Broadlink RM mini 3) — vom Nutzer bestätigt.

**Release-Automatik**

- `.github/workflows/release.yml` erzeugt beim Merge nach main automatisch ein
  Release aus der `manifest.json`-Version (Tag-Push und manueller Dispatch
  bleiben als Trigger). Grund: Der GitHub-App-Token der Session kann weder
  Tags pushen noch Workflows dispatchen (403).
- Ablauf für künftige Versionen: Version in `manifest.json` bumpen → PR mergen
  → Release entsteht → in HA `ha_manage_hacs(update_information)` + `download`.

## Offene Punkte

- [ ] Nach dem HA-Neustart: Panel in der Seitenleiste verifizieren, einen
      SmartIR-Import mit einer echten Datei durchspielen.
- [ ] Optional: `brand/icon.png` ergänzen (HACS-Empfehlung, für Default-Store nötig).
- [ ] Optional: CI-Workflows `hassfest` + `hacs/action` ergänzen — Pflicht für
      die Aufnahme in den HACS-Default-Store.
- [ ] Optional: Panel um „Code lernen" erweitern (Broadlink `remote.learn_command`
      direkt aus dem Panel, um eigene Code-Sets aufzuzeichnen).
