# Onkyo Dimmer

A small Home Assistant custom integration that adds a `select` entity for
controlling the front panel display brightness of Onkyo / Pioneer network
receivers.

The built-in [Onkyo integration](https://www.home-assistant.io/integrations/onkyo)
does not support the display dimmer. This integration adds it by reusing the
connection that the built-in integration already holds, so it does not use an
additional eISCP connection slot on the receiver.

Tested on: Pioneer VSX-LX505.

## Features

- `select.onkyo_display_dimmer` entity with four modes:
  `bright`, `dim`, `dark`, `off` (eISCP commands `DIM00` to `DIM03`)
- Reads the current state from the receiver and follows changes made with the
  remote control or the front panel
- Restores the last known state after a Home Assistant restart
- No extra dependencies

## Requirements

- Home Assistant with the built-in Onkyo integration set up and working
- "Network Standby" enabled on the receiver

## Installation

### HACS (custom repository)

1. Open HACS, click the three dots menu, then **Custom repositories**.
2. Add this repository URL and choose the category **Integration**.
3. Download **Onkyo Dimmer**.
4. Restart Home Assistant.

### Manual

Copy the `custom_components/onkyo_dimmer` folder into the
`custom_components` folder of your Home Assistant configuration, then restart
Home Assistant.

## Configuration

Add this to `configuration.yaml` and restart Home Assistant:

```yaml
onkyo_dimmer:
```

The entity `select.onkyo_display_dimmer` will appear.

### Example automation

Dim the display in the evening:

```yaml
automation:
  - alias: "Dim receiver display in the evening"
    triggers:
      - trigger: time
        at: "21:00:00"
    actions:
      - action: select.select_option
        target:
          entity_id: select.onkyo_display_dimmer
        data:
          option: dim
```

## Modes

| Option   | Command | Description                                 |
|----------|---------|---------------------------------------------|
| `bright` | DIM00   | Full brightness                             |
| `dim`    | DIM01   | Dimmed                                      |
| `dark`   | DIM02   | Darker                                      |
| `off`    | DIM03   | Display off (if the model supports it)      |

Other models may support different values. For example, `DIM08` returns `N/A`
on the VSX-LX505, so it is not exposed.

## How it works

The `aioonkyo` library used by the built-in integration has no dimmer
messages. This integration finds the built-in integration's receiver manager,
sends a raw `DIM` instruction through its existing connection, and listens to
the incoming message stream for `DIM` status messages.

## Limitations

- It relies on internal structures of the built-in Onkyo integration
  (`entry.runtime_data.manager`, its callbacks and `write()`), which are not a
  public API. A future Home Assistant update may break it.
- The entity is unavailable while the built-in Onkyo integration is not loaded
  or not connected.
- Only the display dimmer is supported. For everything else use the built-in
  integration.

## Troubleshooting

Enable debug logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.onkyo_dimmer: debug
```

- `RX: b'DIM01'` lines mean status messages reach the integration.
- If commands fail, open an issue and include the full traceback and your
  Home Assistant version.

## Disclaimer

This project is not affiliated with Onkyo, Pioneer, Integra or Home Assistant.
Use at your own risk.

## License

This project is licensed under the [MIT License](LICENSE).
