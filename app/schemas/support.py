"""Support schemas for request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PaginationMeta


# ============================================================================
# Request Schemas
# ============================================================================


class SupportTicketCreate(BaseModel):
    """Schema for creating a new support ticket."""

    subject: str = Field(..., min_length=5, max_length=255, description="Ticket subject")
    description: str = Field(
        ..., min_length=10, max_length=5000, description="Detailed description of the issue"
    )
    priority: str = Field(
        default="medium",
        description="Ticket priority",
        pattern="^(low|medium|high|urgent)$",
    )

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str) -> str:
        """Validate and clean subject."""
        if not v or not v.strip():
            raise ValueError("Subject is required")
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Subject must be at least 5 characters")
        if len(v) > 255:
            raise ValueError("Subject must be 255 characters or less")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate and clean description."""
        if not v or not v.strip():
            raise ValueError("Description is required")
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Description must be at least 10 characters")
        if len(v) > 5000:
            raise ValueError("Description must be 5000 characters or less")
        return v


class SupportTicketUpdate(BaseModel):
    """Schema for updating a support ticket."""

    status: str | None = Field(
        default=None,
        description="New ticket status",
        pattern="^(open|in_progress|resolved|closed)$",
    )
    priority: str | None = Field(
        default=None,
        description="New ticket priority",
        pattern="^(low|medium|high|urgent)$",
    )


class SupportMessageCreate(BaseModel):
    """Schema for adding a message to a ticket."""

    content: str = Field(
        ..., min_length=1, max_length=5000, description="Message content"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate and clean message content."""
        if not v or not v.strip():
            raise ValueError("Message content is required")
        v = v.strip()
        if len(v) > 5000:
            raise ValueError("Message must be 5000 characters or less")
        return v


# ============================================================================
# Response Schemas
# ============================================================================


class UserBasic(BaseModel):
    """Basic user info for support responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class SupportMessageResponse(BaseModel):
    """Schema for a support message in responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    source: str
    discord_message_id: str | None
    created_at: datetime
    user: UserBasic | None


class SupportTicketListItem(BaseModel):
    """Schema for ticket in list view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class SupportTicketDetail(BaseModel):
    """Schema for full ticket details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject: str
    description: str
    status: str
    priority: str
    discord_channel_id: str | None
    discord_thread_id: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    user: UserBasic | None
    messages: list[SupportMessageResponse] = []


class SupportTicketCreated(BaseModel):
    """Response after successful ticket creation."""

    id: UUID
    message: str = "Support ticket created successfully"


class SupportTicketListResponse(BaseModel):
    """Paginated list of support tickets."""

    data: list[SupportTicketListItem]
    pagination: PaginationMeta


class SupportMessagesResponse(BaseModel):
    """Response with messages for a ticket."""

    data: list[SupportMessageResponse]
