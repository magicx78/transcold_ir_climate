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

**v1.2.1 — Veröffentlichungs-Reife**

- CI `Validate` (hassfest + hacs/action + pytest) bei Push, PR, wöchentlich.
  Fing sofort einen echten Fehler: hassfest verlangt Manifest-Keys als
  „domain, name, dann strikt alphabetisch" — nicht die Core-Gruppierung.
- LGPL-2.1 (LICENSE), passend zu IRremoteESP8266. Von GitHub als
  `spdx_id: LGPL-2.1` erkannt (Erkennung läuft nur auf dem Default-Branch,
  daher erst nach dem Merge grün).
- Brand-Assets `brand/icon.png` (256²) + `logo.png` (512²) — HACS-Check
  „brands" damit grün.
- HA-Neustart durchgeführt; Config-Eintrag `loaded` (beweist, dass Panel-
  und View-Registrierung fehlerfrei liefen), HACS auf v1.2.1 synchron.

## Offene Punkte

- [ ] **Nur manuell möglich:** GitHub-Repo-Topics setzen (Repo → About →
      Zahnrad → Topics, z.B. `home-assistant`, `hacs`, `climate`, `infrared`,
      `broadlink`, `esphome`). Letzter roter HACS-Check; per API-Token dieser
      Session nicht setzbar.
- [ ] Panel im Browser gegenprüfen und einen echten SmartIR-Import testen.
- [ ] Optional: Icon zusätzlich im `home-assistant/brands`-Repo einreichen
      (dann erscheint es auch in der HA-Integrationsliste, nicht nur in HACS).
- [ ] Optional: Panel um „Code lernen" erweitern (Broadlink `remote.learn_command`
      direkt aus dem Panel, um eigene Code-Sets aufzuzeichnen).
- [ ] Optional: Config-Eintrag von „1" auf einen sprechenden Namen umbenennen
      (erscheint so im Panel-Tab „Geräte").
