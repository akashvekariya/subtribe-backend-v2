"""Authentication request/response schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    company_code: str = Field(..., min_length=8, description="Company invite code")

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

    @field_validator("company_code")
    @classmethod
    def validate_company_code(cls, v: str) -> str:
        """Validate company code."""
        if not v or not v.strip():
            raise ValueError("Company code is required")
        v = v.strip()
        if len(v) < 8:
            raise ValueError("Please enter a valid company code")
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


class CompanyResponse(BaseModel):
    """Company details in auth responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    logo_url: str | None = None


class UserResponse(BaseModel):
    """User details in auth responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    first_name: str
    last_name: str
    avatar_url: str | None = None
    company: CompanyResponse


class AuthResponse(BaseModel):
    """Authentication response with JWT."""

    user: UserResponse
    access_token: str
    expires_at: datetime


class MeResponse(BaseModel):
    """Current user details response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    first_name: str
    last_name: str
    avatar_url: str | None = None
    company: CompanyResponse
    last_login_at: datetime | None = None
