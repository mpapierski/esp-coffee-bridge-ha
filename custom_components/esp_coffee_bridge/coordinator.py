"""Coordinator and runtime helpers for the ESP Coffee Bridge integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EspCoffeeBridgeApiError,
    EspCoffeeBridgeClient,
    EspCoffeeBridgeConnectionError,
    EspCoffeeBridgeError,
    EspCoffeeBridgeInvalidResponseError,
)
from .const import (
    CONF_BRIDGE_POLL_SECONDS,
    CONF_DEEP_POLL_SECONDS,
    CONF_SUMMARY_POLL_SECONDS,
    DEFAULT_BRIDGE_POLL_SECONDS,
    DEFAULT_DEEP_POLL_SECONDS,
    DEFAULT_POST_ACTION_REFRESH_DELAY,
    DEFAULT_SUMMARY_POLL_SECONDS,
    DOMAIN,
    MANUFACTURER_BRIDGE,
    MODEL_BRIDGE,
    bridge_identifier,
    machine_identifier,
)
from .models import (
    BridgeInfo,
    MachineInfo,
    MachineSummary,
    RecipeDescriptor,
    SettingValue,
    StatValue,
)

LOGGER = logging.getLogger(__name__)

MachineListener = Callable[["MachineRuntime"], None]
RecipeListener = Callable[[str, tuple[RecipeDescriptor, ...]], None]
StatListener = Callable[[str, tuple[str, ...]], None]
SettingListener = Callable[[str, tuple[str, ...]], None]


@dataclass(slots=True)
class BridgeSnapshot:
    """Top-level bridge coordinator data."""

    status: dict[str, Any]
    machines: dict[str, MachineInfo]


@dataclass(slots=True)
class MachineRuntime:
    """Runtime container for one saved machine."""

    machine: MachineInfo
    summary_coordinator: DataUpdateCoordinator[MachineSummary | None]
    stats_coordinator: DataUpdateCoordinator[dict[str, StatValue]]
    settings_coordinator: DataUpdateCoordinator[dict[str, SettingValue]]
    recipes: tuple[RecipeDescriptor, ...] = ()
    cleanup_callbacks: list[CALLBACK_TYPE] = field(default_factory=list)


@dataclass(slots=True)
class EspCoffeeBridgeRuntimeData:
    """Shared runtime state for one bridge config entry."""

    hass: HomeAssistant
    entry: ConfigEntry
    client: EspCoffeeBridgeClient
    bridge_info: BridgeInfo
    bridge_coordinator: DataUpdateCoordinator[BridgeSnapshot]
    machine_runtimes: dict[str, MachineRuntime] = field(default_factory=dict)
    known_stat_keys: dict[str, set[str]] = field(default_factory=dict)
    known_setting_keys: dict[str, set[str]] = field(default_factory=dict)
    entity_ids: dict[str, set[str]] = field(default_factory=dict)
    machine_listeners: list[MachineListener] = field(default_factory=list)
    recipe_listeners: list[RecipeListener] = field(default_factory=list)
    stat_listeners: list[StatListener] = field(default_factory=list)
    setting_listeners: list[SettingListener] = field(default_factory=list)
    delayed_refresh_unsubs: dict[str, CALLBACK_TYPE] = field(default_factory=dict)

    def bridge_identifier(self) -> str:
        """Return the bridge registry identifier."""

        return bridge_identifier(self.bridge_info.bridge_id)

    def machine_identifier(self, serial: str) -> str:
        """Return the machine registry identifier."""

        return machine_identifier(self.bridge_info.bridge_id, serial)

    def get_machine_runtime(self, serial: str) -> MachineRuntime:
        """Return runtime data for one machine."""

        return self.machine_runtimes[serial]

    @callback
    def add_machine_listener(self, listener: MachineListener) -> CALLBACK_TYPE:
        """Register a listener for newly discovered machines."""

        self.machine_listeners.append(listener)
        return lambda: self.machine_listeners.remove(listener)

    @callback
    def add_recipe_listener(self, listener: RecipeListener) -> CALLBACK_TYPE:
        """Register a listener for new machine recipes."""

        self.recipe_listeners.append(listener)
        return lambda: self.recipe_listeners.remove(listener)

    @callback
    def add_stat_listener(self, listener: StatListener) -> CALLBACK_TYPE:
        """Register a listener for discovered statistic keys."""

        self.stat_listeners.append(listener)
        return lambda: self.stat_listeners.remove(listener)

    @callback
    def add_setting_listener(self, listener: SettingListener) -> CALLBACK_TYPE:
        """Register a listener for discovered setting keys."""

        self.setting_listeners.append(listener)
        return lambda: self.setting_listeners.remove(listener)

    @callback
    def register_entity_id(self, serial: str, entity_id: str) -> None:
        """Track entity registry IDs for cleanup when a machine disappears."""

        self.entity_ids.setdefault(serial, set()).add(entity_id)

    async def async_cleanup_removed_machine(self, serial: str) -> None:
        """Remove registry entries for a machine that disappeared from the bridge."""

        machine_runtime = self.machine_runtimes.get(serial)
        if machine_runtime is not None:
            for unsub in machine_runtime.cleanup_callbacks:
                unsub()
            machine_runtime.cleanup_callbacks.clear()

        if delayed_unsub := self.delayed_refresh_unsubs.pop(serial, None):
            delayed_unsub()

        entity_registry = er.async_get(self.hass)
        for entity_id in self.entity_ids.pop(serial, set()):
            if entity_registry.async_get(entity_id) is not None:
                entity_registry.async_remove(entity_id)

        device_registry = dr.async_get(self.hass)
        if device := device_registry.async_get_device(
            identifiers={(DOMAIN, self.machine_identifier(serial))}
        ):
            device_registry.async_remove_device(device.id)

        self.known_stat_keys.pop(serial, None)
        self.known_setting_keys.pop(serial, None)

    async def async_shutdown(self) -> None:
        """Release runtime callbacks during config-entry unload."""

        for serial in list(self.machine_runtimes):
            machine_runtime = self.machine_runtimes[serial]
            for unsub in machine_runtime.cleanup_callbacks:
                unsub()
            machine_runtime.cleanup_callbacks.clear()

        for delayed_unsub in self.delayed_refresh_unsubs.values():
            delayed_unsub()
        self.delayed_refresh_unsubs.clear()

    async def async_post_action_refresh(
        self,
        serial: str,
        *,
        include_deep: bool = False,
        include_settings: bool = False,
    ) -> None:
        """Refresh live coordinators after a successful action."""

        machine_runtime = self.machine_runtimes.get(serial)
        if machine_runtime is None:
            return

        await machine_runtime.summary_coordinator.async_refresh()
        if include_deep:
            await machine_runtime.stats_coordinator.async_refresh()
        if include_settings:
            await machine_runtime.settings_coordinator.async_refresh()

        self._emit_stat_keys(serial)
        self._emit_setting_keys(serial)

        if delayed_unsub := self.delayed_refresh_unsubs.pop(serial, None):
            delayed_unsub()

        @callback
        def _handle_delayed_refresh(_now) -> None:
            self.delayed_refresh_unsubs.pop(serial, None)
            self.hass.async_create_task(
                self._async_delayed_refresh(
                    serial,
                    include_deep=include_deep,
                    include_settings=include_settings,
                )
            )

        self.delayed_refresh_unsubs[serial] = async_call_later(
            self.hass,
            DEFAULT_POST_ACTION_REFRESH_DELAY,
            _handle_delayed_refresh,
        )

    async def _async_delayed_refresh(
        self,
        serial: str,
        *,
        include_deep: bool,
        include_settings: bool,
    ) -> None:
        """Run the delayed post-action refresh."""

        machine_runtime = self.machine_runtimes.get(serial)
        if machine_runtime is None:
            return

        await machine_runtime.summary_coordinator.async_refresh()
        if include_deep:
            await machine_runtime.stats_coordinator.async_refresh()
        if include_settings:
            await machine_runtime.settings_coordinator.async_refresh()

        self._emit_stat_keys(serial)
        self._emit_setting_keys(serial)

    @callback
    def _emit_machine_added(self, machine_runtime: MachineRuntime) -> None:
        for listener in list(self.machine_listeners):
            listener(machine_runtime)

    @callback
    def _emit_recipes(self, serial: str) -> None:
        recipes = self.machine_runtimes[serial].recipes
        for listener in list(self.recipe_listeners):
            listener(serial, recipes)

    @callback
    def _emit_stat_keys(self, serial: str) -> None:
        machine_runtime = self.machine_runtimes.get(serial)
        if machine_runtime is None or not machine_runtime.stats_coordinator.data:
            return
        current_keys = set(machine_runtime.stats_coordinator.data)
        new_keys = tuple(
            sorted(current_keys - self.known_stat_keys.setdefault(serial, set()))
        )
        if not new_keys:
            return
        self.known_stat_keys[serial].update(new_keys)
        for listener in list(self.stat_listeners):
            listener(serial, new_keys)

    @callback
    def _emit_setting_keys(self, serial: str) -> None:
        machine_runtime = self.machine_runtimes.get(serial)
        if machine_runtime is None or not machine_runtime.settings_coordinator.data:
            return
        current_keys = set(machine_runtime.settings_coordinator.data)
        new_keys = tuple(
            sorted(current_keys - self.known_setting_keys.setdefault(serial, set()))
        )
        if not new_keys:
            return
        self.known_setting_keys[serial].update(new_keys)
        for listener in list(self.setting_listeners):
            listener(serial, new_keys)


def make_bridge_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: EspCoffeeBridgeClient,
) -> DataUpdateCoordinator[BridgeSnapshot]:
    """Create the top-level bridge coordinator."""

    async def _async_update() -> BridgeSnapshot:
        try:
            status = await client.async_get_status()
            machines = {
                machine.serial: machine for machine in await client.async_get_machines()
            }
        except (
            EspCoffeeBridgeApiError,
            EspCoffeeBridgeConnectionError,
            EspCoffeeBridgeInvalidResponseError,
        ) as err:
            raise UpdateFailed(str(err)) from err
        return BridgeSnapshot(status=status, machines=machines)

    return DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}-bridge",
        update_method=_async_update,
        update_interval=timedelta(
            seconds=entry.options.get(
                CONF_BRIDGE_POLL_SECONDS,
                DEFAULT_BRIDGE_POLL_SECONDS,
            )
        ),
    )


def make_summary_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: EspCoffeeBridgeClient,
    serial: str,
) -> DataUpdateCoordinator[MachineSummary | None]:
    """Create the per-machine summary coordinator."""

    async def _async_update() -> MachineSummary:
        try:
            return await client.async_get_summary(serial)
        except EspCoffeeBridgeError as err:
            raise UpdateFailed(str(err)) from err

    return DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}-summary-{serial}",
        update_method=_async_update,
        update_interval=timedelta(
            seconds=entry.options.get(
                CONF_SUMMARY_POLL_SECONDS,
                DEFAULT_SUMMARY_POLL_SECONDS,
            )
        ),
    )


def make_stats_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: EspCoffeeBridgeClient,
    serial: str,
) -> DataUpdateCoordinator[dict[str, StatValue]]:
    """Create the per-machine stats coordinator."""

    async def _async_update() -> dict[str, StatValue]:
        try:
            return await client.async_get_stats(serial)
        except EspCoffeeBridgeError as err:
            raise UpdateFailed(str(err)) from err

    return DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}-stats-{serial}",
        update_method=_async_update,
        update_interval=timedelta(
            seconds=entry.options.get(
                CONF_DEEP_POLL_SECONDS,
                DEFAULT_DEEP_POLL_SECONDS,
            )
        ),
    )


def make_settings_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: EspCoffeeBridgeClient,
    serial: str,
) -> DataUpdateCoordinator[dict[str, SettingValue]]:
    """Create the per-machine settings coordinator."""

    async def _async_update() -> dict[str, SettingValue]:
        try:
            return await client.async_get_settings(serial)
        except EspCoffeeBridgeError as err:
            raise UpdateFailed(str(err)) from err

    return DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}-settings-{serial}",
        update_method=_async_update,
        update_interval=timedelta(
            seconds=entry.options.get(
                CONF_DEEP_POLL_SECONDS,
                DEFAULT_DEEP_POLL_SECONDS,
            )
        ),
    )


async def async_sync_bridge_device(runtime: EspCoffeeBridgeRuntimeData) -> None:
    """Create or update the bridge device registry entry."""

    status = (
        runtime.bridge_coordinator.data.status
        if runtime.bridge_coordinator.data
        else {}
    )
    device_registry = dr.async_get(runtime.hass)
    device_registry.async_get_or_create(
        config_entry_id=runtime.entry.entry_id,
        identifiers={(DOMAIN, runtime.bridge_identifier())},
        manufacturer=MANUFACTURER_BRIDGE,
        model=MODEL_BRIDGE,
        name=runtime.entry.title,
        serial_number=runtime.bridge_info.bridge_id,
        sw_version=status.get("appVersion"),
        configuration_url=runtime.client.base_url,
    )


async def async_sync_machines(runtime: EspCoffeeBridgeRuntimeData) -> None:
    """Synchronize child machine runtime objects with the bridge snapshot."""

    snapshot = runtime.bridge_coordinator.data
    if snapshot is None:
        return

    current_serials = set(runtime.machine_runtimes)
    bridge_serials = set(snapshot.machines)

    for serial in current_serials - bridge_serials:
        await runtime.async_cleanup_removed_machine(serial)
        runtime.machine_runtimes.pop(serial, None)

    for serial, machine in snapshot.machines.items():
        machine_runtime = runtime.machine_runtimes.get(serial)
        is_new = machine_runtime is None

        if machine_runtime is None:
            machine_runtime = MachineRuntime(
                machine=machine,
                summary_coordinator=make_summary_coordinator(
                    runtime.hass, runtime.entry, runtime.client, serial
                ),
                stats_coordinator=make_stats_coordinator(
                    runtime.hass, runtime.entry, runtime.client, serial
                ),
                settings_coordinator=make_settings_coordinator(
                    runtime.hass, runtime.entry, runtime.client, serial
                ),
            )
            runtime.machine_runtimes[serial] = machine_runtime
            _register_machine_runtime_callbacks(runtime, serial, machine_runtime)
        else:
            machine_runtime.machine = machine

        await _async_prime_machine(runtime, serial, machine_runtime, is_new=is_new)
        await _async_sync_machine_device(runtime, machine_runtime.machine)

        if is_new:
            runtime._emit_machine_added(machine_runtime)
            runtime._emit_recipes(serial)
            runtime._emit_stat_keys(serial)
            runtime._emit_setting_keys(serial)


def _register_machine_runtime_callbacks(
    runtime: EspCoffeeBridgeRuntimeData,
    serial: str,
    machine_runtime: MachineRuntime,
) -> None:
    """Register coordinator listeners for dynamic key discovery."""

    machine_runtime.cleanup_callbacks.append(
        machine_runtime.stats_coordinator.async_add_listener(
            lambda: runtime._emit_stat_keys(serial)
        )
    )
    machine_runtime.cleanup_callbacks.append(
        machine_runtime.settings_coordinator.async_add_listener(
            lambda: runtime._emit_setting_keys(serial)
        )
    )


async def _async_prime_machine(
    runtime: EspCoffeeBridgeRuntimeData,
    serial: str,
    machine_runtime: MachineRuntime,
    *,
    is_new: bool,
) -> None:
    """Load initial machine data without failing the whole config entry."""

    if is_new or not machine_runtime.recipes:
        try:
            machine_runtime.recipes = tuple(
                await runtime.client.async_get_recipes(serial)
            )
        except EspCoffeeBridgeError as err:
            LOGGER.debug("Failed to fetch recipes for %s: %s", serial, err)

    await machine_runtime.summary_coordinator.async_refresh()
    await machine_runtime.stats_coordinator.async_refresh()
    await machine_runtime.settings_coordinator.async_refresh()


async def _async_sync_machine_device(
    runtime: EspCoffeeBridgeRuntimeData,
    machine: MachineInfo,
) -> None:
    """Create or update the child machine device."""

    device_registry = dr.async_get(runtime.hass)
    connections: set[tuple[str, str]] = set()
    if machine.address:
        connections.add((dr.CONNECTION_BLUETOOTH, machine.address.upper()))

    device_registry.async_get_or_create(
        config_entry_id=runtime.entry.entry_id,
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
