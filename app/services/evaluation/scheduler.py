"""
AI Resume Evaluation Scheduler.

Handles batch creation, task queueing, and ETA calculations
for the AI resume evaluation system.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_resume_eval_batch import AIResumeEvalBatch
from app.models.ai_resume_eval_task import AIResumeEvalTask
from app.models.application import Application
from app.models.company import Company
from app.models.job import Job
from app.services.evaluation.config import CONCURRENCY_CONFIG, TIMING_CONFIG

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AIResumeEvalScheduler:
    """
    Scheduler for AI resume evaluation batches and tasks.

    Responsible for:
    - Creating evaluation batches for jobs
    - Creating individual evaluation tasks
    - Calculating ETAs based on concurrency limits
    - Managing task priorities
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_batch_for_job(
        self,
        job_id: UUID,
        triggered_by: UUID | None = None,
        application_ids: list[UUID] | None = None,
    ) -> AIResumeEvalBatch:
        """
        Create an evaluation batch for a job.

        If application_ids is provided, only those applications are included.
        Otherwise, all applications without evaluation are included.

        Args:
            job_id: The job to evaluate applications for
            triggered_by: User who triggered the evaluation
            application_ids: Optional specific application IDs to evaluate

        Returns:
            The created AIResumeEvalBatch
        """
        # Get job with company info
        job = await self.db.get(Job, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not job.evaluation_framework:
            raise ValueError(f"Job {job_id} has no evaluation framework (not calibrated)")

        company = await self.db.get(Company, job.company_id)
        if not company:
            raise ValueError(f"Company for job {job_id} not found")

        # Get applications to evaluate
        if application_ids:
            # Specific applications
            stmt = select(Application).where(
                Application.id.in_(application_ids),
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
        else:
            # All applications without evaluation
            stmt = select(Application).where(
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
                Application.ai_resume_eval_status.is_(None),
            )

        result = await self.db.execute(stmt)
        applications = result.scalars().all()

        if not applications:
            logger.info(f"No applications to evaluate for job {job_id}")
            raise ValueError("No applications to evaluate")

        # Get concurrency limit for company
        concurrent_workers = await self._get_company_concurrent_limit(company)

        # Calculate ETA
        total_count = len(applications)
        estimated_seconds, estimated_completion = self._calculate_eta(
            total_count, concurrent_workers
        )

        # Create batch
        batch = AIResumeEvalBatch(
            job_id=job_id,
            company_id=job.company_id,
            triggered_by=triggered_by,
            total_count=total_count,
            estimated_seconds=estimated_seconds,
            estimated_completion_at=estimated_completion,
            status="pending",
        )
        self.db.add(batch)
        await self.db.flush()  # Get batch ID

        logger.info(
            f"Created batch {batch.id} for job {job_id}: "
            f"{total_count} applications, ETA: {estimated_seconds}s"
        )

        # Create tasks for each application
        for application in applications:
            task = AIResumeEvalTask(
                batch_id=batch.id,
                application_id=application.id,
                status="pending",
            )
            self.db.add(task)

            # Update application status
            application.ai_resume_eval_status = "pending"
            application.ai_resume_eval_batch_id = batch.id

        await self.db.flush()

        return batch

    async def get_pending_tasks(
        self,
        batch_id: UUID,
        limit: int = 100,
    ) -> list[AIResumeEvalTask]:
        """
        Get pending tasks for a batch.

        Args:
            batch_id: The batch to get tasks for
            limit: Maximum number of tasks to return

        Returns:
            List of pending tasks
        """
        stmt = (
            select(AIResumeEvalTask)
            .where(
                AIResumeEvalTask.batch_id == batch_id,
                AIResumeEvalTask.status == "pending",
            )
            .order_by(AIResumeEvalTask.created_at)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_retry_scheduled_tasks(
        self,
        limit: int = 100,
    ) -> list[AIResumeEvalTask]:
        """
        Get tasks scheduled for retry that are due.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of tasks ready for retry
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(AIResumeEvalTask)
            .where(
                AIResumeEvalTask.status == "retry_scheduled",
                AIResumeEvalTask.next_retry_at <= now,
            )
            .order_by(AIResumeEvalTask.next_retry_at)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stuck_tasks(
        self,
        threshold_minutes: int | None = None,
        limit: int = 100,
    ) -> list[AIResumeEvalTask]:
        """
        Get tasks that appear to be stuck (processing too long).

        Args:
            threshold_minutes: Minutes before considering stuck (default from config)
            limit: Maximum number of tasks to return

        Returns:
            List of stuck tasks
        """
        threshold = threshold_minutes or TIMING_CONFIG.stuck_task_threshold_minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold)

        stmt = (
            select(AIResumeEvalTask)
            .where(
                AIResumeEvalTask.status == "processing",
                AIResumeEvalTask.started_at < cutoff,
            )
            .order_by(AIResumeEvalTask.started_at)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def can_process_for_company(self, company_id: UUID) -> bool:
        """
        Check if company has available processing slots.

        Args:
            company_id: The company to check

        Returns:
            True if slots available, False otherwise
        """
        company = await self.db.get(Company, company_id)
        if not company:
            return False

        concurrent_limit = await self._get_company_concurrent_limit(company)
        active_count = await self._get_active_task_count(company_id)

        return active_count < concurrent_limit

    async def get_available_slots(self, company_id: UUID) -> int:
        """
        Get number of available processing slots for a company.

        Args:
            company_id: The company to check

        Returns:
            Number of available slots
        """
        company = await self.db.get(Company, company_id)
        if not company:
            return 0

        concurrent_limit = await self._get_company_concurrent_limit(company)
        active_count = await self._get_active_task_count(company_id)

        return max(0, concurrent_limit - active_count)

    async def get_global_available_slots(self) -> int:
        """
        Get number of globally available processing slots.

        Returns:
            Number of available global slots
        """
        global_active = await self._get_global_active_count()
        return max(0, CONCURRENCY_CONFIG.global_max_concurrent - global_active)

    async def mark_task_queued(self, task: AIResumeEvalTask, cloud_task_name: str) -> None:
        """
        Mark a task as queued for processing.

        Args:
            task: The task to mark
            cloud_task_name: The Cloud Tasks task name
        """
        task.status = "queued"
        task.cloud_task_name = cloud_task_name
        task.scheduled_at = datetime.now(timezone.utc)

        # Update application status
        application = await self.db.get(Application, task.application_id)
        if application:
            application.ai_resume_eval_status = "queued"

        # Update batch queued count
        batch = await self.db.get(AIResumeEvalBatch, task.batch_id)
        if batch:
            batch.queued_count += 1

    async def update_batch_progress(self, batch_id: UUID) -> AIResumeEvalBatch | None:
        """
        Update batch progress counts from task statuses.

        Args:
            batch_id: The batch to update

        Returns:
            Updated batch or None if not found
        """
        batch = await self.db.get(AIResumeEvalBatch, batch_id)
        if not batch:
            return None

        # Count tasks by status
        stmt = (
            select(AIResumeEvalTask.status, func.count(AIResumeEvalTask.id))
            .where(AIResumeEvalTask.batch_id == batch_id)
            .group_by(AIResumeEvalTask.status)
        )

        result = await self.db.execute(stmt)
        status_counts = dict(result.all())

        batch.queued_count = status_counts.get("queued", 0)
        batch.processing_count = status_counts.get("processing", 0)
        batch.completed_count = status_counts.get("completed", 0) + status_counts.get("skipped", 0)
        batch.failed_count = status_counts.get("failed", 0)

        # Check if batch is complete
        if batch.is_complete and batch.status == "processing":
            batch.status = "completed"
            batch.completed_at = datetime.now(timezone.utc)
            logger.info(
                f"Batch {batch_id} completed: {batch.completed_count} success, {batch.failed_count} failed"
            )

        return batch

    async def _get_company_concurrent_limit(self, company: Company) -> int:
        """Get concurrent evaluation limit for a company."""
        # Use company override if set
        if company.max_concurrent_ai_evaluations is not None:
            return company.max_concurrent_ai_evaluations

        # Use plan-based limit
        return CONCURRENCY_CONFIG.get_limit_for_plan(company.plan)

    async def _get_active_task_count(self, company_id: UUID) -> int:
        """Get count of active (processing) tasks for a company."""
        stmt = (
            select(func.count(AIResumeEvalTask.id))
            .join(AIResumeEvalBatch)
            .where(
                AIResumeEvalBatch.company_id == company_id,
                AIResumeEvalTask.status == "processing",
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _get_global_active_count(self) -> int:
        """Get count of all active (processing) tasks globally."""
        stmt = select(func.count(AIResumeEvalTask.id)).where(
            AIResumeEvalTask.status == "processing"
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    def _calculate_eta(
        self,
        total_count: int,
        concurrent_workers: int,
    ) -> tuple[int, datetime]:
        """
        Calculate estimated completion time.

        Args:
            total_count: Total number of tasks
            concurrent_workers: Number of concurrent workers

        Returns:
            Tuple of (seconds, completion_datetime)
        """
        if concurrent_workers == 0:
            concurrent_workers = 1

        # Calculate raw time
        raw_seconds = (total_count / concurrent_workers) * TIMING_CONFIG.seconds_per_evaluation

        # Apply buffer
        buffered_seconds = raw_seconds * TIMING_CONFIG.eta_buffer_multiplier

        completion_time = datetime.now(timezone.utc) + timedelta(seconds=buffered_seconds)

        return int(buffered_seconds), completion_time
