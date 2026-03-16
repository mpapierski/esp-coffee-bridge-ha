"""Select entities for ESP Coffee Bridge."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .api import EspCoffeeBridgeApiError
from .coordinator import EspCoffeeBridgeRuntimeData
from .entity import EspCoffeeBridgeCoordinatorEntity


def _build_entities(
    runtime: EspCoffeeBridgeRuntimeData,
    serial: str,
    keys: tuple[str, ...],
) -> list[SelectEntity]:
    coordinator = runtime.get_machine_runtime(serial).settings_coordinator
    return [
        EspCoffeeBridgeSettingSelect(runtime, serial, key, coordinator) for key in keys
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up ESP Coffee Bridge selects."""

    runtime: EspCoffeeBridgeRuntimeData = entry.runtime_data
    known_keys = {
        f"{serial}:{key}"
        for serial, keys in runtime.known_setting_keys.items()
        for key in keys
    }

    async_add_entities(
        [
            entity
            for serial, keys in runtime.known_setting_keys.items()
            for entity in _build_entities(runtime, serial, tuple(sorted(keys)))
        ]
    )

    @callback
    def _handle_settings(serial: str, keys: tuple[str, ...]) -> None:
        new_keys = tuple(key for key in keys if f"{serial}:{key}" not in known_keys)
        if not new_keys:
            return
        for key in new_keys:
            known_keys.add(f"{serial}:{key}")
        async_add_entities(_build_entities(runtime, serial, new_keys))

    entry.async_on_unload(runtime.add_setting_listener(_handle_settings))


class EspCoffeeBridgeSettingSelect(
    EspCoffeeBridgeCoordinatorEntity,
    SelectEntity,
):
    """Writable select for one machine setting."""

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, key: str, coordinator
    ) -> None:
        self.setting_key = key
        super().__init__(runtime, serial, f"setting_{key}", coordinator)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""

        setting = (
            self.coordinator.data.get(self.setting_key)
            if self.coordinator.data
            else None
        )
        return None if setting is None else setting.value_label

    @property
    def name(self) -> str | None:
        """Return the entity name."""

        setting = (
            self.coordinator.data.get(self.setting_key)
            if self.coordinator.data
            else None
        )
        return (
            setting.title
            if setting is not None
            else self.setting_key.replace("_", " ").title()
        )

    @property
    def options(self) -> list[str]:
        """Return the allowed option labels."""

        setting = (
            self.coordinator.data.get(self.setting_key)
            if self.coordinator.data
            else None
        )
        return [] if setting is None else [option.label for option in setting.options]

    async def async_select_option(self, option: str) -> None:
        """Write a new setting value."""

        try:
            await self.runtime.client.async_set_setting(
                self.serial, self.setting_key, option
            )
        except EspCoffeeBridgeApiError as err:
            raise HomeAssistantError(str(err)) from err

        await self.runtime.async_post_action_refresh(
            self.serial,
            include_settings=True,
        )
