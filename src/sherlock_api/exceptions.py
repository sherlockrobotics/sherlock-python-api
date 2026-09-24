"""Exceptions raised by :class:`sherlock_api.SherlockAPIClient`.

The hierarchy is::

    SherlockError
    ├── SherlockConfigurationError   (also a ValueError)
    └── SherlockAPIError             (also a RuntimeError)
        ├── SherlockBadRequestError  (400)
        ├── SherlockNotFoundError    (404)
        ├── SherlockTimeoutError     (408)
        └── SherlockServerError      (5xx)

:class:`SherlockAPIError` subclasses :class:`RuntimeError` and
:class:`SherlockConfigurationError` subclasses :class:`ValueError` so that code
written against earlier versions of this client keeps catching them.
"""

from __future__ import annotations

__all__ = [
    "SherlockError",
    "SherlockConfigurationError",
    "SherlockAPIError",
    "SherlockBadRequestError",
    "SherlockNotFoundError",
    "SherlockTimeoutError",
    "SherlockServerError",
    "exception_for_status",
    "truncate_body",
]

#: Error bodies longer than this are truncated in exception messages.
_MAX_BODY_CHARS = 500


class SherlockError(Exception):
    """Base class for every error raised by this library."""


class SherlockConfigurationError(SherlockError, ValueError):
    """The client is missing configuration needed to make a call.

    Raised when a required id (process, case or batch) was neither passed to
    the method nor supplied to the constructor or the environment.
    """


class SherlockAPIError(SherlockError, RuntimeError):
    """The Sherlock server returned an unexpected HTTP status.

    Attributes:
        status_code: HTTP status code of the response.
        reason: HTTP reason phrase, if any.
        body: Response body, truncated to 500 characters.
        method: HTTP method of the failed request.
        url: URL of the failed request.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        reason: str | None = None,
        body: str = "",
        method: str = "",
        url: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.body = body
        self.method = method
        self.url = url


class SherlockBadRequestError(SherlockAPIError):
    """The server rejected the request payload (HTTP 400)."""


class SherlockNotFoundError(SherlockAPIError):
    """The requested resource does not exist (HTTP 404)."""


class SherlockTimeoutError(SherlockAPIError):
    """The server timed out waiting for something (HTTP 408)."""


class SherlockServerError(SherlockAPIError):
    """The server failed to handle the request (HTTP 5xx)."""


def exception_for_status(status_code: int) -> type[SherlockAPIError]:
    """Return the most specific :class:`SherlockAPIError` subclass for a status."""
    if status_code == 400:
        return SherlockBadRequestError
    if status_code == 404:
        return SherlockNotFoundError
    if status_code == 408:
        return SherlockTimeoutError
    if 500 <= status_code < 600:
        return SherlockServerError
    return SherlockAPIError


def truncate_body(text: str) -> str:
    """Shorten a response body so it stays readable inside an exception message."""
    if len(text) <= _MAX_BODY_CHARS:
        return text
    return text[:_MAX_BODY_CHARS] + f"... [{len(text) - _MAX_BODY_CHARS} more chars]"
