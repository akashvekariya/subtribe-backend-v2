"""Invite request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteCreate(BaseModel):
    """Create invite request."""

    email: EmailStr = Field(..., description="Email of person to invite")
    max_uses: int | None = Field(default=1, gt=0, description="Max number of uses (null = unlimited)")
    expires_in_days: int | None = Field(default=7, gt=0, le=30, description="Days until expiry")
    invite_type: str = Field(
        default="team_member",
        description="Type of invite: 'team_member' (join org) or 'org_creator' (create new org)",
    )
    # Note: role is always "admin" - no role selection in V1


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
    invite_type: str  # 'team_member' or 'org_creator'
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
    invite_type: str | None = None  # 'team_member' or 'org_creator'
    company_name: str | None = None  # Only for team_member invites
    company_logo: str | None = None  # Only for team_member invites
    inviter_name: str | None = None
    role: str | None = None
    error: str | None = None  # "expired", "maxed_out", "inactive", "not_found"


class InviteSendResponse(BaseModel):
    """Response after creating and sending invite."""

    success: bool
    invite: InviteResponse | None = None
    message: str
