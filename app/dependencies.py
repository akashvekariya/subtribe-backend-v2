"""FastAPI dependencies for auth, database, etc."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import settings
from app.exceptions import ForbiddenError, UnauthorizedError

# Security scheme for Swagger UI
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, any]:
    """
    Validate JWT and extract user claims.

    Returns dict with: user_id, company_id, email, first_name, last_name
    """
    token = credentials.credentials

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
