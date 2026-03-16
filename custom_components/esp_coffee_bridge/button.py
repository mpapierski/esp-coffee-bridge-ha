"""Button entities for ESP Coffee Bridge."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .api import EspCoffeeBridgeApiError
from .const import SUMMARY_STATE_READY
from .coordinator import EspCoffeeBridgeRuntimeData, MachineRuntime
from .entity import EspCoffeeBridgeCoordinatorEntity
from .models import RecipeDescriptor


def _build_base_entities(
    runtime: EspCoffeeBridgeRuntimeData, serial: str
) -> list[ButtonEntity]:
    return [
        EspCoffeeBridgeConfirmButton(
            runtime,
            serial,
            runtime.get_machine_runtime(serial).summary_coordinator,
        )
    ]


def _build_recipe_entities(
    runtime: EspCoffeeBridgeRuntimeData,
    serial: str,
    recipes: tuple[RecipeDescriptor, ...],
) -> list[ButtonEntity]:
    summary_coordinator = runtime.get_machine_runtime(serial).summary_coordinator
    return [
        EspCoffeeBridgeRecipeButton(
            runtime,
            serial,
            recipe,
            summary_coordinator,
        )
        for recipe in recipes
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up ESP Coffee Bridge buttons."""

    runtime: EspCoffeeBridgeRuntimeData = entry.runtime_data
    known_serials = set(runtime.machine_runtimes)
    known_recipe_ids = {
        f"{serial}:{recipe.selector}"
        for serial, machine_runtime in runtime.machine_runtimes.items()
        for recipe in machine_runtime.recipes
    }

    async_add_entities(
        [
            entity
            for serial in known_serials
            for entity in (
                _build_base_entities(runtime, serial)
                + _build_recipe_entities(
                    runtime,
                    serial,
                    runtime.get_machine_runtime(serial).recipes,
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
    def _handle_recipes(serial: str, recipes: tuple[RecipeDescriptor, ...]) -> None:
        new_entities: list[ButtonEntity] = []
        for recipe in recipes:
            recipe_id = f"{serial}:{recipe.selector}"
            if recipe_id in known_recipe_ids:
                continue
            known_recipe_ids.add(recipe_id)
            new_entities.extend(_build_recipe_entities(runtime, serial, (recipe,)))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(runtime.add_machine_listener(_handle_machine_added))
    entry.async_on_unload(runtime.add_recipe_listener(_handle_recipes))


class EspCoffeeBridgeConfirmButton(
    EspCoffeeBridgeCoordinatorEntity,
    ButtonEntity,
):
    """Button to confirm machine-driven prompts."""

    _attr_name = "Confirm prompt"

    def __init__(
        self, runtime: EspCoffeeBridgeRuntimeData, serial: str, coordinator
    ) -> None:
        super().__init__(runtime, serial, "confirm_prompt", coordinator)

    @property
    def available(self) -> bool:
        """Return true if confirmation is currently possible."""

        summary = self.coordinator.data
        return bool(super().available and summary and summary.host_confirm_suggested)

    async def async_press(self) -> None:
        """Confirm the prompt."""

        try:
            await self.runtime.client.async_confirm(self.serial)
        except EspCoffeeBridgeApiError as err:
            raise HomeAssistantError(str(err)) from err

        await self.runtime.async_post_action_refresh(self.serial, include_deep=True)


class EspCoffeeBridgeRecipeButton(
    EspCoffeeBridgeCoordinatorEntity,
    ButtonEntity,
):
    """Button for brewing a standard recipe."""

    def __init__(
        self,
        runtime: EspCoffeeBridgeRuntimeData,
        serial: str,
        recipe: RecipeDescriptor,
        coordinator,
    ) -> None:
        self.recipe = recipe
        super().__init__(runtime, serial, f"brew_{recipe.selector}", coordinator)
        self._attr_name = recipe.title

    @property
    def available(self) -> bool:
        """Return true when the latest summary says the machine is ready."""

        summary = self.coordinator.data
        return bool(
            super().available
            and summary
            and summary.summary == SUMMARY_STATE_READY
            and summary.message == 0
        )

    async def async_press(self) -> None:
        """Start the default brew."""

        try:
            await self.runtime.client.async_brew(
                self.serial,
                {"selector": self.recipe.selector},
            )
        except EspCoffeeBridgeApiError as err:
            raise HomeAssistantError(str(err)) from err

        await self.runtime.async_post_action_refresh(self.serial, include_deep=True)
