"""Config flow: access token, optional contract number and (advanced) server address."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ._lib import (
    Auth,
    PricePreview,
    RabotApiError,
    RabotAuthError,
    RabotConnectionError,
    RabotContractNotFoundError,
    RabotEnergyApi,
    RabotRateLimitError,
    RabotServiceUnavailableError,
)
from .const import CONF_CONTRACT_NUMBER, DEFAULT_HOST, DOMAIN

# The server address is tucked into a collapsed section; most users never change it.
SECTION_ADVANCED = "advanced"


def _normalize_host(value: str) -> str | None:
    """Return the base URL without a trailing slash, or None when it is not a valid URL."""
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return value


def _normalize_token(value: str) -> str | None:
    """Return the token without whitespace, or None when it is not a non-empty GUID."""
    value = value.strip()
    try:
        if UUID(value).int == 0:  # the service rejects the empty GUID
            return None
    except ValueError:
        return None
    return value


async def _async_fetch(
    hass: HomeAssistant, host: str, contract_number: str | None, token: str
) -> tuple[PricePreview | None, str | None]:
    """Try one request; return the response, or an error key when the settings fail."""
    api = RabotEnergyApi(Auth(async_get_clientsession(hass), host, token))
    try:
        return await api.async_get_price_preview(contract_number), None
    except RabotAuthError:
        return None, "invalid_auth"
    except RabotContractNotFoundError:
        return None, "contract_not_found"
    except RabotServiceUnavailableError:
        return None, "service_unavailable"
    except (RabotConnectionError, RabotRateLimitError):
        return None, "cannot_connect"
    except RabotApiError:
        return None, "unknown"


async def _async_validate(
    hass: HomeAssistant, host: str, contract_number: str, token: str
) -> str | None:
    """Try one request; return an error key, or None when the settings work."""
    return (await _async_fetch(hass, host, contract_number, token))[1]


class RabotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup of one contract."""

    VERSION = 3

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the token, optionally the contract number, and (advanced) the server."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # The token identifies the contract; the number is optional and, when given,
            # must match the token's contract (the service answers 404 otherwise).
            entered_number = user_input.get(CONF_CONTRACT_NUMBER, "").strip() or None
            token = _normalize_token(user_input[CONF_API_TOKEN])
            host = _normalize_host(user_input[SECTION_ADVANCED][CONF_HOST])
            if token is None:
                errors[CONF_API_TOKEN] = "invalid_token"
            elif host is None:
                errors["base"] = "invalid_host"
            else:
                preview, error = await _async_fetch(self.hass, host, entered_number, token)
                contract_number = entered_number or (preview and preview.contract_number)
                if error:
                    errors["base"] = error
                elif not contract_number:
                    # Older service releases do not return the contract number.
                    errors[CONF_CONTRACT_NUMBER] = "contract_number_required"
                else:
                    await self.async_set_unique_id(contract_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Rabot {contract_number}",
                        data={
                            CONF_HOST: host,
                            CONF_CONTRACT_NUMBER: contract_number,
                            CONF_API_TOKEN: token,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_API_TOKEN): str,
                        vol.Optional(CONF_CONTRACT_NUMBER): str,
                        vol.Required(SECTION_ADVANCED): section(
                            vol.Schema({vol.Required(CONF_HOST): str}),
                            {"collapsed": True},
                        ),
                    }
                ),
                user_input or {SECTION_ADVANCED: {CONF_HOST: DEFAULT_HOST}},
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
            raw_token = user_input.get(CONF_API_TOKEN, "").strip()
            token = _normalize_token(raw_token) if raw_token else entry.data.get(CONF_API_TOKEN)
            if host is None:
                errors[CONF_HOST] = "invalid_host"
            elif not token:
                errors[CONF_API_TOKEN] = "invalid_token"
            elif (
                error := await _async_validate(
                    self.hass, host, entry.data[CONF_CONTRACT_NUMBER], token
                )
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
            description_placeholders={"contract_number": entry.data[CONF_CONTRACT_NUMBER]},
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
            token = _normalize_token(user_input[CONF_API_TOKEN])
            if token is None:
                errors[CONF_API_TOKEN] = "invalid_token"
            elif (
                error := await _async_validate(
                    self.hass, entry.data[CONF_HOST], entry.data[CONF_CONTRACT_NUMBER], token
                )
            ) is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_TOKEN: token}
                )
            else:
                errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
            description_placeholders={"contract_number": entry.data[CONF_CONTRACT_NUMBER]},
        )
