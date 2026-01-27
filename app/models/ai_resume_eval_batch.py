"""AI Resume Evaluation Batch model - Tracks batch resume evaluation jobs for a job posting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.ai_resume_eval_task import AIResumeEvalTask
    from app.models.company import Company
    from app.models.job import Job
    from app.models.user import User


class AIResumeEvalBatch(Base):
    """
    Tracks a batch of AI resume evaluations for a job.

    This evaluates candidate resumes against the Job Description (JD)
    using the job's calibrated evaluation framework.

    Created when:
    - Job is calibrated (evaluate all pending applications)
    - Manual trigger to re-evaluate candidates

    Lifecycle:
    - pending: Batch created, tasks being queued
    - processing: Tasks are being executed
    - completed: All tasks finished (success or failed)
    - failed: Critical error, batch aborted
    - cancelled: Manually cancelled by user
    """

    __tablename__ = "ai_resume_eval_batches"

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
    triggered_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Counts
    total_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    queued_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    processing_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    completed_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        server_default=text("'pending'"),
        default="pending",
        nullable=False,
    )

    # Timing
    estimated_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_completion_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Notification
    notification_sent: Mapped[bool] = mapped_column(
        server_default=text("false"), default=False, nullable=False
    )
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Rate limit tracking
    rate_limited_until: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )

    # Relationships
    job: Mapped[Job] = relationship("Job", back_populates="ai_resume_eval_batches")
    company: Mapped[Company] = relationship("Company", back_populates="ai_resume_eval_batches")
    triggered_by_user: Mapped[User | None] = relationship("User")
    tasks: Mapped[list[AIResumeEvalTask]] = relationship(
        "AIResumeEvalTask",
        back_populates="batch",
        cascade="all, delete-orphan",
    )

    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')",
            name="valid_ai_resume_eval_batch_status",
        ),
        # Index for querying batches by company
        Index("idx_ai_resume_eval_batches_company_status", "company_id", "status"),
        # Index for querying batches by job
        Index("idx_ai_resume_eval_batches_job", "job_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIResumeEvalBatch(id={self.id}, job_id={self.job_id}, "
            f"status={self.status}, {self.completed_count}/{self.total_count})>"
        )

    @property
    def progress_percent(self) -> float:
        """Calculate completion percentage."""
        if self.total_count == 0:
            return 0.0
        return round((self.completed_count + self.failed_count) / self.total_count * 100, 1)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks have finished (success or failure)."""
        return (self.completed_count + self.failed_count) >= self.total_count
