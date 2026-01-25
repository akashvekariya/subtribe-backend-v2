"""V1 Application endpoints with improved architecture.

This module provides:
- Application submission endpoint with hash-based duplicate detection
- Resume display endpoint for structured resume viewing
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_correlation_id, get_current_user
from app.core.exceptions import AppException, ConflictError, NotFoundError
from app.models.application import Application
from app.models.job import Job
from app.models.status_history import ApplicationStatusHistory
from app.schemas.application import ApplicationSubmitted
from app.schemas.resume import (
    Certification,
    Education,
    EducationEntry,
    EducationSummary,
    Experience,
    ExperienceEntry,
    ExperienceSummary,
    OtherLink,
    PersonalInfo,
    ProjectEntry,
    Projects,
    ResumeData,
    ResumeDisplayMeta,
    ResumeDisplayResponse,
    Skills,
)
from app.services.evaluation.auto_trigger import trigger_evaluation_for_application
from app.services.storage import storage_service

router = APIRouter(tags=["V1 Applications"])
logger = logging.getLogger(__name__)


# ============================================================================
# Resume Data Transformation
# ============================================================================


def _transform_resume_data(parsed_json: dict[str, Any] | None) -> ResumeData | None:
    """Transform resume_parsed_json to ResumeData schema.

    Cleans up internal fields and restructures data for frontend display.
    """
    if not parsed_json:
        return None

    # Personal Info
    pi = parsed_json.get("personal_info", {})
    other_links = []
    for link in pi.get("other_links", []):
        if isinstance(link, dict) and link.get("url"):
            other_links.append(OtherLink(url=link["url"], label=link.get("label")))
        elif isinstance(link, str):
            other_links.append(OtherLink(url=link))

    personal_info = PersonalInfo(
        full_name=pi.get("full_name", ""),
        email=pi.get("email"),
        phone=pi.get("phone"),
        location=pi.get("location"),
        linkedin_url=pi.get("linkedin_url"),
        github_url=pi.get("github_url"),
        portfolio_url=pi.get("portfolio_url"),
        other_links=other_links,
    )

    # Skills
    skills_data = parsed_json.get("skills", {})
    skills = Skills(
        technical=skills_data.get("technical", []) if skills_data else [],
        soft=skills_data.get("soft", []) if skills_data else [],
        languages=skills_data.get("languages", []) if skills_data else [],
    )

    # Experience
    exp_data = parsed_json.get("experience", {})
    if isinstance(exp_data, dict):
        exp_summary_data = exp_data.get("summary", {})
        exp_entries_data = exp_data.get("entries", [])
    else:
        # Handle old format where experience is a list
        exp_summary_data = {}
        exp_entries_data = exp_data if isinstance(exp_data, list) else []

    experience = Experience(
        summary=ExperienceSummary(
            total_months=exp_summary_data.get("total_months", 0),
            by_category=exp_summary_data.get("by_category", {}),
            has_overlaps=exp_summary_data.get("has_overlaps", False),
            has_significant_gaps=exp_summary_data.get("has_significant_gaps", False),
        ),
        entries=[
            ExperienceEntry(
                title=e.get("title", ""),
                company=e.get("company", ""),
                location=e.get("location"),
                category=e.get("category"),
                start_date=e.get("start_date"),
                end_date=e.get("end_date"),
                is_ongoing=e.get("is_ongoing", False),
                duration_months=e.get("duration_months"),
                content=e.get("content", []),
                skills=e.get("skills", []),
            )
            for e in exp_entries_data
        ],
    )

    # Education
    edu_data = parsed_json.get("education", {})
    if isinstance(edu_data, dict):
        edu_summary_data = edu_data.get("summary", {})
        edu_entries_data = edu_data.get("entries", [])
    else:
        # Handle old format where education is a list
        edu_summary_data = {}
        edu_entries_data = edu_data if isinstance(edu_data, list) else []

    education = Education(
        summary=EducationSummary(
            highest_level=edu_summary_data.get("highest_level"),
            months_since_graduation=edu_summary_data.get("months_since_graduation"),
        ),
        entries=[
            EducationEntry(
                degree=e.get("degree", ""),
                institution=e.get("institution", ""),
                field_of_study=e.get("field_of_study"),
                level=e.get("level"),
                start_date=e.get("start_date"),
                end_date=e.get("end_date"),
                is_current=e.get("is_current", False),
                score_value=e.get("score_value"),
                relevant_coursework=e.get("relevant_coursework", []),
            )
            for e in edu_entries_data
        ],
    )

    # Projects
    proj_data = parsed_json.get("projects", {})
    if isinstance(proj_data, dict):
        proj_entries_data = proj_data.get("entries", [])
    else:
        # Handle old format where projects is a list
        proj_entries_data = proj_data if isinstance(proj_data, list) else []

    projects = Projects(
        entries=[
            ProjectEntry(
                name=p.get("name", ""),
                category=p.get("category"),
                content=p.get("content", []),
                skills=p.get("skills", []),
                start_date=p.get("start_date"),
                end_date=p.get("end_date"),
                source_url=p.get("source_url"),
                live_url=p.get("live_url"),
            )
            for p in proj_entries_data
        ]
    )

    # Certifications
    certs_data = parsed_json.get("certifications", [])
    certifications = [
        Certification(
            name=c.get("name", ""),
            issuer=c.get("issuer"),
            date=c.get("date"),
        )
        for c in certs_data
        if c.get("name")
    ]

    return ResumeData(
        personal_info=personal_info,
        professional_summary=parsed_json.get("professional_summary"),
        skills=skills,
        experience=experience,
        education=education,
        projects=projects,
        certifications=certifications,
    )


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


# ============================================================================
# Resume Display Endpoint
# ============================================================================


@router.get(
    "/applications/{application_id}/resume",
    response_model=ResumeDisplayResponse,
)
async def get_application_resume(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get parsed resume data for display.

    Returns the structured resume data transformed for frontend rendering,
    along with application metadata.

    Args:
        application_id: Application UUID

    Returns:
        ResumeDisplayResponse with:
        - data: Transformed resume data (null if not yet parsed)
        - meta: Application context and metadata
    """
    # Fetch application with job relationship
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.job))
        .where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Verify user has access to this application's company
    if str(application.company_id) != current_user["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this application")

    # Transform resume data
    resume_data = _transform_resume_data(application.resume_parsed_json)

    # Generate signed URL for resume viewing
    signed_url = None
    expires_at = None
    if application.resume_url:
        try:
            loop = asyncio.get_event_loop()
            signed_url = await loop.run_in_executor(
                None, storage_service.get_resume_view_url, application.resume_url
            )
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        except Exception as e:
            logger.warning(
                f"Failed to generate signed URL for resume: {e}",
                extra={"application_id": str(application.id)},
            )

    # Build response
    return ResumeDisplayResponse(
        data=resume_data,
        meta=ResumeDisplayMeta(
            application_id=application.id,
            candidate_name=f"{application.first_name} {application.last_name}",
            job_id=application.job_id,
            job_title=application.job.title if application.job else "Unknown",
            resume_filename=application.resume_filename,
            resume_url=signed_url,
            resume_url_expires_at=expires_at,
            has_cover_letter=bool(application.cover_letter),
            cover_letter=application.cover_letter,
            applied_at=application.applied_at,
        ),
    )
