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
    RabotServiceUnavailableError,
)
from .models import PricePreview


def _retry_after(response: ClientResponse) -> int | None:
    """Read the Retry-After header as whole seconds, if present and numeric."""
    value = response.headers.get("Retry-After")
    if value is not None and value.isdigit():
        return int(value)
    return None


async def _problem(response: ClientResponse) -> str:
    """Return " (<title>: <detail>)" from an RFC 9457 ProblemDetails body, or "".

    Error bodies are optional and may be empty or not JSON, so this never raises.
    """
    try:
        data = await response.json(content_type=None)
    except (ClientError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    parts = [str(data[key]) for key in ("title", "detail") if data.get(key)]
    return f" ({': '.join(parts)})" if parts else ""


class RabotEnergyApi:
    """Client for the Rabot Energy price endpoint."""

    def __init__(self, auth: Auth) -> None:
        """Store the auth object used for all requests."""
        self._auth = auth

    async def async_get_price_preview(self, contract_number: str) -> PricePreview:
        """Return the price preview (up to 72 hours) for a contract."""
        response = await self._auth.request(
            "get", PRICES_PATH, params={"contractNumber": contract_number}
        )
        try:
            await self._raise_for_status(response)
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
    async def _raise_for_status(response: ClientResponse) -> None:
        """Map HTTP status codes to typed exceptions."""
        status = response.status
        if status < 400:
            return
        problem = await _problem(response)
        # 403 is not documented; treated like 401 to be safe.
        if status in (401, 403):
            raise RabotAuthError(f"The token was rejected{problem}")
        if status == 404:
            raise RabotContractNotFoundError(f"Contract not found{problem}")
        # 429 is not documented; handled defensively.
        if status == 429:
            raise RabotRateLimitError(f"Rate limited{problem}", _retry_after(response))
        if status == 503:
            raise RabotServiceUnavailableError(f"Prices are temporarily unavailable{problem}")
        raise RabotApiError(f"Service returned HTTP {status}{problem}", status)
