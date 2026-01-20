"""Application management endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.application import (
    ApplicationDetail,
    ApplicationStatusUpdate,
    ApplicationSubmitted,
    JobBasic,
    ResumeUrl,
    ScheduledEmailItem,
    ScheduledEmailsResponse,
    StatusHistoryItem,
    StatusHistoryResponse,
    UserBasic,
)
from app.services.application_service import ApplicationService
from app.services.evaluation.auto_trigger import trigger_evaluation_for_application

router = APIRouter()  # Protected endpoints
public_router = APIRouter()  # Public endpoints (no auth)
logger = logging.getLogger(__name__)


# ============================================================================
# Public Endpoints (No Auth Required)
# ============================================================================


@public_router.post(
    "/jobs/{slug}/apply",
    response_model=ApplicationSubmitted,
    status_code=status.HTTP_201_CREATED,
    tags=["Public"],
)
async def submit_application(
    slug: str,
    first_name: str = Form(..., min_length=1, max_length=100),
    last_name: str = Form(..., min_length=1, max_length=100),
    email: str = Form(...),
    phone: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    github_url: str | None = Form(None),
    portfolio_url: str | None = Form(None),
    cover_letter: str | None = Form(None, max_length=5000),
    current_ctc: int | None = Form(None),
    expected_ctc: int | None = Form(None),
    notice_period_days: int | None = Form(None),
    screening_answers: str | None = Form(None),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit job application (public endpoint - no auth required).

    - **slug**: Job slug
    - **resume**: PDF file only, max 5MB
    - **screening_answers**: JSON string of answers (optional)

    Returns application ID and confirmation message.
    """
    service = ApplicationService(db)
    application = await service.submit_application(
        slug=slug,
        first_name=first_name,
        last_name=last_name,
        email=email,
        resume=resume,
        phone=phone,
        linkedin_url=linkedin_url,
        github_url=github_url,
        portfolio_url=portfolio_url,
        cover_letter=cover_letter,
        current_ctc=current_ctc,
        expected_ctc=expected_ctc,
        notice_period_days=notice_period_days,
        screening_answers=screening_answers,
    )

    # Auto-trigger evaluation if job is calibrated
    try:
        triggered = await trigger_evaluation_for_application(db, application.id)
        if triggered:
            logger.info(
                "Auto-triggered evaluation for new application",
                extra={
                    "application_id": str(application.id),
                    "job_id": str(application.job_id),
                },
            )
    except Exception as e:
        logger.warning(
            f"Failed to auto-trigger evaluation: {e}",
            extra={"application_id": str(application.id)},
        )

    return ApplicationSubmitted(id=application.id)


# ============================================================================
# Protected Endpoints (Auth Required - Company Users Only)
# ============================================================================


@router.get("/{application_id}", response_model=ApplicationDetail, tags=["Applications"])
async def get_application(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get application details.

    - **application_id**: Application UUID

    Returns full application details including job info.
    """
    service = ApplicationService(db)
    application = await service.get_application(
        current_user["company_id"], application_id
    )

    response_data = ApplicationDetail.model_validate(application)
    response_data.job = JobBasic(
        id=application.job.id,
        title=application.job.title,
        slug=application.job.slug,
    )

    return response_data


@router.get("/{application_id}/resume/view", response_model=ResumeUrl, tags=["Applications"])
async def get_resume_view_url(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get signed URL for viewing resume (opens in browser/iframe).

    - **application_id**: Application UUID

    Returns signed URL with 1-hour expiry (inline disposition).
    """
    service = ApplicationService(db)
    result = await service.get_resume_view_url(
        current_user["company_id"], application_id
    )

    return ResumeUrl(
        url=result.url,
        filename=result.filename,
        expires_at=result.expires_at,
    )


@router.get(
    "/{application_id}/resume/download", response_model=ResumeUrl, tags=["Applications"]
)
async def get_resume_download_url(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get signed URL for downloading resume (forces browser download).

    - **application_id**: Application UUID

    Returns signed URL with 1-hour expiry (attachment disposition).
    """
    service = ApplicationService(db)
    result = await service.get_resume_download_url(
        current_user["company_id"], application_id
    )

    return ResumeUrl(
        url=result.url,
        filename=result.filename,
        expires_at=result.expires_at,
    )


@router.patch("/{application_id}", response_model=ApplicationDetail, tags=["Applications"])
async def update_application_status(
    application_id: UUID,
    data: ApplicationStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update application status.

    - **application_id**: Application UUID
    - **status**: New status
    - **notes**: Required notes about status change

    Returns updated application details.
    """
    service = ApplicationService(db)
    application = await service.update_status(
        company_id=current_user["company_id"],
        application_id=application_id,
        new_status=data.status,
        notes=data.notes,
        user_id=current_user["user_id"],
    )

    response_data = ApplicationDetail.model_validate(application)
    response_data.job = JobBasic(
        id=application.job.id,
        title=application.job.title,
        slug=application.job.slug,
    )

    return response_data


@router.get(
    "/{application_id}/history",
    response_model=StatusHistoryResponse,
    tags=["Applications"],
)
async def get_application_history(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get application status change history.

    - **application_id**: Application UUID

    Returns list of status changes with user info and notes (newest first).
    """
    service = ApplicationService(db)
    history = await service.get_status_history(
        current_user["company_id"], application_id
    )

    history_items = [
        StatusHistoryItem(
            id=entry.id,
            from_status=entry.from_status,
            to_status=entry.to_status,
            changed_by=UserBasic(id=entry.changed_by_id, full_name=entry.changed_by_name)
            if entry.changed_by_id
            else None,
            notes=entry.notes,
            created_at=entry.created_at,
        )
        for entry in history
    ]

    return StatusHistoryResponse(data=history_items)


@router.get(
    "/{application_id}/scheduled-emails",
    response_model=ScheduledEmailsResponse,
    tags=["Applications"],
)
async def get_application_scheduled_emails(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get scheduled emails for an application.

    - **application_id**: Application UUID

    Returns list of scheduled emails (newest first).
    """
    service = ApplicationService(db)
    emails = await service.get_scheduled_emails(
        current_user["company_id"], application_id
    )

    email_items = [
        ScheduledEmailItem(
            id=email.id,
            template_type=email.template_type,
            recipient_email=email.recipient_email,
            recipient_name=email.recipient_name,
            subject=email.subject,
            scheduled_for=email.scheduled_for,
            status=email.status,
            sent_at=email.sent_at,
            provider_message_id=email.provider_message_id,
            error_message=email.error_message,
            created_at=email.created_at,
        )
        for email in emails
    ]

    return ScheduledEmailsResponse(data=email_items)
