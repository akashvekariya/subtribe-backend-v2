"""Notification service for account-related email notifications.

Handles sending emails for:
- Welcome emails after signup
- Email verification confirmation
- Password reset requests
- Password changed alerts
- Account lockout alerts
"""

import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.email.providers import EmailMessage, SendGridEmailProvider, StubEmailProvider
from app.models.user import User

logger = logging.getLogger(__name__)


def _get_email_provider():
    """Get configured email provider."""
    if not settings.email_enabled or settings.email_provider == "stub":
        return StubEmailProvider()
    return SendGridEmailProvider(
        api_key=settings.sendgrid_api_key,
        sandbox_mode=settings.sendgrid_sandbox_mode,
    )


class NotificationService:
    """Service for sending account-related email notifications."""

    @staticmethod
    async def send_welcome_email(user: User) -> bool:
        """Send welcome email after successful registration.

        Args:
            user: The newly registered user.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Welcome to Subtribe!",
            body=f"""Hi {user.first_name},

Welcome to Subtribe! We're excited to have you on board.

Your account has been created successfully. Here's what you can do next:

1. Verify your email address (check your inbox for the verification link)
2. Enter your invite code to join or create an organization
3. Start hiring the best talent!

If you have any questions, feel free to reach out to our support team.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = _get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(f"Welcome email sent to {user.email}")
        else:
            logger.error(f"Failed to send welcome email to {user.email}: {result.error_message}")

        return result.success

    @staticmethod
    async def send_email_verified_notification(user: User) -> bool:
        """Send notification after email verification.

        Args:
            user: The user who verified their email.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Email Verified Successfully",
            body=f"""Hi {user.first_name},

Great news! Your email address has been verified successfully.

You can now access all features of your Subtribe account. If you haven't already, enter your invite code to join or create an organization.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = _get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(f"Email verified notification sent to {user.email}")
        else:
            logger.error(
                f"Failed to send email verified notification to {user.email}: {result.error_message}"
            )

        return result.success

    @staticmethod
    async def send_password_changed_alert(user: User, ip_address: str | None = None) -> bool:
        """Send alert when password is changed.

        Args:
            user: The user whose password was changed.
            ip_address: The IP address from which the change was made.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        change_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ip_info = f"IP Address: {ip_address}" if ip_address else "IP Address: Unknown"

        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Your Password Has Been Changed",
            body=f"""Hi {user.first_name},

Your Subtribe account password was successfully changed.

Change details:
- Time: {change_time}
- {ip_info}

If you made this change, you can ignore this email.

If you did NOT make this change, your account may be compromised. Please:
1. Reset your password immediately at {settings.dashboard_url}/forgot-password
2. Contact support if you need assistance

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = _get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(f"Password changed alert sent to {user.email}")
        else:
            logger.error(
                f"Failed to send password changed alert to {user.email}: {result.error_message}"
            )

        return result.success

    @staticmethod
    async def send_password_reset_success(user: User) -> bool:
        """Send notification after successful password reset.

        Args:
            user: The user whose password was reset.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Password Reset Successful",
            body=f"""Hi {user.first_name},

Your Subtribe account password has been reset successfully.

You can now log in with your new password at:
{settings.dashboard_url}/sign-in

If you did not perform this action, please contact support immediately.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = _get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(f"Password reset success notification sent to {user.email}")
        else:
            logger.error(
                f"Failed to send password reset success notification to {user.email}: {result.error_message}"
            )

        return result.success

    @staticmethod
    async def send_account_locked_alert(
        user: User, lockout_minutes: int = 15, ip_address: str | None = None
    ) -> bool:
        """Send alert when account is locked due to failed login attempts.

        Args:
            user: The user whose account was locked.
            lockout_minutes: Duration of the lockout in minutes.
            ip_address: The IP address of the last failed attempt.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        lock_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ip_info = f"IP Address: {ip_address}" if ip_address else "IP Address: Unknown"

        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Account Security Alert - Temporary Lockout",
            body=f"""Hi {user.first_name},

Your Subtribe account has been temporarily locked due to multiple failed login attempts.

Lockout details:
- Time: {lock_time}
- Duration: {lockout_minutes} minutes
- Last attempt from: {ip_info}

This is a security measure to protect your account. Your account will be automatically unlocked after {lockout_minutes} minutes.

If this was you, simply wait and try again later. If you've forgotten your password, you can reset it at:
{settings.dashboard_url}/forgot-password

If you did NOT attempt to log in, your account credentials may be compromised. Please reset your password immediately after the lockout expires.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = _get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(f"Account locked alert sent to {user.email}")
        else:
            logger.error(
                f"Failed to send account locked alert to {user.email}: {result.error_message}"
            )

        return result.success

    @staticmethod
    async def send_settings_changed_alert(
        user: User, changes: list[str], ip_address: str | None = None
    ) -> bool:
        """Send alert when account settings are changed.

        Args:
            user: The user whose settings were changed.
            changes: List of settings that were changed.
            ip_address: The IP address from which the change was made.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        change_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ip_info = f"IP Address: {ip_address}" if ip_address else "IP Address: Unknown"
        changes_list = "\n".join(f"- {change}" for change in changes)

        message = EmailMessage(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject="Account Settings Updated",
            body=f"""Hi {user.first_name},

Your Subtribe account settings have been updated.

Changes made:
{changes_list}

Change details:
- Time: {change_time}
- {ip_info}

If you made these changes, you can ignore this email.

If you did NOT make these changes, please contact support immediately.

- Team Subtribe
""",
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        provider = _get_email_provider()
        result = await provider.send_email(message)

        if result.success:
            logger.info(f"Settings changed alert sent to {user.email}")
        else:
            logger.error(
                f"Failed to send settings changed alert to {user.email}: {result.error_message}"
            )

        return result.success


# Create singleton instance
notification_service = NotificationService()
