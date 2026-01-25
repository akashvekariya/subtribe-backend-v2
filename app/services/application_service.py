"""Application business logic service."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.dependencies import get_correlation_id
from app.core.exceptions import AppException, ConflictError, NotFoundError
from app.models.application import Application
from app.models.job import Job
from app.models.scheduled_email import ScheduledEmail
from app.models.status_history import ApplicationStatusHistory
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


@dataclass
class ResumeUrlResult:
    """Result of resume URL generation."""

    url: str
    filename: str
    expires_at: datetime


@dataclass
class StatusHistoryEntry:
    """Status history entry with user info."""

    id: UUID
    from_status: str | None
    to_status: str
    changed_by_id: UUID | None
    changed_by_name: str | None
    notes: str | None
    created_at: datetime


@dataclass
class ScheduledEmailEntry:
    """Scheduled email entry."""

    id: UUID
    template_type: str
    recipient_email: str
    recipient_name: str | None
    subject: str
    scheduled_for: datetime
    status: str
    sent_at: datetime | None
    provider_message_id: str | None
    error_message: str | None
    created_at: datetime


class ApplicationService:
    """Service for application-related business logic."""

    MAX_FILE_SIZE_MB = 5
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_application(
        self,
        slug: str,
        first_name: str,
        last_name: str,
        email: str,
        resume: UploadFile,
        phone: str | None = None,
        linkedin_url: str | None = None,
        github_url: str | None = None,
        portfolio_url: str | None = None,
        cover_letter: str | None = None,
        current_ctc: int | None = None,
        expected_ctc: int | None = None,
        notice_period_days: int | None = None,
        screening_answers: str | None = None,
    ) -> Application:
        """
        Submit a job application.

        Args:
            slug: Job slug
            first_name: Candidate first name
            last_name: Candidate last name
            email: Candidate email
            resume: Resume file (PDF only)
            phone: Optional phone number
            linkedin_url: Optional LinkedIn URL
            github_url: Optional GitHub URL
            portfolio_url: Optional portfolio URL
            cover_letter: Optional cover letter text
            current_ctc: Optional current CTC
            expected_ctc: Optional expected CTC
            notice_period_days: Optional notice period
            screening_answers: Optional JSON string of answers

        Returns:
            Created Application

        Raises:
            NotFoundError: If job doesn't exist or isn't active
            AppException: If file validation fails
            ConflictError: If duplicate application exists
        """
        # Validate job
        job = await self._validate_job(slug)

        # Validate file
        self._validate_resume_file(resume)

        # Check for duplicate
        await self._check_duplicate_application(job.id, email)

        # Parse screening answers
        parsed_answers = self._parse_screening_answers(screening_answers)

        # Create application and upload resume
        return await self._create_application_with_resume(
            job=job,
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
            screening_answers=parsed_answers,
        )

    async def get_application(self, company_id: str | UUID, application_id: UUID) -> Application:
        """
        Get application details with job relationship.

        Args:
            company_id: Company ID for access control
            application_id: Application ID

        Returns:
            Application with job loaded

        Raises:
            NotFoundError: If application doesn't exist
        """
        result = await self.db.execute(
            select(Application)
            .options(joinedload(Application.job))
            .where(
                Application.id == application_id,
                Application.company_id == company_id,
            )
        )
        application = result.scalar_one_or_none()

        if not application:
            raise NotFoundError(message="Application not found", code="application_not_found")

        return application

    async def get_resume_view_url(
        self, company_id: str | UUID, application_id: UUID
    ) -> ResumeUrlResult:
        """
        Get signed URL for viewing resume in browser.

        Args:
            company_id: Company ID for access control
            application_id: Application ID

        Returns:
            ResumeUrlResult with signed URL

        Raises:
            NotFoundError: If application doesn't exist
            AppException: If URL generation fails
        """
        application = await self._get_application_for_resume(company_id, application_id)

        try:
            loop = asyncio.get_event_loop()
            signed_url = await loop.run_in_executor(
                None, storage_service.get_resume_view_url, application.resume_url
            )
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            return ResumeUrlResult(
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
                message="Failed to generate resume URL",
                code="url_generation_failed",
                status_code=503,
            ) from e

    async def get_resume_download_url(
        self, company_id: str | UUID, application_id: UUID
    ) -> ResumeUrlResult:
        """
        Get signed URL for downloading resume.

        Args:
            company_id: Company ID for access control
            application_id: Application ID

        Returns:
            ResumeUrlResult with signed URL

        Raises:
            NotFoundError: If application doesn't exist
            AppException: If URL generation fails
        """
        application = await self._get_application_for_resume(company_id, application_id)

        try:
            loop = asyncio.get_event_loop()
            signed_url = await loop.run_in_executor(
                None, storage_service.get_resume_download_url, application.resume_url
            )
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            return ResumeUrlResult(
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

    async def update_status(
        self,
        company_id: str | UUID,
        application_id: UUID,
        new_status: str,
        notes: str,
        user_id: str | UUID,
    ) -> Application:
        """
        Update application status.

        Args:
            company_id: Company ID for access control
            application_id: Application ID
            new_status: New status value
            notes: Notes about the status change
            user_id: User making the change

        Returns:
            Updated Application with job loaded

        Raises:
            NotFoundError: If application doesn't exist
        """
        result = await self.db.execute(
            select(Application)
            .options(joinedload(Application.job))
            .where(
                Application.id == application_id,
                Application.company_id == company_id,
            )
        )
        application = result.scalar_one_or_none()

        if not application:
            raise NotFoundError(message="Application not found", code="application_not_found")

        old_status = application.status

        if old_status != new_status:
            application.status = new_status
            application.updated_at = datetime.now(timezone.utc)

            # Create status history entry
            history_entry = ApplicationStatusHistory(
                application_id=application.id,
                from_status=old_status,
                to_status=new_status,
                changed_by=user_id,
                notes=notes,
            )
            self.db.add(history_entry)

            await self.db.commit()
            await self.db.refresh(application)

            logger.info(
                "Application status updated",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "business",
                    "event": "application_status_updated",
                    "application_id": str(application_id),
                    "job_id": str(application.job_id),
                    "from_status": old_status,
                    "to_status": new_status,
                    "changed_by": str(user_id),
                },
            )
        else:
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

        return application

    async def get_status_history(
        self, company_id: str | UUID, application_id: UUID
    ) -> list[StatusHistoryEntry]:
        """
        Get application status history.

        Args:
            company_id: Company ID for access control
            application_id: Application ID

        Returns:
            List of StatusHistoryEntry (newest first)

        Raises:
            NotFoundError: If application doesn't exist
        """
        # Verify application exists
        app_result = await self.db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.company_id == company_id,
            )
        )
        if not app_result.scalar_one_or_none():
            raise NotFoundError(message="Application not found", code="application_not_found")

        # Fetch history
        history_result = await self.db.execute(
            select(ApplicationStatusHistory)
            .options(joinedload(ApplicationStatusHistory.changed_by_user))
            .where(ApplicationStatusHistory.application_id == application_id)
            .order_by(ApplicationStatusHistory.created_at.desc())
        )
        history_entries = history_result.scalars().all()

        return [
            StatusHistoryEntry(
                id=entry.id,
                from_status=entry.from_status,
                to_status=entry.to_status,
                changed_by_id=entry.changed_by_user.id if entry.changed_by_user else None,
                changed_by_name=entry.changed_by_user.full_name if entry.changed_by_user else None,
                notes=entry.notes,
                created_at=entry.created_at,
            )
            for entry in history_entries
        ]

    async def get_scheduled_emails(
        self, company_id: str | UUID, application_id: UUID
    ) -> list[ScheduledEmailEntry]:
        """
        Get scheduled emails for an application.

        Args:
            company_id: Company ID for access control
            application_id: Application ID

        Returns:
            List of ScheduledEmailEntry (newest first)

        Raises:
            NotFoundError: If application doesn't exist
        """
        # Verify application exists
        app_result = await self.db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.company_id == company_id,
            )
        )
        if not app_result.scalar_one_or_none():
            raise NotFoundError(message="Application not found", code="application_not_found")

        # Fetch scheduled emails
        emails_result = await self.db.execute(
            select(ScheduledEmail)
            .where(ScheduledEmail.application_id == application_id)
            .order_by(ScheduledEmail.created_at.desc())
        )
        scheduled_emails = emails_result.scalars().all()

        return [
            ScheduledEmailEntry(
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

    # Private helper methods

    async def _validate_job(self, slug: str) -> Job:
        """Validate job exists and is active."""
        result = await self.db.execute(select(Job).where(Job.slug == slug))
        job = result.scalar_one_or_none()

        if not job or job.status != "active":
            raise NotFoundError(
                message="Job not found or no longer accepting applications",
                code="job_not_active",
            )

        return job

    def _validate_resume_file(self, resume: UploadFile) -> None:
        """Validate resume file type and size."""
        if not resume.content_type or resume.content_type != "application/pdf":
            raise AppException(
                message="Only PDF files are allowed",
                code="invalid_file_type",
                status_code=400,
            )

        resume.file.seek(0, 2)
        file_size = resume.file.tell()
        resume.file.seek(0)

        if file_size > self.MAX_FILE_SIZE_BYTES:
            raise AppException(
                message=f"File too large (max {self.MAX_FILE_SIZE_MB}MB)",
                code="file_too_large",
                status_code=400,
            )

    async def _check_duplicate_application(self, job_id: UUID, email: str) -> None:
        """Check for duplicate application."""
        existing = await self.db.execute(
            select(Application).where(
                Application.job_id == job_id,
                Application.email == email.lower().strip(),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                message="You have already applied to this job",
                code="duplicate_application",
            )

    def _parse_screening_answers(self, screening_answers: str | None) -> dict:
        """Parse screening answers JSON string."""
        if not screening_answers:
            return {}

        try:
            return json.loads(screening_answers)
        except json.JSONDecodeError:
            raise AppException(
                message="Invalid screening_answers format (must be valid JSON)",
                code="invalid_json",
                status_code=400,
            ) from None

    async def _create_application_with_resume(
        self,
        job: Job,
        first_name: str,
        last_name: str,
        email: str,
        resume: UploadFile,
        phone: str | None,
        linkedin_url: str | None,
        github_url: str | None,
        portfolio_url: str | None,
        cover_letter: str | None,
        current_ctc: int | None,
        expected_ctc: int | None,
        notice_period_days: int | None,
        screening_answers: dict,
    ) -> Application:
        """Create application record and upload resume."""
        job_id_str = str(job.id)

        try:
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
                screening_answers=screening_answers,
                status="applied",
                resume_url="",
                resume_filename=resume.filename,
            )

            self.db.add(application)
            await self.db.flush()

            # Create initial status history
            initial_history = ApplicationStatusHistory(
                application_id=application.id,
                from_status=None,
                to_status="applied",
                changed_by=None,
                notes="Application submitted",
            )
            self.db.add(initial_history)

            # Upload resume
            full_name = f"{first_name} {last_name}"
            loop = asyncio.get_event_loop()
            resume_uri = await loop.run_in_executor(
                None,
                partial(
                    storage_service.upload_resume,
                    file=resume.file,
                    company_id=str(job.company_id),
                    job_id=job_id_str,
                    application_id=str(application.id),
                    full_name=full_name,
                    content_type=resume.content_type,
                ),
            )

            application.resume_url = resume_uri

            await self.db.commit()
            await self.db.refresh(application)

            logger.info(
                "Application submitted successfully",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "business",
                    "event": "application_submitted",
                    "application_id": str(application.id),
                    "job_id": job_id_str,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )

            return application

        except Exception as e:
            await self.db.rollback()
            logger.error(
                "Application creation failed",
                extra={
                    "correlation_id": get_correlation_id(),
                    "event_type": "business",
                    "event": "application_creation_failed",
                    "job_id": job_id_str,
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

    async def _get_application_for_resume(
        self, company_id: str | UUID, application_id: UUID
    ) -> Application:
        """Get application for resume URL operations."""
        result = await self.db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.company_id == company_id,
            )
        )
        application = result.scalar_one_or_none()

        if not application:
            raise NotFoundError(message="Application not found", code="application_not_found")

        return application
