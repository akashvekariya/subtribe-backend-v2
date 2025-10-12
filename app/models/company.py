"""Company model - Tenant entity for multi-tenancy."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, Boolean, CheckConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job import Job
    from app.models.user import User


class Company(Base):
    """Company/tenant entity."""

    __tablename__ = "companies"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    invite_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Profile (logo_url/website_url are external URLs - no GCS upload for MVP)
    logo_url: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    about: Mapped[str | None] = mapped_column(String(20000), nullable=True)

    # Settings
    settings: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), default=dict, nullable=False
    )

    # Subscription
    plan: Mapped[str] = mapped_column(
        String(50), server_default=text("'free'"), default="free", nullable=False
    )
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
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    users: Mapped[list[User]] = relationship(
        "User", back_populates="company", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[Job]] = relationship(
        "Job", back_populates="company", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(
        "Application", back_populates="company", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (CheckConstraint("slug ~ '^[a-z0-9-]+$'", name="slug_format"),)

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name={self.name}, slug={self.slug}, website_url={self.website_url})>"
