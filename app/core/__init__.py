"""Core infrastructure: config, database, security, exceptions."""

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine, get_db
from app.core.dependencies import (
    get_correlation_id,
    get_current_user,
    require_role,
    set_correlation_id,
)
from app.core.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    register_exception_handlers,
)
from app.core.security import (
    create_access_token,
    delete_auth_cookie,
    generate_invite_code,
    generate_password_reset_token,
    generate_slug,
    generate_verification_token,
    hash_password,
    mask_email,
    set_auth_cookie,
    verify_password,
)

__all__ = [
    # Config
    "settings",
    # Database
    "Base",
    "AsyncSessionLocal",
    "engine",
    "get_db",
    # Dependencies
    "get_correlation_id",
    "get_current_user",
    "require_role",
    "set_correlation_id",
    # Exceptions
    "AppException",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "UnauthorizedError",
    "ValidationError",
    "register_exception_handlers",
    # Security
    "create_access_token",
    "delete_auth_cookie",
    "generate_invite_code",
    "generate_password_reset_token",
    "generate_slug",
    "generate_verification_token",
    "hash_password",
    "mask_email",
    "set_auth_cookie",
    "verify_password",
]
