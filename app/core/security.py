"""Security utilities for authentication and authorization."""

import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Response
from jose import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(
    user_id: str,
    company_id: str | None,
    email: str,
    first_name: str,
    last_name: str,
    email_verified: bool = False,
) -> tuple[str, datetime]:
    """Create JWT access token with user claims."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days)

    payload = {
        "sub": user_id,
        "company_id": company_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "email_verified": email_verified,
        "exp": expires_at,
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def generate_verification_token() -> str:
    """Generate a secure verification token."""
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Generate a secure password reset token (256-bit entropy)."""
    return secrets.token_urlsafe(32)


def generate_invite_code() -> str:
    """Generate a unique invite code (format: XXXXX-XXXXX)."""
    part1 = secrets.token_hex(3).upper()[:5]
    part2 = secrets.token_hex(3).upper()[:5]
    return f"{part1}-{part2}"


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    # Add random suffix for uniqueness
    suffix = secrets.token_hex(3)
    return f"{slug}-{suffix}"


def set_auth_cookie(response: Response, token: str) -> None:
    """Set httpOnly authentication cookie."""
    cookie_kwargs = {
        "key": "access_token",
        "value": token,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "max_age": settings.cookie_max_age,
        "path": "/",
    }
    if settings.cookie_domain:
        cookie_kwargs["domain"] = settings.cookie_domain
    response.set_cookie(**cookie_kwargs)


def delete_auth_cookie(response: Response) -> None:
    """Delete authentication cookie."""
    delete_kwargs = {"key": "access_token", "path": "/"}
    if settings.cookie_domain:
        delete_kwargs["domain"] = settings.cookie_domain
    response.delete_cookie(**delete_kwargs)


def mask_email(email: str) -> str:
    """Mask an email address for privacy.

    Example: user@example.com -> u***@example.com
    """
    parts = email.split("@")
    if len(parts) != 2:
        return "***@***"

    local = parts[0]
    domain = parts[1]

    masked_local = "*" if len(local) <= 1 else local[0] + "***"

    return f"{masked_local}@{domain}"
