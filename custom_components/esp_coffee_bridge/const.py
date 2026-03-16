"""Constants for the ESP Coffee Bridge integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "esp_coffee_bridge"
NAME = "ESP Coffee Bridge"

MANUFACTURER_BRIDGE = "ESP Coffee Bridge"
MODEL_BRIDGE = "ESP32 BLE coffee bridge"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
]

EXPECTED_APP_NAME = "esp-coffee-bridge"
MIN_BRIDGE_API_VERSION = 1
MIN_API_VERSION = MIN_BRIDGE_API_VERSION

CONF_PORT = "port"
CONF_BRIDGE_ID = "bridge_id"
CONF_API_VERSION = "api_version"

CONF_BRIDGE_POLL_SECONDS = "bridge_poll_seconds"
CONF_SUMMARY_POLL_SECONDS = "summary_poll_seconds"
CONF_DEEP_POLL_SECONDS = "deep_poll_seconds"

# Compatibility aliases for older local code/tests.
CONF_BRIDGE_POLL_INTERVAL = CONF_BRIDGE_POLL_SECONDS
CONF_SUMMARY_POLL_INTERVAL = CONF_SUMMARY_POLL_SECONDS
CONF_DEEP_POLL_INTERVAL = CONF_DEEP_POLL_SECONDS

DEFAULT_PORT = 80
DEFAULT_REQUEST_TIMEOUT = 15
DEFAULT_BRIDGE_POLL_SECONDS = 30
DEFAULT_SUMMARY_POLL_SECONDS = 60
DEFAULT_DEEP_POLL_SECONDS = 900
DEFAULT_POST_ACTION_REFRESH_DELAY = 5

DEFAULT_BRIDGE_POLL_INTERVAL = DEFAULT_BRIDGE_POLL_SECONDS
DEFAULT_SUMMARY_POLL_INTERVAL = DEFAULT_SUMMARY_POLL_SECONDS
DEFAULT_DEEP_POLL_INTERVAL = DEFAULT_DEEP_POLL_SECONDS

MIN_BRIDGE_POLL_SECONDS = 10
MAX_BRIDGE_POLL_SECONDS = 300
MIN_SUMMARY_POLL_SECONDS = 15
MAX_SUMMARY_POLL_SECONDS = 300
MIN_DEEP_POLL_SECONDS = 60
MAX_DEEP_POLL_SECONDS = 3600

MIN_BRIDGE_POLL_INTERVAL = MIN_BRIDGE_POLL_SECONDS
MAX_BRIDGE_POLL_INTERVAL = MAX_BRIDGE_POLL_SECONDS
MIN_SUMMARY_POLL_INTERVAL = MIN_SUMMARY_POLL_SECONDS
MAX_SUMMARY_POLL_INTERVAL = MAX_SUMMARY_POLL_SECONDS
MIN_DEEP_POLL_INTERVAL = MIN_DEEP_POLL_SECONDS
MAX_DEEP_POLL_INTERVAL = MAX_DEEP_POLL_SECONDS

SERVICE_BREW = "brew"

ATTR_ACTOR = "actor"
ATTR_AROMA = "aroma"
ATTR_COFFEE_AMOUNT_ML = "coffee_amount_ml"
ATTR_COFFEE_TEMPERATURE = "coffee_temperature"
ATTR_CORRELATION_ID = "correlation_id"
ATTR_LABEL = "label"
ATTR_MILK_AMOUNT_ML = "milk_amount_ml"
ATTR_MILK_FOAM_AMOUNT_ML = "milk_foam_amount_ml"
ATTR_MILK_FOAM_TEMPERATURE = "milk_foam_temperature"
ATTR_MILK_TEMPERATURE = "milk_temperature"
ATTR_NOTE = "note"
ATTR_OVERALL_TEMPERATURE = "overall_temperature"
ATTR_PREPARATION = "preparation"
ATTR_RECIPE = "recipe"
ATTR_SELECTOR = "selector"
ATTR_SIZE_ML = "size_ml"
ATTR_SOURCE = "source"
ATTR_STRENGTH = "strength"
ATTR_STRENGTH_BEANS = "strength_beans"
ATTR_TEMPERATURE = "temperature"
ATTR_TWO_CUPS = "two_cups"
ATTR_WATER_AMOUNT_ML = "water_amount_ml"
ATTR_WATER_TEMPERATURE = "water_temperature"

SERVICE_FIELD_TO_API_FIELD = {
    ATTR_ACTOR: "actor",
    ATTR_AROMA: "aroma",
    ATTR_COFFEE_AMOUNT_ML: "coffeeAmountMl",
    ATTR_COFFEE_TEMPERATURE: "coffeeTemperature",
    ATTR_CORRELATION_ID: "correlationId",
    ATTR_LABEL: "label",
    ATTR_MILK_AMOUNT_ML: "milkAmountMl",
    ATTR_MILK_FOAM_AMOUNT_ML: "milkFoamAmountMl",
    ATTR_MILK_FOAM_TEMPERATURE: "milkFoamTemperature",
    ATTR_MILK_TEMPERATURE: "milkTemperature",
    ATTR_NOTE: "note",
    ATTR_OVERALL_TEMPERATURE: "overallTemperature",
    ATTR_PREPARATION: "preparation",
    ATTR_SELECTOR: "selector",
    ATTR_SIZE_ML: "sizeMl",
    ATTR_SOURCE: "source",
    ATTR_STRENGTH: "strength",
    ATTR_STRENGTH_BEANS: "strengthBeans",
    ATTR_TEMPERATURE: "temperature",
    ATTR_TWO_CUPS: "twoCups",
    ATTR_WATER_AMOUNT_ML: "waterAmountMl",
    ATTR_WATER_TEMPERATURE: "waterTemperature",
}

SUMMARY_STATE_READY = "ready"

SUMMARY_STATES: tuple[str, ...] = (
    "active",
    "attention",
    "flush required",
    "idle",
    "offline",
    "preparing",
    "ready",
    "unavailable",
    "working",
)

STAT_SECTION_BEVERAGES = "beverages"
STAT_SECTION_MAINTENANCE = "maintenance"

SENSITIVE_STATUS_KEYS = {
    "apPassword",
    "apIp",
    "password",
    "peerAddress",
    "selectedAddress",
    "ssid",
    "staIp",
    "staSsid",
}


def bridge_identifier(bridge_id: str) -> str:
    """Build the bridge device identifier."""

    return f"bridge::{bridge_id}"


def machine_identifier(bridge_id: str, serial: str) -> str:
    """Build the machine device identifier."""

    return f"machine::{bridge_id}::{serial}"


def bridge_entity_unique_id(bridge_id: str, suffix: str) -> str:
    """Build a bridge entity unique ID."""

    return f"{bridge_identifier(bridge_id)}:{suffix}"


def machine_entity_unique_id(bridge_id: str, serial: str, suffix: str) -> str:
    """Build a machine entity unique ID."""

    return f"{machine_identifier(bridge_id, serial)}:{suffix}"
