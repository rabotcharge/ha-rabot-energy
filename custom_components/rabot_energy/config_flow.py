"""Config flow: server address, contract number and an optional access token."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ._lib import (
    Auth,
    RabotApiError,
    RabotAuthError,
    RabotConnectionError,
    RabotContractNotFoundError,
    RabotEnergyApi,
    RabotRateLimitError,
)
from .const import CONF_CONTRACT_ID, DOMAIN


def _normalize_host(value: str) -> str | None:
    """Return the base URL without a trailing slash, or None when it is not a valid URL."""
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return value


async def _async_validate(
    hass: HomeAssistant, host: str, contract_id: str, token: str | None
) -> str | None:
    """Try one request; return an error key, or None when the settings work."""
    api = RabotEnergyApi(Auth(async_get_clientsession(hass), host, token))
    try:
        await api.async_get_price_preview(contract_id)
    except RabotAuthError:
        return "invalid_auth"
    except RabotContractNotFoundError:
        return "contract_not_found"
    except (RabotConnectionError, RabotRateLimitError):
        return "cannot_connect"
    except RabotApiError:
        return "unknown"
    return None


class RabotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup of one contract."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for server address, contract number and (optionally) a token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            contract_id = user_input[CONF_CONTRACT_ID].strip()
            token = user_input.get(CONF_API_TOKEN, "").strip()
            host = _normalize_host(user_input[CONF_HOST])
            await self.async_set_unique_id(contract_id)
            self._abort_if_unique_id_configured()
            if host is None:
                errors[CONF_HOST] = "invalid_host"
            elif (error := await _async_validate(self.hass, host, contract_id, token)) is None:
                return self.async_create_entry(
                    title=f"Rabot {contract_id}",
                    data={CONF_HOST: host, CONF_CONTRACT_ID: contract_id, CONF_API_TOKEN: token},
                )
            else:
                errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_CONTRACT_ID): str,
                        vol.Optional(CONF_API_TOKEN, default=""): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the server address (and optionally the token) of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _normalize_host(user_input[CONF_HOST])
            # An empty token field keeps the stored one.
            token = user_input.get(CONF_API_TOKEN, "").strip() or entry.data.get(CONF_API_TOKEN, "")
            if host is None:
                errors[CONF_HOST] = "invalid_host"
            elif (
                error := await _async_validate(self.hass, host, entry.data[CONF_CONTRACT_ID], token)
            ) is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host, CONF_API_TOKEN: token}
                )
            else:
                errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Optional(CONF_API_TOKEN, default=""): str,
                    }
                ),
                user_input or {CONF_HOST: entry.data.get(CONF_HOST, "")},
            ),
            errors=errors,
            description_placeholders={"contract_id": entry.data[CONF_CONTRACT_ID]},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauthentication after the token was rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new token for the same contract."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            if (
                error := await _async_validate(
                    self.hass, entry.data[CONF_HOST], entry.data[CONF_CONTRACT_ID], token
                )
            ) is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_TOKEN: token}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
            description_placeholders={"contract_id": entry.data[CONF_CONTRACT_ID]},
        )
