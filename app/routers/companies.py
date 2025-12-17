"""Company management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.company import Company
from app.schemas.company import CompanyResponse, CompanyUpdate, OnboardingRequest, OnboardingResponse

router = APIRouter()


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


@router.post("/onboarding", response_model=OnboardingResponse, status_code=status.HTTP_200_OK, tags=["Companies"])
async def complete_onboarding(
    data: OnboardingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Complete organization onboarding.

    **Auth**: Required

    Sets company name, slug, logo, tagline, and about.
    Marks onboarding as complete.
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise ForbiddenError(
            message="You must belong to an organization to complete onboarding",
            code="no_company",
        )

    # Fetch company
    stmt = select(Company).where(Company.id == UUID(company_id))
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise NotFoundError(message="Organization not found", code="company_not_found")

    if company.onboarding_completed:
        raise ValidationError(
            message="Onboarding has already been completed",
            code="onboarding_already_completed",
        )

    # Check if slug is unique (excluding current company)
    stmt = select(Company).where(Company.slug == data.slug, Company.id != UUID(company_id))
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise ConflictError(
            message="This URL slug is already taken. Please choose a different one.",
            code="slug_taken",
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
