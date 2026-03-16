# ESP Coffee Bridge Home Assistant Integration

Custom Home Assistant integration for the `esp-coffee-bridge` ESP32 app.

This integration connects to one bridge over local HTTP and exposes:

- one bridge device
- one child device per saved coffee machine
- binary sensors for online state and confirmation prompts
- sensors for status, operator message, RSSI, progress, and machine stats
- select entities for writable machine settings
- brew buttons for standard recipes
- a `esp_coffee_bridge.brew` action for recipe-based or selector-based brewing

## Firmware contract

This integration requires bridge firmware that exposes:

- `GET /api/status` with `appName == "esp-coffee-bridge"`, `apiVersion`, and stable `bridgeId`
- `GET /api/machines/{serial}/settings` with `values.<key>.options`

The matching firmware changes were implemented in the companion source tree at `/Users/michal/Dev/nivona`.

## Installation

1. Copy this repository into Home Assistant as a custom integration, or install it through HACS as a local/custom repository.
2. Restart Home Assistant.
3. Add `ESP Coffee Bridge` from the integrations UI.
4. Enter the bridge host and port.

## Notes

- The integration assumes the bridge web UI remains the source of truth for Wi-Fi and saved-machine management.
- The bridge API is unauthenticated local HTTP. Run it only on a trusted LAN.
- Stats and settings entities appear only after the bridge successfully returns those live endpoints.

## Development

Local checks used for this implementation:

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
```
