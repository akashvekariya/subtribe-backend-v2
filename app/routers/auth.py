"""Authentication endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from fastapi import APIRouter, Depends, Response, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    CompanyResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    UserResponse,
)

router = APIRouter()


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
    user_id: str, company_id: str, email: str, first_name: str, last_name: str
) -> tuple[str, datetime]:
    """Create JWT access token with user claims."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days)

    payload = {
        "sub": user_id,
        "company_id": company_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "exp": expires_at,
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"]
)
async def register(response: Response, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register new user with company code.

    - Validates company code exists
    - Creates user with hashed password
    - Returns JWT with company_id claim
    """
    # Check if email already exists
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise ConflictError(message="Email already registered", code="duplicate_email")

    # Validate company code
    stmt = select(Company).where(Company.invite_code == data.company_code)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise NotFoundError(
            message="Company not found with the provided code", code="company_not_found"
        )

    if not company.is_active:
        raise ValidationError(message="Company is not active", code="company_inactive")

    # Hash password
    password_hash = hash_password(data.password)

    # Create user
    user = User(
        company_id=company.id,
        email=data.email,
        password_hash=password_hash,
        first_name=data.first_name,
        last_name=data.last_name,
        role="admin",  # Everyone is admin in MVP
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(company)

    # Create JWT
    access_token, expires_at = create_access_token(
        user_id=str(user.id),
        company_id=str(company.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Set httpOnly cookie (secure for browsers)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Not accessible via JavaScript
        secure=settings.environment == "production",  # HTTPS only in production
        samesite="lax",  # CSRF protection
        max_age=settings.jwt_expiry_days * 24 * 60 * 60,  # seconds
    )

    # Build response (also return token in body for API clients)
    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            avatar_url=user.avatar_url,
            company=CompanyResponse(
                id=str(company.id), name=company.name, slug=company.slug, logo_url=company.logo_url
            ),
        ),
        access_token=access_token,
        expires_at=expires_at,
    )


@router.post("/login", response_model=AuthResponse, tags=["Auth"])
async def login(response: Response, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login with email/password.

    - Validates credentials
    - Updates last_login_at
    - Returns JWT with company_id claim
    """
    # Find user by email
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError(message="Invalid email or password", code="invalid_credentials")

    # Verify password
    if not verify_password(data.password, user.password_hash):
        raise UnauthorizedError(message="Invalid email or password", code="invalid_credentials")

    # Check if user is active
    if not user.is_active:
        raise UnauthorizedError(message="Account is inactive", code="account_inactive")

    # Get company
    stmt = select(Company).where(Company.id == user.company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company or not company.is_active:
        raise UnauthorizedError(message="Company is not active", code="company_inactive")

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Create JWT
    access_token, expires_at = create_access_token(
        user_id=str(user.id),
        company_id=str(company.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Set httpOnly cookie (secure for browsers)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Not accessible via JavaScript
        secure=settings.environment == "production",  # HTTPS only in production
        samesite="lax",  # CSRF protection
        max_age=settings.jwt_expiry_days * 24 * 60 * 60,  # seconds
    )

    # Build response (also return token in body for API clients)
    return AuthResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            avatar_url=user.avatar_url,
            company=CompanyResponse(
                id=str(company.id), name=company.name, slug=company.slug, logo_url=company.logo_url
            ),
        ),
        access_token=access_token,
        expires_at=expires_at,
    )


@router.post("/logout", status_code=status.HTTP_200_OK, tags=["Auth"])
async def logout(response: Response):
    """
    Logout user by clearing authentication cookie.

    Note: For API clients using Authorization header, simply discard the token on client side.
    """
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=MeResponse, tags=["Auth"])
async def get_me(
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get current user info from JWT.

    - Extracts user_id from JWT
    - Returns full user details with company
    """
    # Get user from database
    user_id = UUID(current_user["user_id"])

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(message="User not found", code="user_not_found")

    # Get company
    stmt = select(Company).where(Company.id == user.company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise NotFoundError(message="Company not found", code="company_not_found")

    # Build response
    return MeResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=user.avatar_url,
        company=CompanyResponse(
            id=str(company.id), name=company.name, slug=company.slug, logo_url=company.logo_url
        ),
        last_login_at=user.last_login_at,
    )
