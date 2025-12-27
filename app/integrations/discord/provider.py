"""Discord provider for sending messages and managing threads."""

import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings
from app.integrations.discord.schemas import DiscordMessage, DiscordResult

logger = logging.getLogger(__name__)


class DiscordProvider(ABC):
    """Abstract base class for Discord providers."""

    @abstractmethod
    async def send_message(
        self, channel_id: str, message: DiscordMessage
    ) -> DiscordResult:
        """Send a message to a Discord channel."""
        pass

    @abstractmethod
    async def create_thread(
        self, channel_id: str, name: str, message: DiscordMessage
    ) -> DiscordResult:
        """Create a thread in a Discord channel with an initial message."""
        pass

    @abstractmethod
    async def send_thread_message(
        self, thread_id: str, message: DiscordMessage
    ) -> DiscordResult:
        """Send a message to a Discord thread."""
        pass


class StubDiscordProvider(DiscordProvider):
    """Stub provider for development - logs messages instead of sending."""

    def __init__(self):
        self.sent_messages: list[dict] = []
        self.created_threads: list[dict] = []

    async def send_message(
        self, channel_id: str, message: DiscordMessage
    ) -> DiscordResult:
        """Log message instead of sending."""
        log_data = {
            "channel_id": channel_id,
            "message": message.to_dict(),
        }
        self.sent_messages.append(log_data)
        logger.info(
            f"[STUB] Discord message to channel {channel_id}: {message.content or message.embeds[0].title if message.embeds else 'No content'}"
        )
        return DiscordResult(
            success=True,
            message_id="stub-msg-123",
            channel_id=channel_id,
        )

    async def create_thread(
        self, channel_id: str, name: str, message: DiscordMessage
    ) -> DiscordResult:
        """Log thread creation instead of creating."""
        log_data = {
            "channel_id": channel_id,
            "thread_name": name,
            "message": message.to_dict(),
        }
        self.created_threads.append(log_data)
        logger.info(
            f"[STUB] Discord thread created in channel {channel_id}: {name}"
        )
        return DiscordResult(
            success=True,
            message_id="stub-msg-456",
            channel_id=channel_id,
            thread_id="stub-thread-789",
        )

    async def send_thread_message(
        self, thread_id: str, message: DiscordMessage
    ) -> DiscordResult:
        """Log thread message instead of sending."""
        log_data = {
            "thread_id": thread_id,
            "message": message.to_dict(),
        }
        self.sent_messages.append(log_data)
        logger.info(
            f"[STUB] Discord message to thread {thread_id}: {message.content or 'Embed only'}"
        )
        return DiscordResult(
            success=True,
            message_id="stub-msg-thread-123",
            thread_id=thread_id,
        )


class DiscordBotProvider(DiscordProvider):
    """Production Discord provider using Discord Bot API."""

    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        }

    async def send_message(
        self, channel_id: str, message: DiscordMessage
    ) -> DiscordResult:
        """Send a message to a Discord channel."""
        url = f"{self.BASE_URL}/channels/{channel_id}/messages"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=message.to_dict(),
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"Discord message sent to channel {channel_id}",
                        extra={"message_id": data.get("id")},
                    )
                    return DiscordResult(
                        success=True,
                        message_id=data.get("id"),
                        channel_id=channel_id,
                    )
                else:
                    logger.error(
                        f"Discord API error: {response.status_code}",
                        extra={"response": response.text},
                    )
                    return DiscordResult(
                        success=False,
                        error_message=f"Discord API error: {response.status_code}",
                    )

        except httpx.TimeoutException:
            logger.error("Discord API timeout")
            return DiscordResult(
                success=False,
                error_message="Discord API timeout",
            )
        except Exception as e:
            logger.error(f"Discord API error: {e}")
            return DiscordResult(
                success=False,
                error_message=str(e),
            )

    async def create_thread(
        self, channel_id: str, name: str, message: DiscordMessage
    ) -> DiscordResult:
        """Create a thread in a Discord channel with an initial message.

        This creates a thread from a message (forum post style).
        """
        # First, send a message to the channel
        msg_result = await self.send_message(channel_id, message)
        if not msg_result.success:
            return msg_result

        # Create a thread from that message
        url = f"{self.BASE_URL}/channels/{channel_id}/messages/{msg_result.message_id}/threads"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json={
                        "name": name[:100],  # Discord thread name max 100 chars
                        "auto_archive_duration": 10080,  # 7 days
                    },
                    timeout=10.0,
                )

                if response.status_code == 201:
                    data = response.json()
                    logger.info(
                        f"Discord thread created: {name}",
                        extra={"thread_id": data.get("id")},
                    )
                    return DiscordResult(
                        success=True,
                        message_id=msg_result.message_id,
                        channel_id=channel_id,
                        thread_id=data.get("id"),
                    )
                else:
                    logger.error(
                        f"Discord thread creation error: {response.status_code}",
                        extra={"response": response.text},
                    )
                    return DiscordResult(
                        success=False,
                        message_id=msg_result.message_id,
                        error_message=f"Thread creation failed: {response.status_code}",
                    )

        except Exception as e:
            logger.error(f"Discord thread creation error: {e}")
            return DiscordResult(
                success=False,
                message_id=msg_result.message_id,
                error_message=str(e),
            )

    async def send_thread_message(
        self, thread_id: str, message: DiscordMessage
    ) -> DiscordResult:
        """Send a message to a Discord thread.

        Threads are channels, so we use the same endpoint.
        """
        return await self.send_message(thread_id, message)


def get_discord_provider() -> DiscordProvider:
    """Get the appropriate Discord provider based on configuration."""
    if settings.discord_enabled and settings.discord_bot_token:
        logger.info("Using Discord Bot provider")
        return DiscordBotProvider(settings.discord_bot_token)
    else:
        logger.info("Using stub Discord provider (discord_enabled=False or no token)")
        return StubDiscordProvider()
