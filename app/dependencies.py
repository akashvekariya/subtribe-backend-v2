"""FastAPI dependencies for auth, database, etc."""

from fastapi import Cookie, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import settings
from app.exceptions import ForbiddenError, UnauthorizedError

# Security scheme for Swagger UI (optional to allow cookie fallback)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    access_token: str | None = Cookie(None),
) -> dict[str, any]:
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
        company_id = payload.get("company_id")

        if not user_id or not company_id:
            raise UnauthorizedError(message="Invalid token claims")

        return {
            "user_id": user_id,
            "company_id": company_id,
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
