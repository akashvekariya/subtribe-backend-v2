"""Company management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import ForbiddenError, NotFoundError
from app.models.company import Company
from app.schemas.company import CompanyResponse, CompanyUpdate

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
