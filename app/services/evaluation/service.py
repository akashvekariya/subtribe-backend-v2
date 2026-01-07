"""
AI Resume Evaluation Service.

Main orchestration service for the AI resume evaluation system.
This is the primary entry point for starting and managing evaluations.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_resume_eval_batch import AIResumeEvalBatch
from app.models.ai_resume_eval_task import AIResumeEvalTask
from app.models.application import Application
from app.models.job import Job
from app.services.evaluation.notifications import notify_batch_completion
from app.services.evaluation.scheduler import AIResumeEvalScheduler
from app.services.evaluation.worker import AIResumeEvalWorker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AIResumeEvalService:
    """
    Main service for AI resume evaluation.

    This service orchestrates:
    - Starting evaluations (single or batch)
    - Processing tasks
    - Tracking progress
    - Handling completion
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scheduler = AIResumeEvalScheduler(db)
        self.worker = AIResumeEvalWorker(db)

    # =========================================================================
    # PUBLIC API - Starting Evaluations
    # =========================================================================

    async def start_job_evaluation(
        self,
        job_id: UUID,
        triggered_by: UUID | None = None,
        application_ids: list[UUID] | None = None,
    ) -> AIResumeEvalBatch:
        """
        Start AI resume evaluation for a job.

        If application_ids is provided, only those applications are evaluated.
        Otherwise, all unevaluated applications for the job are evaluated.

        Args:
            job_id: The job to evaluate applications for
            triggered_by: User who triggered the evaluation (for notifications)
            application_ids: Optional specific application IDs

        Returns:
            The created AIResumeEvalBatch

        Raises:
            ValueError: If job not found, not calibrated, or no applications
        """
        # Validate job exists and is calibrated
        job = await self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.evaluation_framework:
            raise ValueError(f"Job {job_id} is not calibrated. Please complete calibration first.")

        # Create batch
        batch = await self.scheduler.create_batch_for_job(
            job_id=job_id,
            triggered_by=triggered_by,
            application_ids=application_ids,
        )

        # Start processing
        batch.status = "processing"
        batch.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            f"Started AI resume evaluation for job {job_id}: "
            f"batch={batch.id}, applications={batch.total_count}"
        )

        return batch

    async def evaluate_single_application(
        self,
        application_id: UUID,
        triggered_by: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate a single application immediately.

        This is for on-demand evaluation of new applications
        that arrive after calibration.

        Args:
            application_id: The application to evaluate
            triggered_by: User who triggered the evaluation

        Returns:
            Evaluation result dict

        Raises:
            ValueError: If application not found or job not calibrated
        """
        application = await self.db.get(Application, application_id)
        if not application:
            raise ValueError(f"Application {application_id} not found")

        job = await self.db.get(Job, application.job_id)
        if not job:
            raise ValueError(f"Job for application {application_id} not found")

        if not job.evaluation_framework:
            raise ValueError(f"Job {job.id} is not calibrated")

        # Create a single-item batch
        batch = await self.scheduler.create_batch_for_job(
            job_id=job.id,
            triggered_by=triggered_by,
            application_ids=[application_id],
        )

        # Get the task
        tasks = await self.scheduler.get_pending_tasks(batch.id, limit=1)
        if not tasks:
            raise ValueError("Failed to create evaluation task")

        task = tasks[0]

        # Process immediately (synchronous)
        batch.status = "processing"
        batch.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        result = await self.worker.process_task(task.id)

        # Update batch
        await self.scheduler.update_batch_progress(batch.id)

        return result

    # =========================================================================
    # PUBLIC API - Task Processing
    # =========================================================================

    async def process_task(self, task_id: UUID) -> dict[str, Any]:
        """
        Process a single evaluation task.

        Called by Cloud Tasks or direct invocation.

        Args:
            task_id: The task to process

        Returns:
            Processing result dict
        """
        result = await self.worker.process_task(task_id)

        # Get task to update batch
        task = await self.db.get(AIResumeEvalTask, task_id)
        if task:
            batch = await self.scheduler.update_batch_progress(task.batch_id)

            # Check if batch is complete and send notification
            if batch and batch.is_complete and not batch.notification_sent:
                await notify_batch_completion(self.db, batch.id)

        return result

    # =========================================================================
    # PUBLIC API - Status & Progress
    # =========================================================================

    async def get_batch_status(self, batch_id: UUID) -> dict[str, Any] | None:
        """
        Get status and progress for a batch.

        Args:
            batch_id: The batch to check

        Returns:
            Status dict or None if not found
        """
        batch = await self.db.get(AIResumeEvalBatch, batch_id)
        if not batch:
            return None

        # Calculate ETA
        remaining = batch.total_count - (batch.completed_count + batch.failed_count)
        eta_seconds = None
        # Rough estimate based on elapsed time
        if (
            batch.status == "processing"
            and remaining > 0
            and batch.started_at
            and batch.completed_count > 0
        ):
            elapsed = (datetime.now(timezone.utc) - batch.started_at).total_seconds()
            seconds_per_task = elapsed / batch.completed_count
            eta_seconds = int(remaining * seconds_per_task)

        return {
            "batch_id": str(batch.id),
            "job_id": str(batch.job_id),
            "status": batch.status,
            "progress": {
                "total": batch.total_count,
                "queued": batch.queued_count,
                "processing": batch.processing_count,
                "completed": batch.completed_count,
                "failed": batch.failed_count,
                "percent": batch.progress_percent,
            },
            "timing": {
                "started_at": batch.started_at.isoformat() if batch.started_at else None,
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
                "estimated_seconds": batch.estimated_seconds,
                "estimated_completion_at": (
                    batch.estimated_completion_at.isoformat()
                    if batch.estimated_completion_at
                    else None
                ),
                "eta_seconds": eta_seconds,
            },
            "created_at": batch.created_at.isoformat(),
        }

    async def get_job_evaluation_status(self, job_id: UUID) -> dict[str, Any]:
        """
        Get evaluation status for a job (latest batch).

        Args:
            job_id: The job to check

        Returns:
            Status dict
        """
        # Get most recent batch for job
        stmt = (
            select(AIResumeEvalBatch)
            .where(AIResumeEvalBatch.job_id == job_id)
            .order_by(AIResumeEvalBatch.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        batch = result.scalar_one_or_none()

        if not batch:
            return {
                "job_id": str(job_id),
                "has_evaluation": False,
                "latest_batch": None,
            }

        batch_status = await self.get_batch_status(batch.id)
        return {
            "job_id": str(job_id),
            "has_evaluation": True,
            "latest_batch": batch_status,
        }

    async def get_application_evaluation(
        self,
        application_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Get evaluation results for an application.

        Args:
            application_id: The application to check

        Returns:
            Evaluation dict or None if not evaluated
        """
        application = await self.db.get(Application, application_id)
        if not application:
            return None

        if not application.evaluation_json:
            return {
                "application_id": str(application_id),
                "evaluated": False,
                "status": application.ai_resume_eval_status,
            }

        return {
            "application_id": str(application_id),
            "evaluated": True,
            "status": application.ai_resume_eval_status,
            "score": application.evaluation_score,
            "tier": application.evaluation_tier,
            "evaluated_at": (
                application.evaluated_at.isoformat() if application.evaluated_at else None
            ),
            "evaluation": application.evaluation_json,
        }

    # =========================================================================
    # PUBLIC API - Batch Management
    # =========================================================================

    async def cancel_batch(self, batch_id: UUID) -> bool:
        """
        Cancel a pending or processing batch.

        Args:
            batch_id: The batch to cancel

        Returns:
            True if cancelled, False if not found or already complete
        """
        batch = await self.db.get(AIResumeEvalBatch, batch_id)
        if not batch:
            return False

        if batch.status in ("completed", "failed", "cancelled"):
            logger.info(f"Batch {batch_id} already in terminal state: {batch.status}")
            return False

        # Cancel all pending/queued tasks
        stmt = select(AIResumeEvalTask).where(
            AIResumeEvalTask.batch_id == batch_id,
            AIResumeEvalTask.status.in_(["pending", "queued", "retry_scheduled"]),
        )
        result = await self.db.execute(stmt)
        tasks = result.scalars().all()

        for task in tasks:
            task.status = "skipped"
            task.last_error = "Batch cancelled"
            task.completed_at = datetime.now(timezone.utc)

            # Update application status
            application = await self.db.get(Application, task.application_id)
            if application:
                application.ai_resume_eval_status = "skipped"

        # Update batch
        batch.status = "cancelled"
        batch.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(f"Cancelled batch {batch_id}: {len(tasks)} tasks skipped")
        return True

    # =========================================================================
    # PUBLIC API - Retry Management
    # =========================================================================

    async def retry_failed_tasks(self, batch_id: UUID) -> int:
        """
        Retry all failed or skipped tasks in a batch.

        Args:
            batch_id: The batch to retry failed tasks for

        Returns:
            Number of tasks queued for retry
        """
        stmt = select(AIResumeEvalTask).where(
            AIResumeEvalTask.batch_id == batch_id,
            AIResumeEvalTask.status.in_(["failed", "skipped", "queued", "pending"]),
        )
        result = await self.db.execute(stmt)
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            # Reset task for retry
            task.status = "pending"
            task.last_error = None
            task.last_error_code = None
            task.attempt_count = 0  # Reset attempts for skipped tasks

            application = await self.db.get(Application, task.application_id)
            if application:
                application.ai_resume_eval_status = "pending"

            count += 1

        # Update batch status if it was completed/failed
        batch = await self.db.get(AIResumeEvalBatch, batch_id)
        if batch and batch.status in ("completed", "failed"):
            batch.status = "processing"
            batch.completed_at = None

        await self.db.flush()

        logger.info(f"Queued {count} failed tasks for retry in batch {batch_id}")
        return count

    async def process_stuck_tasks(self) -> int:
        """
        Find and reschedule stuck tasks.

        Called periodically by cron job.

        Returns:
            Number of tasks rescheduled
        """
        tasks = await self.scheduler.get_stuck_tasks()

        count = 0
        for task in tasks:
            logger.warning(
                f"Task {task.id} appears stuck (started {task.started_at}). Rescheduling..."
            )
            task.status = "retry_scheduled"
            task.next_retry_at = datetime.now(timezone.utc)
            task.last_error = "Task appeared stuck, rescheduled"
            count += 1

        await self.db.flush()

        if count > 0:
            logger.info(f"Rescheduled {count} stuck tasks")

        return count

    async def process_retry_scheduled_tasks(self) -> int:
        """
        Process tasks that are scheduled for retry.

        Called periodically by cron job or Cloud Scheduler.

        Returns:
            Number of tasks processed
        """
        tasks = await self.scheduler.get_retry_scheduled_tasks()

        count = 0
        for task in tasks:
            # Reset to pending so it can be picked up
            task.status = "pending"
            count += 1

        await self.db.flush()

        if count > 0:
            logger.info(f"Reset {count} retry-scheduled tasks to pending")

        return count


# =========================================================================
# Convenience Functions
# =========================================================================


async def start_job_evaluation(
    db: AsyncSession,
    job_id: UUID,
    triggered_by: UUID | None = None,
) -> AIResumeEvalBatch:
    """Start AI resume evaluation for all unevaluated applications in a job."""
    service = AIResumeEvalService(db)
    return await service.start_job_evaluation(job_id, triggered_by)


async def process_evaluation_task(
    db: AsyncSession,
    task_id: UUID,
) -> dict[str, Any]:
    """Process a single evaluation task."""
    service = AIResumeEvalService(db)
    return await service.process_task(task_id)


async def get_batch_status(
    db: AsyncSession,
    batch_id: UUID,
) -> dict[str, Any] | None:
    """Get status for an evaluation batch."""
    service = AIResumeEvalService(db)
    return await service.get_batch_status(batch_id)
