"""DEPRECATED: Use app.core.database instead.

This module re-exports from app.core.database for backward compatibility.
"""

from app.core.database import AsyncSessionLocal, Base, engine, get_db

__all__ = ["AsyncSessionLocal", "Base", "engine", "get_db"]
