"""Data models for the ESP Coffee Bridge integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BridgeInfo:
    """Validated bridge metadata."""

    bridge_id: str
    api_version: int
    app_name: str
    app_version: str | None
    hostname: str | None
    base_url: str
    raw_status: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RecipeDescriptor:
    """A standard recipe exposed by the bridge."""

    selector: int
    name: str
    title: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MachineInfo:
    """Saved-machine metadata returned by the bridge."""

    serial: str
    alias: str | None
    address: str | None
    address_type: int | None
    model: str | None
    model_code: str | None
    model_name: str | None
    family_key: str | None
    manufacturer: str | None
    hardware_revision: str | None
    firmware_revision: str | None
    software_revision: str | None
    ad06_hex: str | None
    ad06_ascii: str | None
    last_seen_rssi: int | None
    last_seen_at_ms: int | None
    saved_at_ms: int | None
    online: bool
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MachineSummary:
    """Current live summary for one machine."""

    summary: str | None
    process: int | None
    process_label: str | None
    sub_process: int | None
    sub_process_label: str | None
    message: int | None
    message_label: str | None
    progress: int | None
    host_confirm_suggested: bool
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SettingOption:
    """One allowed value for a machine setting."""

    code: int | str
    label: str


@dataclass(frozen=True, slots=True)
class SettingValue:
    """Writable machine setting metadata and current value."""

    key: str
    title: str
    register_id: int | None
    raw_value: int | float | str | bool | None
    value_label: str | None
    value_code_hex: str | None
    options: tuple[SettingOption, ...]
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StatValue:
    """Machine statistic metadata and current value."""

    key: str
    title: str
    section: str
    unit: str | None
    register_id: int | None
    raw_value: int | float | str | bool | None
    raw: dict[str, Any]


def parse_bridge_info(status: dict[str, Any], base_url: str) -> BridgeInfo:
    """Parse validated bridge status."""

    return BridgeInfo(
        bridge_id=str(status["bridgeId"]),
        api_version=int(status["apiVersion"]),
        app_name=str(status["appName"]),
        app_version=_optional_str(status.get("appVersion")),
        hostname=_optional_str(status.get("hostname")),
        base_url=base_url,
        raw_status=dict(status),
    )


def parse_machine_info(payload: dict[str, Any]) -> MachineInfo:
    """Parse one machine payload."""

    return MachineInfo(
        serial=str(payload["serial"]),
        alias=_optional_str(payload.get("alias")),
        address=_optional_str(payload.get("address")),
        address_type=_optional_int(payload.get("addressType")),
        model=_optional_str(payload.get("model")),
        model_code=_optional_str(payload.get("modelCode")),
        model_name=_optional_str(payload.get("modelName")),
        family_key=_optional_str(payload.get("familyKey")),
        manufacturer=_optional_str(payload.get("manufacturer")),
        hardware_revision=_optional_str(payload.get("hardwareRevision")),
        firmware_revision=_optional_str(payload.get("firmwareRevision")),
        software_revision=_optional_str(payload.get("softwareRevision")),
        ad06_hex=_optional_str(payload.get("ad06Hex")),
        ad06_ascii=_optional_str(payload.get("ad06Ascii")),
        last_seen_rssi=_optional_int(payload.get("lastSeenRssi")),
        last_seen_at_ms=_optional_int(payload.get("lastSeenAtMs")),
        saved_at_ms=_optional_int(payload.get("savedAtMs")),
        online=bool(payload.get("online", False)),
        raw=dict(payload),
    )


def parse_recipe_descriptor(payload: dict[str, Any]) -> RecipeDescriptor:
    """Parse one recipe descriptor."""

    title = _optional_str(payload.get("title")) or _optional_str(payload.get("label"))
    name = _optional_str(payload.get("name")) or title or str(payload["selector"])
    return RecipeDescriptor(
        selector=int(payload["selector"]),
        name=name,
        title=title or name,
        raw=dict(payload),
    )


def parse_machine_summary(payload: dict[str, Any]) -> MachineSummary:
    """Parse a live machine summary response."""

    status = payload.get("status")
    data = status if isinstance(status, dict) else payload
    return MachineSummary(
        summary=_optional_str(data.get("summary")),
        process=_optional_int(data.get("process")),
        process_label=_optional_str(data.get("processLabel")),
        sub_process=_optional_int(data.get("subProcess")),
        sub_process_label=_optional_str(data.get("subProcessLabel")),
        message=_optional_int(data.get("message")),
        message_label=_optional_str(data.get("messageLabel")),
        progress=_optional_int(data.get("progress")),
        host_confirm_suggested=bool(data.get("hostConfirmSuggested", False)),
        raw=dict(data),
    )


def parse_setting_value(key: str, payload: dict[str, Any]) -> SettingValue:
    """Parse one machine setting."""

    options_payload = payload.get("options")
    options = (
        tuple(
            SettingOption(
                code=option.get("code", option.get("value", option.get("label", ""))),
                label=str(
                    option.get("label", option.get("title", option.get("value", "")))
                ),
            )
            for option in options_payload
            if isinstance(option, dict)
            and option.get("label", option.get("title")) is not None
        )
        if isinstance(options_payload, list)
        else ()
    )

    return SettingValue(
        key=key,
        title=_optional_str(payload.get("title")) or key.replace("_", " ").title(),
        register_id=_optional_int(payload.get("registerId")),
        raw_value=payload.get("rawValue"),
        value_label=_optional_str(payload.get("valueLabel")),
        value_code_hex=_optional_str(payload.get("valueCodeHex")),
        options=options,
        raw=dict(payload),
    )


def parse_stat_value(key: str, payload: dict[str, Any]) -> StatValue:
    """Parse one machine statistic."""

    return StatValue(
        key=key,
        title=_optional_str(payload.get("title")) or key.replace("_", " ").title(),
        section=_optional_str(payload.get("section")) or "unknown",
        unit=_optional_str(payload.get("unit")),
        register_id=_optional_int(payload.get("registerId")),
        raw_value=payload.get("rawValue"),
        raw=dict(payload),
    )


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
