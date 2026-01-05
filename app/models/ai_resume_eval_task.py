"""AI Resume Evaluation Task model - Individual evaluation task for one application."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ai_resume_eval_batch import AIResumeEvalBatch
    from app.models.application import Application


class AIResumeEvalTask(Base):
    """
    Individual AI resume evaluation task for a single application.

    Each task represents one resume parse + JD matching evaluation operation.

    Lifecycle:
    - pending: Task created, not yet queued
    - queued: Cloud Task created, waiting to execute
    - processing: Currently being processed
    - completed: Successfully evaluated
    - failed: Failed after max retries
    - retry_scheduled: Failed, retry scheduled
    - skipped: Skipped (e.g., no resume, already evaluated)
    """

    __tablename__ = "ai_resume_eval_tasks"

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
        ForeignKey("ai_resume_eval_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )

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
        Integer, server_default=text("5"), default=5, nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # rate_limit, timeout, api_error, parse_error, auth_error, unknown

    # Timing
    scheduled_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Cloud Task reference
    cloud_task_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    batch: Mapped[AIResumeEvalBatch] = relationship(
        "AIResumeEvalBatch", back_populates="tasks"
    )
    application: Mapped[Application] = relationship("Application")

    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'queued', 'processing', 'completed', 'failed', 'retry_scheduled', 'skipped')",
            name="valid_ai_resume_eval_task_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts + 1",
            name="valid_ai_resume_eval_attempt_count",
        ),
        # Index for querying tasks by batch and status
        Index("idx_ai_resume_eval_tasks_batch_status", "batch_id", "status"),
        # Index for retry scheduler
        Index(
            "idx_ai_resume_eval_tasks_retry",
            "status",
            "next_retry_at",
            postgresql_where=text("status = 'retry_scheduled'"),
        ),
        # Index for finding stuck tasks
        Index(
            "idx_ai_resume_eval_tasks_stuck",
            "status",
            "started_at",
            postgresql_where=text("status = 'processing'"),
        ),
        # Unique constraint: one task per application per batch
        Index(
            "idx_ai_resume_eval_tasks_batch_app_unique",
            "batch_id",
            "application_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AIResumeEvalTask(id={self.id}, application_id={self.application_id}, "
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
        self.started_at = datetime.now(timezone.utc)
        self.status = "processing"

    def mark_completed(self) -> None:
        """Mark task as successfully completed."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)
        self.last_error = None
        self.last_error_code = None

    def mark_failed(self, error: str, error_code: str) -> None:
        """Mark task as permanently failed."""
        self.status = "failed"
        self.completed_at = datetime.now(timezone.utc)
        self.last_error = error
        self.last_error_code = error_code

    def schedule_retry(self, error: str, error_code: str, retry_at: datetime) -> None:
        """Schedule task for retry."""
        self.status = "retry_scheduled"
        self.last_error = error
        self.last_error_code = error_code
        self.next_retry_at = retry_at
