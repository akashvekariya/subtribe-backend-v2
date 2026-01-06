"""
Auto-trigger logic for AI Resume Evaluation.

Handles automatic evaluation triggering when:
1. A new application is submitted to a calibrated job
2. A job is calibrated (for existing unevaluated applications)
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.job import Job
from app.services.evaluation.cloud_tasks import queue_evaluation_tasks
from app.services.evaluation.service import AIResumeEvalService

logger = logging.getLogger(__name__)


async def trigger_evaluation_for_application(
    db: AsyncSession,
    application_id: UUID,
    triggered_by: UUID | None = None,
) -> bool:
    """
    Trigger evaluation for a single application if the job is calibrated.

    Args:
        db: Database session
        application_id: The application to evaluate
        triggered_by: User ID who triggered (None for auto-trigger)

    Returns:
        True if evaluation was triggered, False otherwise
    """
    try:
        # Get application with job
        application = await db.get(Application, application_id)
        if not application:
            logger.warning(f"Application {application_id} not found for auto-evaluation")
            return False

        # Check if already evaluated or in progress
        if application.ai_resume_eval_status in ("completed", "processing", "queued"):
            logger.debug(f"Application {application_id} already evaluated or in progress")
            return False

        # Check if job is calibrated
        job = await db.get(Job, application.job_id)
        if not job or not job.evaluation_framework:
            logger.debug(f"Job {application.job_id} not calibrated, skipping auto-evaluation")
            return False

        # Check if application has resume URL (worker will download and parse)
        if not application.resume_url:
            logger.debug(f"Application {application_id} has no resume, skipping auto-evaluation")
            return False

        # Create evaluation batch and task
        service = AIResumeEvalService(db)
        batch = await service.start_job_evaluation(
            job_id=application.job_id,
            triggered_by=triggered_by,
            application_ids=[application_id],
        )

        # Queue the task
        pending_tasks = await service.scheduler.get_pending_tasks(batch.id, limit=1)
        if pending_tasks:
            task_ids = [task.id for task in pending_tasks]
            queue_result = await queue_evaluation_tasks(task_ids, stagger_seconds=0)
            logger.info(
                f"Auto-triggered evaluation for application {application_id}: "
                f"batch={batch.id}, queued={queue_result.get('queued', 0)}"
            )

            # Update task status to queued
            for task in pending_tasks:
                task.status = "queued"

        await db.commit()
        return True

    except ValueError as e:
        # Expected errors (e.g., no applications to evaluate)
        logger.debug(f"Auto-evaluation skipped for {application_id}: {e}")
        return False
    except Exception as e:
        logger.error(
            f"Failed to auto-trigger evaluation for application {application_id}: {e}",
            exc_info=True,
        )
        return False


async def trigger_evaluation_for_job(
    db: AsyncSession,
    job_id: UUID,
    triggered_by: UUID | None = None,
    max_applications: int = 100,
) -> int:
    """
    Trigger evaluation for all unevaluated applications in a job.

    Called when a job is calibrated.

    Args:
        db: Database session
        job_id: The job to evaluate applications for
        triggered_by: User ID who triggered
        max_applications: Maximum applications to evaluate in one batch

    Returns:
        Number of applications queued for evaluation
    """
    try:
        # Check if job is calibrated
        job = await db.get(Job, job_id)
        if not job or not job.evaluation_framework:
            logger.warning(f"Job {job_id} not calibrated")
            return 0

        # Get unevaluated applications with resumes (worker will parse)
        stmt = select(Application).where(
            Application.job_id == job_id,
            Application.deleted_at.is_(None),
            Application.ai_resume_eval_status.is_(None),
            Application.resume_url.isnot(None),
        ).limit(max_applications)

        result = await db.execute(stmt)
        applications = result.scalars().all()

        if not applications:
            logger.debug(f"No unevaluated applications with parsed resumes for job {job_id}")
            return 0

        application_ids = [app.id for app in applications]

        # Create evaluation batch
        service = AIResumeEvalService(db)
        batch = await service.start_job_evaluation(
            job_id=job_id,
            triggered_by=triggered_by,
            application_ids=application_ids,
        )

        # Queue the tasks
        pending_tasks = await service.scheduler.get_pending_tasks(batch.id, limit=max_applications)
        if pending_tasks:
            task_ids = [task.id for task in pending_tasks]
            queue_result = await queue_evaluation_tasks(task_ids, stagger_seconds=2)
            logger.info(
                f"Auto-triggered evaluation for job {job_id}: "
                f"batch={batch.id}, applications={len(application_ids)}, "
                f"queued={queue_result.get('queued', 0)}"
            )

            # Update task status to queued
            for task in pending_tasks:
                task.status = "queued"

        await db.commit()
        return len(application_ids)

    except ValueError as e:
        logger.debug(f"Auto-evaluation skipped for job {job_id}: {e}")
        return 0
    except Exception as e:
        logger.error(
            f"Failed to auto-trigger evaluation for job {job_id}: {e}",
            exc_info=True,
        )
        return 0
