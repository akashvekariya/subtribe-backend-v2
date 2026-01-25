"""Invite management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import ForbiddenError
from app.schemas.invite import (
    InviteCreate,
    InviteCreatorResponse,
    InviteListResponse,
    InviteResponse,
    InviteSendResponse,
    InviteUpdate,
    InviteValidateResponse,
)
from app.services.invite_service import InviteService

router = APIRouter()


def _build_invite_response(invite, creator) -> InviteResponse:
    """Build InviteResponse from invite and creator."""
    creator_response = None
    if creator:
        creator_response = InviteCreatorResponse(
            id=creator.id,
            full_name=creator.full_name,
        )

    return InviteResponse(
        id=str(invite.id),
        code=invite.code,
        email=invite.email,
        role=invite.role,
        invite_type=invite.invite_type,
        max_uses=invite.max_uses,
        uses_count=invite.uses_count,
        expires_at=invite.expires_at,
        is_active=invite.is_active,
        created_at=invite.created_at,
        creator=creator_response,
    )


def _require_company(current_user: dict) -> str:
    """Require user to have a company, return company_id."""
    company_id = current_user.get("company_id")
    if not company_id:
        raise ForbiddenError(
            message="You must belong to an organization to manage invites",
            code="no_company",
        )
    return company_id


@router.get("", response_model=InviteListResponse, tags=["Invites"])
async def list_invites(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all invites for current user's company.

    Only admin users can view invites.
    """
    company_id = _require_company(current_user)
    service = InviteService(db)

    invites_with_creators = await service.list_invites(company_id)
    invite_responses = [
        _build_invite_response(invite, creator)
        for invite, creator in invites_with_creators
    ]

    return InviteListResponse(invites=invite_responses, total=len(invite_responses))


@router.post(
    "",
    response_model=InviteSendResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Invites"],
)
async def create_invite(
    data: InviteCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create and send an invite.

    Two types of invites:
    - team_member: Invite someone to join your organization (default)
    - org_creator: Invite someone to create their own organization (super admin only)
    """
    service = InviteService(db)

    result = await service.create_invite(
        user_id=UUID(current_user["user_id"]),
        user_email=current_user.get("email", ""),
        company_id=current_user.get("company_id"),
        email=data.email,
        invite_type=data.invite_type,
        max_uses=data.max_uses,
    )

    return InviteSendResponse(
        success=True,
        invite=_build_invite_response(result.invite, result.creator),
        message=result.message,
    )


@router.get("/{invite_id}", response_model=InviteResponse, tags=["Invites"])
async def get_invite(
    invite_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get invite details by ID.
    """
    company_id = _require_company(current_user)
    service = InviteService(db)

    invite, creator = await service.get_invite(company_id, invite_id)
    return _build_invite_response(invite, creator)


@router.patch("/{invite_id}", response_model=InviteResponse, tags=["Invites"])
async def update_invite(
    invite_id: UUID,
    data: InviteUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update invite (deactivate or change max_uses).
    """
    company_id = _require_company(current_user)
    service = InviteService(db)

    invite, creator = await service.update_invite(
        company_id=company_id,
        invite_id=invite_id,
        is_active=data.is_active,
        max_uses=data.max_uses,
    )

    return _build_invite_response(invite, creator)


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Invites"])
async def delete_invite(
    invite_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate an invite (soft delete).
    """
    company_id = _require_company(current_user)
    service = InviteService(db)

    await service.delete_invite(company_id, invite_id)


@router.get("/validate/{code}", response_model=InviteValidateResponse, tags=["Invites"])
async def validate_invite(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate an invite code (public endpoint).

    Returns invite info if valid:
    - For team_member invites: includes company info
    - For org_creator invites: no company info (user will create their own org)
    """
    service = InviteService(db)
    result = await service.validate_invite(code)

    return InviteValidateResponse(
        valid=result.valid,
        error=result.error,
        invite_type=result.invite_type,
        company_name=result.company_name,
        company_logo=result.company_logo,
        inviter_name=result.inviter_name,
        role=result.role,
    )
