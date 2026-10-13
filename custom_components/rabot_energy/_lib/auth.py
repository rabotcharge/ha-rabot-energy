"""Authenticated requests.

This is the only code that talks to the service. It knows nothing about what is
inside a request. It does not store the token: Home Assistant keeps it in the
config entry.
"""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import DEFAULT_TIMEOUT
from .exceptions import RabotConnectionError


class Auth:
    """Make authenticated requests to the Rabot Energy service."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        token: str | None = None,
    ) -> None:
        """Initialize with an injected session, the service host and an optional token.

        `host` is the base URL including the scheme, for example `https://example.org`
        or `http://10.0.0.5:8012`. Some environments need no token.
        """
        self._session = session
        self._host = host.rstrip("/")
        self._token = token

    def _headers(self) -> dict[str, str]:
        """Return the authorization headers, empty when there is no token.

        ASSUMPTION: the service takes a bearer token when it needs one. If the real
        header differs, this is the only place to change.
        """
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    async def request(self, method: str, path: str, **kwargs: Any) -> ClientResponse:
        """Make a request and return the raw response."""
        headers = dict(kwargs.pop("headers", {}))
        headers.update(self._headers())
        try:
            return await self._session.request(
                method,
                f"{self._host}{path}",
                headers=headers,
                timeout=kwargs.pop("timeout", ClientTimeout(total=DEFAULT_TIMEOUT)),
                **kwargs,
            )
        except (ClientError, TimeoutError) as err:
            raise RabotConnectionError(f"Cannot reach the Rabot service: {err}") from err
