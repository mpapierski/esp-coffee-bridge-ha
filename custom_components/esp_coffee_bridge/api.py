"""HTTP client for the ESP Coffee Bridge REST API."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_REQUEST_TIMEOUT, EXPECTED_APP_NAME, MIN_BRIDGE_API_VERSION
from .models import (
    BridgeInfo,
    MachineInfo,
    MachineSummary,
    RecipeDescriptor,
    SettingValue,
    StatValue,
    parse_bridge_info,
    parse_machine_info,
    parse_machine_summary,
    parse_recipe_descriptor,
    parse_setting_value,
    parse_stat_value,
)


class EspCoffeeBridgeError(HomeAssistantError):
    """Base integration error."""


class EspCoffeeBridgeConnectionError(EspCoffeeBridgeError):
    """Raised when the bridge cannot be reached."""


class EspCoffeeBridgeApiError(EspCoffeeBridgeError):
    """Raised when the bridge API returns an error."""

    def __init__(self, message: str, *, payload: Any | None = None) -> None:
        """Initialize the API error."""

        super().__init__(message)
        self.payload = payload


class EspCoffeeBridgeInvalidResponseError(EspCoffeeBridgeError):
    """Raised when the bridge returns malformed data."""


class EspCoffeeBridgeUnsupportedError(EspCoffeeBridgeError):
    """Raised when the bridge firmware is unsupported."""


class EspCoffeeBridgeClient:
    """Small aiohttp client for the bridge."""

    def __init__(self, session: ClientSession, host: str, port: int) -> None:
        """Initialize the client."""

        self._session = session
        self.host = host
        self.port = port
        self._request_timeout = DEFAULT_REQUEST_TIMEOUT
        self._live_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """Return the bridge base URL."""

        return f"http://{self.host}:{self.port}"

    async def async_validate_bridge(self) -> BridgeInfo:
        """Validate the bridge contract and return parsed metadata."""

        status = await self.async_get_status()
        app_name = status.get("appName")
        if app_name != EXPECTED_APP_NAME:
            raise EspCoffeeBridgeUnsupportedError(
                "The target host is not an ESP Coffee Bridge firmware"
            )

        api_version = status.get("apiVersion")
        if not isinstance(api_version, int) or api_version < MIN_BRIDGE_API_VERSION:
            raise EspCoffeeBridgeUnsupportedError(
                "The bridge firmware is too old for this integration"
            )

        bridge_id = status.get("bridgeId")
        if not isinstance(bridge_id, str) or not bridge_id:
            raise EspCoffeeBridgeInvalidResponseError(
                "The bridge did not return a stable bridge identifier"
            )

        return parse_bridge_info(status, self.base_url)

    async def async_get_status(self) -> dict[str, Any]:
        """Fetch bridge status."""

        return await self._request("GET", "/api/status")

    async def async_get_machines(self) -> list[MachineInfo]:
        """Fetch saved machines."""

        payload = await self._request("GET", "/api/machines")
        machines_payload = payload.get("machines", payload)
        if not isinstance(machines_payload, list):
            raise EspCoffeeBridgeInvalidResponseError(
                "The bridge returned an unexpected machines payload"
            )
        return [
            parse_machine_info(machine)
            for machine in machines_payload
            if isinstance(machine, dict) and machine.get("serial") is not None
        ]

    async def async_get_recipes(self, serial: str) -> list[RecipeDescriptor]:
        """Fetch standard recipes for a machine."""

        payload = await self._request("GET", f"/api/machines/{serial}/recipes")
        recipes_payload = payload.get("recipes", payload)
        if not isinstance(recipes_payload, list):
            raise EspCoffeeBridgeInvalidResponseError(
                "The bridge returned an unexpected recipes payload"
            )
        return [
            parse_recipe_descriptor(recipe)
            for recipe in recipes_payload
            if isinstance(recipe, dict) and recipe.get("selector") is not None
        ]

    async def async_get_recipe_detail(
        self, serial: str, selector: int
    ) -> dict[str, Any]:
        """Fetch recipe details for override validation."""

        return await self._request(
            "GET",
            f"/api/machines/{serial}/recipes/{selector}",
            serialized=True,
        )

    async def async_get_summary(self, serial: str) -> MachineSummary:
        """Fetch live summary for a machine."""

        payload = await self._request(
            "GET",
            f"/api/machines/{serial}/summary",
            serialized=True,
        )
        return parse_machine_summary(payload)

    async def async_get_stats(self, serial: str) -> dict[str, StatValue]:
        """Fetch machine statistics."""

        payload = await self._request(
            "GET",
            f"/api/machines/{serial}/stats",
            serialized=True,
        )
        values = payload.get("values", payload)
        if not isinstance(values, dict):
            raise EspCoffeeBridgeInvalidResponseError(
                "The bridge returned an unexpected statistics payload"
            )
        return {
            key: parse_stat_value(key, value)
            for key, value in values.items()
            if isinstance(key, str) and isinstance(value, dict)
        }

    async def async_get_settings(self, serial: str) -> dict[str, SettingValue]:
        """Fetch writable machine settings."""

        payload = await self._request(
            "GET",
            f"/api/machines/{serial}/settings",
            serialized=True,
        )
        values = payload.get("values", payload)
        if not isinstance(values, dict):
            raise EspCoffeeBridgeInvalidResponseError(
                "The bridge returned an unexpected settings payload"
            )
        return {
            key: parse_setting_value(key, value)
            for key, value in values.items()
            if isinstance(key, str) and isinstance(value, dict)
        }

    async def async_brew(
        self, serial: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Start a brew."""

        return await self._request(
            "POST",
            f"/api/machines/{serial}/brew",
            json_payload=payload,
            serialized=True,
        )

    async def async_confirm(self, serial: str) -> dict[str, Any]:
        """Confirm the current machine prompt."""

        return await self._request(
            "POST",
            f"/api/machines/{serial}/confirm",
            json_payload={},
            serialized=True,
        )

    async def async_set_setting(
        self, serial: str, key: str, value: Any
    ) -> dict[str, Any]:
        """Write a machine setting."""

        return await self._request(
            "POST",
            f"/api/machines/{serial}/settings",
            json_payload={"key": key, "value": value},
            serialized=True,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: Mapping[str, Any] | None = None,
        serialized: bool = False,
    ) -> dict[str, Any]:
        """Perform one API request."""

        lock = self._live_lock if serialized else _NoOpLock()
        async with lock:
            try:
                async with asyncio.timeout(self._request_timeout):
                    response = await self._session.request(
                        method,
                        f"{self.base_url}{path}",
                        json=json_payload,
                    )
                    payload = await response.json(content_type=None)
            except TimeoutError as err:
                raise EspCoffeeBridgeConnectionError(
                    "Timed out while connecting to the bridge"
                ) from err
            except ClientError as err:
                raise EspCoffeeBridgeConnectionError(
                    "Failed to connect to the bridge"
                ) from err
            except ValueError as err:
                raise EspCoffeeBridgeInvalidResponseError(
                    "The bridge returned invalid JSON"
                ) from err

        status_code = getattr(response, "status", None)
        if not isinstance(status_code, int):
            raise EspCoffeeBridgeInvalidResponseError(
                "The bridge response did not include an HTTP status code"
            )

        if status_code >= 400:
            message = None
            if isinstance(payload, dict):
                message = payload.get("error") or payload.get("message")
            raise EspCoffeeBridgeApiError(
                message or getattr(response, "reason", None) or "Bridge request failed",
                payload=payload,
            )

        if not isinstance(payload, dict):
            raise EspCoffeeBridgeInvalidResponseError(
                "The bridge returned an unexpected response type"
            )

        return payload


class _NoOpLock:
    """Async context manager used for non-serialized requests."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None
