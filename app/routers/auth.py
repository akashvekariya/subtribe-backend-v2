"""Authentication endpoints."""

import logging
import secrets
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
from app.email.providers import EmailMessage, SendGridEmailProvider, StubEmailProvider
from app.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.models.company import Company
from app.models.invite import Invite
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ClaimInviteRequest,
    ClaimInviteResponse,
    CompanyResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResendVerificationResponse,
    UserResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)

logger = logging.getLogger(__name__)
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


def generate_invite_code() -> str:
    """Generate a unique invite code (format: XXXXX-XXXXX)."""
    part1 = secrets.token_hex(3).upper()[:5]
    part2 = secrets.token_hex(3).upper()[:5]
    return f"{part1}-{part2}"


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from name."""
    import re

    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    # Add random suffix for uniqueness
    suffix = secrets.token_hex(3)
    return f"{slug}-{suffix}"


def _get_email_provider():
    """Get configured email provider."""
    if not settings.email_enabled or settings.email_provider == "stub":
        return StubEmailProvider()
    return SendGridEmailProvider(
        api_key=settings.sendgrid_api_key,
        sandbox_mode=settings.sendgrid_sandbox_mode,
    )


async def send_verification_email(user: User, token: str) -> bool:
    """Send email verification email."""
    verification_url = f"{settings.dashboard_url}/verify-email/{token}"

    message = EmailMessage(
        to_email=user.email,
        to_name=f"{user.first_name} {user.last_name}",
        subject="Verify your Subtribe account",
        body=f"""Hi {user.first_name},

Please verify your email address to complete your Subtribe registration.

Click the link below to verify:
{verification_url}

This link expires in 24 hours.

If you didn't create this account, you can ignore this email.

- Team Subtribe
""",
        from_email=settings.email_from_address,
        from_name=settings.email_from_name,
    )

    provider = _get_email_provider()
    result = await provider.send_email(message)

    if result.success:
        logger.info(f"Verification email sent to {user.email}")
    else:
        logger.error(f"Failed to send verification email to {user.email}: {result.error_message}")

    return result.success


def set_auth_cookie(response: Response, token: str) -> None:
    """Set httpOnly authentication cookie."""
    cookie_kwargs = {
        "key": "access_token",
        "value": token,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "max_age": settings.cookie_max_age,
    }
    if settings.cookie_domain:
        cookie_kwargs["domain"] = settings.cookie_domain
    response.set_cookie(**cookie_kwargs)


def build_user_response(user: User, company: Company | None = None) -> UserResponse:
    """Build UserResponse from User model."""
    company_response = None
    if company:
        company_response = CompanyResponse(
            id=str(company.id),
            name=company.name,
            slug=company.slug,
            logo_url=company.logo_url,
            onboarding_completed=company.onboarding_completed,
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        pending_onboarding=user.pending_onboarding,
        company=company_response,
    )


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"]
)
async def register(response: Response, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register new user.

    Creates user account WITHOUT organization. User must claim an invite code
    after email verification to join or create an organization.

    Flow:
    1. User registers (this endpoint)
    2. User verifies email
    3. User enters invite code (/auth/claim-invite)
       - org_creator invite → User goes to onboarding to create org
       - team_member invite → User joins existing org
    """
    # Check if email already exists
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise ConflictError(message="Email already registered", code="duplicate_email")

    # Hash password
    password_hash = hash_password(data.password)

    # Generate verification token
    verification_token = generate_verification_token()
    verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    # Create user WITHOUT company (they'll claim invite after verification)
    user = User(
        company_id=None,  # No company until invite is claimed
        email=data.email,
        password_hash=password_hash,
        first_name=data.first_name,
        last_name=data.last_name,
        role="admin",  # All users are admin in V1
        is_active=True,
        email_verified=False,
        pending_onboarding=False,  # Will be set to True when they claim org_creator invite
        email_verification_token=verification_token,
        email_verification_expires_at=verification_expires_at,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email
    await send_verification_email(user, verification_token)

    # Create JWT (no company_id yet)
    access_token, expires_at = create_access_token(
        user_id=str(user.id),
        company_id=None,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        email_verified=False,
    )

    # Set cookie
    set_auth_cookie(response, access_token)

    return AuthResponse(
        user=build_user_response(user, None),
        access_token=access_token,
        expires_at=expires_at,
        message="Account created. Please check your email to verify.",
    )


@router.post("/login", response_model=AuthResponse, tags=["Auth"])
async def login(response: Response, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login with email/password.

    Returns JWT with user claims. Works for users with or without company.
    """
    # Find user by email
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError(message="Invalid email or password", code="invalid_credentials")

    if not verify_password(data.password, user.password_hash):
        raise UnauthorizedError(message="Invalid email or password", code="invalid_credentials")

    if not user.is_active:
        raise UnauthorizedError(message="Account is inactive", code="account_inactive")

    # Get company if user has one
    company = None
    if user.company_id:
        stmt = select(Company).where(Company.id == user.company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()

        if company and not company.is_active:
            raise UnauthorizedError(message="Organization is not active", code="company_inactive")

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Create JWT
    access_token, expires_at = create_access_token(
        user_id=str(user.id),
        company_id=str(company.id) if company else None,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        email_verified=user.email_verified,
    )

    # Set cookie
    set_auth_cookie(response, access_token)

    return AuthResponse(
        user=build_user_response(user, company),
        access_token=access_token,
        expires_at=expires_at,
    )


@router.post("/verify-email", response_model=VerifyEmailResponse, tags=["Auth"])
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify email address using token from verification email.
    """
    # Find user by verification token
    stmt = select(User).where(User.email_verification_token == data.token)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(message="Invalid verification token", code="invalid_token")

    if user.email_verified:
        return VerifyEmailResponse(success=True, message="Email already verified")

    # Check if token expired
    if (
        user.email_verification_expires_at
        and datetime.now(timezone.utc) > user.email_verification_expires_at
    ):
        raise ValidationError(
            message="Verification token has expired. Please request a new one.",
            code="token_expired",
        )

    # Mark email as verified
    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    user.email_verification_token = None
    user.email_verification_expires_at = None

    await db.commit()

    logger.info(f"Email verified for user {user.email}")

    return VerifyEmailResponse(success=True, message="Email verified successfully")


@router.post("/resend-verification", response_model=ResendVerificationResponse, tags=["Auth"])
async def resend_verification(data: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    """
    Resend verification email.
    """
    # Find user by email
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal if email exists
        return ResendVerificationResponse(
            success=True, message="If the email exists, a verification link has been sent."
        )

    if user.email_verified:
        return ResendVerificationResponse(success=True, message="Email is already verified.")

    # Generate new verification token
    verification_token = generate_verification_token()
    user.email_verification_token = verification_token
    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    await db.commit()

    # Send verification email
    await send_verification_email(user, verification_token)

    return ResendVerificationResponse(
        success=True, message="If the email exists, a verification link has been sent."
    )


@router.post("/logout", status_code=status.HTTP_200_OK, tags=["Auth"])
async def logout(response: Response):
    """
    Logout user by clearing authentication cookie.
    """
    delete_kwargs = {"key": "access_token"}
    if settings.cookie_domain:
        delete_kwargs["domain"] = settings.cookie_domain
    response.delete_cookie(**delete_kwargs)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=MeResponse, tags=["Auth"])
async def get_me(
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get current user info from JWT.

    Returns user details including email_verified status and company info.
    """
    user_id = UUID(current_user["user_id"])

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(message="User not found", code="user_not_found")

    # Get company if user has one
    company = None
    if user.company_id:
        stmt = select(Company).where(Company.id == user.company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()

    # Build response
    company_response = None
    if company:
        company_response = CompanyResponse(
            id=str(company.id),
            name=company.name,
            slug=company.slug,
            logo_url=company.logo_url,
            onboarding_completed=company.onboarding_completed,
        )

    return MeResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        pending_onboarding=user.pending_onboarding,
        company=company_response,
        last_login_at=user.last_login_at,
    )


@router.post("/claim-invite", response_model=ClaimInviteResponse, tags=["Auth"])
async def claim_invite(
    response: Response,
    data: ClaimInviteRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Claim an invite code to join or create an organization.

    This endpoint is called after email verification. It handles two invite types:
    - org_creator: Sets pending_onboarding=True, user goes to onboarding to create org
    - team_member: Assigns user to the invite's company immediately
    """
    user_id = UUID(current_user["user_id"])

    # Get current user from DB
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(message="User not found", code="user_not_found")

    # Check if user already has a company
    if user.company_id:
        raise ValidationError(
            message="You are already part of an organization",
            code="already_has_company",
        )

    # Get invite
    stmt = select(Invite).where(Invite.code == data.code)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if not invite:
        raise NotFoundError(message="Invalid invite code", code="invalid_invite")

    # Security: Verify invite was intended for this user's email
    if invite.email and invite.email.lower() != user.email.lower():
        logger.warning(
            f"Invite claim attempt with email mismatch: invite={invite.email}, user={user.email}"
        )
        raise ValidationError(
            message="Invalid invite code",
            code="email_mismatch",
        )

    # Check invite validity
    if not invite.is_valid:
        if invite.expires_at and datetime.now(timezone.utc) > invite.expires_at:
            raise ValidationError(message="Invite code has expired", code="invite_expired")
        if invite.max_uses and invite.uses_count >= invite.max_uses:
            raise ValidationError(
                message="Invite code has reached maximum uses", code="invite_maxed"
            )
        raise ValidationError(message="Invite code is no longer active", code="invite_inactive")

    # Handle based on invite type
    company = None
    redirect_to = "/"

    if invite.invite_type == "org_creator":
        # org_creator: Mark user as pending onboarding
        user.pending_onboarding = True
        redirect_to = "/onboarding"
        message = "Invite claimed. Please complete organization setup."
    else:
        # team_member: Join existing organization
        if not invite.company_id:
            raise ValidationError(
                message="Invalid invite configuration", code="invalid_invite_config"
            )

        stmt = select(Company).where(Company.id == invite.company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company or not company.is_active:
            raise ValidationError(message="Organization is not active", code="company_inactive")

        user.company_id = company.id
        user.pending_onboarding = False
        redirect_to = "/"
        message = f"Welcome to {company.name}!"

    # Increment invite usage
    invite.uses_count += 1

    await db.commit()
    await db.refresh(user)

    # Build company response if joining team
    company_response = None
    if company:
        company_response = CompanyResponse(
            id=str(company.id),
            name=company.name,
            slug=company.slug,
            logo_url=company.logo_url,
            onboarding_completed=company.onboarding_completed,
        )

    # Refresh JWT with updated claims
    access_token, expires_at = create_access_token(
        user_id=str(user.id),
        company_id=str(company.id) if company else None,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        email_verified=user.email_verified,
    )

    # Update cookie
    set_auth_cookie(response, access_token)

    return ClaimInviteResponse(
        success=True,
        invite_type=invite.invite_type,
        company=company_response,
        redirect_to=redirect_to,
        message=message,
        access_token=access_token,
    )
