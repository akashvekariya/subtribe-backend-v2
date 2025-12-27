"""Discord integration module for support ticket routing."""

from app.integrations.discord.provider import DiscordProvider, get_discord_provider
from app.integrations.discord.schemas import DiscordEmbed, DiscordMessage, DiscordResult

__all__ = [
    "DiscordProvider",
    "get_discord_provider",
    "DiscordMessage",
    "DiscordEmbed",
    "DiscordResult",
]
