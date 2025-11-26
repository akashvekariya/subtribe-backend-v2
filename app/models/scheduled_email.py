"""Scheduled Email model - Tracks emails to be sent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.company import Company


class ScheduledEmail(Base):
    """Scheduled email entity for tracking email delivery."""

    __tablename__ = "scheduled_emails"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )
    application_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    # Template Type
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Recipient Info
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Email Content (rendered)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Scheduling
    scheduled_for: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    # Status Tracking
    status: Mapped[str] = mapped_column(
        String(50), server_default=text("'pending'"), default="pending", nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Provider Response
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata (calendly_link, job_title, etc.)
    email_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb"), default=dict, nullable=False
    )

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
    application: Mapped[Application] = relationship(
        "Application", back_populates="scheduled_emails"
    )
    company: Mapped[Company] = relationship("Company", back_populates="scheduled_emails")

    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint(
            "template_type IN ('interview_invite', 'rejection', 'manual', 'bulk', 'custom')",
            name="valid_scheduled_email_template_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'cancelled')",
            name="valid_scheduled_email_status",
        ),
        # Performance index for finding pending emails to send
        Index("idx_scheduled_emails_status_time", "status", "scheduled_for"),
        # Performance index for querying application's email history
        Index("idx_scheduled_emails_application", "application_id"),
    )

    def __repr__(self) -> str:
        return f"<ScheduledEmail(id={self.id}, status={self.status}, to={self.recipient_email})>"
