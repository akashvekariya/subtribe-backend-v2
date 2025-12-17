"""Invite model - Team member invitations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, Boolean, CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class Invite(Base):
    """Team member invitation entity."""

    __tablename__ = "invites"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )

    # Foreign Keys
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Invite Details
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), server_default=text("'recruiter'"), default="recruiter", nullable=False
    )

    # Usage Limits
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    uses_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )

    # Expiry
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), default=True, nullable=False
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
    company: Mapped[Company] = relationship("Company", back_populates="invites")
    creator: Mapped[User | None] = relationship("User", back_populates="created_invites")

    # Constraints
    __table_args__ = (
        CheckConstraint("uses_count >= 0", name="positive_uses_count"),
        CheckConstraint("max_uses IS NULL OR max_uses > 0", name="valid_max_uses"),
        CheckConstraint("role IN ('admin', 'recruiter', 'interviewer')", name="valid_invite_role"),
    )

    @property
    def is_valid(self) -> bool:
        """Check if invite is still valid (active, not expired, not maxed out)."""
        if not self.is_active:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        return True

    def __repr__(self) -> str:
        return f"<Invite(id={self.id}, email={self.email}, company_id={self.company_id})>"
