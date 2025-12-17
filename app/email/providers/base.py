"""Abstract base class for email providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailMessage:
    """Email message data structure."""

    to_email: str
    to_name: str | None
    subject: str
    body: str  # Plain text body
    from_email: str
    from_name: str


@dataclass
class EmailResult:
    """Result of email send operation."""

    success: bool
    message_id: str | None = None
    error_message: str | None = None
    provider_response: dict | None = None


class EmailProvider(ABC):
    """Abstract base class for email service providers.

    All email providers must implement the send_email method.
    This abstraction allows easy switching between providers (SendGrid, AWS SES, etc.)
    without changing the application code.
    """

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send an email message.

        Args:
            message: EmailMessage containing all email details

        Returns:
            EmailResult with success status and provider details

        Raises:
            Exception: If send operation fails critically
        """
        pass

    @abstractmethod
    def validate_configuration(self) -> bool:
        """Validate that the provider is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        pass
