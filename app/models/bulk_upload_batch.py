"""Bulk Upload Batch model - Tracks bulk resume upload jobs for a job posting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.bulk_upload_task import BulkUploadTask
    from app.models.company import Company
    from app.models.job import Job
    from app.models.user import User


class BulkUploadBatch(Base):
    """
    Tracks a batch of bulk resume uploads for a job.

    Created when a recruiter uploads a ZIP file containing multiple resumes.
    The system extracts PDFs, validates them, and creates individual tasks
    for AI parsing and evaluation.

    Lifecycle:
    - pending: Batch created, ZIP uploaded to temp storage
    - extracting: Extracting and validating PDFs from ZIP
    - processing: Individual tasks are being processed
    - completed: All tasks finished (success or failed)
    - failed: Critical error, batch aborted
    """

    __tablename__ = "bulk_upload_batches"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )

    # Foreign Keys
    job_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Source file
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    zip_gcs_uri: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Temporary storage, deleted after processing

    # Counts
    total_files: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )  # Total files in ZIP
    valid_pdfs: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )  # Valid PDFs found
    skipped_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )  # Non-PDFs + corrupt files
    duplicate_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )  # Hash duplicates detected
    processed_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )  # Successfully processed
    failed_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )  # Failed to process

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        server_default=text("'pending'"),
        default="pending",
        nullable=False,
    )

    # Error tracking
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    job: Mapped[Job] = relationship("Job", back_populates="bulk_upload_batches")
    company: Mapped[Company] = relationship("Company", back_populates="bulk_upload_batches")
    uploaded_by_user: Mapped[User | None] = relationship("User")
    tasks: Mapped[list[BulkUploadTask]] = relationship(
        "BulkUploadTask",
        back_populates="batch",
        cascade="all, delete-orphan",
    )

    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'extracting', 'processing', 'completed', 'failed')",
            name="valid_bulk_upload_batch_status",
        ),
        # Index for querying batches by company
        Index("idx_bulk_upload_batches_company_status", "company_id", "status"),
        # Index for querying batches by job
        Index("idx_bulk_upload_batches_job", "job_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<BulkUploadBatch(id={self.id}, job_id={self.job_id}, "
            f"status={self.status}, {self.processed_count}/{self.valid_pdfs})>"
        )

    @property
    def progress_percent(self) -> float:
        """Calculate completion percentage."""
        if self.valid_pdfs == 0:
            return 0.0
        return round((self.processed_count + self.failed_count) / self.valid_pdfs * 100, 1)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks have finished (success or failure)."""
        return (self.processed_count + self.failed_count) >= self.valid_pdfs
