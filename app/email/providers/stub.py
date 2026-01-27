"""Stub email provider for development and testing."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from app.email.providers.base import EmailMessage, EmailProvider, EmailResult

logger = logging.getLogger(__name__)


class StubEmailProvider(EmailProvider):
    """Stub email provider that logs emails instead of sending them.

    Used for development and testing to avoid accidentally sending real emails.
    All emails are logged with full details but never actually delivered.
    """

    def __init__(self) -> None:
        """Initialize stub provider."""
        self.sent_emails: list[dict] = []  # Track sent emails in memory

    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Log the email instead of sending it.

        Args:
            message: EmailMessage to "send"

        Returns:
            EmailResult with success=True and mock message_id
        """
        # Generate mock message ID
        message_id = f"stub-{uuid4()}"
        timestamp = datetime.utcnow().isoformat()

        # Log the email
        logger.info(
            f"📧 [STUB EMAIL] Sent at {timestamp}\n"
            f"  From: {message.from_name} <{message.from_email}>\n"
            f"  To: {message.to_name or 'N/A'} <{message.to_email}>\n"
            f"  Subject: {message.subject}\n"
            f"  Message ID: {message_id}\n"
            f"  Body:\n{message.body}\n"
            f"  {'=' * 80}"
        )

        # Store in memory for testing/debugging
        self.sent_emails.append(
            {
                "message_id": message_id,
                "timestamp": timestamp,
                "to_email": message.to_email,
                "to_name": message.to_name,
                "subject": message.subject,
                "body": message.body,
                "from_email": message.from_email,
                "from_name": message.from_name,
            }
        )

        return EmailResult(
            success=True,
            message_id=message_id,
            provider_response={"stub": True, "timestamp": timestamp},
        )

    def validate_configuration(self) -> bool:
        """Stub provider always validates successfully.

        Returns:
            Always True
        """
        logger.info("✅ Stub email provider configured (no real emails will be sent)")
        return True

    def get_sent_emails(self) -> list[dict]:
        """Get list of all emails sent during this session.

        Returns:
            List of email dictionaries
        """
        return self.sent_emails

    def clear_sent_emails(self) -> None:
        """Clear the sent emails list."""
        self.sent_emails.clear()
        logger.info("🗑️  Cleared stub email history")
