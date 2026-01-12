"""Custom exceptions for ingestion."""

from __future__ import annotations


class ApiError(Exception):
    """Base API error."""


class ApiConfigError(ApiError):
    """Raised when API configuration is invalid."""


class ApiHttpError(ApiError):
    """Raised when an HTTP request fails."""

    def __init__(self, status_code: int, url: str, message: str | None = None) -> None:
        if message is None:
            message = f"HTTP {status_code} for {url}"
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class ApiDecodeError(ApiError):
    """Raised when JSON decoding fails."""
