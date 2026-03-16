"""Integration setup and entity tests."""

from __future__ import annotations

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.esp_coffee_bridge.const import (
    ATTR_RECIPE,
    ATTR_STRENGTH_BEANS,
    ATTR_TEMPERATURE,
    DOMAIN,
    SERVICE_BREW,
    bridge_entity_unique_id,
    bridge_identifier,
    machine_entity_unique_id,
    machine_identifier,
)

from .conftest import BRIDGE_ID, HOST, MACHINE_ONE, MACHINE_TWO, PORT


async def test_setup_entry_creates_devices_and_entities(hass, api_routes) -> None:
    """Setting up the entry should create bridge and machine entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"ESP Coffee Bridge ({HOST})",
        data={"host": HOST, "port": PORT},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    bridge_sensor = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, bridge_entity_unique_id(BRIDGE_ID, "saved_machine_count")
    )
    status_sensor = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        machine_entity_unique_id(BRIDGE_ID, MACHINE_ONE["serial"], "status"),
    )
    online_sensor = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        machine_entity_unique_id(BRIDGE_ID, MACHINE_ONE["serial"], "online"),
    )
    stat_sensor = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        machine_entity_unique_id(BRIDGE_ID, MACHINE_ONE["serial"], "stat_espresso"),
    )
    select_entity = entity_registry.async_get_entity_id(
        "select",
        DOMAIN,
        machine_entity_unique_id(
            BRIDGE_ID, MACHINE_ONE["serial"], "setting_water_hardness"
        ),
    )

    assert hass.states.get(bridge_sensor).state == "1"
    assert hass.states.get(status_sensor).state == "ready"
    assert hass.states.get(online_sensor).state == "on"
    assert hass.states.get(stat_sensor).state == "42"
    assert hass.states.get(select_entity).state == "medium"

    device_registry = dr.async_get(hass)
    bridge_device = device_registry.async_get_device(
        identifiers={(DOMAIN, bridge_identifier(BRIDGE_ID))}
    )
    machine_device = device_registry.async_get_device(
        identifiers={(DOMAIN, machine_identifier(BRIDGE_ID, MACHINE_ONE["serial"]))}
    )

    assert bridge_device is not None
    assert machine_device is not None
    assert machine_device.via_device_id == bridge_device.id


async def test_brew_service_posts_validated_payload(hass, api_routes) -> None:
    """The brew service should resolve the recipe and forward normalized overrides."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"ESP Coffee Bridge ({HOST})",
        data={"host": HOST, "port": PORT},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    machine_device = device_registry.async_get_device(
        identifiers={(DOMAIN, machine_identifier(BRIDGE_ID, MACHINE_ONE["serial"]))}
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_BREW,
        {
            ATTR_DEVICE_ID: machine_device.id,
            ATTR_RECIPE: "espresso",
            ATTR_STRENGTH_BEANS: 3,
            ATTR_TEMPERATURE: "high",
        },
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()

    assert response["ok"] is True
    assert api_routes["captured"]["brew"] == {
        "selector": 0,
        "strengthBeans": 3,
        "temperature": 1,
    }


async def test_select_entity_posts_setting_update(hass, api_routes) -> None:
    """Changing a select entity should write back to the bridge."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"ESP Coffee Bridge ({HOST})",
        data={"host": HOST, "port": PORT},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    select_entity = entity_registry.async_get_entity_id(
        "select",
        DOMAIN,
        machine_entity_unique_id(
            BRIDGE_ID, MACHINE_ONE["serial"], "setting_water_hardness"
        ),
    )

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: select_entity, "option": "hard"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert api_routes["captured"]["setting"] == {
        "key": "water_hardness",
        "value": "hard",
    }


async def test_dynamic_machine_add_and_remove(hass, api_routes) -> None:
    """Machine additions and removals on the bridge should update HA entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"ESP Coffee Bridge ({HOST})",
        data={"host": HOST, "port": PORT},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    api_routes["add_second_machine"]()
    await entry.runtime_data.bridge_coordinator.async_refresh()
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    second_online = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        machine_entity_unique_id(BRIDGE_ID, MACHINE_TWO["serial"], "online"),
    )
    assert second_online is not None

    api_routes["remove_second_machine"]()
    await entry.runtime_data.bridge_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            "binary_sensor",
            DOMAIN,
            machine_entity_unique_id(BRIDGE_ID, MACHINE_TWO["serial"], "online"),
        )
        is None
    )
