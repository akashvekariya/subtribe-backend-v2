"""Application model - Candidate applications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.job import Job
    from app.models.scheduled_email import ScheduledEmail
    from app.models.status_history import ApplicationStatusHistory


class Application(Base):
    """Candidate application entity."""

    __tablename__ = "applications"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )
    job_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    # Candidate Info
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Salary Info
    current_ctc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_ctc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Resume (GCS storage required)
    resume_url: Mapped[str] = mapped_column(
        String(3000), nullable=False
    )  # GCS path: gs://bucket/{company_id}/{job_id}/{app_id}_resume.pdf
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Raw OCR text
    resume_parsed_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Structured data (skills, experience, education)

    # Screening Answers
    screening_answers: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), default=dict, nullable=False
    )

    # AI Evaluation Results (from Pipeline C: Candidate Evaluation)
    evaluation_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Full evaluation result: scores, analysis, skill_matches, dimension_assessments, etc.
    evaluation_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Final score (0-10 scale)
    evaluation_tier: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Tier: strong_match, good_match, moderate_match, weak_match, mismatch (+ _blocked/_flagged suffix)
    evaluated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )  # Timestamp when AI evaluation was completed

    # AI Resume Evaluation Batch Tracking
    ai_resume_eval_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # pending, processing, completed, failed, skipped
    ai_resume_eval_batch_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_resume_eval_batches.id", ondelete="SET NULL"), nullable=True
    )  # Reference to the batch this application was evaluated in

    # Pipeline Status
    status: Mapped[str] = mapped_column(
        String(100), server_default=text("'applied'"), default="applied", nullable=False
    )

    # Metadata
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referrer_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Timestamps
    applied_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
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
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    job: Mapped[Job] = relationship("Job", back_populates="applications")
    company: Mapped[Company] = relationship("Company", back_populates="applications")
    status_history: Mapped[list[ApplicationStatusHistory]] = relationship(
        "ApplicationStatusHistory", back_populates="application", cascade="all, delete-orphan"
    )
    scheduled_emails: Mapped[list[ScheduledEmail]] = relationship(
        "ScheduledEmail", back_populates="application", cascade="all, delete-orphan"
    )

    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('applied', 'screening', 'interviewing', 'offer', 'hired', 'rejected')",
            name="valid_application_status",
        ),
        # Performance index for GET /jobs/{job_id}/applications endpoint
        Index("idx_applications_job_applied", "job_id", "applied_at"),
        # Composite index for status filtering (common recruiter workflow)
        Index("idx_applications_job_status_applied", "job_id", "status", "applied_at"),
        # Index for evaluation queries (sorting by score within a job)
        Index("idx_applications_job_eval_score", "job_id", "evaluation_score"),
    )

    def __repr__(self) -> str:
        name = f"{self.first_name} {self.last_name}"
        return f"<Application(id={self.id}, name={name}, status={self.status})>"
