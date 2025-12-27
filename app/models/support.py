"""Support models - Support tickets and messages for help system."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class SupportTicket(Base):
    """Support ticket entity for help requests."""

    __tablename__ = "support_tickets"

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
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Ticket details
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), server_default=text("'open'"), default="open", nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(50), server_default=text("'medium'"), default="medium", nullable=False
    )

    # Discord integration
    discord_channel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discord_thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

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
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    company: Mapped[Company] = relationship("Company", back_populates="support_tickets")
    user: Mapped[User | None] = relationship("User", back_populates="support_tickets")
    messages: Mapped[list[SupportMessage]] = relationship(
        "SupportMessage", back_populates="ticket", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')", name="valid_ticket_status"
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')", name="valid_ticket_priority"
        ),
    )

    @property
    def message_count(self) -> int:
        """Count of messages in this ticket."""
        return len(self.messages) if self.messages else 0

    def __repr__(self) -> str:
        return f"<SupportTicket(id={self.id}, subject={self.subject}, status={self.status})>"


class SupportMessage(Base):
    """Support message entity for ticket conversations."""

    __tablename__ = "support_messages"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid4,
    )
    ticket_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Message content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50), server_default=text("'dashboard'"), default="dashboard", nullable=False
    )

    # Discord sync
    discord_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    ticket: Mapped[SupportTicket] = relationship("SupportTicket", back_populates="messages")
    user: Mapped[User | None] = relationship("User")

    # Constraints
    __table_args__ = (
        CheckConstraint("source IN ('dashboard', 'discord')", name="valid_message_source"),
    )

    def __repr__(self) -> str:
        return f"<SupportMessage(id={self.id}, ticket_id={self.ticket_id}, source={self.source})>"
