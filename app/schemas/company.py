"""Company-related Pydantic schemas for request/response validation."""

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

    @field_validator("logo_url", "website_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """Basic URL validation - must start with http:// or https://"""
        if v is not None and v.strip():
            v = v.strip()
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
        return v if v else None


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
