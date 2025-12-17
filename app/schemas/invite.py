"""Invite request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteCreate(BaseModel):
    """Create invite request."""

    email: EmailStr = Field(..., description="Email of person to invite")
    role: str = Field(default="recruiter", description="Role for invited user")
    max_uses: int | None = Field(default=1, gt=0, description="Max number of uses (null = unlimited)")
    expires_in_days: int | None = Field(default=7, gt=0, le=30, description="Days until expiry")


class InviteUpdate(BaseModel):
    """Update invite request."""

    is_active: bool | None = None
    max_uses: int | None = Field(None, gt=0)


class InviteCreatorResponse(BaseModel):
    """Creator info in invite response."""

    id: str
    full_name: str


class InviteResponse(BaseModel):
    """Invite details response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    email: str
    role: str
    max_uses: int | None
    uses_count: int
    expires_at: datetime | None
    is_active: bool
    created_at: datetime
    creator: InviteCreatorResponse | None = None


class InviteListResponse(BaseModel):
    """List of invites response."""

    invites: list[InviteResponse]
    total: int


class InviteValidateResponse(BaseModel):
    """Invite validation response."""

    valid: bool
    company_name: str | None = None
    company_logo: str | None = None
    inviter_name: str | None = None
    role: str | None = None
    error: str | None = None  # "expired", "maxed_out", "inactive", "not_found"


class InviteSendResponse(BaseModel):
    """Response after creating and sending invite."""

    success: bool
    invite: InviteResponse | None = None
    message: str
