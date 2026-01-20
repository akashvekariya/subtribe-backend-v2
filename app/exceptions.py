"""DEPRECATED: Use app.core.exceptions instead.

This module re-exports from app.core.exceptions for backward compatibility.
"""

from app.core.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    register_exception_handlers,
)

__all__ = [
    "AppException",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "UnauthorizedError",
    "ValidationError",
    "register_exception_handlers",
]
