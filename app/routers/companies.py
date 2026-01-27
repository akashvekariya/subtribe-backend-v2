"""Company management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import set_auth_cookie
from app.schemas.company import (
    CompanyResponse,
    CompanyUpdate,
    OnboardingRequest,
    OnboardingResponse,
)
from app.services.company_service import CompanyService

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
    service = CompanyService(db)
    return await service.get_company(current_user["company_id"], company_id)


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
    service = CompanyService(db)
    return await service.update_company(current_user["company_id"], company_id, data)


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
    service = CompanyService(db)

    result = await service.complete_onboarding(user_id, data)

    # Set updated cookie if new token was generated (org_creator flow)
    if result.access_token:
        set_auth_cookie(response, result.access_token)

    return OnboardingResponse(
        success=True,
        company=result.company,
        message=result.message,
    )
