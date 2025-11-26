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
    cover_letter: str | None = Field(
        None, max_length=5000, description="Cover letter or additional notes (max 5000 characters)"
    )

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
        if not v or not v.strip():
            raise ValueError("Name is required and cannot be empty")
        v = v.strip()
        if len(v) > 100:
            raise ValueError("Name must be 100 characters or less")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Clean and validate phone number."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 50:
            raise ValueError("Phone number must be 50 characters or less")
        return v

    @field_validator("linkedin_url", "github_url", "portfolio_url")
    @classmethod
    def validate_url(cls, v: str | None, info) -> str | None:
        """Validate URL format."""
        if v is None:
            return None
        v_str = str(v).strip()
        if not v_str:
            return None
        if not (v_str.startswith("http://") or v_str.startswith("https://")):
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} must start with http:// or https://")
        return v

    @field_validator("cover_letter")
    @classmethod
    def validate_cover_letter(cls, v: str | None) -> str | None:
        """Validate cover letter length and content."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 5000:
            raise ValueError(
                "Cover letter must be 5000 characters or less. Please shorten your message."
            )
        return v

    @field_validator("current_ctc", "expected_ctc")
    @classmethod
    def validate_ctc(cls, v: int | None, info) -> int | None:
        """Validate CTC fields."""
        if v is None:
            return None
        if not isinstance(v, int):
            field_name = "Current CTC" if info.field_name == "current_ctc" else "Expected CTC"
            raise ValueError(f"{field_name} must be a valid number")
        if v < 0:
            field_name = "Current CTC" if info.field_name == "current_ctc" else "Expected CTC"
            raise ValueError(f"{field_name} must be 0 or greater")
        return v

    @field_validator("notice_period_days")
    @classmethod
    def validate_notice_period(cls, v: int | None) -> int | None:
        """Validate notice period."""
        if v is None:
            return None
        if not isinstance(v, int):
            raise ValueError("Notice period must be a valid number of days")
        if v < 0:
            raise ValueError("Notice period cannot be negative")
        if v > 365:
            raise ValueError("Notice period must be 365 days or less")
        return v


class ApplicationStatusUpdate(BaseModel):
    """Schema for updating application status."""

    status: str = Field(
        ...,
        description="New status",
        pattern="^(applied|screening|interviewing|offer|hired|rejected)$",
    )
    notes: str | None = Field(None, description="Notes about the status change (optional)")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        """Clean and validate notes if provided."""
        if v:
            v = v.strip()
            return v if v else None
        return None


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
    cover_letter: str | None

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


class ScheduledEmailItem(BaseModel):
    """Single scheduled email entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_type: str
    recipient_email: str
    recipient_name: str
    subject: str
    scheduled_for: datetime
    status: str
    sent_at: datetime | None
    provider_message_id: str | None
    error_message: str | None
    created_at: datetime


class ScheduledEmailsResponse(BaseModel):
    """Response with scheduled emails for an application."""

    data: list[ScheduledEmailItem]
