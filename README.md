# Transcold IR Climate

Home Assistant Custom Integration zur Steuerung von Transcold Klimaanlagen über den Home Assistant Infrarot Proxy (z.B. Broadlink, ESPHome IR Remote, etc.).

## Features

- Vollständige Home Assistant Climate Entity
- Kompatibel mit der **HVAC Card**
- Steuerung über `remote.send_command` (Broadlink, ESPHome, etc.)
- Unterstützte Modi: Cool, Heat, Dry, Fan Only, Auto
- Lüfterstufen: Auto, Low, Medium, High
- Swing-Unterstützung
- Konfiguration über UI (Config Flow)
- HACS-kompatibel

## Installation

### HACS

1. HACS -> Integrationen -> Benutzerdefinierte Repositorys
2. URL: `https://github.com/DEIN_USERNAME/transcold_ir_climate`
3. Kategorie: **Integration**
4. Installieren

### Manuell

1. Inhalt von `custom_components/transcold_ir_climate/` nach `<config>/custom_components/transcold_ir_climate/` kopieren
2. Home Assistant neu starten

## Konfiguration

1. Einstellungen -> Geräte & Dienste -> Integration hinzufügen
2. **Transcold IR Climate** suchen
3. IR-Remote Entity auswählen (z.B. `remote.broadlink_rm4_pro`)
4. Name, Temperaturbereich und Standardmodus festlegen

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
| `command_topic` | IR-Remote Entity auswählen |
| `state_topic` | Nicht mehr nötig |
| `temperature_sensor` | Separater Sensor in HA |
| `protocol: TRANSCOLD` | Automatisch |
| `min_temp` / `max_temp` | In der UI konfigurierbar |
| `target_temp` | In der UI konfigurierbar |
| `initial_operation_mode` | In der UI konfigurierbar |

## Unterstützte Geräte

- Transcold M1-F-NO-6
- Andere Transcold-Modelle mit kompatiblem IR-Protokoll

## Credits

IR-Protokoll basiert auf [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) von crankyoldgit.
