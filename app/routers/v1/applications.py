"""V1 Application endpoints with improved architecture.

This module provides the new application submission endpoint that:
- Generates SHA-256 hash of resume for duplicate detection
- Sets explicit AI evaluation status for background processing
- Uses cleaner separation between backend and AI package
"""

import asyncio
import hashlib
import json
import logging
from functools import partial

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_correlation_id
from app.exceptions import AppException, ConflictError, NotFoundError
from app.models.application import Application
from app.models.job import Job
from app.models.status_history import ApplicationStatusHistory
from app.schemas.application import ApplicationSubmitted
from app.services.evaluation.auto_trigger import trigger_evaluation_for_application
from app.services.storage import storage_service

router = APIRouter(tags=["V1 Applications"])
logger = logging.getLogger(__name__)


@router.post(
    "/jobs/{slug}/apply",
    response_model=ApplicationSubmitted,
    status_code=status.HTTP_201_CREATED,
)
async def submit_application_v1(
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
    Submit job application (V1 - improved architecture).

    This endpoint:
    - Validates job and file
    - Generates SHA-256 hash of resume for duplicate detection
    - Uploads resume to GCS
    - Saves application to database
    - Triggers async AI evaluation

    Args:
        slug: Job slug
        resume: PDF file only, max 5MB
        screening_answers: JSON string of answers (optional)

    Returns:
        Application ID and confirmation message
    """
    # Step 1: Validate job exists and is active
    result = await db.execute(select(Job).where(Job.slug == slug))
    job = result.scalar_one_or_none()

    if not job or job.status != "active":
        raise NotFoundError(
            message="Job not found or no longer accepting applications",
            code="job_not_active",
        )

    # Step 2: Validate file type (PDF only)
    if not resume.content_type or resume.content_type != "application/pdf":
        raise AppException(
            message="Only PDF files are allowed",
            code="invalid_file_type",
            status_code=400,
        )

    # Step 3: Read PDF bytes and validate size
    pdf_bytes = await resume.read()
    file_size = len(pdf_bytes)

    max_size_bytes = 5 * 1024 * 1024  # 5MB
    if file_size > max_size_bytes:
        raise AppException(
            message="File too large (max 5MB)",
            code="file_too_large",
            status_code=400,
        )

    # Step 4: Check for duplicate application (same email for this job)
    normalized_email = email.lower().strip()
    existing = await db.execute(
        select(Application).where(
            Application.job_id == job.id,
            Application.email == normalized_email,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            message="You have already applied to this job",
            code="duplicate_application",
        )

    # Step 5: Generate SHA-256 hash of PDF bytes
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Step 6: Parse screening answers if provided
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

    # Step 7: Create application and upload resume
    job_id = job.id
    job_id_str = str(job.id)
    job_company_id = job.company_id

    try:
        # Create application record
        application = Application(
            job_id=job_id,
            company_id=job_company_id,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=normalized_email,
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
            resume_file_hash=file_hash,
            ai_resume_eval_status="pending",  # Explicit status for AI processing
        )

        db.add(application)
        await db.flush()  # Get application.id

        # Create initial status history entry
        initial_history = ApplicationStatusHistory(
            application_id=application.id,
            from_status=None,
            to_status="applied",
            changed_by=None,
            notes="Application submitted",
        )
        db.add(initial_history)

        # Upload resume to GCS (use BytesIO since we already have bytes)
        from io import BytesIO

        pdf_file = BytesIO(pdf_bytes)
        full_name = f"{first_name} {last_name}"

        loop = asyncio.get_event_loop()
        resume_uri = await loop.run_in_executor(
            None,
            partial(
                storage_service.upload_resume,
                file=pdf_file,
                company_id=str(job_company_id),
                job_id=job_id_str,
                application_id=str(application.id),
                full_name=full_name,
                content_type="application/pdf",
            ),
        )

        # Update application with resume URL
        application.resume_url = resume_uri

        # Commit the transaction
        await db.commit()
        await db.refresh(application)

    except Exception as e:
        await db.rollback()
        logger.error(
            "Application creation failed",
            extra={
                "correlation_id": get_correlation_id(),
                "event_type": "business",
                "event": "application_creation_failed",
                "job_id": job_id_str,
                "email": normalized_email,
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
        "Application submitted successfully (v1)",
        extra={
            "correlation_id": get_correlation_id(),
            "event_type": "business",
            "event": "application_submitted_v1",
            "application_id": str(application.id),
            "job_id": job_id_str,
            "email": normalized_email,
            "resume_hash": file_hash[:16] + "...",  # Log truncated hash
        },
    )

    # Step 8: Trigger AI evaluation (fire-and-forget)
    try:
        triggered = await trigger_evaluation_for_application(db, application.id)
        if triggered:
            logger.info(
                "Auto-triggered evaluation for new application",
                extra={
                    "application_id": str(application.id),
                    "job_id": job_id_str,
                },
            )
    except Exception as e:
        # Don't fail the application submission if auto-trigger fails
        logger.warning(
            f"Failed to auto-trigger evaluation: {e}",
            extra={"application_id": str(application.id)},
        )

    return ApplicationSubmitted(id=application.id)
