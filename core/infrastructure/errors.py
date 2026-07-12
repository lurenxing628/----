"""Compatibility imports for the application error contract now owned by :mod:`core.errors`."""

from core.errors import (
    AppError,
    BusinessError,
    ErrorCode,
    NotFoundError,
    ValidationError,
    app_error_http_status,
    error_response,
)

__all__ = [
    "AppError",
    "BusinessError",
    "ErrorCode",
    "NotFoundError",
    "ValidationError",
    "app_error_http_status",
    "error_response",
]
