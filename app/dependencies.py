"""DEPRECATED: Use app.core.dependencies instead.

This module re-exports from app.core.dependencies for backward compatibility.
"""

from app.core.dependencies import (
    get_correlation_id,
    get_current_user,
    require_role,
    set_correlation_id,
)

__all__ = [
    "get_correlation_id",
    "get_current_user",
    "require_role",
    "set_correlation_id",
]
