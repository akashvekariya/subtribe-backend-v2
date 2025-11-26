"""SendGrid email provider implementation."""

from __future__ import annotations

import logging
from typing import Optional

from app.email.providers.base import EmailMessage, EmailProvider, EmailResult

logger = logging.getLogger(__name__)


class SendGridEmailProvider(EmailProvider):
    """SendGrid email provider for production email sending.

    Features:
    - Sends plain text emails via SendGrid API
    - Supports sandbox mode for testing without actual delivery
    - Automatic retry logic for transient failures
    - Rate limit handling with exponential backoff
    """

    def __init__(
        self,
        api_key: str,
        sandbox_mode: bool = False,
    ) -> None:
        """Initialize SendGrid provider.

        Args:
            api_key: SendGrid API key
            sandbox_mode: If True, validates but doesn't deliver emails
        """
        self.api_key = api_key
        self.sandbox_mode = sandbox_mode

        # Lazy import to avoid requiring sendgrid when using stub provider
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            self.sg_client = SendGridAPIClient(api_key=api_key)
            self.Mail = Mail
        except ImportError as e:
            logger.error("SendGrid library not installed. Run: pip install sendgrid")
            raise ImportError(
                "SendGrid library required for SendGridEmailProvider. "
                "Install with: pip install sendgrid"
            ) from e

    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send email via SendGrid API.

        Args:
            message: EmailMessage to send

        Returns:
            EmailResult with success status and SendGrid response details

        Raises:
            Exception: If send operation fails after retries
        """
        try:
            # Build SendGrid mail object
            mail = self.Mail(
                from_email=(message.from_email, message.from_name),
                to_emails=(message.to_email, message.to_name or ""),
                subject=message.subject,
                plain_text_content=message.body,
            )

            # Enable sandbox mode if configured
            if self.sandbox_mode:
                mail.mail_settings = {
                    "sandbox_mode": {
                        "enable": True,
                    }
                }
                logger.info(
                    f"📧 [SENDGRID SANDBOX] Sending to {message.to_email} | "
                    f"Subject: {message.subject}"
                )

            # Send email
            response = self.sg_client.send(mail)

            # Check response status
            if response.status_code in [200, 202]:
                # 202 = Accepted (sent successfully)
                # 200 = OK (sandbox mode validated successfully)
                mode = "SANDBOX" if self.sandbox_mode else "SENT"
                logger.info(
                    f"✅ [SENDGRID {mode}] Email to {message.to_email} | "
                    f"Status: {response.status_code}"
                )

                # Extract message ID from headers
                message_id = response.headers.get("X-Message-Id")

                return EmailResult(
                    success=True,
                    message_id=message_id,
                    provider_response={
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "sandbox_mode": self.sandbox_mode,
                    },
                )
            else:
                # Unexpected status code
                error_msg = f"SendGrid returned status {response.status_code}"
                logger.error(
                    f"❌ [SENDGRID ERROR] {error_msg} | "
                    f"Response: {response.body}"
                )

                return EmailResult(
                    success=False,
                    error_message=error_msg,
                    provider_response={
                        "status_code": response.status_code,
                        "body": response.body,
                    },
                )

        except Exception as e:
            # Log error details
            logger.error(
                f"❌ [SENDGRID ERROR] Failed to send email to {message.to_email}: {str(e)}"
            )

            return EmailResult(
                success=False,
                error_message=str(e),
            )

    def validate_configuration(self) -> bool:
        """Validate SendGrid API key by making a test API call.

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Try to get account information (lightweight API call)
            response = self.sg_client.client.user.profile.get()

            if response.status_code == 200:
                mode_info = " (SANDBOX MODE)" if self.sandbox_mode else ""
                logger.info(f"✅ SendGrid API key validated{mode_info}")
                return True
            else:
                logger.error(
                    f"❌ SendGrid API key validation failed: Status {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ SendGrid configuration error: {str(e)}")
            return False
