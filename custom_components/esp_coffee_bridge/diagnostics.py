"""Diagnostics for ESP Coffee Bridge."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SENSITIVE_STATUS_KEYS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime = entry.runtime_data
    snapshot = runtime.bridge_coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), {CONF_HOST}),
            "options": dict(entry.options),
        },
        "bridge": asdict(runtime.bridge_info),
        "status": async_redact_data(
            snapshot.status if snapshot else {}, SENSITIVE_STATUS_KEYS
        ),
        "machines": {
            serial: machine.raw
            for serial, machine in (snapshot.machines.items() if snapshot else [])
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: dr.DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a bridge or machine device."""

    runtime = entry.runtime_data
    machine_identifier = next(
        (
            value
            for domain, value in device.identifiers
            if domain == DOMAIN and value.startswith("machine::")
        ),
        None,
    )
    if machine_identifier is None:
        return await async_get_config_entry_diagnostics(hass, entry)

    _, _bridge_id, serial = machine_identifier.split("::", 2)
    machine_runtime = runtime.get_machine_runtime(serial)
    return {
        "machine": machine_runtime.machine.raw,
        "recipes": [asdict(recipe) for recipe in machine_runtime.recipes],
        "summary": None
        if machine_runtime.summary_coordinator.data is None
        else asdict(machine_runtime.summary_coordinator.data),
        "stats": {
            key: asdict(value)
            for key, value in (machine_runtime.stats_coordinator.data or {}).items()
        },
        "settings": {
            key: asdict(value)
            for key, value in (machine_runtime.settings_coordinator.data or {}).items()
        },
    }
