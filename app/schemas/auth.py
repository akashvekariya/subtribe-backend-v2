"""Authentication request/response schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """User registration request.

    Creates user account WITHOUT organization. User must claim an invite code
    after email verification to join or create an organization.
    """

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str, info) -> str:
        """Validate name fields."""
        if not v or not v.strip():
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} is required and cannot be empty")
        v = v.strip()
        if len(v) > 100:
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} must be 100 characters or less")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength: min 8 chars, uppercase, number, special char."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter (A-Z)")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number (0-9)")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character (!@#$%^&*...)")
        return v


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    """Email verification request."""

    token: str = Field(..., min_length=1, description="Email verification token")


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""

    email: EmailStr


class CompanyResponse(BaseModel):
    """Company details in auth responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    logo_url: str | None = None
    onboarding_completed: bool = False


class UserResponse(BaseModel):
    """User details in auth responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    first_name: str
    last_name: str
    avatar_url: str | None = None
    email_verified: bool = False
    pending_onboarding: bool = False
    company: CompanyResponse | None = None


class AuthResponse(BaseModel):
    """Authentication response with JWT."""

    user: UserResponse
    access_token: str
    expires_at: datetime
    message: str | None = None


class MeResponse(BaseModel):
    """Current user details response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    first_name: str
    last_name: str
    avatar_url: str | None = None
    email_verified: bool = False
    pending_onboarding: bool = False
    company: CompanyResponse | None = None
    last_login_at: datetime | None = None


class VerifyEmailResponse(BaseModel):
    """Email verification response."""

    success: bool
    message: str


class ResendVerificationResponse(BaseModel):
    """Resend verification email response."""

    success: bool
    message: str


class ClaimInviteRequest(BaseModel):
    """Request to claim an invite code."""

    code: str = Field(..., min_length=1, description="Invite code (e.g., XXXXX-XXXXX)")


class ClaimInviteResponse(BaseModel):
    """Response after claiming an invite."""

    success: bool
    invite_type: str  # 'org_creator' or 'team_member'
    company: CompanyResponse | None = None  # Only for team_member invites
    redirect_to: str  # '/onboarding' or '/'
    message: str | None = None
    access_token: str  # New JWT with updated company_id


# =============================================================================
# Password Reset Schemas
# =============================================================================


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset.

    Always returns success message to prevent email enumeration.
    """

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Response after requesting password reset."""

    success: bool = True
    message: str = "If an account exists with this email, a password reset link has been sent."


class ResetPasswordRequest(BaseModel):
    """Request to reset password with valid token."""

    token: str = Field(..., min_length=1, description="Password reset token")
    password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., min_length=8, description="Confirm new password")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength: min 8 chars, uppercase, number, special char."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter (A-Z)")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number (0-9)")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character (!@#$%^&*...)")
        return v

    @field_validator("confirm_password")
    @classmethod
    def validate_passwords_match(cls, v: str, info) -> str:
        """Validate that passwords match."""
        password = info.data.get("password")
        if password and v != password:
            raise ValueError("Passwords do not match")
        return v


class ResetPasswordResponse(BaseModel):
    """Response after successful password reset."""

    success: bool = True
    message: str = (
        "Your password has been reset successfully. Please log in with your new password."
    )


class ValidateResetTokenRequest(BaseModel):
    """Request to validate a password reset token."""

    token: str = Field(..., min_length=1, description="Password reset token")


class ValidateResetTokenResponse(BaseModel):
    """Response after validating reset token."""

    valid: bool
    email: str | None = None  # Masked email (e.g., "u***@example.com")
    message: str | None = None
