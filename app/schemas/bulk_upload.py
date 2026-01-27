"""Bulk Upload schemas for request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Response Schemas
# ============================================================================


class BulkUploadBatchResponse(BaseModel):
    """Response after initiating bulk upload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    status: str
    original_filename: str
    created_at: datetime
    message: str = "Bulk upload initiated. Processing will begin shortly."


class BulkUploadStatusResponse(BaseModel):
    """Response with bulk upload batch status."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    status: str  # pending, extracting, processing, completed, failed
    original_filename: str

    # Counts
    total_files: int = Field(description="Total files in ZIP")
    valid_pdfs: int = Field(description="Valid PDFs found")
    skipped_count: int = Field(description="Non-PDFs + corrupt files skipped")
    duplicate_count: int = Field(description="Duplicate resumes detected")
    processed_count: int = Field(description="Successfully processed")
    failed_count: int = Field(description="Failed to process")

    # Computed
    progress_percent: float = Field(description="Processing progress percentage")

    # Error
    last_error: str | None = None

    # Timing
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class BulkUploadTaskStatusResponse(BaseModel):
    """Response with individual task status."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    application_id: UUID
    original_filename: str
    status: str  # pending, queued, processing, completed, failed, skipped
    attempt_count: int
    last_error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class BulkUploadExtractionResult(BaseModel):
    """Result of ZIP extraction phase."""

    total_files: int = Field(description="Total files in ZIP")
    valid_pdfs: int = Field(description="Valid PDFs that will be processed")
    skipped_files: list[str] = Field(description="Filenames that were skipped (with reasons)")
    duplicate_files: list[str] = Field(description="Filenames that were duplicates")


class BulkUploadHistoryItem(BaseModel):
    """Single bulk upload history item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    status: str
    valid_pdfs: int
    processed_count: int
    failed_count: int
    duplicate_count: int
    created_at: datetime
    completed_at: datetime | None = None


class BulkUploadHistoryResponse(BaseModel):
    """List of bulk upload history for a job."""

    data: list[BulkUploadHistoryItem]
