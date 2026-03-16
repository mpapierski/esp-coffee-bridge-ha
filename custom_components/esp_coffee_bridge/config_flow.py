"""Config flow for ESP Coffee Bridge."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
import yarl
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EspCoffeeBridgeClient,
    EspCoffeeBridgeConnectionError,
    EspCoffeeBridgeError,
    EspCoffeeBridgeUnsupportedError,
)
from .const import (
    CONF_BRIDGE_POLL_SECONDS,
    CONF_DEEP_POLL_SECONDS,
    CONF_PORT,
    CONF_SUMMARY_POLL_SECONDS,
    DEFAULT_BRIDGE_POLL_SECONDS,
    DEFAULT_DEEP_POLL_SECONDS,
    DEFAULT_PORT,
    DEFAULT_SUMMARY_POLL_SECONDS,
    DOMAIN,
    MAX_BRIDGE_POLL_SECONDS,
    MAX_DEEP_POLL_SECONDS,
    MAX_SUMMARY_POLL_SECONDS,
    MIN_BRIDGE_POLL_SECONDS,
    MIN_DEEP_POLL_SECONDS,
    MIN_SUMMARY_POLL_SECONDS,
)
from .models import BridgeInfo


def _normalize_host(host: str) -> str:
    """Normalize a host or URL into a plain hostname."""

    try:
        return yarl.URL(host).host or host
    except ValueError:
        return host


async def _async_validate_bridge(
    hass,
    host: str,
    port: int,
) -> BridgeInfo:
    """Validate the bridge and return parsed metadata."""

    client = EspCoffeeBridgeClient(async_get_clientsession(hass), host, port)
    return await client.async_validate_bridge()


class EspCoffeeBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> EspCoffeeBridgeOptionsFlow:
        """Return the options flow."""

        return EspCoffeeBridgeOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        return await self._async_step_connect("user", user_input)

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfigure."""

        return await self._async_step_connect("reconfigure", user_input)

    async def _async_step_connect(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = _normalize_host(user_input[CONF_HOST])
            port = int(user_input[CONF_PORT])

            try:
                bridge_info = await _async_validate_bridge(self.hass, host, port)
            except EspCoffeeBridgeUnsupportedError:
                errors["base"] = "unsupported_bridge"
            except EspCoffeeBridgeConnectionError:
                errors["base"] = "cannot_connect"
            except EspCoffeeBridgeError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    bridge_info.bridge_id, raise_on_progress=False
                )
                title = f"ESP Coffee Bridge ({host})"

                if self.source == SOURCE_RECONFIGURE:
                    entry = self._get_reconfigure_entry()
                    if entry.unique_id is None:
                        self.hass.config_entries.async_update_entry(
                            entry,
                            unique_id=bridge_info.bridge_id,
                        )
                    else:
                        self._abort_if_unique_id_mismatch(reason="bridge_changed")
                    return self.async_update_reload_and_abort(
                        entry,
                        title=title,
                        data_updates={CONF_HOST: host, CONF_PORT: port},
                    )

                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=1, max=65535),
                ),
            }
        )

        if step_id == "reconfigure":
            schema = self.add_suggested_values_to_schema(
                schema,
                self._get_reconfigure_entry().data,
            )

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
        )


class EspCoffeeBridgeOptionsFlow(OptionsFlowWithReload):
    """Handle integration options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage integration options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BRIDGE_POLL_SECONDS,
                        default=options.get(
                            CONF_BRIDGE_POLL_SECONDS,
                            DEFAULT_BRIDGE_POLL_SECONDS,
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_BRIDGE_POLL_SECONDS,
                            max=MAX_BRIDGE_POLL_SECONDS,
                        ),
                    ),
                    vol.Required(
                        CONF_SUMMARY_POLL_SECONDS,
                        default=options.get(
                            CONF_SUMMARY_POLL_SECONDS,
                            DEFAULT_SUMMARY_POLL_SECONDS,
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_SUMMARY_POLL_SECONDS,
                            max=MAX_SUMMARY_POLL_SECONDS,
                        ),
                    ),
                    vol.Required(
                        CONF_DEEP_POLL_SECONDS,
                        default=options.get(
                            CONF_DEEP_POLL_SECONDS,
                            DEFAULT_DEEP_POLL_SECONDS,
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_DEEP_POLL_SECONDS,
                            max=MAX_DEEP_POLL_SECONDS,
                        ),
                    ),
                }
            ),
        )
