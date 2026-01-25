"""Company business logic service."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.core.security import create_access_token, generate_invite_code
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyUpdate, OnboardingRequest


@dataclass
class OnboardingResult:
    """Result of onboarding operation."""

    company: Company
    user: User
    access_token: str | None = None
    expires_at: datetime | None = None
    message: str = ""


class CompanyService:
    """Service for company-related business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_company(self, user_company_id: str | UUID | None, company_id: UUID) -> Company:
        """
        Get company by ID with access control.

        Args:
            user_company_id: The company ID of the requesting user
            company_id: The company ID to retrieve

        Returns:
            Company object

        Raises:
            ForbiddenError: If user doesn't have access to this company
            NotFoundError: If company doesn't exist
        """
        # Multi-tenant security check
        if str(user_company_id) != str(company_id):
            raise ForbiddenError(
                message="You don't have access to this company",
                code="company_access_denied",
            )

        stmt = select(Company).where(Company.id == company_id)
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            raise NotFoundError(message="Company not found", code="company_not_found")

        return company

    async def update_company(
        self,
        user_company_id: str | UUID | None,
        company_id: UUID,
        data: CompanyUpdate,
    ) -> Company:
        """
        Update company profile.

        Args:
            user_company_id: The company ID of the requesting user
            company_id: The company ID to update
            data: Update data

        Returns:
            Updated Company object

        Raises:
            ForbiddenError: If user doesn't have access to this company
            NotFoundError: If company doesn't exist
        """
        # Multi-tenant security check
        if str(user_company_id) != str(company_id):
            raise ForbiddenError(
                message="You don't have access to this company",
                code="company_access_denied",
            )

        stmt = select(Company).where(Company.id == company_id)
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            raise NotFoundError(message="Company not found", code="company_not_found")

        # Update fields (only non-None values)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)

        await self.db.commit()
        await self.db.refresh(company)

        return company

    async def _check_slug_uniqueness(
        self, slug: str, exclude_company_id: UUID | None = None
    ) -> None:
        """
        Check if a slug is already taken.

        Args:
            slug: The slug to check
            exclude_company_id: Company ID to exclude from check (for updates)

        Raises:
            ConflictError: If slug is already taken
        """
        stmt = select(Company).where(Company.slug == slug)
        if exclude_company_id:
            stmt = stmt.where(Company.id != exclude_company_id)

        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ConflictError(
                message="This URL slug is already taken. Please choose a different one.",
                code="slug_taken",
            )

    async def complete_onboarding(self, user_id: UUID, data: OnboardingRequest) -> OnboardingResult:
        """
        Complete organization onboarding.

        For org_creator users (pending_onboarding=True, no company):
        - Creates new company with provided details
        - Assigns company to user
        - Sets pending_onboarding=False
        - Returns new JWT with company_id

        For existing company users:
        - Updates company details
        - Marks onboarding as complete

        Args:
            user_id: The user completing onboarding
            data: Onboarding data (name, slug, etc.)

        Returns:
            OnboardingResult with company, user, and optionally new token

        Raises:
            NotFoundError: If user not found
            ConflictError: If slug is taken
            ForbiddenError: If user has no invite claimed
            ValidationError: If onboarding already completed
        """
        # Fetch user
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(message="User not found", code="user_not_found")

        # Check slug uniqueness (exclude current company if exists)
        await self._check_slug_uniqueness(data.slug, user.company_id)

        # Handle org_creator users (no company yet, pending_onboarding=True)
        if user.pending_onboarding and not user.company_id:
            return await self._create_company_for_user(user, data)

        # Handle existing company users
        if not user.company_id:
            raise ForbiddenError(
                message="You must claim an invite code first",
                code="no_invite_claimed",
            )

        return await self._update_company_onboarding(user, data)

    async def _create_company_for_user(
        self, user: User, data: OnboardingRequest
    ) -> OnboardingResult:
        """Create a new company for an org_creator user."""
        company = Company(
            name=data.name,
            slug=data.slug,
            logo_url=data.logo_url,
            tagline=data.tagline,
            about=data.about,
            invite_code=generate_invite_code(),
            onboarding_completed=True,
        )
        self.db.add(company)
        await self.db.flush()

        # Assign company to user and clear pending_onboarding
        user.company_id = company.id
        user.pending_onboarding = False

        await self.db.commit()
        await self.db.refresh(company)
        await self.db.refresh(user)

        # Create new JWT with company_id
        access_token, expires_at = create_access_token(
            user_id=str(user.id),
            company_id=str(company.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            email_verified=user.email_verified,
        )

        return OnboardingResult(
            company=company,
            user=user,
            access_token=access_token,
            expires_at=expires_at,
            message="Organization created successfully",
        )

    async def _update_company_onboarding(
        self, user: User, data: OnboardingRequest
    ) -> OnboardingResult:
        """Update existing company during onboarding."""
        stmt = select(Company).where(Company.id == user.company_id)
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            raise NotFoundError(message="Organization not found", code="company_not_found")

        if company.onboarding_completed:
            raise ValidationError(
                message="Onboarding has already been completed",
                code="onboarding_already_completed",
            )

        # Update company
        company.name = data.name
        company.slug = data.slug
        company.logo_url = data.logo_url
        company.tagline = data.tagline
        company.about = data.about
        company.onboarding_completed = True

        await self.db.commit()
        await self.db.refresh(company)

        return OnboardingResult(
            company=company,
            user=user,
            message="Organization setup completed successfully",
        )
