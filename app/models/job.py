"""Job model - Job postings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.company import Company
    from app.models.user import User


class Job(Base):
    """Job posting entity."""

    __tablename__ = "jobs"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Basic Info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(100000), nullable=False)

    # Job Details
    position_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Location
    location_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_country: Mapped[str] = mapped_column(String(100), nullable=True)

    # Salary
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), nullable=True)

    # Experience Requirements
    min_experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Skills & Requirements
    required_skills: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )
    preferred_skills: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )

    # Screening Questions
    screening_questions: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(100), server_default=text("'draft'"), default="draft", nullable=False
    )

    # Public URL
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Metadata
    views_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )

    # Timestamps
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
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
    company: Mapped[Company] = relationship("Company", back_populates="jobs")
    creator: Mapped[User] = relationship(
        "User", back_populates="created_jobs", foreign_keys=[created_by]
    )
    applications: Mapped[list[Application]] = relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )

    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'closed')", name="valid_job_status"),
        CheckConstraint(
            "location_type IN ('remote', 'hybrid', 'onsite')", name="valid_location_type"
        ),
        CheckConstraint(
            "position_type IN ('full_time', 'part_time', 'contract', 'temporary', "
            "'other', 'volunteer', 'internship')",
            name="valid_position_type",
        ),
        # Performance index for GET /jobs endpoint (paginated listing)
        Index("idx_jobs_company_created", "company_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, title={self.title}, status={self.status})>"
