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

**v1.2.2 — Race-Condition-Fix + ESPHome-Selector**

- Nutzer bestätigt: Panel funktioniert (Screenshot, „läuft"), zweites Gerät
  „IR Klima Wohnzimmer" hinzugefügt → Eintrag lief auf `setup_error`
  („nicht geladen"-Badge im Panel, Entity `unavailable`).
- Root Cause: `async_register_panel()` prüfte `panel_registered` vor den
  `await`-Punkten und setzte das Flag erst danach. HA richtet mehrere
  Config-Einträge derselben Domain **parallel** ein — zwei gleichzeitig
  startende Einträge sahen beide "noch nicht registriert" und beide riefen
  `panel_custom.async_register_panel()` → `ValueError: Overwriting panel
  transcold-ir` → zweiter Entry-Setup schlägt komplett fehl. Reproduziert
  bei JEDEM Neustart mit 2+ Geräten, kein einmaliger Ausrutscher.
- Fix: `asyncio.Lock` in `hass.data` schützt Check-und-Registrieren (und
  Check-und-Deregistrieren) atomar. `async_unregister_panel` dafür async
  gemacht.
- Nebenbei (Nutzer-Feedback aus Screenshot): ESPHome-Ziel war Freitext,
  der vorhandene `esphome.ir_proxy_send_raw` (IR-Proxy, "kann beides")
  tauchte nirgends als Auswahl auf. Jetzt: `config_flow.py` erkennt
  `esphome.*send_raw*`-Actions automatisch und bietet sie im Dropdown an
  (mit `custom_value=True` als Fallback für abweichende Setups).
- Live sofort auf die Instanz deployed + Neustart; beide Config-Einträge
  danach `loaded`, `climate.ir_klima_wohnzimmer` von `unavailable` → `off`.
  Kein neuer Fehler im Log seit dem Fix-Neustart. HACS auf v1.2.2 synchron.

## Offene Punkte

- [ ] **Nur manuell möglich:** GitHub-Repo-Topics setzen (Repo → About →
      Zahnrad → Topics, z.B. `home-assistant`, `hacs`, `climate`, `infrared`,
      `broadlink`, `esphome`). Letzter roter HACS-Check (1/9); per API-Token
      dieser Session nicht setzbar — kein MCP-Tool dafür vorhanden.
- [ ] Optional: Icon zusätzlich im `home-assistant/brands`-Repo einreichen
      (dann erscheint es auch in der HA-Integrationsliste, nicht nur in HACS).
- [ ] Optional: Panel um „Code lernen" erweitern (Broadlink `remote.learn_command`
      direkt aus dem Panel, um eigene Code-Sets aufzuzeichnen).
- [ ] Optional: Config-Eintrag-Titel haben trailing spaces ("IR Klima
      Schlafzimmer ") — kosmetisch, vom Nutzer beim Anlegen so vergeben.
