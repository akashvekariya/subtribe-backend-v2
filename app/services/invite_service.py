"""Invite business logic service."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.security import generate_invite_code
from app.email.providers import EmailMessage, SendGridEmailProvider, StubEmailProvider
from app.models.company import Company
from app.models.invite import Invite
from app.models.user import User

logger = logging.getLogger(__name__)

# Default invite expiration in days
INVITE_EXPIRY_DAYS = 7


@dataclass
class InviteCreator:
    """Invite creator info."""

    id: str
    full_name: str


@dataclass
class InviteResult:
    """Result of invite operations."""

    invite: Invite
    creator: InviteCreator | None
    email_sent: bool = False
    message: str = ""


@dataclass
class InviteValidation:
    """Result of invite validation."""

    valid: bool
    error: str | None = None
    invite_type: str | None = None
    company_name: str | None = None
    company_logo: str | None = None
    inviter_name: str | None = None
    role: str | None = None


class InviteService:
    """Service for invite-related business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def is_super_admin(email: str) -> bool:
        """Check if the email is in the super admin whitelist."""
        if not settings.super_admin_emails:
            return False
        admin_emails = [
            e.strip().lower()
            for e in settings.super_admin_emails.split(",")
            if e.strip()
        ]
        return email.lower() in admin_emails

    @staticmethod
    def _get_email_provider():
        """Get configured email provider."""
        if not settings.email_enabled or settings.email_provider == "stub":
            return StubEmailProvider()
        return SendGridEmailProvider(
            api_key=settings.sendgrid_api_key,
            sandbox_mode=settings.sendgrid_sandbox_mode,
        )

    async def list_invites(
        self, company_id: str | UUID
    ) -> list[tuple[Invite, InviteCreator | None]]:
        """
        List all invites for a company.

        Args:
            company_id: Company ID

        Returns:
            List of tuples (Invite, InviteCreator or None)
        """
        stmt = (
            select(Invite)
            .where(Invite.company_id == UUID(str(company_id)))
            .order_by(Invite.created_at.desc())
        )
        result = await self.db.execute(stmt)
        invites = list(result.scalars().all())

        # Get creators
        creator_ids = [inv.created_by for inv in invites if inv.created_by]
        creators_map: dict[str, InviteCreator] = {}

        if creator_ids:
            stmt = select(User).where(User.id.in_(creator_ids))
            result = await self.db.execute(stmt)
            creators = result.scalars().all()
            creators_map = {
                str(c.id): InviteCreator(id=str(c.id), full_name=c.full_name)
                for c in creators
            }

        return [
            (inv, creators_map.get(str(inv.created_by)) if inv.created_by else None)
            for inv in invites
        ]

    async def create_invite(
        self,
        user_id: UUID,
        user_email: str,
        company_id: str | UUID | None,
        email: str,
        invite_type: str = "team_member",
        max_uses: int | None = None,
    ) -> InviteResult:
        """
        Create and send an invite.

        Args:
            user_id: ID of the user creating the invite
            user_email: Email of the user creating the invite
            company_id: Company ID (None for org_creator invites)
            email: Email to invite
            invite_type: 'team_member' or 'org_creator'
            max_uses: Maximum uses for the invite

        Returns:
            InviteResult with invite and status

        Raises:
            ValidationError: If trying to self-invite
            ForbiddenError: If not authorized for the invite type
            NotFoundError: If company not found
        """
        # Prevent self-invites
        if email.lower() == user_email.lower():
            raise ValidationError(
                message="You cannot send an invite to yourself",
                code="self_invite",
            )

        # Get inviter
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        inviter = result.scalar_one_or_none()

        if invite_type == "org_creator":
            return await self._create_org_creator_invite(
                user_id, user_email, email, max_uses, inviter
            )

        return await self._create_team_member_invite(
            user_id, company_id, email, max_uses, inviter
        )

    async def get_invite(
        self, company_id: str | UUID, invite_id: UUID
    ) -> tuple[Invite, InviteCreator | None]:
        """
        Get invite by ID.

        Args:
            company_id: Company ID for access control
            invite_id: Invite ID

        Returns:
            Tuple of (Invite, InviteCreator or None)

        Raises:
            NotFoundError: If invite not found
        """
        stmt = select(Invite).where(
            Invite.id == invite_id,
            Invite.company_id == UUID(str(company_id)),
        )
        result = await self.db.execute(stmt)
        invite = result.scalar_one_or_none()

        if not invite:
            raise NotFoundError(message="Invite not found", code="invite_not_found")

        creator = await self._get_invite_creator(invite.created_by)
        return invite, creator

    async def update_invite(
        self,
        company_id: str | UUID,
        invite_id: UUID,
        is_active: bool | None = None,
        max_uses: int | None = None,
    ) -> tuple[Invite, InviteCreator | None]:
        """
        Update invite settings.

        Args:
            company_id: Company ID for access control
            invite_id: Invite ID
            is_active: New active status
            max_uses: New max uses

        Returns:
            Tuple of (updated Invite, InviteCreator or None)

        Raises:
            NotFoundError: If invite not found
        """
        stmt = select(Invite).where(
            Invite.id == invite_id,
            Invite.company_id == UUID(str(company_id)),
        )
        result = await self.db.execute(stmt)
        invite = result.scalar_one_or_none()

        if not invite:
            raise NotFoundError(message="Invite not found", code="invite_not_found")

        if is_active is not None:
            invite.is_active = is_active
        if max_uses is not None:
            invite.max_uses = max_uses

        await self.db.commit()
        await self.db.refresh(invite)

        creator = await self._get_invite_creator(invite.created_by)
        return invite, creator

    async def delete_invite(self, company_id: str | UUID, invite_id: UUID) -> None:
        """
        Deactivate an invite (soft delete).

        Args:
            company_id: Company ID for access control
            invite_id: Invite ID

        Raises:
            NotFoundError: If invite not found
        """
        stmt = select(Invite).where(
            Invite.id == invite_id,
            Invite.company_id == UUID(str(company_id)),
        )
        result = await self.db.execute(stmt)
        invite = result.scalar_one_or_none()

        if not invite:
            raise NotFoundError(message="Invite not found", code="invite_not_found")

        invite.is_active = False
        await self.db.commit()

    async def validate_invite(self, code: str) -> InviteValidation:
        """
        Validate an invite code.

        Args:
            code: Invite code

        Returns:
            InviteValidation with status and info
        """
        stmt = select(Invite).where(Invite.code == code)
        result = await self.db.execute(stmt)
        invite = result.scalar_one_or_none()

        if not invite:
            return InviteValidation(valid=False, error="not_found")

        if not invite.is_active:
            return InviteValidation(valid=False, error="inactive")

        if invite.expires_at and datetime.now(timezone.utc) > invite.expires_at:
            return InviteValidation(valid=False, error="expired")

        if invite.max_uses and invite.uses_count >= invite.max_uses:
            return InviteValidation(valid=False, error="maxed_out")

        # Get inviter name
        inviter_name = None
        if invite.created_by:
            stmt = select(User).where(User.id == invite.created_by)
            result = await self.db.execute(stmt)
            inviter = result.scalar_one_or_none()
            if inviter:
                inviter_name = inviter.full_name

        # Handle org_creator invites
        if invite.invite_type == "org_creator":
            return InviteValidation(
                valid=True,
                invite_type="org_creator",
                inviter_name=inviter_name,
                role=invite.role,
            )

        # Handle team_member invites
        if not invite.company_id:
            return InviteValidation(valid=False, error="inactive")

        stmt = select(Company).where(Company.id == invite.company_id)
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company or not company.is_active:
            return InviteValidation(valid=False, error="inactive")

        return InviteValidation(
            valid=True,
            invite_type="team_member",
            company_name=company.name,
            company_logo=company.logo_url,
            inviter_name=inviter_name,
            role=invite.role,
        )

    # Private helper methods

    async def _create_org_creator_invite(
        self,
        user_id: UUID,
        user_email: str,
        email: str,
        max_uses: int | None,
        inviter: User | None,
    ) -> InviteResult:
        """Create an org_creator invite (super admin only)."""
        if not self.is_super_admin(user_email):
            raise ForbiddenError(
                message="Only super administrators can create organization creator invites",
                code="not_super_admin",
            )

        # Deactivate existing active org_creator invite
        stmt = select(Invite).where(
            Invite.email == email,
            Invite.invite_type == "org_creator",
            Invite.is_active == True,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        existing_invite = result.scalar_one_or_none()

        if existing_invite:
            existing_invite.is_active = False

        expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS)

        invite = Invite(
            company_id=None,
            created_by=user_id,
            email=email,
            code=generate_invite_code(),
            role="admin",
            invite_type="org_creator",
            max_uses=max_uses,
            expires_at=expires_at,
        )

        self.db.add(invite)
        await self.db.commit()
        await self.db.refresh(invite)

        email_sent = await self._send_org_creator_invite_email(invite, inviter)

        creator = (
            InviteCreator(id=str(inviter.id), full_name=inviter.full_name)
            if inviter
            else None
        )

        return InviteResult(
            invite=invite,
            creator=creator,
            email_sent=email_sent,
            message="Organization creator invite sent successfully"
            if email_sent
            else "Invite created but email failed to send",
        )

    async def _create_team_member_invite(
        self,
        user_id: UUID,
        company_id: str | UUID | None,
        email: str,
        max_uses: int | None,
        inviter: User | None,
    ) -> InviteResult:
        """Create a team_member invite."""
        if not company_id:
            raise ForbiddenError(
                message="You must belong to an organization to send team invites",
                code="no_company",
            )

        # Get company
        stmt = select(Company).where(Company.id == UUID(str(company_id)))
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            raise NotFoundError(
                message="Organization not found", code="company_not_found"
            )

        # Deactivate existing active invite
        stmt = select(Invite).where(
            Invite.company_id == UUID(str(company_id)),
            Invite.email == email,
            Invite.is_active == True,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        existing_invite = result.scalar_one_or_none()

        if existing_invite:
            existing_invite.is_active = False

        expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS)

        invite = Invite(
            company_id=UUID(str(company_id)),
            created_by=user_id,
            email=email,
            code=generate_invite_code(),
            role="admin",
            invite_type="team_member",
            max_uses=max_uses,
            expires_at=expires_at,
        )

        self.db.add(invite)
        await self.db.commit()
        await self.db.refresh(invite)

        email_sent = await self._send_team_member_invite_email(invite, company, inviter)

        creator = (
            InviteCreator(id=str(inviter.id), full_name=inviter.full_name)
            if inviter
            else None
        )

        return InviteResult(
            invite=invite,
            creator=creator,
            email_sent=email_sent,
            message="Team invite sent successfully"
            if email_sent
            else "Invite created but email failed to send",
        )

    async def _send_team_member_invite_email(
        self, invite: Invite, company: Company, inviter: User | None
    ) -> bool:
        """Send invitation email to team member."""
        invite_url = f"{settings.dashboard_url}/invite/{invite.code}"
        inviter_name = inviter.full_name if inviter else "Someone"

        message = EmailMessage(
            to_email=invite.email,
            to_name=None,
            subject=f"You're invited to join {company.name} on Subtribe",
            body=f"""Hi,

{inviter_name} has invited you to join {company.name} on Subtribe.

Click the link below to accept the invitation:
{invite_url}

Your invite code: {invite.code}

This invitation expires in {INVITE_EXPIRY_DAYS} days.

If you weren't expecting this invitation, you can ignore this email.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = self._get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(
                f"Team member invite email sent to {invite.email} for company {company.name}"
            )
        else:
            logger.error(
                f"Failed to send team member invite email to {invite.email}: "
                f"{result.error_message}"
            )

        return result.success

    async def _send_org_creator_invite_email(
        self, invite: Invite, inviter: User | None
    ) -> bool:
        """Send invitation email to create organization."""
        invite_url = f"{settings.dashboard_url}/invite/{invite.code}"
        inviter_text = f"{inviter.full_name} has" if inviter else "You have been"

        message = EmailMessage(
            to_email=invite.email,
            to_name=None,
            subject="You're invited to create your organization on Subtribe",
            body=f"""Hi,

{inviter_text} invited you to create your organization on Subtribe.

Click the link below to get started:
{invite_url}

Your invite code: {invite.code}

You'll be able to:
- Set up your organization profile
- Invite your team members
- Start managing your recruitment pipeline

This invitation expires in {INVITE_EXPIRY_DAYS} days.

If you weren't expecting this invitation, you can ignore this email.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = self._get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(f"Org creator invite email sent to {invite.email}")
        else:
            logger.error(
                f"Failed to send org creator invite email to {invite.email}: "
                f"{result.error_message}"
            )

        return result.success

    async def _get_invite_creator(
        self, created_by: UUID | None
    ) -> InviteCreator | None:
        """Get invite creator info."""
        if not created_by:
            return None

        stmt = select(User).where(User.id == created_by)
        result = await self.db.execute(stmt)
        creator = result.scalar_one_or_none()

        if not creator:
            return None

        return InviteCreator(id=str(creator.id), full_name=creator.full_name)
