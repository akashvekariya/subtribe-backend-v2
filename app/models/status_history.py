"""ApplicationStatusHistory model - Status change tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User


class ApplicationStatusHistory(Base):
    """Application status change history for audit trail."""

    __tablename__ = "application_status_history"

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

    # Status Change
    from_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_status: Mapped[str] = mapped_column(String(100), nullable=False)

    # Metadata
    changed_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(5000), nullable=True)

    # Timestamp (no deleted_at - audit trail is immutable)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    application: Mapped[Application] = relationship("Application", back_populates="status_history")
    changed_by_user: Mapped[User | None] = relationship("User", foreign_keys=[changed_by])

    def __repr__(self) -> str:
        return (
            f"<ApplicationStatusHistory(id={self.id}, "
            f"{self.from_status} -> {self.to_status}, "
            f"changed_by={self.changed_by}, notes={self.notes})>"
        )
