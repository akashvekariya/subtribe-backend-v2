"""Bulk Upload API Router."""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.bulk_upload import (
    BulkUploadBatchResponse,
    BulkUploadHistoryItem,
    BulkUploadHistoryResponse,
    BulkUploadStatusResponse,
)
from app.services.bulk_upload import BulkUploadService
from app.services.bulk_upload.service import process_batch_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bulk-uploads", tags=["bulk-uploads"])


@router.post("/jobs/{job_id}/upload", response_model=BulkUploadBatchResponse)
async def create_bulk_upload(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP file containing PDF resumes"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a ZIP file containing PDF resumes for bulk processing.

    The system will:
    1. Upload ZIP file to storage
    2. Return immediately with batch ID
    3. Process resumes in background (extract, parse, create applications)

    Processing happens asynchronously. Check back later or refresh the
    applications list to see processed candidates.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a ZIP file")

    # Validate content type
    if file.content_type and file.content_type not in [
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    ]:
        raise HTTPException(status_code=400, detail="Invalid file type. Expected ZIP file.")

    # Validate company_id is present
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Company ID is required")

    user_id = UUID(current_user["user_id"])
    company_id = UUID(current_user["company_id"])

    service = BulkUploadService(db)

    try:
        # Create batch record and upload ZIP to GCS
        batch = await service.create_bulk_upload(
            job_id=job_id,
            zip_file=file.file,
            original_filename=file.filename,
            user_id=user_id,
            company_id=company_id,
        )

        # Start background processing (non-blocking)
        background_tasks.add_task(process_batch_background, batch.id)

        return BulkUploadBatchResponse(
            id=batch.id,
            job_id=batch.job_id,
            status=batch.status,
            original_filename=batch.original_filename,
            created_at=batch.created_at,
            message="Upload complete. Processing will continue in the background. "
            "Refresh the applications list to see processed candidates.",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Bulk upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process bulk upload") from e


@router.get("/{batch_id}", response_model=BulkUploadStatusResponse)
async def get_bulk_upload_status(
    batch_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status of a bulk upload batch.

    This is a read-only status check, not for polling.
    Use it to check on a batch after some time has passed.
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Company ID is required")

    company_id = UUID(current_user["company_id"])
    service = BulkUploadService(db)

    batch = await service.get_batch_status(
        batch_id=batch_id,
        company_id=company_id,
    )

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    return BulkUploadStatusResponse(
        id=batch.id,
        job_id=batch.job_id,
        status=batch.status,
        original_filename=batch.original_filename,
        total_files=batch.total_files,
        valid_pdfs=batch.valid_pdfs,
        skipped_count=batch.skipped_count,
        duplicate_count=batch.duplicate_count,
        processed_count=batch.processed_count,
        failed_count=batch.failed_count,
        progress_percent=batch.progress_percent,
        last_error=batch.last_error,
        created_at=batch.created_at,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
    )


@router.get("/jobs/{job_id}/history", response_model=BulkUploadHistoryResponse)
async def get_bulk_upload_history(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent bulk upload history for a job.

    Returns a list of past bulk uploads with their status and counts.
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Company ID is required")

    company_id = UUID(current_user["company_id"])
    service = BulkUploadService(db)

    batches = await service.get_batch_history(
        job_id=job_id,
        company_id=company_id,
        limit=10,
    )

    return BulkUploadHistoryResponse(
        data=[
            BulkUploadHistoryItem(
                id=batch.id,
                original_filename=batch.original_filename,
                status=batch.status,
                valid_pdfs=batch.valid_pdfs,
                processed_count=batch.processed_count,
                failed_count=batch.failed_count,
                duplicate_count=batch.duplicate_count,
                created_at=batch.created_at,
                completed_at=batch.completed_at,
            )
            for batch in batches
        ]
    )
