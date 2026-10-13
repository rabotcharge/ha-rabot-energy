"""Exceptions raised by the Rabot Energy client."""

from __future__ import annotations


class RabotError(Exception):
    """Base class for all errors raised by this library."""


class RabotConnectionError(RabotError):
    """The service could not be reached (network error or timeout)."""


class RabotAuthError(RabotError):
    """The token was rejected (HTTP 401 or 403)."""


class RabotContractNotFoundError(RabotError):
    """The contract does not exist or is not visible to this token (HTTP 404)."""


class RabotRateLimitError(RabotError):
    """Too many requests (HTTP 429)."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        """Store the number of seconds to wait, when the service sent it."""
        super().__init__(message)
        self.retry_after = retry_after


class RabotApiError(RabotError):
    """Any other error status or an unreadable response."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Store the HTTP status, when there is one."""
        super().__init__(message)
        self.status = status
