"""Company-related Pydantic schemas for request/response validation."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyBase(BaseModel):
    """Base company schema with shared fields."""

    name: str | None = Field(None, max_length=255)
    slug: str | None = Field(None, max_length=100, pattern=r"^[a-z0-9-]+$")
    logo_url: str | None = Field(None, max_length=3000)
    website_url: str | None = Field(None, max_length=3000)
    tagline: str | None = Field(None, max_length=500)
    about: str | None = Field(None, max_length=20000)


class CompanyUpdate(CompanyBase):
    """Schema for updating company profile (PATCH /companies/{id})."""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate company name."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Company name cannot be empty")
        if len(v) > 255:
            raise ValueError("Company name must be 255 characters or less")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        """Validate company slug."""
        if v is None:
            return None
        v = v.strip().lower()
        if not v:
            raise ValueError("Company slug cannot be empty")
        if len(v) > 100:
            raise ValueError("Company slug must be 100 characters or less")
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Company slug can only contain lowercase letters, numbers, and hyphens"
            )
        return v

    @field_validator("logo_url", "website_url")
    @classmethod
    def validate_url(cls, v: str | None, info) -> str | None:
        """Basic URL validation - must start with http:// or https://"""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not (v.startswith("http://") or v.startswith("https://")):
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} must start with http:// or https://")
        if len(v) > 3000:
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} is too long (maximum 3000 characters)")
        return v

    @field_validator("tagline")
    @classmethod
    def validate_tagline(cls, v: str | None) -> str | None:
        """Validate tagline."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 500:
            raise ValueError("Tagline must be 500 characters or less")
        return v

    @field_validator("about")
    @classmethod
    def validate_about(cls, v: str | None) -> str | None:
        """Validate about."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 20000:
            raise ValueError("About section must be 20,000 characters or less")
        return v


class CompanyResponse(BaseModel):
    """Schema for company response (GET /companies/{id})."""

    model_config = ConfigDict(from_attributes=True)  # SQLAlchemy 2.0 compatibility

    id: UUID
    name: str
    slug: str
    invite_code: str
    domain: str | None = None
    logo_url: str | None = None
    website_url: str | None = None
    tagline: str | None = None
    about: str | None = None
    settings: dict
    plan: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
