"""Config-flow coverage for ESP Coffee Bridge."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_RECONFIGURE
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.esp_coffee_bridge.const import CONF_PORT, DOMAIN

from .conftest import HOST, PORT


async def test_user_flow_creates_entry(hass, api_routes) -> None:
    """The user flow should validate the bridge and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={"host": HOST, "port": PORT},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == f"ESP Coffee Bridge ({HOST})"
    assert result["data"] == {"host": HOST, "port": PORT}


async def test_reconfigure_updates_existing_entry(hass, api_routes) -> None:
    """The reconfigure flow should update host and port in-place."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="ESP Coffee Bridge", data={"host": HOST, "port": PORT}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        data={"host": "http://bridge.local", "port": 8080},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PORT] == 8080
