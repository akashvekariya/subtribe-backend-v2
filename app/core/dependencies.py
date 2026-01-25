"""FastAPI dependencies for auth, database, etc."""

from contextvars import ContextVar
from typing import Any

from fastapi import Cookie, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError

# Correlation ID context variable (thread-safe, async-safe)
_correlation_id_ctx_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get correlation ID for current request.

    Returns None if no correlation ID is set (e.g., called outside request context).

    Returns:
        Correlation ID (UUID string) or None
    """
    return _correlation_id_ctx_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current request.

    This is called by LoggingMiddleware. Should not be called manually.

    Args:
        correlation_id: Correlation ID (UUID string)
    """
    _correlation_id_ctx_var.set(correlation_id)


# Security scheme for Swagger UI (optional to allow cookie fallback)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    access_token: str | None = Cookie(None),
) -> dict[str, Any]:
    """
    Validate JWT from cookie or Authorization header.

    Priority:
    1. Cookie (httpOnly, secure for browsers)
    2. Authorization header (for API clients, curl, Postman)

    Returns dict with: user_id, company_id, email, first_name, last_name
    """
    # Try cookie first (secure method for browsers)
    token = access_token

    # Fall back to Authorization header (for API testing/clients)
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise UnauthorizedError(
            message="Authentication required. Provide token in cookie or Authorization header",
            code="missing_token",
        )

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        user_id = payload.get("sub")
        company_id = payload.get(
            "company_id"
        )  # Can be None for users who haven't claimed invite yet

        if not user_id:
            raise UnauthorizedError(message="Invalid token claims")

        return {
            "user_id": user_id,
            "company_id": company_id,  # May be None until user claims invite
            "email": payload.get("email"),
            "first_name": payload.get("first_name"),
            "last_name": payload.get("last_name"),
        }

    except ExpiredSignatureError:
        raise UnauthorizedError(message="Token has expired", code="token_expired") from None
    except JWTError:
        raise UnauthorizedError(message="Invalid or expired token", code="invalid_token") from None


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.

    Usage:
        @router.post("/jobs")
        async def create_job(
            current_user: dict = Depends(require_role("admin", "recruiter"))
        ):
            ...
    """

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "admin")  # Default to admin for MVP
        if user_role not in allowed_roles:
            raise ForbiddenError(
                message=f"This action requires one of these roles: {', '.join(allowed_roles)}",
                code="insufficient_permissions",
            )
        return current_user

    return role_checker
