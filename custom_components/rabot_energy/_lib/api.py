"""The Rabot Energy API: knows the paths and parses responses."""

from __future__ import annotations

from aiohttp import ClientError, ClientResponse

from .auth import Auth
from .const import PRICES_PATH
from .exceptions import (
    RabotApiError,
    RabotAuthError,
    RabotContractNotFoundError,
    RabotRateLimitError,
)
from .models import PricePreview


def _retry_after(response: ClientResponse) -> int | None:
    """Read the Retry-After header as whole seconds, if present and numeric."""
    value = response.headers.get("Retry-After")
    if value is not None and value.isdigit():
        return int(value)
    return None


class RabotEnergyApi:
    """Client for the Rabot Energy price endpoint."""

    def __init__(self, auth: Auth) -> None:
        """Store the auth object used for all requests."""
        self._auth = auth

    async def async_get_price_preview(self, contract_id: str) -> PricePreview:
        """Return the price preview (up to 72 hours) for a contract."""
        response = await self._auth.request("get", PRICES_PATH, params={"contractId": contract_id})
        try:
            self._raise_for_status(response)
            try:
                data = await response.json()
            except (ClientError, ValueError) as err:
                raise RabotApiError("Response is not valid JSON", response.status) from err
        finally:
            response.release()
        if not isinstance(data, dict):
            raise RabotApiError("Unexpected response shape", response.status)
        return PricePreview(data)

    @staticmethod
    def _raise_for_status(response: ClientResponse) -> None:
        """Map HTTP status codes to typed exceptions."""
        status = response.status
        if status < 400:
            return
        if status in (401, 403):
            raise RabotAuthError("The token was rejected")
        if status == 404:
            raise RabotContractNotFoundError("Contract not found")
        if status == 429:
            raise RabotRateLimitError("Rate limited", _retry_after(response))
        raise RabotApiError(f"Service returned HTTP {status}", status)
