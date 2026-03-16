"""Binary sensors for ESP Coffee Bridge."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .coordinator import EspCoffeeBridgeRuntimeData, MachineRuntime
from .entity import EspCoffeeBridgeCoordinatorEntity


def _build_entities(
    runtime: EspCoffeeBridgeRuntimeData, serial: str
) -> list[BinarySensorEntity]:
    return [
        EspCoffeeBridgeOnlineBinarySensor(
            runtime,
            serial,
            runtime.bridge_coordinator,
        ),
        EspCoffeeBridgeNeedsConfirmationBinarySensor(
            runtime,
            serial,
            runtime.get_machine_runtime(serial).summary_coordinator,
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up ESP Coffee Bridge binary sensors."""

    runtime: EspCoffeeBridgeRuntimeData = entry.runtime_data
    known_serials = set(runtime.machine_runtimes)
    async_add_entities(
        [
            entity
            for serial in known_serials
            for entity in _build_entities(runtime, serial)
        ]
    )

    @callback
    def _handle_machine_added(machine_runtime: MachineRuntime) -> None:
        serial = machine_runtime.machine.serial
        if serial in known_serials:
            return
        known_serials.add(serial)
        async_add_entities(_build_entities(runtime, serial))

    entry.async_on_unload(runtime.add_machine_listener(_handle_machine_added))


class EspCoffeeBridgeOnlineBinarySensor(
    EspCoffeeBridgeCoordinatorEntity,
    BinarySensorEntity,
):
    """Expose saved-machine online presence."""

    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, coordinator
    ) -> None:
        super().__init__(runtime, serial, "online", coordinator)

    @property
    def is_on(self) -> bool:
        """Return true if the bridge reports the machine as online."""

        return self.machine.online


class EspCoffeeBridgeNeedsConfirmationBinarySensor(
    EspCoffeeBridgeCoordinatorEntity,
    BinarySensorEntity,
):
    """Expose whether the machine needs a host confirmation."""

    _attr_name = "Needs confirmation"

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, coordinator
    ) -> None:
        super().__init__(runtime, serial, "needs_confirmation", coordinator)

    @property
    def is_on(self) -> bool:
        """Return true if the current summary suggests a confirm action."""

        summary = self.coordinator.data
        return bool(summary and summary.host_confirm_suggested)
