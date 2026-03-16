"""Fixtures for the ESP Coffee Bridge tests."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

HOST = "bridge.local"
PORT = 80
BASE_URL = f"http://{HOST}:{PORT}"
BRIDGE_ID = "AA:BB:CC:DD:EE:FF"

MACHINE_ONE = {
    "serial": "NIV123456",
    "alias": "Kitchen",
    "address": "C8:B4:17:D8:A3:8C",
    "addressType": 0,
    "model": "NICR 756",
    "modelCode": "756",
    "modelName": "NICR 756",
    "familyKey": "700",
    "manufacturer": "NIVONA",
    "hardwareRevision": "1.0",
    "firmwareRevision": "FW1",
    "softwareRevision": "SW1",
    "ad06Hex": "",
    "ad06Ascii": "",
    "lastSeenRssi": -55,
    "lastSeenAtMs": 123,
    "savedAtMs": 1,
    "online": True,
}

MACHINE_TWO = {
    "serial": "NIV654321",
    "alias": "Office",
    "address": "C8:B4:17:D8:A3:8D",
    "addressType": 0,
    "model": "NICR 790",
    "modelCode": "790",
    "modelName": "NICR 790",
    "familyKey": "79x",
    "manufacturer": "NIVONA",
    "hardwareRevision": "1.0",
    "firmwareRevision": "FW2",
    "softwareRevision": "SW2",
    "ad06Hex": "",
    "ad06Ascii": "",
    "lastSeenRssi": -60,
    "lastSeenAtMs": 456,
    "savedAtMs": 2,
    "online": True,
}

STATUS_PAYLOAD = {
    "ok": True,
    "appName": "esp-coffee-bridge",
    "appVersion": "1.2.3",
    "buildTime": "2026-03-16T10:00:00Z",
    "hostname": "esp-coffee-bridge",
    "bridgeId": BRIDGE_ID,
    "apiVersion": 1,
    "apPassword": "coffee-setup",
    "staIp": "192.168.1.33",
    "apIp": "192.168.4.1",
    "staSsid": "MyWifi",
}

SUMMARY_READY = {
    "ok": True,
    "machine": MACHINE_ONE,
    "status": {
        "ok": True,
        "summary": "ready",
        "process": 8,
        "processLabel": "ready",
        "subProcess": 0,
        "subProcessLabel": "",
        "message": 0,
        "messageLabel": "none",
        "progress": 0,
        "hostConfirmSuggested": False,
    },
}

SUMMARY_PREPARING = {
    "ok": True,
    "machine": MACHINE_ONE,
    "status": {
        "ok": True,
        "summary": "preparing",
        "process": 4,
        "processLabel": "preparing",
        "subProcess": 0,
        "subProcessLabel": "",
        "message": 0,
        "messageLabel": "none",
        "progress": 15,
        "hostConfirmSuggested": False,
    },
}

STATS_PAYLOAD = {
    "ok": True,
    "supported": True,
    "values": {
        "espresso": {
            "title": "Espresso",
            "section": "beverages",
            "unit": "count",
            "registerId": 200,
            "rawValue": 42,
        },
        "descale_warning": {
            "title": "Descaling warning",
            "section": "maintenance",
            "unit": "flag",
            "registerId": 601,
            "rawValue": 0,
        },
    },
}

SETTINGS_PAYLOAD = {
    "ok": True,
    "supported": True,
    "values": {
        "water_hardness": {
            "title": "Water hardness",
            "registerId": 101,
            "rawValue": 1,
            "valueCodeHex": "0x0001",
            "valueLabel": "medium",
            "options": [
                {"code": 0, "label": "soft"},
                {"code": 1, "label": "medium"},
                {"code": 2, "label": "hard"},
                {"code": 3, "label": "very hard"},
            ],
        },
        "temperature": {
            "title": "Temperature",
            "registerId": 102,
            "rawValue": 1,
            "valueCodeHex": "0x0001",
            "valueLabel": "high",
            "options": [
                {"code": 0, "label": "normal"},
                {"code": 1, "label": "high"},
                {"code": 2, "label": "max"},
                {"code": 3, "label": "individual"},
            ],
        },
    },
}

RECIPES_PAYLOAD = {
    "ok": True,
    "machine": MACHINE_ONE,
    "recipes": [
        {"selector": 0, "name": "espresso", "title": "Espresso"},
        {"selector": 3, "name": "cappuccino", "title": "Cappuccino"},
    ],
}

RECIPES_PAYLOAD_TWO = {
    "ok": True,
    "machine": MACHINE_TWO,
    "recipes": [
        {"selector": 0, "name": "espresso", "title": "Espresso"},
        {"selector": 1, "name": "coffee", "title": "Coffee"},
    ],
}

RECIPE_DETAIL_PAYLOAD = {
    "ok": True,
    "recipe": {
        "selector": 0,
        "name": "espresso",
        "title": "Espresso",
        "writableFields": [
            "strength",
            "strengthBeans",
            "temperature",
            "twoCups",
        ],
        "options": {
            "strength": [
                {"value": 0, "label": "1 bean"},
                {"value": 1, "label": "2 beans"},
                {"value": 2, "label": "3 beans"},
            ],
            "strengthBeans": [
                {"value": 1, "label": "1 bean"},
                {"value": 2, "label": "2 beans"},
                {"value": 3, "label": "3 beans"},
            ],
            "temperature": [
                {"value": 0, "label": "normal", "name": "normal"},
                {"value": 1, "label": "high", "name": "high"},
                {"value": 2, "label": "max", "name": "max"},
            ],
            "twoCups": [
                {"value": 0, "label": "off", "name": "off"},
                {"value": 1, "label": "on", "name": "on"},
            ],
        },
    },
}

BREW_RESPONSE = {
    "ok": True,
    "selector": 0,
    "status": SUMMARY_PREPARING["status"],
    "recipe": {"selector": 0, "name": "espresso"},
    "history": {"timeUnix": 1710580000},
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading the custom integration from this repo."""
    yield


def _side_effect(
    payload_factory: Callable[..., dict[str, Any]],
) -> Callable[..., Any]:
    """Wrap a payload factory for aioclient_mock side effects."""

    async def _wrapped(method: str, url, data: Any) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(
            method=method,
            url=url,
            json=payload_factory(str(url), data=data),
        )

    return _wrapped


@pytest.fixture
def api_routes(aioclient_mock):
    """Register mocked bridge routes and expose captured requests."""
    captured: dict[str, Any] = {}
    machines_payload = {
        "ok": True,
        "machines": [deepcopy(MACHINE_ONE)],
        "count": 1,
        "lastScanAtMs": 123,
    }
    summary_counter = {"count": 0}

    def status_factory(url: str, **kwargs: Any) -> dict[str, Any]:
        return deepcopy(STATUS_PAYLOAD)

    def machines_factory(url: str, **kwargs: Any) -> dict[str, Any]:
        return deepcopy(machines_payload)

    def summary_factory(url: str, **kwargs: Any) -> dict[str, Any]:
        summary_counter["count"] += 1
        if summary_counter["count"] >= 3 and captured.get("brew"):
            return deepcopy(SUMMARY_PREPARING)
        return deepcopy(SUMMARY_READY)

    aioclient_mock.get(
        f"{BASE_URL}/api/status", side_effect=_side_effect(status_factory)
    )
    aioclient_mock.get(
        f"{BASE_URL}/api/machines", side_effect=_side_effect(machines_factory)
    )
    aioclient_mock.get(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/recipes",
        json=deepcopy(RECIPES_PAYLOAD),
    )
    aioclient_mock.get(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/summary",
        side_effect=_side_effect(summary_factory),
    )
    aioclient_mock.get(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/stats",
        json=deepcopy(STATS_PAYLOAD),
    )
    aioclient_mock.get(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/settings",
        json=deepcopy(SETTINGS_PAYLOAD),
    )
    aioclient_mock.get(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/recipes/0",
        json=deepcopy(RECIPE_DETAIL_PAYLOAD),
    )

    async def brew_callback(method: str, url, data: Any) -> AiohttpClientMockResponse:
        captured["brew"] = data
        return AiohttpClientMockResponse(
            method=method, url=url, json=deepcopy(BREW_RESPONSE)
        )

    async def setting_callback(
        method: str, url, data: Any
    ) -> AiohttpClientMockResponse:
        captured["setting"] = data
        return AiohttpClientMockResponse(method=method, url=url, json={"ok": True})

    aioclient_mock.post(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/brew",
        side_effect=brew_callback,
    )
    aioclient_mock.post(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/settings",
        side_effect=setting_callback,
    )
    aioclient_mock.post(
        f"{BASE_URL}/api/machines/{MACHINE_ONE['serial']}/confirm",
        json={"ok": True},
    )

    def add_second_machine() -> None:
        machines_payload["machines"] = [deepcopy(MACHINE_ONE), deepcopy(MACHINE_TWO)]
        machines_payload["count"] = 2
        aioclient_mock.get(
            f"{BASE_URL}/api/machines/{MACHINE_TWO['serial']}/recipes",
            json=deepcopy(RECIPES_PAYLOAD_TWO),
        )
        aioclient_mock.get(
            f"{BASE_URL}/api/machines/{MACHINE_TWO['serial']}/summary",
            json={
                "ok": True,
                "machine": deepcopy(MACHINE_TWO),
                "status": deepcopy(SUMMARY_READY["status"]),
            },
        )
        aioclient_mock.get(
            f"{BASE_URL}/api/machines/{MACHINE_TWO['serial']}/stats",
            json=deepcopy(STATS_PAYLOAD),
        )
        aioclient_mock.get(
            f"{BASE_URL}/api/machines/{MACHINE_TWO['serial']}/settings",
            json=deepcopy(SETTINGS_PAYLOAD),
        )

    def remove_second_machine() -> None:
        machines_payload["machines"] = [deepcopy(MACHINE_ONE)]
        machines_payload["count"] = 1

    return {
        "captured": captured,
        "add_second_machine": add_second_machine,
        "remove_second_machine": remove_second_machine,
    }
