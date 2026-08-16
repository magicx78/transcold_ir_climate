# Transcold IR Climate

Home Assistant Custom Integration zur Steuerung von Transcold Klimaanlagen über einen Infrarot-Proxy (Broadlink RM oder ESPHome IR-Sender).

Das IR-Protokoll ist aus [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) (`ir_Transcold.cpp/.h`) portiert und per Testsuite bitgenau gegen die C++-Referenz verifiziert (`tests/test_transcold_protocol.py`).

## Features

- Vollständige Home Assistant Climate Entity (assumed state, da IR one-way)
- Kompatibel mit der **HVAC Card**
- **Broadlink**: sendet Base64-Pakete (`b64:...`) über `remote.send_command` — wird automatisch erkannt
- **ESPHome**: sendet rohe IR-Timings über eine ESPHome-Action (siehe unten)
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
python tests/test_transcold_protocol.py
```

Vergleicht den Encoder gegen eine unabhängige Transkription von `IRsend::sendTranscold` und die im IRremoteESP8266-Header dokumentierten Raw-Captures.

## Unterstützte Geräte

- Transcold M1-F-NO-6
- Andere Transcold-Modelle mit kompatiblem IR-Protokoll

## Credits

IR-Protokoll basiert auf [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) von crankyoldgit.
