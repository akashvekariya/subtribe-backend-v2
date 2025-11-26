"""Email service for scheduling and sending emails."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.email.default_templates import get_default_template, get_variable_fallbacks
from app.email.providers import (
    EmailMessage,
    EmailProvider,
    SendGridEmailProvider,
    StubEmailProvider,
)
from app.email.template_renderer import template_renderer
from app.models.application import Application
from app.models.email_template import EmailTemplate
from app.models.scheduled_email import ScheduledEmail

logger = logging.getLogger(__name__)


class EmailService:
    """Service for scheduling and sending candidate emails.

    Responsibilities:
    - Schedule emails when application status changes
    - Cancel previous scheduled emails
    - Render email templates with variable substitution
    - Send emails via configured provider (stub or sendgrid)
    """

    def __init__(self, db: AsyncSession):
        """Initialize email service.

        Args:
            db: Database session
        """
        self.db = db
        self.provider = self._get_email_provider()

    def _get_email_provider(self) -> EmailProvider:
        """Get configured email provider based on settings.

        Returns:
            EmailProvider instance (StubEmailProvider or SendGridEmailProvider)
        """
        if not settings.email_enabled:
            logger.info("📧 Email sending disabled in config")
            return StubEmailProvider()

        if settings.email_provider == "stub":
            logger.info("📧 Using StubEmailProvider (emails will be logged, not sent)")
            return StubEmailProvider()
        elif settings.email_provider == "sendgrid":
            logger.info(
                f"📧 Using SendGridEmailProvider "
                f"(sandbox_mode={settings.sendgrid_sandbox_mode})"
            )
            return SendGridEmailProvider(
                api_key=settings.sendgrid_api_key,
                sandbox_mode=settings.sendgrid_sandbox_mode,
            )
        else:
            logger.warning(
                f"Unknown email_provider: {settings.email_provider}, "
                f"falling back to StubEmailProvider"
            )
            return StubEmailProvider()

    async def schedule_email(
        self,
        application: Application,
        template_type: str,
        metadata: Optional[Dict] = None,
    ) -> ScheduledEmail:
        """Schedule an email to be sent at 5 PM IST the next day.

        Args:
            application: Application object
            template_type: 'interview_invite' or 'rejection'
            metadata: Optional metadata (calendly_link, etc.)

        Returns:
            Created ScheduledEmail record

        Raises:
            ValueError: If template_type is invalid or required data is missing
        """
        # Cancel any previous pending emails for this application
        await self._cancel_previous_emails(application.id, template_type)

        # Get or create email template
        template = await self._get_template(application.company_id, template_type)

        # Prepare template variables
        variables = {
            "candidate_name": application.first_name,
            "company_name": application.company.name,
            "job_title": application.job.title,
        }

        # Add metadata variables (calendly_link, etc.)
        if metadata:
            variables.update(metadata)

        # Render subject and body with fallbacks
        fallbacks = get_variable_fallbacks()
        rendered_subject = template_renderer.render_with_fallbacks(
            template["subject"], variables, fallbacks
        )
        rendered_body = template_renderer.render_with_fallbacks(
            template["body"], variables, fallbacks
        )

        # Calculate send time (5 PM IST next day)
        scheduled_for = self._calculate_send_time()

        # Create scheduled email record
        scheduled_email = ScheduledEmail(
            application_id=application.id,
            company_id=application.company_id,
            template_type=template_type,
            recipient_email=application.email,
            recipient_name=f"{application.first_name} {application.last_name}",
            subject=rendered_subject,
            body=rendered_body,
            scheduled_for=scheduled_for,
            status="pending",
            email_metadata=metadata or {},
        )

        self.db.add(scheduled_email)
        await self.db.flush()

        logger.info(
            f"📅 Scheduled {template_type} email for {application.email} "
            f"at {scheduled_for.isoformat()}"
        )

        return scheduled_email

    async def send_scheduled_email(self, scheduled_email_id: UUID) -> bool:
        """Send a scheduled email immediately.

        Args:
            scheduled_email_id: ID of scheduled email to send

        Returns:
            True if email sent successfully, False otherwise
        """
        # Fetch scheduled email
        stmt = select(ScheduledEmail).where(ScheduledEmail.id == scheduled_email_id)
        result = await self.db.execute(stmt)
        scheduled_email = result.scalar_one_or_none()

        if not scheduled_email:
            logger.error(f"❌ Scheduled email {scheduled_email_id} not found")
            return False

        if scheduled_email.status != "pending":
            logger.warning(
                f"⚠️  Scheduled email {scheduled_email_id} already processed "
                f"(status={scheduled_email.status})"
            )
            return False

        # Build email message
        message = EmailMessage(
            to_email=scheduled_email.recipient_email,
            to_name=scheduled_email.recipient_name,
            subject=scheduled_email.subject,
            body=scheduled_email.body,
            from_email=settings.email_from_address,
            from_name=settings.email_from_name,
        )

        # Send email via provider
        try:
            result = await self.provider.send_email(message)

            if result.success:
                # Update scheduled email status
                scheduled_email.status = "sent"
                scheduled_email.sent_at = datetime.now(timezone.utc)
                scheduled_email.provider_message_id = result.message_id
                await self.db.commit()

                logger.info(
                    f"✅ Email sent successfully to {scheduled_email.recipient_email} "
                    f"(message_id={result.message_id})"
                )
                return True
            else:
                # Mark as failed
                scheduled_email.status = "failed"
                scheduled_email.error_message = result.error_message
                await self.db.commit()

                logger.error(
                    f"❌ Failed to send email to {scheduled_email.recipient_email}: "
                    f"{result.error_message}"
                )
                return False

        except Exception as e:
            # Mark as failed
            scheduled_email.status = "failed"
            scheduled_email.error_message = str(e)
            await self.db.commit()

            logger.exception(
                f"❌ Exception while sending email to {scheduled_email.recipient_email}: {str(e)}"
            )
            return False

    async def _cancel_previous_emails(
        self, application_id: UUID, template_type: str
    ) -> int:
        """Cancel any pending emails for this application and template type.

        Args:
            application_id: Application ID
            template_type: Email template type

        Returns:
            Number of emails cancelled
        """
        stmt = (
            select(ScheduledEmail)
            .where(ScheduledEmail.application_id == application_id)
            .where(ScheduledEmail.template_type == template_type)
            .where(ScheduledEmail.status == "pending")
        )

        result = await self.db.execute(stmt)
        pending_emails = result.scalars().all()

        count = 0
        for email in pending_emails:
            email.status = "cancelled"
            count += 1

        if count > 0:
            await self.db.flush()
            logger.info(
                f"🚫 Cancelled {count} pending {template_type} email(s) "
                f"for application {application_id}"
            )

        return count

    async def _get_template(
        self, company_id: UUID, template_type: str
    ) -> Dict[str, str]:
        """Get email template (custom or default).

        Args:
            company_id: Company ID
            template_type: Template type

        Returns:
            Dictionary with 'subject' and 'body' keys
        """
        # Try to get company's custom template
        stmt = (
            select(EmailTemplate)
            .where(EmailTemplate.company_id == company_id)
            .where(EmailTemplate.template_type == template_type)
        )

        result = await self.db.execute(stmt)
        custom_template = result.scalar_one_or_none()

        if custom_template:
            logger.debug(f"Using custom {template_type} template for company {company_id}")
            return {
                "subject": custom_template.subject,
                "body": custom_template.body,
            }

        # Fall back to default template
        logger.debug(f"Using default {template_type} template for company {company_id}")
        return get_default_template(template_type)

    def _calculate_send_time(self) -> datetime:
        """Calculate the send time (5 PM IST next day).

        Returns:
            Datetime in UTC timezone
        """
        # Get current time in IST
        ist = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(ist)

        # Calculate next day 5 PM IST
        send_time_ist = now_ist.replace(
            hour=17, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # Parse configured send time (default: "17:00")
        try:
            hour, minute = settings.email_send_time_ist.split(":")
            send_time_ist = send_time_ist.replace(hour=int(hour), minute=int(minute))
        except (ValueError, AttributeError):
            logger.warning(
                f"Invalid email_send_time_ist: {settings.email_send_time_ist}, "
                f"using default 17:00"
            )

        # Convert to UTC
        send_time_utc = send_time_ist.astimezone(timezone.utc)

        return send_time_utc
