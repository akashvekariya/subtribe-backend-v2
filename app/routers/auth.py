"""Authentication endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import delete_auth_cookie, set_auth_cookie
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ClaimInviteRequest,
    ClaimInviteResponse,
    CompanyResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserResponse,
    ValidateResetTokenRequest,
    ValidateResetTokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services.auth_service import AuthService
from app.utils.rate_limiter import password_reset_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


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
       - org_creator invite -> User goes to onboarding to create org
       - team_member invite -> User joins existing org
    """
    auth_service = AuthService(db)
    result = await auth_service.register(
        email=data.email,
        password=data.password,
        first_name=data.first_name,
        last_name=data.last_name,
    )

    set_auth_cookie(response, result.access_token)

    return AuthResponse(
        user=build_user_response(result.user, result.company),
        access_token=result.access_token,
        expires_at=result.expires_at,
        message="Account created. Please check your email to verify.",
    )


@router.post("/login", response_model=AuthResponse, tags=["Auth"])
async def login(
    response: Response,
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email/password.

    Returns JWT with user claims. Works for users with or without company.
    Implements account lockout after 5 failed attempts (15 min lockout).
    """
    auth_service = AuthService(db)
    client_ip = request.client.host if request.client else None

    result = await auth_service.login(
        email=data.email,
        password=data.password,
        client_ip=client_ip,
    )

    set_auth_cookie(response, result.access_token)

    return AuthResponse(
        user=build_user_response(result.user, result.company),
        access_token=result.access_token,
        expires_at=result.expires_at,
    )


@router.post("/verify-email", response_model=VerifyEmailResponse, tags=["Auth"])
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify email address using token from verification email.
    """
    auth_service = AuthService(db)
    success, message = await auth_service.verify_email(data.token)
    return VerifyEmailResponse(success=success, message=message)


@router.post("/resend-verification", response_model=ResendVerificationResponse, tags=["Auth"])
async def resend_verification(data: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    """
    Resend verification email.
    """
    auth_service = AuthService(db)
    success, message = await auth_service.resend_verification(data.email)
    return ResendVerificationResponse(success=success, message=message)


@router.post("/logout", status_code=status.HTTP_200_OK, tags=["Auth"])
async def logout(response: Response):
    """
    Logout user by clearing authentication cookie.
    """
    delete_auth_cookie(response)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=MeResponse, tags=["Auth"])
async def get_me(
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get current user info from JWT.

    Returns user details including email_verified status and company info.
    """
    auth_service = AuthService(db)
    user_id = UUID(current_user["user_id"])

    user, company = await auth_service.get_user_with_company(user_id)

    if not user:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(message="User not found", code="user_not_found")

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
    auth_service = AuthService(db)
    user_id = UUID(current_user["user_id"])

    result = await auth_service.claim_invite(user_id, data.code)

    set_auth_cookie(response, result.access_token)

    company_response = None
    if result.company:
        company_response = CompanyResponse(
            id=str(result.company.id),
            name=result.company.name,
            slug=result.company.slug,
            logo_url=result.company.logo_url,
            onboarding_completed=result.company.onboarding_completed,
        )

    return ClaimInviteResponse(
        success=True,
        invite_type=result.invite_type,
        company=company_response,
        redirect_to=result.redirect_to,
        message=result.message,
        access_token=result.access_token,
    )


# =============================================================================
# Password Reset Endpoints
# =============================================================================


@router.post("/forgot-password", response_model=ForgotPasswordResponse, tags=["Auth"])
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset email.

    Always returns success to prevent email enumeration.
    Rate limited to 3 requests per email per hour.
    """
    email_lower = data.email.lower()

    # Check rate limit
    if not password_reset_limiter.is_allowed(email_lower):
        logger.warning(f"Rate limit exceeded for password reset: {email_lower}")
        return ForgotPasswordResponse()

    password_reset_limiter.record(email_lower)

    auth_service = AuthService(db)
    await auth_service.request_password_reset(data.email)

    return ForgotPasswordResponse()


@router.post("/reset-password", response_model=ResetPasswordResponse, tags=["Auth"])
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password using a valid reset token.

    Token must be valid and not expired.
    Password must meet strength requirements (8+ chars, uppercase, number, special char).
    Clears reset token after successful reset.
    """
    auth_service = AuthService(db)
    await auth_service.reset_password(data.token, data.password)
    return ResetPasswordResponse()


@router.post("/validate-reset-token", response_model=ValidateResetTokenResponse, tags=["Auth"])
async def validate_reset_token(
    data: ValidateResetTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate a password reset token.

    Returns whether the token is valid and a masked email.
    Used by frontend to show appropriate UI before user enters new password.
    """
    auth_service = AuthService(db)
    valid, masked_email, message = await auth_service.validate_reset_token(data.token)

    if valid:
        return ValidateResetTokenResponse(valid=True, email=masked_email)
    else:
        return ValidateResetTokenResponse(valid=False, message=message)
