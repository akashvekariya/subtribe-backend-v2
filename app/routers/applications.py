"""Application management endpoints."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import partial
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.dependencies import get_correlation_id, get_current_user
from app.exceptions import AppException, ConflictError, NotFoundError
from app.models.application import Application
from app.models.job import Job
from app.models.scheduled_email import ScheduledEmail
from app.models.status_history import ApplicationStatusHistory
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
from app.services.storage import storage_service

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
    screening_answers: str | None = Form(None),  # JSON string
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
    import json

    # 1. Validate job exists and is active
    result = await db.execute(select(Job).where(Job.slug == slug))
    job = result.scalar_one_or_none()

    if not job or job.status != "active":
        raise NotFoundError(
            message="Job not found or no longer accepting applications", code="job_not_active"
        )

    # 2. Validate file type (PDF only - strict)
    if not resume.content_type or resume.content_type != "application/pdf":
        raise AppException(
            message="Only PDF files are allowed", code="invalid_file_type", status_code=400
        )

    # 3. Validate file size (max 5MB)
    resume.file.seek(0, 2)  # Seek to end
    file_size = resume.file.tell()
    resume.file.seek(0)  # Reset to beginning

    max_size_bytes = 5 * 1024 * 1024  # 5MB
    if file_size > max_size_bytes:
        raise AppException(
            message="File too large (max 5MB)", code="file_too_large", status_code=400
        )

    # 4. Check for duplicate application (same email for this job)
    existing = await db.execute(
        select(Application).where(
            Application.job_id == job.id, Application.email == email.lower().strip()
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            message="You have already applied to this job", code="duplicate_application"
        )

    # 5. Parse screening answers if provided
    parsed_answers = {}
    if screening_answers:
        try:
            parsed_answers = json.loads(screening_answers)
        except json.JSONDecodeError:
            raise AppException(
                message="Invalid screening_answers format (must be valid JSON)",
                code="invalid_json",
                status_code=400,
            ) from None

    # 6. Create application and upload resume
    try:
        # Create application record
        application = Application(
            job_id=job.id,
            company_id=job.company_id,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.lower().strip(),
            phone=phone.strip() if phone else None,
            linkedin_url=linkedin_url if linkedin_url else None,
            github_url=github_url if github_url else None,
            portfolio_url=portfolio_url if portfolio_url else None,
            cover_letter=cover_letter.strip() if cover_letter else None,
            current_ctc=current_ctc,
            expected_ctc=expected_ctc,
            notice_period_days=notice_period_days,
            screening_answers=parsed_answers,
            status="applied",
            resume_url="",  # Will be updated after upload
            resume_filename=resume.filename,
        )

        db.add(application)
        await db.flush()  # Get application.id

        # Create initial status history entry (applied)
        initial_history = ApplicationStatusHistory(
            application_id=application.id,
            from_status=None,  # First status, no previous status
            to_status="applied",
            changed_by=None,  # Public application, no user
            notes="Application submitted",
        )
        db.add(initial_history)

        # Upload resume to GCS (run in thread pool to avoid blocking event loop)
        full_name = f"{first_name} {last_name}"
        loop = asyncio.get_event_loop()
        resume_uri = await loop.run_in_executor(
            None,
            partial(
                storage_service.upload_resume,
                file=resume.file,
                company_id=str(job.company_id),
                job_id=str(job.id),
                application_id=str(application.id),
                full_name=full_name,
                content_type=resume.content_type,
            ),
        )

        # Update application with resume URL
        application.resume_url = resume_uri

        # Commit the transaction
        await db.commit()
        await db.refresh(application)

    except Exception as e:
        # Upload failed - rollback
        await db.rollback()
        logger.error(
            "Application creation failed",
            extra={
                "correlation_id": get_correlation_id(),
                "event_type": "business",
                "event": "application_creation_failed",
                "job_id": str(job.id),
                "email": email,
                "error": str(e),
            },
            exc_info=True,
        )
        raise AppException(
            message="Failed to upload resume. Please try again.",
            code="upload_failed",
            status_code=503,
        ) from e

    logger.info(
        "Application submitted successfully",
        extra={
            "correlation_id": get_correlation_id(),
            "event_type": "business",
            "event": "application_submitted",
            "application_id": str(application.id),
            "job_id": str(job.id),
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        },
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
    # Fetch application with job relationship
    result = await db.execute(
        select(Application)
        .options(joinedload(Application.job))
        .where(
            Application.id == application_id, Application.company_id == current_user["company_id"]
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise NotFoundError(message="Application not found", code="application_not_found")

    # Build response with job info
    response_data = ApplicationDetail.model_validate(application)
    response_data.job = JobBasic(
        id=application.job.id, title=application.job.title, slug=application.job.slug
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
    # Fetch application
    result = await db.execute(
        select(Application).where(
            Application.id == application_id, Application.company_id == current_user["company_id"]
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise NotFoundError(message="Application not found", code="application_not_found")

    # Generate signed URL for viewing (run in thread pool)
    try:
        loop = asyncio.get_event_loop()
        signed_url = await loop.run_in_executor(
            None, storage_service.get_resume_view_url, application.resume_url
        )
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        return ResumeUrl(
            url=signed_url,
            filename=application.resume_filename or "resume.pdf",
            expires_at=expires_at,
        )
    except Exception as e:
        logger.error(
            "Failed to generate resume view URL",
            extra={
                "correlation_id": get_correlation_id(),
                "event_type": "external_service",
                "service": "gcs",
                "operation": "generate_view_url",
                "application_id": str(application_id),
                "gcs_uri": application.resume_url,
                "error": str(e),
            },
            exc_info=True,
        )
        raise AppException(
            message="Failed to generate resume URL", code="url_generation_failed", status_code=503
        ) from e


@router.get("/{application_id}/resume/download", response_model=ResumeUrl, tags=["Applications"])
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
    # Fetch application
    result = await db.execute(
        select(Application).where(
            Application.id == application_id, Application.company_id == current_user["company_id"]
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise NotFoundError(message="Application not found", code="application_not_found")

    # Generate signed URL for download (run in thread pool)
    try:
        loop = asyncio.get_event_loop()
        signed_url = await loop.run_in_executor(
            None, storage_service.get_resume_download_url, application.resume_url
        )
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        return ResumeUrl(
            url=signed_url,
            filename=application.resume_filename or "resume.pdf",
            expires_at=expires_at,
        )
    except Exception as e:
        logger.error(
            "Failed to generate resume download URL",
            extra={
                "correlation_id": get_correlation_id(),
                "event_type": "external_service",
                "service": "gcs",
                "operation": "generate_download_url",
                "application_id": str(application_id),
                "gcs_uri": application.resume_url,
                "error": str(e),
            },
            exc_info=True,
        )
        raise AppException(
            message="Failed to generate resume download URL",
            code="url_generation_failed",
            status_code=503,
        ) from e


@router.patch("/{application_id}", response_model=ApplicationDetail, tags=["Applications"])
async def update_application_status(
    application_id: UUID,
    data: ApplicationStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update application status (for Phase 7 - Status Management).

    - **application_id**: Application UUID
    - **status**: New status
    - **notes**: Required notes about status change

    Returns updated application details.

    Note: This endpoint will create status history entries in Phase 7.
    """
    # Fetch application
    result = await db.execute(
        select(Application)
        .options(joinedload(Application.job))
        .where(
            Application.id == application_id, Application.company_id == current_user["company_id"]
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise NotFoundError(message="Application not found", code="application_not_found")

    # Update status
    old_status = application.status

    # Only update if status actually changed
    if old_status != data.status:
        application.status = data.status
        application.updated_at = datetime.now(timezone.utc)

        # Create status history entry only when status changes
        history_entry = ApplicationStatusHistory(
            application_id=application.id,
            from_status=old_status,
            to_status=data.status,
            changed_by=current_user["user_id"],
            notes=data.notes,
        )
        db.add(history_entry)

        await db.commit()
        await db.refresh(application)

        logger.info(
            "Application status updated",
            extra={
                "correlation_id": get_correlation_id(),
                "event_type": "business",
                "event": "application_status_updated",
                "application_id": str(application_id),
                "job_id": str(application.job_id),
                "from_status": old_status,
                "to_status": data.status,
                "changed_by": str(current_user["user_id"]),
            },
        )

        # Note: Auto-scheduling removed. Recruiters manually send emails via Communication tab.

    else:
        # Status unchanged - no history entry needed
        logger.info(
            "Application status unchanged",
            extra={
                "correlation_id": get_correlation_id(),
                "event_type": "business",
                "event": "application_status_unchanged",
                "application_id": str(application_id),
                "status": old_status,
            },
        )

    # Build response
    response_data = ApplicationDetail.model_validate(application)
    response_data.job = JobBasic(
        id=application.job.id, title=application.job.title, slug=application.job.slug
    )

    return response_data


@router.get(
    "/{application_id}/history", response_model=StatusHistoryResponse, tags=["Applications"]
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
    # Verify application exists and belongs to user's company
    app_result = await db.execute(
        select(Application).where(
            Application.id == application_id, Application.company_id == current_user["company_id"]
        )
    )
    application = app_result.scalar_one_or_none()

    if not application:
        raise NotFoundError(message="Application not found", code="application_not_found")

    # Fetch status history with user details (newest first)
    history_result = await db.execute(
        select(ApplicationStatusHistory)
        .options(joinedload(ApplicationStatusHistory.changed_by_user))
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(ApplicationStatusHistory.created_at.desc())
    )
    history_entries = history_result.scalars().all()

    # Build response with user details
    history_items = []
    for entry in history_entries:
        # Build user info if changed_by_user relationship exists
        user_info = None
        if entry.changed_by_user:
            user_info = UserBasic(
                id=entry.changed_by_user.id, full_name=entry.changed_by_user.full_name
            )

        history_items.append(
            StatusHistoryItem(
                id=entry.id,
                from_status=entry.from_status,
                to_status=entry.to_status,
                changed_by=user_info,
                notes=entry.notes,
                created_at=entry.created_at,
            )
        )

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
    # Verify application exists and belongs to user's company
    app_result = await db.execute(
        select(Application).where(
            Application.id == application_id, Application.company_id == current_user["company_id"]
        )
    )
    application = app_result.scalar_one_or_none()

    if not application:
        raise NotFoundError(message="Application not found", code="application_not_found")

    # Fetch scheduled emails (newest first)
    emails_result = await db.execute(
        select(ScheduledEmail)
        .where(ScheduledEmail.application_id == application_id)
        .order_by(ScheduledEmail.created_at.desc())
    )
    scheduled_emails = emails_result.scalars().all()

    # Build response
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
        for email in scheduled_emails
    ]

    return ScheduledEmailsResponse(data=email_items)
