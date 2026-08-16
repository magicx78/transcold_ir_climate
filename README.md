# Transcold IR Climate

Home Assistant Custom Integration zur Steuerung von Klimaanlagen über einen Infrarot-Proxy (Broadlink RM oder ESPHome IR-Sender) — mit eigenem Verwaltungs-Panel in der Seitenleiste und Import-Funktion für IR-Code-Bibliotheken.

Das mitgelieferte Transcold-Protokoll ist aus [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) (`ir_Transcold.cpp/.h`) portiert und per Testsuite bitgenau gegen die C++-Referenz verifiziert (`tests/test_transcold_protocol.py`).

## Features

- Vollständige Home Assistant Climate Entity (assumed state, da IR one-way)
- **Verwaltungs-Panel in der Seitenleiste**: Geräteübersicht, Protokoll-Bibliothek und Drag-&-Drop-Import
- **SmartIR-Import**: hunderte fertige Klima-Code-Sets nutzbar, ohne Programmieren
- **Eigene Protokolle** als Python-Datei importierbar — update-sicher in `/config/transcold_ir/`
- Kompatibel mit der **HVAC Card**
- **Broadlink**: sendet Base64-Pakete (`b64:...`) über `remote.send_command` — wird automatisch erkannt
- **ESPHome**: sendet rohe IR-Timings über eine ESPHome-Action (siehe unten); SmartIR-Base64-Codes werden dafür automatisch zurück in Timings dekodiert
- Unterstützte Modi: Cool, Heat, Dry, Fan Only, Auto
- Lüfterstufen: Auto, Low, Medium, High
- Swing (als Toggle-Kommando, wie beim Original-Handsender)
- Konfiguration über UI (Config Flow)
- HACS-kompatibel

## Installation

### HACS

1. HACS → Integrationen → Benutzerdefinierte Repositorys
2. URL: `https://github.com/magicx78/transcold_ir_climate`
3. Kategorie: **Integration**
4. Installieren (benötigt ein GitHub-Release, z.B. `v1.1.0`)

### Manuell

1. Inhalt von `custom_components/transcold_ir_climate/` nach `<config>/custom_components/transcold_ir_climate/` kopieren
2. Home Assistant neu starten

## Konfiguration

1. Einstellungen → Geräte & Dienste → Integration hinzufügen
2. **Transcold IR Climate** suchen
3. **Entweder** eine IR-Remote Entity auswählen (z.B. `remote.wohnzimmer`, Broadlink)
   **oder** einen ESPHome-Service eintragen (z.B. `esphome.ir_proxy_send_raw_command`)
4. Name, Temperaturbereich und Standardmodus festlegen

Das Befehlsformat wird für Broadlink-Remotes automatisch auf `broadlink` (Base64) gesetzt — `remote.send_command` akzeptiert bei Broadlink nur gelernte Befehlsnamen oder `b64:`-Base64, niemals rohe Timing-Listen.

> **Hinweis:** In der Remote-Auswahl erscheinen ausschließlich Broadlink-Remotes. TV-/Media-Remotes (Android TV, Apple TV …) tauchen zwar in HA als `remote`-Entity auf, können aber physikalisch kein Infrarot senden. Für andere IR-Sender den ESPHome-Pfad nutzen.

## Panel: Geräte, Bibliothek und Import

Nach der Installation erscheint **IR Klima** in der Seitenleiste (nur für Administratoren). Das Panel hat drei Tabs:

| Tab | Inhalt |
|---|---|
| **Geräte** | Alle konfigurierten Klimageräte mit Protokoll, Sender und Live-Status |
| **Bibliothek** | Alle verfügbaren Protokolle — eingebaute, importierte Code-Sets und eigene Python-Protokolle; einzeln löschbar |
| **Import** | Drag-&-Drop-Feld für `.json`-Code-Sets und `.py`-Protokolldateien |

Importierte Dateien landen **update-sicher** unter `/config/transcold_ir/` und überleben damit HACS-Updates:

```
/config/transcold_ir/
├── codes/        ← SmartIR-Code-Sets (*.json)
└── protocols/    ← eigene Protokolle (*.py)
```

Nach dem Import steht das Gerät sofort im Protokoll-Dropdown eines neuen Config-Flows zur Verfügung — ohne Neustart.

### SmartIR-Code-Sets importieren

[SmartIR](https://github.com/smartHomeHub/SmartIR/tree/master/codes/climate) pflegt eine große Sammlung aufgezeichneter IR-Codes für Klimageräte (Daikin, Mitsubishi, LG, Samsung, Gree, Midea …).

1. Passende JSON-Datei aus dem SmartIR-Repository herunterladen
2. Im Panel auf **Import** ziehen
3. Neues Gerät hinzufügen und das importierte Protokoll (`Hersteller (Modell)`) auswählen

Unterstützt werden Code-Sets mit `"supportedController": "Broadlink"` und `"commandsEncoding": "Base64"`. Ungültige Dateien werden beim Import mit Begründung abgelehnt, statt später still zu scheitern.

Die Base64-Kommandos werden für ESPHome-Sender automatisch in rohe Timings zurückgerechnet — ein SmartIR-Code-Set funktioniert also mit beiden Sendertypen.

### Eigenes Protokoll schreiben

Für Exoten, die in keiner Datenbank stehen, genügt eine Python-Datei mit einer `BaseIRProtocol`-Unterklasse:

```python
from custom_components.transcold_ir_climate.protocols.base import BaseIRProtocol

class MyACProtocol(BaseIRProtocol):
    name = "my_ac"
    description = "My Custom AC"
    supported_models = ["MyAC Model X"]
    min_temp = 16
    max_temp = 30

    def encode(self, mode, temp, fan, power=True, swing=False, command_format="raw"):
        ...  # raw-Timings (Liste) oder Broadlink-Base64 (String) zurückgeben

    def get_raw_timings(self, state):
        return self.encode(**state, command_format="raw")
```

Datei im Panel auf **Import** ziehen (oder nach `/config/transcold_ir/protocols/` kopieren). Als Vorlage dient `protocols/transcold.py`; die C++-Referenzen für über 100 Klima-Protokolle stehen in [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266/tree/master/src) unter `ir_<Hersteller>.cpp`.

## ESPHome IR-Proxy einrichten

Rohe Timings lassen sich nicht über `remote.send_command` senden (ESPHome erzeugt gar keine `remote`-Entity). Stattdessen im ESPHome-Node eine Action definieren:

```yaml
remote_transmitter:
  pin: GPIO4
  carrier_duty_percent: 50%

api:
  actions:
    - action: send_raw_command
      variables:
        command: int[]
      then:
        - remote_transmitter.transmit_raw:
            carrier_frequency: 38kHz
            code: !lambda "return command;"
```

In der Integration dann als ESPHome-Service `esphome.<nodename>_send_raw_command` eintragen. Die Integration ruft ihn mit `{"command": [5944, -7563, 555, ...]}` auf (positiv = Mark, negativ = Space).

## Beispiel HVAC Card

```yaml
type: thermostat
entity: climate.klima_wohnbereich
features:
  - type: climate-hvac-modes
    hvac_modes:
      - 'off'
      - cool
      - heat
      - dry
      - fan_only
      - auto
  - type: climate-fan-modes
    fan_modes:
      - auto
      - low
      - medium
      - high
  - type: climate-swing-modes
    swing_modes:
      - 'off'
      - 'on'
```

## Migration von tasmota_irhvac

| Alt (YAML) | Neu (UI) |
|---|---|
| `name: Klima Wohnbereich` | Name in der UI |
| `command_topic` | IR-Remote Entity / ESPHome-Service auswählen |
| `state_topic` | Nicht mehr nötig |
| `temperature_sensor` | Separater Sensor in HA |
| `protocol: TRANSCOLD` | Protokoll `transcold` in der UI |
| `min_temp` / `max_temp` | In der UI konfigurierbar |
| `target_temp` | In der UI konfigurierbar |
| `initial_operation_mode` | In der UI konfigurierbar |

## Protokolldetails (Transcold, 24 Bit)

```
MSB                                              LSB
[0xE (4)] [Fan (4)] [Mode (4)] [Temp (4)] [0x54 (8)]
```

- Jedes Byte wird MSB-first gesendet, direkt gefolgt vom bitweise invertierten Byte
- Temperatur: `reverse(invert(temp - 18 + 1, 4), 4)`
- Power Off (`0xEF7954`) und Swing (`0xE76154`) sind eigenständige Spezial-Codes; Swing ist ein **Toggle**
- Fan-Only wird als Dry + Temp-Code `0b1111` kodiert
- Bekannter Referenz-State: `0xE96554` = Cool / 22 °C / Fan min
- Broadlink-Einheiten: `µs × 269 / 8192` (≈ 30,46 µs pro Tick)

## Tests

```bash
python -m pytest tests/          # alle Tests
python tests/test_transcold_protocol.py   # einzeln, ohne pytest
python tests/test_smartir_codeset.py
```

`test_transcold_protocol.py` vergleicht den Encoder gegen eine unabhängige Transkription von `IRsend::sendTranscold` und die im IRremoteESP8266-Header dokumentierten Raw-Captures. `test_smartir_codeset.py` prüft Validierung, Kommando-Lookup und die Base64-↔-Timings-Umrechnung.

## Unterstützte Geräte

- Transcold M1-F-NO-6 (eingebautes Protokoll)
- Andere Transcold-Modelle mit kompatiblem IR-Protokoll
- Alle Klimageräte, für die ein SmartIR-Broadlink-Code-Set existiert (Import über das Panel)
- Beliebige weitere Geräte über eigene Protokoll-Dateien

## Credits

IR-Protokoll basiert auf [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) von crankyoldgit.

Importierbare Code-Sets stammen aus dem [SmartIR](https://github.com/smartHomeHub/SmartIR)-Projekt; sie werden nicht mitgeliefert, sondern vom Nutzer importiert.

## Lizenz

[LGPL-2.1](LICENSE) — passend zur Lizenz von IRremoteESP8266, aus dem das Transcold-Protokoll portiert wurde.
