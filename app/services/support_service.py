"""Support service for ticket management with Discord integration."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.discord import (
    DiscordEmbed,
    DiscordMessage,
    DiscordProvider,
    DiscordResult,
    get_discord_provider,
)
from app.integrations.discord.schemas import DiscordEmbedField
from app.models.support import SupportMessage, SupportTicket
from app.models.user import User

logger = logging.getLogger(__name__)


# Priority colors for Discord embeds
PRIORITY_COLORS = {
    "low": 0x57F287,  # Green
    "medium": 0xFEE75C,  # Yellow
    "high": 0xED4245,  # Red
    "urgent": 0xEB459E,  # Pink/Magenta
}

# Status colors for Discord embeds
STATUS_COLORS = {
    "open": 0x5865F2,  # Discord Blurple
    "in_progress": 0xFEE75C,  # Yellow
    "resolved": 0x57F287,  # Green
    "closed": 0x99AAB5,  # Gray
}


class SupportService:
    """Service for managing support tickets with Discord integration."""

    def __init__(self, db: AsyncSession, discord: DiscordProvider | None = None):
        self.db = db
        self.discord = discord or get_discord_provider()

    async def create_ticket_discord_thread(
        self,
        ticket: SupportTicket,
        user: User | None,
    ) -> DiscordResult:
        """Create a Discord thread for a support ticket.

        Args:
            ticket: The support ticket
            user: The user who created the ticket

        Returns:
            DiscordResult with thread information
        """
        if not settings.discord_enabled or not settings.discord_support_channel_id:
            logger.info("Discord integration disabled, skipping thread creation")
            return DiscordResult(success=False, error_message="Discord disabled")

        # Build the embed
        user_name = user.full_name if user else "Unknown User"
        embed = DiscordEmbed(
            title=f"🎫 New Support Ticket: {ticket.subject}",
            description=ticket.description[:1000] if len(ticket.description) > 1000 else ticket.description,
            color=PRIORITY_COLORS.get(ticket.priority, 0x5865F2),
            fields=[
                DiscordEmbedField(name="Priority", value=ticket.priority.upper(), inline=True),
                DiscordEmbedField(name="Status", value=ticket.status.upper(), inline=True),
                DiscordEmbedField(name="Created By", value=user_name, inline=True),
            ],
            footer_text=f"Ticket ID: {ticket.id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        message = DiscordMessage(embeds=[embed])

        # Create thread
        result = await self.discord.create_thread(
            channel_id=settings.discord_support_channel_id,
            name=f"[{ticket.priority.upper()}] {ticket.subject[:80]}",
            message=message,
        )

        if result.success:
            # Update ticket with Discord IDs
            ticket.discord_channel_id = result.channel_id
            ticket.discord_thread_id = result.thread_id
            await self.db.commit()
            logger.info(
                f"Discord thread created for ticket {ticket.id}",
                extra={"thread_id": result.thread_id},
            )

        return result

    async def send_message_to_discord(
        self,
        ticket: SupportTicket,
        message: SupportMessage,
        user: User | None,
    ) -> DiscordResult:
        """Send a message to the Discord thread for a ticket.

        Args:
            ticket: The support ticket
            message: The message to send
            user: The user who sent the message

        Returns:
            DiscordResult with message information
        """
        if not settings.discord_enabled or not ticket.discord_thread_id:
            logger.info("Discord integration disabled or no thread, skipping message sync")
            return DiscordResult(success=False, error_message="Discord disabled or no thread")

        user_name = user.full_name if user else "Dashboard User"

        discord_message = DiscordMessage(
            content=f"**{user_name}** (via Dashboard):\n{message.content}"
        )

        result = await self.discord.send_thread_message(
            thread_id=ticket.discord_thread_id,
            message=discord_message,
        )

        if result.success:
            # Update message with Discord message ID
            message.discord_message_id = result.message_id
            await self.db.commit()
            logger.info(
                f"Message synced to Discord for ticket {ticket.id}",
                extra={"discord_message_id": result.message_id},
            )

        return result

    async def send_status_update_to_discord(
        self,
        ticket: SupportTicket,
        old_status: str,
        new_status: str,
        user: User | None,
    ) -> DiscordResult:
        """Send a status update notification to the Discord thread.

        Args:
            ticket: The support ticket
            old_status: Previous status
            new_status: New status
            user: The user who made the change

        Returns:
            DiscordResult with message information
        """
        if not settings.discord_enabled or not ticket.discord_thread_id:
            logger.info("Discord integration disabled or no thread, skipping status update")
            return DiscordResult(success=False, error_message="Discord disabled or no thread")

        user_name = user.full_name if user else "System"

        embed = DiscordEmbed(
            title="📋 Status Updated",
            description=f"**{old_status.upper()}** → **{new_status.upper()}**",
            color=STATUS_COLORS.get(new_status, 0x5865F2),
            fields=[
                DiscordEmbedField(name="Updated By", value=user_name, inline=True),
            ],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        discord_message = DiscordMessage(embeds=[embed])

        return await self.discord.send_thread_message(
            thread_id=ticket.discord_thread_id,
            message=discord_message,
        )

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get a user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
