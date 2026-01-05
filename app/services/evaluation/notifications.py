"""
AI Resume Evaluation Notifications.

Handles email and other notifications for the AI resume evaluation system.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_resume_eval_batch import AIResumeEvalBatch
from app.models.job import Job
from app.models.user import User

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AIResumeEvalNotifier:
    """
    Notifier for AI resume evaluation events.

    Responsible for:
    - Sending batch completion emails
    - Logging notification events
    - Managing notification state
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_batch_complete(self, batch_id: UUID) -> bool:
        """
        Send notification that a batch has completed.

        Args:
            batch_id: The completed batch ID

        Returns:
            True if notification sent, False otherwise
        """
        batch = await self.db.get(AIResumeEvalBatch, batch_id)
        if not batch:
            logger.error(f"Batch {batch_id} not found for notification")
            return False

        if batch.notification_sent:
            logger.info(f"Batch {batch_id} notification already sent")
            return True

        # Get job and triggering user
        job = await self.db.get(Job, batch.job_id)
        if not job:
            logger.error(f"Job not found for batch {batch_id}")
            return False

        user = None
        if batch.triggered_by:
            user = await self.db.get(User, batch.triggered_by)

        # Build notification
        notification = self._build_completion_notification(batch, job, user)

        # Send notification (currently just logs)
        await self._send_notification(notification)

        # Mark as sent
        batch.notification_sent = True
        batch.notification_sent_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"Batch {batch_id} completion notification sent")
        return True

    def _build_completion_notification(
        self,
        batch: AIResumeEvalBatch,
        job: Job,
        user: User | None,
    ) -> dict:
        """Build notification content for batch completion."""
        success_rate = 0
        if batch.total_count > 0:
            success_rate = round(
                (batch.completed_count / batch.total_count) * 100, 1
            )

        # Calculate duration
        duration_seconds = None
        if batch.started_at and batch.completed_at:
            duration_seconds = int(
                (batch.completed_at - batch.started_at).total_seconds()
            )

        return {
            "type": "batch_complete",
            "batch_id": str(batch.id),
            "job_id": str(job.id),
            "job_title": job.title,
            "recipient_email": user.email if user else None,
            "recipient_name": f"{user.first_name} {user.last_name}" if user else None,
            "stats": {
                "total": batch.total_count,
                "completed": batch.completed_count,
                "failed": batch.failed_count,
                "success_rate": success_rate,
                "duration_seconds": duration_seconds,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _send_notification(self, notification: dict) -> None:
        """
        Send the notification.

        Currently logs to console. Future: integrate with email service.

        Args:
            notification: The notification payload
        """
        # Log notification (future: send email via SendGrid/SES)
        stats = notification.get("stats", {})
        recipient = notification.get("recipient_email", "N/A")

        logger.info(
            f"📧 AI RESUME EVAL COMPLETE | "
            f"Job: {notification.get('job_title', 'Unknown')} | "
            f"Results: {stats.get('completed', 0)}/{stats.get('total', 0)} "
            f"({stats.get('success_rate', 0)}% success) | "
            f"Duration: {stats.get('duration_seconds', 'N/A')}s | "
            f"Recipient: {recipient}"
        )

        # TODO: Implement actual email sending
        # Example with SendGrid:
        # await send_email(
        #     to=notification["recipient_email"],
        #     subject=f"AI Evaluation Complete: {notification['job_title']}",
        #     template="batch_complete",
        #     context=notification,
        # )


async def notify_batch_completion(db: AsyncSession, batch_id: UUID) -> bool:
    """
    Convenience function to send batch completion notification.

    Args:
        db: Database session
        batch_id: Batch ID to notify about

    Returns:
        True if sent, False otherwise
    """
    notifier = AIResumeEvalNotifier(db)
    return await notifier.notify_batch_complete(batch_id)
