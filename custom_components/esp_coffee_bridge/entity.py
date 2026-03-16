"""Shared entity helpers for the ESP Coffee Bridge integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER_BRIDGE,
    MODEL_BRIDGE,
    bridge_identifier,
    machine_entity_unique_id,
)
from .coordinator import EspCoffeeBridgeRuntimeData, MachineRuntime
from .models import MachineInfo


def build_bridge_device_info(runtime: EspCoffeeBridgeRuntimeData) -> DeviceInfo:
    """Build the bridge device info."""

    status = (
        runtime.bridge_coordinator.data.status
        if runtime.bridge_coordinator.data
        else {}
    )
    return DeviceInfo(
        identifiers={(DOMAIN, bridge_identifier(runtime.bridge_info.bridge_id))},
        manufacturer=MANUFACTURER_BRIDGE,
        model=MODEL_BRIDGE,
        name=runtime.entry.title,
        serial_number=runtime.bridge_info.bridge_id,
        sw_version=status.get("appVersion"),
        configuration_url=runtime.client.base_url,
    )


def build_machine_device_info(
    runtime: EspCoffeeBridgeRuntimeData,
    machine: MachineInfo,
) -> DeviceInfo:
    """Build the machine device info."""

    connections: set[tuple[str, str]] = set()
    if machine.address:
        connections.add((dr.CONNECTION_BLUETOOTH, machine.address.upper()))

    return DeviceInfo(
        identifiers={(DOMAIN, runtime.machine_identifier(machine.serial))},
        via_device=(DOMAIN, runtime.bridge_identifier()),
        connections=connections or None,
        manufacturer=machine.manufacturer or "NIVONA",
        model=machine.model_name or machine.model or machine.family_key,
        model_id=machine.model_code,
        name=machine.alias or machine.model_name or machine.serial,
        serial_number=machine.serial,
        sw_version=machine.software_revision or machine.firmware_revision,
    )


class EspCoffeeBridgeEntityMixin:
    """Common helpers shared by all machine entities."""

    _attr_has_entity_name = True

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, suffix: str
    ) -> None:
        """Initialize the entity mixin."""

        self.runtime = runtime
        self.serial = serial
        self._attr_unique_id = machine_entity_unique_id(
            runtime.bridge_info.bridge_id,
            serial,
            suffix,
        )

    @property
    def machine_runtime(self) -> MachineRuntime:
        """Return the current runtime object for the machine."""

        return self.runtime.get_machine_runtime(self.serial)

    @property
    def machine(self) -> MachineInfo:
        """Return the current machine metadata."""

        return self.machine_runtime.machine

    @property
    def device_info(self) -> DeviceInfo:
        """Return the Home Assistant device description."""

        return build_machine_device_info(self.runtime, self.machine)

    async def async_added_to_hass(self) -> None:
        """Track entity IDs for later cleanup."""

        await super().async_added_to_hass()
        if self.entity_id:
            self.runtime.register_entity_id(self.serial, self.entity_id)


class EspCoffeeBridgeCoordinatorEntity(
    EspCoffeeBridgeEntityMixin,
    CoordinatorEntity,
):
    """Coordinator-backed machine entity."""

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, suffix: str, coordinator
    ):
        """Initialize the coordinator-backed entity."""

        EspCoffeeBridgeEntityMixin.__init__(self, runtime, serial, suffix)
        CoordinatorEntity.__init__(self, coordinator)
