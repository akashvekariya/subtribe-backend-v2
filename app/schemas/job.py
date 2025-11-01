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

    # Experience (optional)
    min_experience_years: int | None = Field(None, ge=0, description="Minimum years of experience")
    max_experience_years: int | None = Field(None, ge=0, description="Maximum years of experience")

    # Skills (optional)
    required_skills: list[str] = Field(default_factory=list, description="Required skills")
    preferred_skills: list[str] = Field(default_factory=list, description="Nice-to-have skills")

    # Screening Questions (optional)
    screening_questions: list[dict] = Field(
        default_factory=list, description="Custom screening questions for candidates"
    )

    # Status (optional, defaults to draft)
    status: str | None = Field("draft", description="draft | active | closed")

    @field_validator("title", "description")
    @classmethod
    def validate_required_text(cls, v: str, info) -> str:
        """Validate required text fields."""
        if not v or not v.strip():
            field_name = info.field_name.title()
            raise ValueError(f"{field_name} is required and cannot be empty")
        v = v.strip()
        if info.field_name == "title" and len(v) > 255:
            raise ValueError("Job title must be 255 characters or less")
        if info.field_name == "description" and len(v) > 100000:
            raise ValueError("Job description is too long (maximum 100,000 characters)")
        return v

    @field_validator("position_type")
    @classmethod
    def validate_position_type(cls, v):
        valid_types = [
            "full_time",
            "part_time",
            "contract",
            "temporary",
            "other",
            "volunteer",
            "internship",
        ]
        if v and v not in valid_types:
            raise ValueError(
                "Position type must be one of: Full-time, Part-time, Contract, "
                "Temporary, Other, Volunteer, or Internship"
            )
        return v

    @field_validator("location_type")
    @classmethod
    def validate_location_type(cls, v):
        if v and v not in ["remote", "hybrid", "onsite"]:
            raise ValueError("Location type must be one of: Remote, Hybrid, or Onsite")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in ["draft", "active", "closed"]:
            raise ValueError("Job status must be one of: Draft, Active, or Closed")
        return v

    @field_validator("salary_min", "salary_max")
    @classmethod
    def validate_salary(cls, v: int | None, info) -> int | None:
        """Validate salary fields."""
        if v is None:
            return None
        if v < 0:
            field_name = "Minimum salary" if info.field_name == "salary_min" else "Maximum salary"
            raise ValueError(f"{field_name} cannot be negative")
        return v

    @field_validator("min_experience_years", "max_experience_years")
    @classmethod
    def validate_experience(cls, v: int | None, info) -> int | None:
        """Validate experience fields."""
        if v is None:
            return None
        if v < 0:
            raise ValueError("Years of experience cannot be negative")
        if v > 50:
            raise ValueError("Years of experience must be 50 or less")
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

    min_experience_years: int | None = Field(None, ge=0)
    max_experience_years: int | None = Field(None, ge=0)

    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None

    screening_questions: list[dict] | None = None

    status: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """Validate title."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Job title cannot be empty")
        if len(v) > 255:
            raise ValueError("Job title must be 255 characters or less")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """Validate description."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Job description cannot be empty")
        if len(v) > 100000:
            raise ValueError("Job description is too long (maximum 100,000 characters)")
        return v

    @field_validator("position_type")
    @classmethod
    def validate_position_type(cls, v):
        valid_types = [
            "full_time",
            "part_time",
            "contract",
            "temporary",
            "other",
            "volunteer",
            "internship",
        ]
        if v and v not in valid_types:
            raise ValueError(
                "Position type must be one of: Full-time, Part-time, Contract, "
                "Temporary, Other, Volunteer, or Internship"
            )
        return v

    @field_validator("location_type")
    @classmethod
    def validate_location_type(cls, v):
        if v and v not in ["remote", "hybrid", "onsite"]:
            raise ValueError("Location type must be one of: Remote, Hybrid, or Onsite")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in ["draft", "active", "closed"]:
            raise ValueError("Job status must be one of: Draft, Active, or Closed")
        return v

    @field_validator("salary_min", "salary_max")
    @classmethod
    def validate_salary(cls, v: int | None, info) -> int | None:
        """Validate salary fields."""
        if v is None:
            return None
        if v < 0:
            field_name = "Minimum salary" if info.field_name == "salary_min" else "Maximum salary"
            raise ValueError(f"{field_name} cannot be negative")
        return v

    @field_validator("min_experience_years", "max_experience_years")
    @classmethod
    def validate_experience(cls, v: int | None, info) -> int | None:
        """Validate experience fields."""
        if v is None:
            return None
        if v < 0:
            raise ValueError("Years of experience cannot be negative")
        if v > 50:
            raise ValueError("Years of experience must be 50 or less")
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

    min_experience_years: int | None = None
    max_experience_years: int | None = None

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    screening_questions: list[dict] = Field(default_factory=list)

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

    min_experience_years: int | None = None
    max_experience_years: int | None = None

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    screening_questions: list[dict] = Field(default_factory=list)

    status: str
    views_count: int

    published_at: datetime | None = None
    created_at: datetime

    # Company details for candidates
    company: CompanyPublicResponse
