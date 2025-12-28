"""Company management endpoints."""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.models.company import Company
from app.models.user import User
from app.schemas.company import (
    CompanyResponse,
    CompanyUpdate,
    OnboardingRequest,
    OnboardingResponse,
)

router = APIRouter()


def generate_invite_code() -> str:
    """Generate a unique invite code (format: XXXXX-XXXXX)."""
    part1 = secrets.token_hex(3).upper()[:5]
    part2 = secrets.token_hex(3).upper()[:5]
    return f"{part1}-{part2}"


@router.get("/{company_id}", response_model=CompanyResponse, tags=["Companies"])
async def get_company(
    company_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get company details.

    **Auth**: Required (users can only access their own company)

    **Returns**: Company profile including invite_code (for team onboarding)
    """
    # Check if user belongs to this company (multi-tenant security)
    if str(current_user["company_id"]) != str(company_id):
        raise ForbiddenError(
            message="You don't have access to this company", code="company_access_denied"
        )

    # Fetch company
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise NotFoundError(message="Company not found", code="company_not_found")

    return company


@router.patch("/{company_id}", response_model=CompanyResponse, tags=["Companies"])
async def update_company(
    company_id: UUID,
    data: CompanyUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update company profile.

    **Auth**: Required (users can only update their own company)

    **Updatable fields**: name, slug, logo_url, website_url, tagline, about

    **Read-only fields**: plan, is_active, invite_code, settings

    **Note**: These fields are displayed to candidates on public job pages
    """
    # Check if user belongs to this company (multi-tenant security)
    if str(current_user["company_id"]) != str(company_id):
        raise ForbiddenError(
            message="You don't have access to this company", code="company_access_denied"
        )

    # Fetch company
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise NotFoundError(message="Company not found", code="company_not_found")

    # Update fields (only non-None values)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    # Commit changes
    await db.commit()
    await db.refresh(company)

    return company


@router.post(
    "/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_200_OK,
    tags=["Companies"],
)
async def complete_onboarding(
    data: OnboardingRequest,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Complete organization onboarding.

    **Auth**: Required

    For org_creator users (pending_onboarding=True):
    - Creates new company with provided details
    - Assigns company to user
    - Sets pending_onboarding=False

    For existing company users:
    - Updates company details
    - Marks onboarding as complete
    """
    user_id = UUID(current_user["user_id"])

    # Fetch user from DB
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError(message="User not found", code="user_not_found")

    # Check if slug is unique
    stmt = select(Company).where(Company.slug == data.slug)
    if user.company_id:
        # Exclude current company from check
        stmt = stmt.where(Company.id != user.company_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise ConflictError(
            message="This URL slug is already taken. Please choose a different one.",
            code="slug_taken",
        )

    # Handle org_creator users (no company yet, pending_onboarding=True)
    if user.pending_onboarding and not user.company_id:
        # Create new company
        company = Company(
            name=data.name,
            slug=data.slug,
            logo_url=data.logo_url,
            tagline=data.tagline,
            about=data.about,
            invite_code=generate_invite_code(),
            onboarding_completed=True,
        )
        db.add(company)
        await db.flush()

        # Assign company to user and clear pending_onboarding
        user.company_id = company.id
        user.pending_onboarding = False

        await db.commit()
        await db.refresh(company)
        await db.refresh(user)

        # Update JWT cookie with new company_id
        from datetime import datetime, timedelta, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days)
        payload = {
            "sub": str(user.id),
            "company_id": str(company.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email_verified": user.email_verified,
            "exp": expires_at,
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        # Set updated cookie
        cookie_kwargs = {
            "key": "access_token",
            "value": token,
            "httponly": True,
            "secure": settings.cookie_secure,
            "samesite": settings.cookie_samesite,
            "max_age": settings.cookie_max_age,
            "path": "/",
        }
        if settings.cookie_domain:
            cookie_kwargs["domain"] = settings.cookie_domain
        response.set_cookie(**cookie_kwargs)

        return OnboardingResponse(
            success=True,
            company=company,
            message="Organization created successfully",
        )

    # Handle existing company users (update company details)
    if not user.company_id:
        raise ForbiddenError(
            message="You must claim an invite code first",
            code="no_invite_claimed",
        )

    # Fetch company
    stmt = select(Company).where(Company.id == user.company_id)
    result = await db.execute(stmt)
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

    await db.commit()
    await db.refresh(company)

    return OnboardingResponse(
        success=True,
        company=company,
        message="Organization setup completed successfully",
    )
