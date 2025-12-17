"""Invite management endpoints."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.email.providers import EmailMessage, SendGridEmailProvider, StubEmailProvider
from app.exceptions import ForbiddenError, NotFoundError
from app.models.company import Company
from app.models.invite import Invite
from app.models.user import User
from app.schemas.invite import (
    InviteCreate,
    InviteCreatorResponse,
    InviteListResponse,
    InviteResponse,
    InviteSendResponse,
    InviteUpdate,
    InviteValidateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def generate_invite_code() -> str:
    """Generate a unique invite code (format: XXXXX-XXXXX)."""
    part1 = secrets.token_hex(3).upper()[:5]
    part2 = secrets.token_hex(3).upper()[:5]
    return f"{part1}-{part2}"


def _get_email_provider():
    """Get configured email provider."""
    if not settings.email_enabled or settings.email_provider == "stub":
        return StubEmailProvider()
    return SendGridEmailProvider(
        api_key=settings.sendgrid_api_key,
        sandbox_mode=settings.sendgrid_sandbox_mode,
    )


async def send_invite_email(
    invite: Invite, company: Company, inviter: User
) -> bool:
    """Send invitation email to invitee."""
    invite_url = f"{settings.frontend_url}/invite/{invite.code}"

    message = EmailMessage(
        to_email=invite.email,
        to_name=None,
        subject=f"You're invited to join {company.name} on Subtribe",
        body=f"""Hi,

{inviter.full_name} has invited you to join {company.name} on Subtribe ATS.

Click the link below to accept the invitation:
{invite_url}

This invitation expires in 7 days.

If you weren't expecting this invitation, you can ignore this email.

- The Subtribe Team
""",
        from_email=settings.email_from_address,
        from_name=settings.email_from_name,
    )

    provider = _get_email_provider()
    result = await provider.send_email(message)

    if result.success:
        logger.info(f"Invite email sent to {invite.email} for company {company.name}")
    else:
        logger.error(f"Failed to send invite email to {invite.email}: {result.error_message}")

    return result.success


def build_invite_response(invite: Invite, creator: User | None = None) -> InviteResponse:
    """Build InviteResponse from Invite model."""
    creator_response = None
    if creator:
        creator_response = InviteCreatorResponse(
            id=str(creator.id),
            full_name=creator.full_name,
        )

    return InviteResponse(
        id=str(invite.id),
        code=invite.code,
        email=invite.email,
        role=invite.role,
        max_uses=invite.max_uses,
        uses_count=invite.uses_count,
        expires_at=invite.expires_at,
        is_active=invite.is_active,
        created_at=invite.created_at,
        creator=creator_response,
    )


@router.get("", response_model=InviteListResponse, tags=["Invites"])
async def list_invites(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all invites for current user's company.

    Only admin users can view invites.
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise ForbiddenError(
            message="You must belong to an organization to manage invites",
            code="no_company",
        )

    # Get all invites for company
    stmt = (
        select(Invite)
        .where(Invite.company_id == UUID(company_id))
        .order_by(Invite.created_at.desc())
    )
    result = await db.execute(stmt)
    invites = result.scalars().all()

    # Get creators for each invite
    creator_ids = [inv.created_by for inv in invites if inv.created_by]
    creators_map = {}
    if creator_ids:
        stmt = select(User).where(User.id.in_(creator_ids))
        result = await db.execute(stmt)
        creators = result.scalars().all()
        creators_map = {str(c.id): c for c in creators}

    invite_responses = [
        build_invite_response(
            inv, creators_map.get(str(inv.created_by)) if inv.created_by else None
        )
        for inv in invites
    ]

    return InviteListResponse(invites=invite_responses, total=len(invite_responses))


@router.post(
    "", response_model=InviteSendResponse, status_code=status.HTTP_201_CREATED, tags=["Invites"]
)
async def create_invite(
    data: InviteCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create and send an invite to a team member.

    Creates an invite record and sends an email to the invitee.
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise ForbiddenError(
            message="You must belong to an organization to send invites",
            code="no_company",
        )

    user_id = UUID(current_user["user_id"])

    # Get company
    stmt = select(Company).where(Company.id == UUID(company_id))
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise NotFoundError(message="Organization not found", code="company_not_found")

    # Get current user for inviter name
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    inviter = result.scalar_one_or_none()

    # Check if email already has an active invite for this company
    stmt = select(Invite).where(
        Invite.company_id == UUID(company_id),
        Invite.email == data.email,
        Invite.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    existing_invite = result.scalar_one_or_none()

    if existing_invite:
        # Deactivate old invite
        existing_invite.is_active = False

    # Calculate expiry
    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    # Create invite
    invite = Invite(
        company_id=UUID(company_id),
        created_by=user_id,
        email=data.email,
        code=generate_invite_code(),
        role=data.role,
        max_uses=data.max_uses,
        expires_at=expires_at,
    )

    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    # Send invite email
    email_sent = await send_invite_email(invite, company, inviter)

    return InviteSendResponse(
        success=True,
        invite=build_invite_response(invite, inviter),
        message="Invite sent successfully" if email_sent else "Invite created but email failed to send",
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
    company_id = current_user.get("company_id")
    if not company_id:
        raise ForbiddenError(
            message="You must belong to an organization to view invites",
            code="no_company",
        )

    stmt = select(Invite).where(
        Invite.id == invite_id,
        Invite.company_id == UUID(company_id),
    )
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if not invite:
        raise NotFoundError(message="Invite not found", code="invite_not_found")

    # Get creator
    creator = None
    if invite.created_by:
        stmt = select(User).where(User.id == invite.created_by)
        result = await db.execute(stmt)
        creator = result.scalar_one_or_none()

    return build_invite_response(invite, creator)


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
    company_id = current_user.get("company_id")
    if not company_id:
        raise ForbiddenError(
            message="You must belong to an organization to update invites",
            code="no_company",
        )

    stmt = select(Invite).where(
        Invite.id == invite_id,
        Invite.company_id == UUID(company_id),
    )
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if not invite:
        raise NotFoundError(message="Invite not found", code="invite_not_found")

    # Update fields
    if data.is_active is not None:
        invite.is_active = data.is_active
    if data.max_uses is not None:
        invite.max_uses = data.max_uses

    await db.commit()
    await db.refresh(invite)

    # Get creator
    creator = None
    if invite.created_by:
        stmt = select(User).where(User.id == invite.created_by)
        result = await db.execute(stmt)
        creator = result.scalar_one_or_none()

    return build_invite_response(invite, creator)


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Invites"])
async def delete_invite(
    invite_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate an invite (soft delete).
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise ForbiddenError(
            message="You must belong to an organization to delete invites",
            code="no_company",
        )

    stmt = select(Invite).where(
        Invite.id == invite_id,
        Invite.company_id == UUID(company_id),
    )
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if not invite:
        raise NotFoundError(message="Invite not found", code="invite_not_found")

    invite.is_active = False
    await db.commit()


@router.get("/validate/{code}", response_model=InviteValidateResponse, tags=["Invites"])
async def validate_invite(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate an invite code (public endpoint).

    Returns company info if valid, error info if invalid.
    """
    stmt = select(Invite).where(Invite.code == code)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if not invite:
        return InviteValidateResponse(valid=False, error="not_found")

    if not invite.is_active:
        return InviteValidateResponse(valid=False, error="inactive")

    if invite.expires_at and datetime.now(timezone.utc) > invite.expires_at:
        return InviteValidateResponse(valid=False, error="expired")

    if invite.max_uses and invite.uses_count >= invite.max_uses:
        return InviteValidateResponse(valid=False, error="maxed_out")

    # Get company info
    stmt = select(Company).where(Company.id == invite.company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company or not company.is_active:
        return InviteValidateResponse(valid=False, error="inactive")

    # Get inviter name
    inviter_name = None
    if invite.created_by:
        stmt = select(User).where(User.id == invite.created_by)
        result = await db.execute(stmt)
        inviter = result.scalar_one_or_none()
        if inviter:
            inviter_name = inviter.full_name

    return InviteValidateResponse(
        valid=True,
        company_name=company.name,
        company_logo=company.logo_url,
        inviter_name=inviter_name,
        role=invite.role,
    )
