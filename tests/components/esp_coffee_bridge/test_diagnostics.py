"""Diagnostics tests for ESP Coffee Bridge."""

from __future__ import annotations

from homeassistant.components.diagnostics import REDACTED
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.esp_coffee_bridge.const import (
    DOMAIN,
    machine_identifier,
)
from custom_components.esp_coffee_bridge.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

from .conftest import BRIDGE_ID, HOST, MACHINE_ONE, PORT


async def test_diagnostics_redact_sensitive_bridge_fields(hass, api_routes) -> None:
    """Diagnostics should redact network-sensitive bridge data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"ESP Coffee Bridge ({HOST})",
        data={"host": HOST, "port": PORT},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["data"]["host"] == REDACTED
    assert diagnostics["status"]["apPassword"] == REDACTED

    device_registry = dr.async_get(hass)
    machine_device = device_registry.async_get_device(
        identifiers={(DOMAIN, machine_identifier(BRIDGE_ID, MACHINE_ONE["serial"]))}
    )
    device_data = await async_get_device_diagnostics(hass, entry, machine_device)

    assert device_data["machine"]["serial"] == MACHINE_ONE["serial"]
    assert device_data["recipes"][0]["title"] == "Espresso"
