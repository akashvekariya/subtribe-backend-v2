"""
Bulk Upload Service.

Handles bulk resume upload processing including:
- ZIP file upload and storage
- PDF extraction and validation
- Duplicate detection via SHA-256 hash
- Background processing with local concurrency (no Cloud Tasks)
"""

import asyncio
import hashlib
import io
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import AsyncSessionLocal
from app.core.dependencies import get_correlation_id
from app.models.application import Application
from app.models.bulk_upload_batch import BulkUploadBatch
from app.models.bulk_upload_task import BulkUploadTask
from app.models.job import Job
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

# Concurrency limit for processing tasks
MAX_CONCURRENT_TASKS = 5


@dataclass
class ExtractionResult:
    """Result of ZIP extraction phase."""

    total_files: int
    valid_pdfs: int
    skipped_files: list[tuple[str, str]]  # (filename, reason)
    duplicate_files: list[str]
    tasks_created: list[UUID]


@dataclass
class ProcessingResult:
    """Result of processing a single task."""

    success: bool
    error: str | None = None
    application_id: UUID | None = None


class BulkUploadService:
    """Service for managing bulk resume uploads."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_bulk_upload(
        self,
        job_id: UUID,
        zip_file: BinaryIO,
        original_filename: str,
        user_id: UUID,
        company_id: UUID,
    ) -> BulkUploadBatch:
        """
        Create a new bulk upload batch.

        1. Validate job exists and belongs to company
        2. Upload ZIP to GCS temp location
        3. Create batch record
        4. Return batch (processing happens in background)

        Args:
            job_id: Job to upload resumes for
            zip_file: ZIP file containing PDFs
            original_filename: Original filename of uploaded ZIP
            user_id: User performing the upload
            company_id: Company the job belongs to

        Returns:
            Created BulkUploadBatch

        Raises:
            ValueError: If job not found or invalid ZIP
        """
        correlation_id = get_correlation_id()

        # Validate job exists and belongs to company
        job = await self.db.get(Job, job_id)
        if not job or job.company_id != company_id:
            raise ValueError("Job not found")

        # Validate it's a valid ZIP file
        try:
            # Save position and validate ZIP
            position = zip_file.tell()
            with zipfile.ZipFile(zip_file, "r") as zf:
                # Just check if it opens - don't extract yet
                if zf.testzip() is not None:
                    raise ValueError("ZIP file is corrupted")
            # Reset position for upload
            zip_file.seek(position)
        except zipfile.BadZipFile as e:
            raise ValueError("Invalid ZIP file") from e

        # Create batch record
        batch = BulkUploadBatch(
            job_id=job_id,
            company_id=company_id,
            uploaded_by=user_id,
            original_filename=original_filename,
            status="pending",
        )
        self.db.add(batch)
        await self.db.flush()

        # Upload ZIP to GCS temp location
        gcs_uri = storage_service.upload_temp_zip(
            file=zip_file,
            company_id=str(company_id),
            batch_id=str(batch.id),
        )
        batch.zip_gcs_uri = gcs_uri

        await self.db.commit()
        await self.db.refresh(batch)

        logger.info(
            "Bulk upload batch created",
            extra={
                "correlation_id": correlation_id,
                "batch_id": str(batch.id),
                "job_id": str(job_id),
                "original_filename": original_filename,
                "gcs_uri": gcs_uri,
            },
        )

        return batch

    async def get_batch_status(self, batch_id: UUID, company_id: UUID) -> BulkUploadBatch | None:
        """Get batch status with authorization check."""
        batch = await self.db.get(BulkUploadBatch, batch_id)
        if not batch or batch.company_id != company_id:
            return None
        return batch

    async def get_batch_history(
        self, job_id: UUID, company_id: UUID, limit: int = 10
    ) -> list[BulkUploadBatch]:
        """Get recent bulk upload batches for a job."""
        result = await self.db.execute(
            select(BulkUploadBatch)
            .where(
                BulkUploadBatch.job_id == job_id,
                BulkUploadBatch.company_id == company_id,
            )
            .order_by(BulkUploadBatch.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def process_batch_background(batch_id: UUID) -> None:
    """
    Process a bulk upload batch in the background.

    This function runs independently of the request lifecycle and creates
    its own database session. It:
    1. Extracts PDFs from the uploaded ZIP
    2. Creates application and task records
    3. Processes tasks concurrently (5 at a time)
    4. Updates batch status on completion

    Args:
        batch_id: ID of the batch to process
    """
    logger.info(f"Starting background processing for batch {batch_id}")

    async with AsyncSessionLocal() as db:
        try:
            # Get batch
            batch = await db.get(BulkUploadBatch, batch_id)
            if not batch:
                logger.error(f"Batch {batch_id} not found")
                return

            if batch.status != "pending":
                logger.warning(f"Batch {batch_id} is not pending (status: {batch.status})")
                return

            # Update status to extracting
            batch.status = "extracting"
            batch.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Download ZIP from GCS
            zip_bytes = storage_service.download_file(batch.zip_gcs_uri)

            # Get existing hashes for duplicate detection
            existing_hashes = await _get_existing_hashes(db, batch.job_id)

            # Extract and create tasks
            extraction_result = await _extract_and_create_tasks(
                db=db,
                zip_bytes=zip_bytes,
                batch=batch,
                existing_hashes=existing_hashes,
            )

            # Update batch counts
            batch.total_files = extraction_result.total_files
            batch.valid_pdfs = extraction_result.valid_pdfs
            batch.skipped_count = len(extraction_result.skipped_files)
            batch.duplicate_count = len(extraction_result.duplicate_files)

            if not extraction_result.tasks_created:
                # No valid PDFs - mark as completed
                batch.status = "completed"
                batch.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Batch {batch_id} completed with no valid PDFs")
                return

            # Update status to processing
            batch.status = "processing"
            await db.commit()

            logger.info(
                f"Batch {batch_id} extraction complete: "
                f"{extraction_result.valid_pdfs} valid PDFs, "
                f"{len(extraction_result.skipped_files)} skipped, "
                f"{len(extraction_result.duplicate_files)} duplicates"
            )

            # Process tasks with concurrency limit
            await _process_tasks_with_concurrency(
                batch_id=batch_id,
                task_ids=extraction_result.tasks_created,
                max_concurrent=MAX_CONCURRENT_TASKS,
            )

            logger.info(f"Batch {batch_id} processing complete")

        except Exception as e:
            logger.error(f"Background processing failed for batch {batch_id}: {e}", exc_info=True)
            # Try to update batch status to failed
            try:
                batch = await db.get(BulkUploadBatch, batch_id)
                if batch:
                    batch.status = "failed"
                    batch.last_error = str(e)[:1000]
                    batch.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update batch status: {update_error}")


async def _get_existing_hashes(db: AsyncSession, job_id: UUID) -> set[str]:
    """Get existing resume hashes for a job."""
    result = await db.execute(
        select(Application.resume_file_hash).where(
            Application.job_id == job_id,
            Application.resume_file_hash.isnot(None),
        )
    )
    return {row[0] for row in result.fetchall()}


async def _extract_and_create_tasks(
    db: AsyncSession,
    zip_bytes: bytes,
    batch: BulkUploadBatch,
    existing_hashes: set[str],
) -> ExtractionResult:
    """Extract PDFs from ZIP and create application/task records."""
    result = ExtractionResult(
        total_files=0,
        valid_pdfs=0,
        skipped_files=[],
        duplicate_files=[],
        tasks_created=[],
    )

    # Track hashes within this batch to detect duplicates
    batch_hashes: set[str] = set()

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for file_info in zf.infolist():
            # Skip directories
            if file_info.is_dir():
                continue

            # Skip hidden files (macOS __MACOSX, .DS_Store, etc.)
            filename = file_info.filename
            if filename.startswith("__") or filename.startswith("."):
                continue

            result.total_files += 1

            # Check if PDF
            if not filename.lower().endswith(".pdf"):
                result.skipped_files.append((filename, "Not a PDF file"))
                continue

            # Try to read the file
            try:
                pdf_bytes = zf.read(file_info)
            except Exception as e:
                result.skipped_files.append((filename, f"Failed to read: {str(e)}"))
                continue

            # Validate PDF (basic check - starts with %PDF)
            if not pdf_bytes.startswith(b"%PDF"):
                result.skipped_files.append((filename, "Invalid PDF format"))
                continue

            # Compute SHA-256 hash
            file_hash = hashlib.sha256(pdf_bytes).hexdigest()

            # Check for duplicates
            if file_hash in existing_hashes or file_hash in batch_hashes:
                result.duplicate_files.append(filename)
                continue

            batch_hashes.add(file_hash)

            # Create application and task
            task_id = await _create_application_and_task(
                db=db,
                batch=batch,
                pdf_bytes=pdf_bytes,
                original_filename=filename,
                file_hash=file_hash,
            )

            result.valid_pdfs += 1
            result.tasks_created.append(task_id)

    await db.commit()
    return result


async def _create_application_and_task(
    db: AsyncSession,
    batch: BulkUploadBatch,
    pdf_bytes: bytes,
    original_filename: str,
    file_hash: str,
) -> UUID:
    """Create Application with placeholder data and BulkUploadTask."""
    # Generate unique placeholder email (temp- prefix for temporary/processing state)
    app_id = uuid4()
    placeholder_email = f"temp-{app_id}@404.thesubtribe.com"

    # Upload PDF to permanent GCS location
    timestamp = int(datetime.now(timezone.utc).timestamp())
    path = f"{batch.company_id}/{batch.job_id}/{app_id}_{timestamp}_resume.pdf"
    gcs_uri = storage_service.upload_file_bytes(
        content=pdf_bytes,
        path=path,
        content_type="application/pdf",
    )

    # Create Application with placeholder data
    application = Application(
        id=app_id,
        job_id=batch.job_id,
        company_id=batch.company_id,
        first_name="[Processing]",
        last_name="[Processing]",
        email=placeholder_email,
        resume_url=gcs_uri,
        resume_filename=original_filename,
        resume_file_hash=file_hash,
        status="applied",
        source="bulk_upload",
        processing_status="processing",  # Hidden from candidate list until AI parsing completes
    )
    db.add(application)

    # Create BulkUploadTask
    task = BulkUploadTask(
        batch_id=batch.id,
        application_id=app_id,
        original_filename=original_filename,
        file_hash=file_hash,
        status="pending",
    )
    db.add(task)

    await db.flush()
    return task.id


async def _process_tasks_with_concurrency(
    batch_id: UUID,
    task_ids: list[UUID],
    max_concurrent: int,
) -> None:
    """Process tasks with a concurrency limit using semaphore."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(task_id: UUID) -> None:
        async with semaphore:
            await _process_single_task(batch_id, task_id)

    # Process all tasks concurrently (limited by semaphore)
    await asyncio.gather(*[process_with_semaphore(tid) for tid in task_ids])


async def _process_single_task(batch_id: UUID, task_id: UUID) -> None:
    """Process a single task with its own database session."""
    async with AsyncSessionLocal() as db:
        try:
            task = await db.get(BulkUploadTask, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            if task.status in ("completed", "failed", "skipped"):
                return

            # Mark task as processing
            task.record_attempt()
            await db.commit()

            # Get application
            application = await db.get(Application, task.application_id)
            if not application:
                raise ValueError("Application not found")

            # Download PDF
            pdf_bytes = storage_service.download_file(application.resume_url)

            # Parse resume via AI
            parsed_data = _parse_resume(pdf_bytes)

            # Update application with extracted data
            _update_application_from_parsed(application, parsed_data)

            # Mark processing complete - now visible in candidate list
            application.processing_status = "complete"

            # Get job to check if calibrated
            job = await db.get(Job, application.job_id)

            # Mark task as completed
            task.mark_completed()
            await db.commit()

            # Update batch counts
            await _update_batch_processed_count(db, batch_id)

            # Trigger evaluation if job is calibrated
            if job and job.calibrated_at is not None:
                await _trigger_evaluation(db, application.id)

            logger.info(
                f"Task {task_id} processed: {application.first_name} {application.last_name}"
            )

        except Exception as e:
            error_msg = str(e)[:1000]
            logger.error(f"Task {task_id} failed: {error_msg}")

            try:
                task = await db.get(BulkUploadTask, task_id)
                if task:
                    if task.can_retry:
                        task.last_error = error_msg
                        task.status = "pending"
                    else:
                        task.mark_failed(error_msg)
                        # Update application to show failure
                        application = await db.get(Application, task.application_id)
                        if application:
                            application.first_name = "[Failed]"
                            application.last_name = "[Processing Error]"
                        await _update_batch_failed_count(db, batch_id)
                    await db.commit()
            except Exception as update_error:
                logger.error(f"Failed to update task status: {update_error}")


def _parse_resume(pdf_bytes: bytes) -> dict:
    """Parse resume PDF using AI service."""
    from subtribe_ai import parse_resume

    try:
        result = parse_resume(pdf_bytes)
        parsed = result.get("parsed", {}) or {}
        return {
            "markdown": result.get("markdown"),
            "personal_info": parsed.get("personal_info", {}),
            "structured_data": parsed,
        }
    except Exception as e:
        # If AI parsing fails completely, return empty result
        # The update function will use fallback values like [Unknown]
        logger.warning(f"Resume parsing failed: {str(e)[:200]}")
        return {
            "markdown": None,
            "personal_info": {},
            "structured_data": {},
        }


def _update_application_from_parsed(application: Application, parsed_data: dict) -> None:
    """Update application with parsed resume data."""
    personal_info = parsed_data.get("personal_info", {})

    # Extract name
    full_name = personal_info.get("full_name", "")
    if full_name:
        parts = full_name.split(" ", 1)
        application.first_name = parts[0] or "[Unknown]"
        application.last_name = parts[1] if len(parts) > 1 else "[Unknown]"
    else:
        application.first_name = personal_info.get("first_name") or "[Unknown]"
        application.last_name = personal_info.get("last_name") or "[Unknown]"

    # Extract email (keep placeholder if not found)
    email = personal_info.get("email")
    if email and "@" in email:
        application.email = email
    else:
        # Use 404.thesubtribe.com domain for placeholder emails
        # This allows frontend to filter out unprocessed applications
        # Keep full UUID to avoid collisions
        application.email = f"unknown-{str(application.id)}@404.thesubtribe.com"

    # Extract other fields
    application.phone = personal_info.get("phone")
    application.linkedin_url = personal_info.get("linkedin_url")
    application.github_url = personal_info.get("github_url")
    application.portfolio_url = personal_info.get("portfolio_url")

    # Store parsed content
    application.resume_parsed_md = parsed_data.get("markdown")
    application.resume_parsed_json = parsed_data.get("structured_data")

    # Explicitly flag JSONB column as modified so SQLAlchemy commits it
    flag_modified(application, "resume_parsed_json")


async def _update_batch_processed_count(db: AsyncSession, batch_id: UUID) -> None:
    """Update batch processed count and check for completion."""
    batch = await db.get(BulkUploadBatch, batch_id)
    if not batch:
        return

    batch.processed_count += 1
    await _check_batch_completion(db, batch)
    await db.commit()


async def _update_batch_failed_count(db: AsyncSession, batch_id: UUID) -> None:
    """Update batch failed count and check for completion."""
    batch = await db.get(BulkUploadBatch, batch_id)
    if not batch:
        return

    batch.failed_count += 1
    await _check_batch_completion(db, batch)
    await db.commit()


async def _check_batch_completion(db: AsyncSession, batch: BulkUploadBatch) -> None:
    """Check if batch is complete and update status."""
    if batch.is_complete:
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)

        # Delete temporary ZIP
        if batch.zip_gcs_uri:
            try:
                storage_service.delete_file(batch.zip_gcs_uri)
                batch.zip_gcs_uri = None
            except Exception as e:
                logger.warning(f"Failed to delete temp ZIP: {e}")


async def _trigger_evaluation(db: AsyncSession, application_id: UUID) -> None:
    """Trigger AI evaluation for an application."""
    try:
        from app.services.evaluation.service import AIResumeEvalService

        eval_service = AIResumeEvalService(db)
        await eval_service.evaluate_single_application(application_id)
    except Exception as e:
        logger.warning(f"Failed to trigger evaluation for {application_id}: {e}")
