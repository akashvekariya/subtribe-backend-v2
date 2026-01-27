"""Bulk Upload Task model - Individual task for one resume in a bulk upload."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.bulk_upload_batch import BulkUploadBatch


class BulkUploadTask(Base):
    """
    Individual task for processing one resume from a bulk upload.

    Each task represents one PDF that needs to be parsed by AI
    to extract candidate information.

    Lifecycle:
    - pending: Task created, not yet queued
    - queued: Cloud Task created, waiting to execute
    - processing: Currently being processed by AI
    - completed: Successfully parsed and application updated
    - failed: Failed after max retries
    - skipped: Skipped (e.g., duplicate detected later)
    """

    __tablename__ = "bulk_upload_tasks"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )

    # Foreign Keys
    batch_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bulk_upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Source file info
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        server_default=text("'pending'"),
        default="pending",
        nullable=False,
    )

    # Retry tracking
    attempt_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, server_default=text("3"), default=3, nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cloud Task reference
    cloud_task_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    batch: Mapped[BulkUploadBatch] = relationship("BulkUploadBatch", back_populates="tasks")
    application: Mapped[Application] = relationship("Application")

    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'queued', 'processing', 'completed', 'failed', 'skipped')",
            name="valid_bulk_upload_task_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts + 1",
            name="valid_bulk_upload_attempt_count",
        ),
        # Index for querying tasks by batch and status
        Index("idx_bulk_upload_tasks_batch_status", "batch_id", "status"),
        # Unique constraint: one task per application
        Index(
            "idx_bulk_upload_tasks_application_unique",
            "application_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BulkUploadTask(id={self.id}, filename={self.original_filename}, "
            f"status={self.status}, attempts={self.attempt_count})>"
        )

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.attempt_count < self.max_attempts

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in ("completed", "failed", "skipped")

    def record_attempt(self) -> None:
        """Record an attempt (call before processing)."""
        self.attempt_count += 1
        self.status = "processing"

    def mark_completed(self) -> None:
        """Mark task as successfully completed."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)
        self.last_error = None

    def mark_failed(self, error: str) -> None:
        """Mark task as permanently failed."""
        self.status = "failed"
        self.completed_at = datetime.now(timezone.utc)
        self.last_error = error
