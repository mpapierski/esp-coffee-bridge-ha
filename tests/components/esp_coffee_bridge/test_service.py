"""Service tests for ESP Coffee Bridge."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import ATTR_DEVICE_ID, CONF_HOST, CONF_PORT
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.esp_coffee_bridge.const import DOMAIN, SERVICE_BREW
from custom_components.esp_coffee_bridge.models import (
    BridgeInfo,
    MachineInfo,
    MachineSummary,
    RecipeDescriptor,
)


def _bridge_info() -> BridgeInfo:
    return BridgeInfo(
        bridge_id="bridge-1234",
        api_version=1,
        app_name="esp-coffee-bridge",
        app_version="0.0.1",
        hostname="esp-coffee-bridge",
        base_url="http://bridge.local",
        raw_status={"ok": True},
    )


def _machine() -> MachineInfo:
    raw = {
        "serial": "NIV123",
        "alias": "Kitchen",
        "address": "AA:BB:CC:DD:EE:FF",
        "addressType": 0,
        "model": "NICR 756",
        "modelCode": "756",
        "modelName": "NICR 756",
        "familyKey": "700",
        "manufacturer": "NIVONA",
        "hardwareRevision": "HW1",
        "firmwareRevision": "FW1",
        "softwareRevision": "SW1",
        "ad06Hex": "",
        "ad06Ascii": "",
        "lastSeenRssi": -55,
        "lastSeenAtMs": 1234,
        "savedAtMs": 1200,
        "online": True,
    }
    return MachineInfo(
        serial=raw["serial"],
        alias=raw["alias"],
        address=raw["address"],
        address_type=raw["addressType"],
        model=raw["model"],
        model_code=raw["modelCode"],
        model_name=raw["modelName"],
        family_key=raw["familyKey"],
        manufacturer=raw["manufacturer"],
        hardware_revision=raw["hardwareRevision"],
        firmware_revision=raw["firmwareRevision"],
        software_revision=raw["softwareRevision"],
        ad06_hex=raw["ad06Hex"],
        ad06_ascii=raw["ad06Ascii"],
        last_seen_rssi=raw["lastSeenRssi"],
        last_seen_at_ms=raw["lastSeenAtMs"],
        saved_at_ms=raw["savedAtMs"],
        online=raw["online"],
        raw=raw,
    )


async def test_brew_service_targets_machine_device_and_returns_response(hass):
    """The brew action should resolve the machine device and return the bridge response."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "bridge.local", CONF_PORT: 80},
        title="ESP Coffee Bridge (bridge.local)",
    )
    entry.add_to_hass(hass)

    summary = MachineSummary(
        summary="ready",
        process=8,
        process_label="ready",
        sub_process=0,
        sub_process_label="",
        message=0,
        message_label="none",
        progress=0,
        host_confirm_suggested=False,
        raw={"summary": "ready"},
    )

    with (
        patch(
            "custom_components.esp_coffee_bridge.api.EspCoffeeBridgeClient.async_validate_bridge",
            AsyncMock(return_value=_bridge_info()),
        ),
        patch(
            "custom_components.esp_coffee_bridge.api.EspCoffeeBridgeClient.async_get_status",
            AsyncMock(
                return_value={
                    "ok": True,
                    "appName": "esp-coffee-bridge",
                    "bridgeId": "bridge-1234",
                    "apiVersion": 1,
                }
            ),
        ),
        patch(
            "custom_components.esp_coffee_bridge.api.EspCoffeeBridgeClient.async_get_machines",
            AsyncMock(return_value=[_machine()]),
        ),
        patch(
            "custom_components.esp_coffee_bridge.api.EspCoffeeBridgeClient.async_get_recipes",
            AsyncMock(
                return_value=[
                    RecipeDescriptor(selector=0, name="espresso", title="Espresso")
                ]
            ),
        ),
        patch(
            "custom_components.esp_coffee_bridge.api.EspCoffeeBridgeClient.async_get_summary",
            AsyncMock(return_value=summary),
        ),
        patch(
            "custom_components.esp_coffee_bridge.api.EspCoffeeBridgeClient.async_get_stats",
            AsyncMock(return_value={}),
        ),
        patch(
            "custom_components.esp_coffee_bridge.api.EspCoffeeBridgeClient.async_get_settings",
            AsyncMock(return_value={}),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    runtime = entry.runtime_data
    runtime.client.async_brew = AsyncMock(
        return_value={"ok": True, "historyLogged": True}
    )
    runtime.client.async_get_summary = AsyncMock(return_value=summary)
    runtime.client.async_get_stats = AsyncMock(return_value={})

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "machine::bridge-1234::NIV123")}
    )
    assert device is not None

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_BREW,
        {ATTR_DEVICE_ID: [device.id], "recipe": "espresso"},
        blocking=True,
        return_response=True,
    )

    assert response == {"ok": True, "history_logged": True}
    runtime.client.async_brew.assert_awaited_once_with("NIV123", {"selector": 0})
