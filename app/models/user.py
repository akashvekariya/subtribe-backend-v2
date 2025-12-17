"""User model - Recruiters and admins."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.invite import Invite
    from app.models.job import Job


class User(Base):
    """User entity (recruiters/admins)."""

    __tablename__ = "users"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )
    company_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )

    # Auth
    auth_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Email Verification
    email_verified: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False, nullable=False
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    email_verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Profile (avatar_url is external URL - no GCS upload for MVP)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Role & Permissions
    role: Mapped[str] = mapped_column(
        String(50), server_default=text("'admin'"), default="admin", nullable=False
    )
    permissions: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), default=True, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

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
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    company: Mapped[Company | None] = relationship("Company", back_populates="users")
    created_jobs: Mapped[list[Job]] = relationship(
        "Job", back_populates="creator", foreign_keys="Job.created_by"
    )
    created_invites: Mapped[list[Invite]] = relationship(
        "Invite", back_populates="creator", foreign_keys="Invite.created_by"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'recruiter', 'interviewer')", name="valid_role"),
    )

    @property
    def full_name(self) -> str:
        """Full name computed property."""
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name={self.full_name}, email={self.email}, role={self.role})>"
