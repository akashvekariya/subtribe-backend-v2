"""Job schemas - Request/Response models for job endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PaginationMeta

# ============================================================================
# Request Schemas
# ============================================================================


class JobCreate(BaseModel):
    """Schema for creating a new job."""

    title: str = Field(..., min_length=1, max_length=255, description="Job title")
    description: str = Field(
        ..., min_length=1, max_length=100000, description="Job description (markdown supported)"
    )

    # Job Details (optional)
    position_type: str | None = Field(
        None, description="full_time | part_time | contract | internship"
    )
    experience_level: str | None = Field(
        None, max_length=50, description="Experience level required"
    )
    department: str | None = Field(None, max_length=100, description="Department")

    # Location (optional except country)
    location_type: str | None = Field(None, description="remote | hybrid | onsite")
    location_city: str | None = Field(None, max_length=100)
    location_state: str | None = Field(None, max_length=100)
    location_country: str | None = Field("India", max_length=100, description="Default: India")

    # Salary (optional)
    salary_min: int | None = Field(None, ge=0, description="Minimum salary")
    salary_max: int | None = Field(None, ge=0, description="Maximum salary")
    salary_currency: str | None = Field("INR", max_length=10, description="Default: INR")

    # Status (optional, defaults to draft)
    status: str | None = Field("draft", description="draft | active | closed")

    @field_validator("position_type")
    @classmethod
    def validate_position_type(cls, v):
        if v and v not in ["full_time", "part_time", "contract", "internship"]:
            raise ValueError(
                "position_type must be one of: full_time, part_time, contract, internship"
            )
        return v

    @field_validator("location_type")
    @classmethod
    def validate_location_type(cls, v):
        if v and v not in ["remote", "hybrid", "onsite"]:
            raise ValueError("location_type must be one of: remote, hybrid, onsite")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in ["draft", "active", "closed"]:
            raise ValueError("status must be one of: draft, active, closed")
        return v


class JobUpdate(BaseModel):
    """Schema for updating a job (all fields optional for partial update)."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1, max_length=100000)

    position_type: str | None = None
    experience_level: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=100)

    location_type: str | None = None
    location_city: str | None = Field(None, max_length=100)
    location_state: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=100)

    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    salary_currency: str | None = Field(None, max_length=10)

    status: str | None = None

    @field_validator("position_type")
    @classmethod
    def validate_position_type(cls, v):
        if v and v not in ["full_time", "part_time", "contract", "internship"]:
            raise ValueError(
                "position_type must be one of: full_time, part_time, contract, internship"
            )
        return v

    @field_validator("location_type")
    @classmethod
    def validate_location_type(cls, v):
        if v and v not in ["remote", "hybrid", "onsite"]:
            raise ValueError("location_type must be one of: remote, hybrid, onsite")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in ["draft", "active", "closed"]:
            raise ValueError("status must be one of: draft, active, closed")
        return v


# ============================================================================
# Response Schemas
# ============================================================================


class JobCreatorResponse(BaseModel):
    """Schema for job creator info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str


class CompanyBriefResponse(BaseModel):
    """Brief company info for job responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    logo_url: str | None = None


class CompanyPublicResponse(BaseModel):
    """Public company info for job page (candidates view)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    logo_url: str | None = None
    website_url: str | None = None
    tagline: str | None = None
    about: str | None = None


class JobResponse(BaseModel):
    """Full job response for authenticated users."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    created_by: UUID

    title: str
    description: str

    position_type: str | None = None
    experience_level: str | None = None
    department: str | None = None

    location_type: str | None = None
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None

    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None

    status: str
    slug: str
    views_count: int

    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Relationships
    creator: JobCreatorResponse | None = None
    company: CompanyBriefResponse | None = None


class JobListItem(BaseModel):
    """Job list item (brief info for listing)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    status: str
    position_type: str | None = None
    location_type: str | None = None
    views_count: int
    applications_count: int

    created_by: UUID
    creator: JobCreatorResponse | None = None

    published_at: datetime | None = None
    created_at: datetime


class JobListResponse(BaseModel):
    """Response for job list with data wrapper and pagination."""

    data: list[JobListItem]
    pagination: PaginationMeta


class PublicJobResponse(BaseModel):
    """Public job response for candidates (no sensitive data)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    title: str
    description: str

    position_type: str | None = None
    experience_level: str | None = None
    department: str | None = None

    location_type: str | None = None
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None

    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None

    status: str
    views_count: int

    published_at: datetime | None = None
    created_at: datetime

    # Company details for candidates
    company: CompanyPublicResponse
