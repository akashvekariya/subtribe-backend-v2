"""Application schemas for request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.schemas.common import PaginationMeta

# ============================================================================
# Request Schemas
# ============================================================================


class ApplicationCreate(BaseModel):
    """Schema for creating a new application (public endpoint)."""

    first_name: str = Field(..., min_length=1, max_length=100, description="Candidate's first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Candidate's last name")
    email: EmailStr = Field(..., description="Candidate's email address")
    phone: str | None = Field(None, max_length=50, description="Phone number")
    linkedin_url: HttpUrl | None = Field(None, description="LinkedIn profile URL")
    github_url: HttpUrl | None = Field(None, description="GitHub profile URL")
    portfolio_url: HttpUrl | None = Field(None, description="Portfolio website URL")

    # Salary info (optional)
    current_ctc: int | None = Field(None, ge=0, description="Current CTC (in base currency)")
    expected_ctc: int | None = Field(None, ge=0, description="Expected CTC (in base currency)")
    notice_period_days: int | None = Field(None, ge=0, le=365, description="Notice period in days")

    # Screening answers (optional)
    screening_answers: dict | None = Field(
        default_factory=dict, description="Answers to screening questions"
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and clean name fields."""
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Clean phone number."""
        if v:
            v = v.strip()
            return v if v else None
        return None


class ApplicationStatusUpdate(BaseModel):
    """Schema for updating application status."""

    status: str = Field(
        ...,
        description="New status",
        pattern="^(applied|screening|interviewing|offer|hired|rejected)$",
    )
    notes: str = Field(..., min_length=1, description="Notes about the status change (required)")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str) -> str:
        """Validate notes are not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Notes are required when changing status")
        return v


# ============================================================================
# Response Schemas
# ============================================================================


class ApplicationListItem(BaseModel):
    """Schema for application in list view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    linkedin_url: str | None
    status: str
    applied_at: datetime


class JobBasic(BaseModel):
    """Basic job info for application detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str


class ApplicationDetail(BaseModel):
    """Schema for full application details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job: JobBasic

    # Candidate info
    first_name: str
    last_name: str
    email: str
    phone: str | None
    linkedin_url: str | None
    github_url: str | None
    portfolio_url: str | None

    # Salary info
    current_ctc: int | None
    expected_ctc: int | None
    notice_period_days: int | None

    # Resume
    resume_url: str
    resume_filename: str | None

    # Screening
    screening_answers: dict

    # Status
    status: str

    # Metadata
    source: str | None
    applied_at: datetime
    created_at: datetime
    updated_at: datetime


class ApplicationSubmitted(BaseModel):
    """Response after successful application submission."""

    id: UUID
    message: str = "Application submitted successfully"


class ResumeUrl(BaseModel):
    """Response with signed resume URL."""

    url: str
    filename: str
    expires_at: datetime


class ApplicationListResponse(BaseModel):
    """Paginated list of applications."""

    data: list[ApplicationListItem]
    pagination: PaginationMeta


class UserBasic(BaseModel):
    """Basic user info for status history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str


class StatusHistoryItem(BaseModel):
    """Single status history entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_status: str | None
    to_status: str
    changed_by: UserBasic | None
    notes: str | None
    created_at: datetime


class StatusHistoryResponse(BaseModel):
    """Response with status change history."""

    data: list[StatusHistoryItem]
