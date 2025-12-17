"""Authentication request/response schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """User registration request.

    Two modes:
    1. New organization: No invite_token - creates user + new org
    2. Join via invite: With invite_token - creates user and joins existing org
    """

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    invite_token: str | None = Field(None, description="Invite token to join existing organization")

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
