"""ESP Coffee Bridge integration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EspCoffeeBridgeApiError,
    EspCoffeeBridgeClient,
    EspCoffeeBridgeConnectionError,
    EspCoffeeBridgeInvalidResponseError,
    EspCoffeeBridgeUnsupportedError,
)
from .const import (
    ATTR_ACTOR,
    ATTR_AROMA,
    ATTR_COFFEE_AMOUNT_ML,
    ATTR_COFFEE_TEMPERATURE,
    ATTR_CORRELATION_ID,
    ATTR_LABEL,
    ATTR_MILK_AMOUNT_ML,
    ATTR_MILK_FOAM_AMOUNT_ML,
    ATTR_MILK_FOAM_TEMPERATURE,
    ATTR_MILK_TEMPERATURE,
    ATTR_NOTE,
    ATTR_OVERALL_TEMPERATURE,
    ATTR_PREPARATION,
    ATTR_RECIPE,
    ATTR_SELECTOR,
    ATTR_SIZE_ML,
    ATTR_SOURCE,
    ATTR_STRENGTH,
    ATTR_STRENGTH_BEANS,
    ATTR_TEMPERATURE,
    ATTR_TWO_CUPS,
    ATTR_WATER_AMOUNT_ML,
    ATTR_WATER_TEMPERATURE,
    CONF_PORT,
    DOMAIN,
    PLATFORMS,
    SERVICE_BREW,
    SERVICE_FIELD_TO_API_FIELD,
)
from .coordinator import (
    EspCoffeeBridgeRuntimeData,
    async_sync_bridge_device,
    async_sync_machines,
    make_bridge_coordinator,
)

BREW_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_RECIPE): cv.string,
        vol.Optional(ATTR_SELECTOR): vol.Coerce(int),
        vol.Optional(ATTR_STRENGTH): vol.Coerce(int),
        vol.Optional(ATTR_STRENGTH_BEANS): vol.Coerce(int),
        vol.Optional(ATTR_AROMA): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional(ATTR_TEMPERATURE): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional(ATTR_COFFEE_TEMPERATURE): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional(ATTR_WATER_TEMPERATURE): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional(ATTR_MILK_TEMPERATURE): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional(ATTR_MILK_FOAM_TEMPERATURE): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional(ATTR_OVERALL_TEMPERATURE): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional(ATTR_PREPARATION): vol.Coerce(int),
        vol.Optional(ATTR_TWO_CUPS): vol.Any(cv.boolean, vol.Coerce(int), cv.string),
        vol.Optional(ATTR_COFFEE_AMOUNT_ML): vol.Coerce(float),
        vol.Optional(ATTR_WATER_AMOUNT_ML): vol.Coerce(float),
        vol.Optional(ATTR_MILK_AMOUNT_ML): vol.Coerce(float),
        vol.Optional(ATTR_MILK_FOAM_AMOUNT_ML): vol.Coerce(float),
        vol.Optional(ATTR_SIZE_ML): vol.Coerce(float),
        vol.Optional(ATTR_SOURCE): cv.string,
        vol.Optional(ATTR_ACTOR): cv.string,
        vol.Optional(ATTR_LABEL): cv.string,
        vol.Optional(ATTR_NOTE): cv.string,
        vol.Optional(ATTR_CORRELATION_ID): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: Mapping[str, Any]) -> bool:
    """Set up the ESP Coffee Bridge domain."""

    hass.data.setdefault(DOMAIN, {})

    if not hass.services.has_service(DOMAIN, SERVICE_BREW):

        async def async_brew_service(call: ServiceCall) -> dict[str, Any] | None:
            return await _async_handle_brew_service(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_BREW,
            async_brew_service,
            schema=BREW_SERVICE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one bridge entry."""

    session = async_get_clientsession(hass)
    client = EspCoffeeBridgeClient(
        session=session,
        host=str(entry.data[CONF_HOST]),
        port=int(entry.data[CONF_PORT]),
    )

    try:
        bridge_info = await client.async_validate_bridge()
        bridge_coordinator = make_bridge_coordinator(hass, entry, client)
        await bridge_coordinator.async_config_entry_first_refresh()
    except EspCoffeeBridgeConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err
    except (
        EspCoffeeBridgeUnsupportedError,
        EspCoffeeBridgeInvalidResponseError,
    ) as err:
        raise ConfigEntryError(str(err)) from err
    except EspCoffeeBridgeApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    runtime = EspCoffeeBridgeRuntimeData(
        hass=hass,
        entry=entry,
        client=client,
        bridge_info=bridge_info,
        bridge_coordinator=bridge_coordinator,
    )

    entry.runtime_data = runtime
    hass.data[DOMAIN][entry.entry_id] = runtime

    await async_sync_bridge_device(runtime)
    await async_sync_machines(runtime)

    @callback
    def _handle_bridge_refresh() -> None:
        hass.async_create_task(_async_handle_bridge_refresh(runtime))

    entry.async_on_unload(bridge_coordinator.async_add_listener(_handle_bridge_refresh))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one bridge entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    runtime: EspCoffeeBridgeRuntimeData = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.async_shutdown()

    if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, SERVICE_BREW):
        hass.services.async_remove(DOMAIN, SERVICE_BREW)

    return True


async def _async_handle_bridge_refresh(runtime: EspCoffeeBridgeRuntimeData) -> None:
    """Synchronize devices and machine runtime after bridge refreshes."""

    await async_sync_bridge_device(runtime)
    await async_sync_machines(runtime)


async def _async_handle_brew_service(
    hass: HomeAssistant,
    call: ServiceCall,
) -> dict[str, Any] | None:
    """Handle the brew service."""

    runtime, serial = _resolve_runtime_and_serial_from_call(hass, call)
    machine_runtime = runtime.get_machine_runtime(serial)

    selector = call.data.get(ATTR_SELECTOR)
    if selector is None:
        recipe_name = call.data.get(ATTR_RECIPE)
        if not isinstance(recipe_name, str) or not recipe_name:
            raise HomeAssistantError(
                "The brew action requires either a recipe or selector"
            )
        selector = _resolve_selector_from_recipe(machine_runtime.recipes, recipe_name)

    api_payload = _map_service_payload(call.data, selector)

    if _payload_requires_recipe_validation(api_payload):
        detail = await runtime.client.async_get_recipe_detail(serial, selector)
        api_payload = _validate_recipe_payload(detail, api_payload)

    try:
        response = await runtime.client.async_brew(serial, api_payload)
    except EspCoffeeBridgeApiError as err:
        raise HomeAssistantError(str(err)) from err

    await runtime.async_post_action_refresh(serial, include_deep=True)
    return _snake_case_dict(response)


def _resolve_runtime_and_serial_from_call(
    hass: HomeAssistant,
    call: ServiceCall,
) -> tuple[EspCoffeeBridgeRuntimeData, str]:
    """Resolve the service target to one machine."""

    device_ids = _normalize_list(call.data.get(ATTR_DEVICE_ID))
    if not device_ids:
        entity_ids = _normalize_list(call.data.get(ATTR_ENTITY_ID))
        if entity_ids:
            entity_registry = er.async_get(hass)
            for entity_id in entity_ids:
                if (entity_entry := entity_registry.async_get(entity_id)) and entity_entry.device_id:
                    device_ids.append(entity_entry.device_id)

    if len(device_ids) != 1:
        raise HomeAssistantError(
            "The brew action requires exactly one machine device target"
        )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_ids[0])
    if device is None:
        raise HomeAssistantError("The selected device is no longer available")

    for domain, value in device.identifiers:
        if domain != DOMAIN or not value.startswith("machine::"):
            continue
        _, bridge_id, serial = value.split("::", 2)
        for runtime in hass.data[DOMAIN].values():
            if runtime.bridge_info.bridge_id == bridge_id:
                return runtime, serial

    raise HomeAssistantError("The selected target is not an ESP Coffee Bridge machine")


def _resolve_selector_from_recipe(recipes, recipe_name: str) -> int:
    """Resolve a recipe name to its selector."""

    normalized = recipe_name.casefold()
    for recipe in recipes:
        if (
            recipe.name.casefold() == normalized
            or recipe.title.casefold() == normalized
        ):
            return recipe.selector
    raise HomeAssistantError(f"Unknown recipe '{recipe_name}' for the selected machine")


def _map_service_payload(data: Mapping[str, Any], selector: int) -> dict[str, Any]:
    """Map Home Assistant service data to the bridge API payload."""

    payload: dict[str, Any] = {"selector": selector}
    for field_name, api_name in SERVICE_FIELD_TO_API_FIELD.items():
        if field_name not in data or field_name == ATTR_SELECTOR:
            continue
        value = data[field_name]
        if field_name == ATTR_TWO_CUPS:
            value = _normalize_booleanish(value)
        payload[api_name] = value
    return payload


def _payload_requires_recipe_validation(payload: Mapping[str, Any]) -> bool:
    """Return whether override validation is required."""

    return set(payload) != {"selector"}


def _validate_recipe_payload(
    detail: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and normalize brew overrides against a recipe detail payload."""

    recipe_detail = detail.get("recipe")
    if isinstance(recipe_detail, Mapping):
        detail = recipe_detail

    normalized_payload = dict(payload)

    writable_fields = detail.get("writableFields")
    if isinstance(writable_fields, list):
        allowed_fields = {field for field in writable_fields if isinstance(field, str)}
        for field in normalized_payload:
            if field != "selector" and field not in allowed_fields:
                raise HomeAssistantError(
                    f"Field '{field}' cannot be overridden for this recipe"
                )

    options = detail.get("options")
    if not isinstance(options, dict):
        return normalized_payload

    for field, value in tuple(normalized_payload.items()):
        if field == "selector":
            continue
        field_options = options.get(field)
        if not isinstance(field_options, list):
            continue

        normalized_value = _normalize_option_value(value, field_options)
        if normalized_value is None:
            raise HomeAssistantError(f"Unsupported value for field '{field}'")
        normalized_payload[field] = normalized_value

    return normalized_payload


def _normalize_option_value(value: Any, field_options: list[Any]) -> Any | None:
    """Normalize an option label or name to the bridge payload value."""

    normalized_str = value.casefold() if isinstance(value, str) else None
    for option in field_options:
        if not isinstance(option, dict):
            continue

        option_value = option.get("value", option.get("code"))
        if value == option_value:
            return value

        if normalized_str is None:
            continue

        for key in ("label", "name", "title"):
            option_name = option.get(key)
            if (
                isinstance(option_name, str)
                and option_name.casefold() == normalized_str
            ):
                return option_value

    if not field_options:
        return value

    return None


def _normalize_booleanish(value: Any) -> Any:
    """Normalize loose boolean values."""

    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "on", "true", "yes"}:
            return True
        if normalized in {"0", "off", "false", "no"}:
            return False
    return value


def _normalize_list(value: Any) -> list[str]:
    """Normalize a scalar or list to a list of strings."""

    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _snake_case_dict(value: Any) -> Any:
    """Convert mapping keys to snake_case recursively."""

    if isinstance(value, dict):
        return {
            _to_snake_case(key): _snake_case_dict(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_snake_case_dict(item) for item in value]
    return value


def _to_snake_case(value: Any) -> Any:
    """Convert a string key to snake_case."""

    if not isinstance(value, str):
        return value
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()
