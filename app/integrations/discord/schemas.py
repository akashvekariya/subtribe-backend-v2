"""Discord message schemas."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiscordEmbedField:
    """A field in a Discord embed."""

    name: str
    value: str
    inline: bool = False


@dataclass
class DiscordEmbed:
    """Discord rich embed structure."""

    title: str | None = None
    description: str | None = None
    color: int | None = None  # Discord color as integer (e.g., 0x5865F2 for blurple)
    fields: list[DiscordEmbedField] = field(default_factory=list)
    footer_text: str | None = None
    timestamp: str | None = None  # ISO8601 timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to Discord API format."""
        embed: dict[str, Any] = {}
        if self.title:
            embed["title"] = self.title
        if self.description:
            embed["description"] = self.description
        if self.color is not None:
            embed["color"] = self.color
        if self.fields:
            embed["fields"] = [
                {"name": f.name, "value": f.value, "inline": f.inline} for f in self.fields
            ]
        if self.footer_text:
            embed["footer"] = {"text": self.footer_text}
        if self.timestamp:
            embed["timestamp"] = self.timestamp
        return embed


@dataclass
class DiscordMessage:
    """Discord message structure."""

    content: str | None = None
    embeds: list[DiscordEmbed] = field(default_factory=list)
    thread_name: str | None = None  # For creating a thread

    def to_dict(self) -> dict[str, Any]:
        """Convert to Discord API format."""
        message: dict[str, Any] = {}
        if self.content:
            message["content"] = self.content
        if self.embeds:
            message["embeds"] = [e.to_dict() for e in self.embeds]
        return message


@dataclass
class DiscordResult:
    """Result of a Discord API operation."""

    success: bool
    message_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    error_message: str | None = None
