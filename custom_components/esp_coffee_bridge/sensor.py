"""Sensor entities for ESP Coffee Bridge."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    STAT_SECTION_MAINTENANCE,
    SUMMARY_STATES,
    bridge_entity_unique_id,
)
from .coordinator import EspCoffeeBridgeRuntimeData, MachineRuntime
from .entity import EspCoffeeBridgeCoordinatorEntity, build_bridge_device_info


def _build_base_entities(
    runtime: EspCoffeeBridgeRuntimeData, serial: str
) -> list[SensorEntity]:
    machine_runtime = runtime.get_machine_runtime(serial)
    return [
        EspCoffeeBridgeStatusSensor(
            runtime,
            serial,
            machine_runtime.summary_coordinator,
        ),
        EspCoffeeBridgeOperatorMessageSensor(
            runtime,
            serial,
            machine_runtime.summary_coordinator,
        ),
        EspCoffeeBridgeRssiSensor(
            runtime,
            serial,
            runtime.bridge_coordinator,
        ),
        EspCoffeeBridgeProgressSensor(
            runtime,
            serial,
            machine_runtime.summary_coordinator,
        ),
    ]


def _build_stat_entities(
    runtime: EspCoffeeBridgeRuntimeData,
    serial: str,
    keys: tuple[str, ...],
) -> list[SensorEntity]:
    coordinator = runtime.get_machine_runtime(serial).stats_coordinator
    return [
        EspCoffeeBridgeStatSensor(runtime, serial, key, coordinator) for key in keys
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up ESP Coffee Bridge sensors."""

    runtime: EspCoffeeBridgeRuntimeData = entry.runtime_data
    known_serials = set(runtime.machine_runtimes)
    known_stat_ids = {
        f"{serial}:{key}"
        for serial, keys in runtime.known_stat_keys.items()
        for key in keys
    }

    async_add_entities(
        [EspCoffeeBridgeSavedMachineCountSensor(runtime)]
        + [
            entity
            for serial in known_serials
            for entity in (
                _build_base_entities(runtime, serial)
                + _build_stat_entities(
                    runtime,
                    serial,
                    tuple(sorted(runtime.known_stat_keys.get(serial, set()))),
                )
            )
        ]
    )

    @callback
    def _handle_machine_added(machine_runtime: MachineRuntime) -> None:
        serial = machine_runtime.machine.serial
        if serial in known_serials:
            return
        known_serials.add(serial)
        async_add_entities(_build_base_entities(runtime, serial))

    @callback
    def _handle_stats(serial: str, keys: tuple[str, ...]) -> None:
        new_keys = tuple(key for key in keys if f"{serial}:{key}" not in known_stat_ids)
        if not new_keys:
            return
        for key in new_keys:
            known_stat_ids.add(f"{serial}:{key}")
        async_add_entities(_build_stat_entities(runtime, serial, new_keys))

    entry.async_on_unload(runtime.add_machine_listener(_handle_machine_added))
    entry.async_on_unload(runtime.add_stat_listener(_handle_stats))


class EspCoffeeBridgeSavedMachineCountSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic bridge sensor for the number of saved machines."""

    _attr_name = "Saved machines"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: EspCoffeeBridgeRuntimeData) -> None:
        self.runtime = runtime
        super().__init__(runtime.bridge_coordinator)
        self._attr_unique_id = bridge_entity_unique_id(
            runtime.bridge_info.bridge_id,
            "saved_machine_count",
        )

    @property
    def device_info(self):
        return build_bridge_device_info(self.runtime)

    @property
    def native_value(self) -> int | None:
        snapshot = self.runtime.bridge_coordinator.data
        return None if snapshot is None else len(snapshot.machines)


class EspCoffeeBridgeStatusSensor(
    EspCoffeeBridgeCoordinatorEntity,
    SensorEntity,
):
    """Expose the high-level machine state."""

    _attr_name = "Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(SUMMARY_STATES)

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, coordinator
    ) -> None:
        super().__init__(runtime, serial, "status", coordinator)

    @property
    def native_value(self) -> str | None:
        summary = self.coordinator.data
        return None if summary is None else summary.summary

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        summary = self.coordinator.data
        if summary is None:
            return None
        return {
            "process": summary.process,
            "process_label": summary.process_label,
            "sub_process": summary.sub_process,
            "sub_process_label": summary.sub_process_label,
            "message": summary.message,
            "message_label": summary.message_label,
        }


class EspCoffeeBridgeOperatorMessageSensor(
    EspCoffeeBridgeCoordinatorEntity,
    SensorEntity,
):
    """Expose the current operator message."""

    _attr_name = "Operator message"

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, coordinator
    ) -> None:
        super().__init__(runtime, serial, "operator_message", coordinator)

    @property
    def native_value(self) -> str | None:
        summary = self.coordinator.data
        return None if summary is None else summary.message_label


class EspCoffeeBridgeRssiSensor(
    EspCoffeeBridgeCoordinatorEntity,
    SensorEntity,
):
    """Expose saved-machine RSSI."""

    _attr_name = "RSSI"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, coordinator
    ) -> None:
        super().__init__(runtime, serial, "rssi", coordinator)

    @property
    def native_value(self) -> int | None:
        return self.machine.last_seen_rssi


class EspCoffeeBridgeProgressSensor(
    EspCoffeeBridgeCoordinatorEntity,
    SensorEntity,
):
    """Expose machine progress."""

    _attr_name = "Progress"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, coordinator
    ) -> None:
        super().__init__(runtime, serial, "progress", coordinator)

    @property
    def native_value(self) -> int | None:
        summary = self.coordinator.data
        return None if summary is None else summary.progress


class EspCoffeeBridgeStatSensor(
    EspCoffeeBridgeCoordinatorEntity,
    SensorEntity,
):
    """Expose one machine statistic."""

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, key: str, coordinator
    ) -> None:
        self.stat_key = key
        super().__init__(runtime, serial, f"stat_{key}", coordinator)

    @property
    def name(self) -> str | None:
        stat = (
            self.coordinator.data.get(self.stat_key) if self.coordinator.data else None
        )
        return (
            stat.title if stat is not None else self.stat_key.replace("_", " ").title()
        )

    @property
    def entity_category(self) -> EntityCategory | None:
        stat = (
            self.coordinator.data.get(self.stat_key) if self.coordinator.data else None
        )
        if stat is None or stat.section != STAT_SECTION_MAINTENANCE:
            return None
        return EntityCategory.DIAGNOSTIC

    @property
    def native_unit_of_measurement(self) -> str | None:
        stat = (
            self.coordinator.data.get(self.stat_key) if self.coordinator.data else None
        )
        if stat is None:
            return None
        return PERCENTAGE if stat.unit == "percent" else stat.unit

    @property
    def native_value(self) -> int | float | str | bool | None:
        stat = (
            self.coordinator.data.get(self.stat_key) if self.coordinator.data else None
        )
        return None if stat is None else stat.raw_value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        stat = (
            self.coordinator.data.get(self.stat_key) if self.coordinator.data else None
        )
        if stat is None:
            return None
        return {
            "section": stat.section,
            "unit": stat.unit,
            "register_id": stat.register_id,
        }
