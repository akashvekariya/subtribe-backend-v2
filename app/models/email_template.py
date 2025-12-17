"""Email Template model - Company-specific email templates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company


class EmailTemplate(Base):
    """Email template entity for company-specific email customization."""

    __tablename__ = "email_templates"

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

    # Template Identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # For backwards compatibility
    category: Mapped[str] = mapped_column(String(50), nullable=False, server_default="custom")

    # Template Content
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Dynamic Wildcards
    wildcards: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        default=list,
        nullable=False,
    )

    # System Template Flag
    is_default: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
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
    company: Mapped[Company] = relationship("Company", back_populates="email_templates")

    # Constraints
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_company_template_name"),)

    def __repr__(self) -> str:
        return f"<EmailTemplate(company_id={self.company_id}, type={self.template_type})>"
