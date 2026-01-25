"""
AI Resume Evaluation API Endpoints.

Provides endpoints for starting, monitoring, and managing
AI resume evaluation batches.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.ai_resume_eval_batch import AIResumeEvalBatch
from app.models.job import Job
from app.schemas.application import EvaluationDetailResponse
from app.services.evaluation import (
    AIResumeEvalService,
    get_batch_status,
    queue_evaluation_tasks,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-resume-eval", tags=["AI Resume Evaluation"])


# =========================================================================
# Request/Response Schemas
# =========================================================================


class StartEvaluationRequest(BaseModel):
    """Request to start AI resume evaluation for a job."""

    application_ids: list[UUID] | None = Field(
        default=None,
        description="Specific application IDs to evaluate. If not provided, all unevaluated applications are included.",
    )


class StartEvaluationResponse(BaseModel):
    """Response after starting AI resume evaluation."""

    batch_id: UUID
    job_id: UUID
    total_count: int
    estimated_seconds: int | None
    estimated_completion_at: str | None
    status: str
    message: str


class BatchStatusResponse(BaseModel):
    """Response with batch status and progress."""

    batch_id: str
    job_id: str
    status: str
    progress: dict[str, Any]
    timing: dict[str, Any]
    created_at: str


class JobEvaluationStatusResponse(BaseModel):
    """Response with job evaluation status."""

    job_id: str
    has_evaluation: bool
    latest_batch: BatchStatusResponse | None = None


class CancelBatchResponse(BaseModel):
    """Response after cancelling a batch."""

    success: bool
    message: str


class RetryFailedResponse(BaseModel):
    """Response after retrying failed tasks."""

    success: bool
    retried_count: int
    message: str


class ProcessTaskResponse(BaseModel):
    """Response after processing a single task."""

    success: bool
    score: float | None = None
    tier: str | None = None
    error: str | None = None
    error_code: str | None = None
    will_retry: bool | None = None


# =========================================================================
# Public API Endpoints
# =========================================================================


@router.post(
    "/jobs/{job_id}/start",
    response_model=StartEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_job_evaluation(
    job_id: UUID,
    request: StartEvaluationRequest | None = None,
    current_user: dict = Depends(require_role("admin", "recruiter")),
    db: AsyncSession = Depends(get_db),
):
    """
    Start AI resume evaluation for a job.

    This will create evaluation tasks for all unevaluated applications
    in the job (or specific applications if provided).

    Requirements:
    - Job must be calibrated (have evaluation_framework)
    - User must have admin or recruiter role
    """
    # Check job exists and belongs to user's company
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if str(job.company_id) != current_user["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this job")

    if not job.evaluation_framework:
        raise HTTPException(
            status_code=400,
            detail="Job is not calibrated. Please complete calibration first.",
        )

    try:
        service = AIResumeEvalService(db)
        application_ids = request.application_ids if request else None

        batch = await service.start_job_evaluation(
            job_id=job_id,
            triggered_by=UUID(current_user["user_id"]),
            application_ids=application_ids,
        )

        # Queue tasks to Cloud Tasks for background processing
        pending_tasks = await service.scheduler.get_pending_tasks(batch.id, limit=1000)
        task_ids = [task.id for task in pending_tasks]

        if task_ids:
            # Queue with staggered execution (2 seconds between tasks)
            queue_result = await queue_evaluation_tasks(task_ids, stagger_seconds=2)
            logger.info(
                f"Queued {queue_result['queued']}/{queue_result['total']} tasks "
                f"for batch {batch.id}"
            )

            # Update task statuses
            for task in pending_tasks:
                task.status = "queued"

        await db.commit()

        return StartEvaluationResponse(
            batch_id=batch.id,
            job_id=batch.job_id,
            total_count=batch.total_count,
            estimated_seconds=batch.estimated_seconds,
            estimated_completion_at=(
                batch.estimated_completion_at.isoformat() if batch.estimated_completion_at else None
            ),
            status=batch.status,
            message=f"Started evaluation for {batch.total_count} applications",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/jobs/{job_id}/status", response_model=JobEvaluationStatusResponse)
async def get_job_evaluation_status(
    job_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get evaluation status for a job.

    Returns the latest evaluation batch status and progress.
    """
    # Check job exists and belongs to user's company
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if str(job.company_id) != current_user["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this job")

    service = AIResumeEvalService(db)
    status_data = await service.get_job_evaluation_status(job_id)

    return JobEvaluationStatusResponse(**status_data)


@router.get("/batches/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status_endpoint(
    batch_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get status and progress for a specific batch.
    """
    batch = await db.get(AIResumeEvalBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if str(batch.company_id) != current_user["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this batch")

    status_data = await get_batch_status(db, batch_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Batch not found")

    return BatchStatusResponse(**status_data)


@router.post("/batches/{batch_id}/cancel", response_model=CancelBatchResponse)
async def cancel_batch(
    batch_id: UUID,
    current_user: dict = Depends(require_role("admin", "recruiter")),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a pending or processing evaluation batch.

    All pending tasks will be marked as skipped.
    """
    batch = await db.get(AIResumeEvalBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if str(batch.company_id) != current_user["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this batch")

    service = AIResumeEvalService(db)
    success = await service.cancel_batch(batch_id)
    await db.commit()

    if success:
        return CancelBatchResponse(success=True, message="Batch cancelled successfully")
    else:
        return CancelBatchResponse(
            success=False,
            message="Batch is already complete or cancelled",
        )


@router.post("/batches/{batch_id}/retry-failed", response_model=RetryFailedResponse)
async def retry_failed_tasks(
    batch_id: UUID,
    current_user: dict = Depends(require_role("admin", "recruiter")),
    db: AsyncSession = Depends(get_db),
):
    """
    Retry all failed tasks in a batch.
    """
    batch = await db.get(AIResumeEvalBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if str(batch.company_id) != current_user["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this batch")

    service = AIResumeEvalService(db)
    count = await service.retry_failed_tasks(batch_id)

    # Queue the retried tasks
    if count > 0:
        pending_tasks = await service.scheduler.get_pending_tasks(batch_id, limit=count)
        task_ids = [task.id for task in pending_tasks]
        if task_ids:
            await queue_evaluation_tasks(task_ids, stagger_seconds=2)

    await db.commit()

    return RetryFailedResponse(
        success=True,
        retried_count=count,
        message=f"Queued {count} failed tasks for retry",
    )


@router.get(
    "/applications/{application_id}",
    response_model=EvaluationDetailResponse,
)
async def get_application_evaluation(
    application_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get evaluation results for a specific application.

    Returns:
        - data: Full AI evaluation result (pass-through from subtribe_ai)
        - meta: Backend context (application_id, candidate_name, job info, status)
    """
    from app.models.application import Application

    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if str(application.company_id) != current_user["company_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this application")

    service = AIResumeEvalService(db)
    result = await service.get_application_evaluation(application_id)

    if not result:
        raise HTTPException(status_code=404, detail="Application not found")

    return EvaluationDetailResponse(**result)


# =========================================================================
# Internal API Endpoints (for Cloud Tasks)
# =========================================================================


@router.post("/internal/process/{task_id}", response_model=ProcessTaskResponse)
async def process_task_internal(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Process a single evaluation task.

    This endpoint is called by Cloud Tasks.

    Note: In production, this should be protected by
    Cloud Tasks authentication headers.
    """
    # TODO: Add Cloud Tasks authentication verification
    # headers = request.headers
    # if not verify_cloud_tasks_request(headers):
    #     raise HTTPException(status_code=403, detail="Invalid Cloud Tasks request")

    service = AIResumeEvalService(db)
    result = await service.process_task(task_id)
    await db.commit()

    return ProcessTaskResponse(
        success=result.get("success", False),
        score=result.get("score"),
        tier=result.get("tier"),
        error=result.get("error"),
        error_code=result.get("error_code"),
        will_retry=result.get("will_retry"),
    )


@router.post("/internal/retry-stuck")
async def retry_stuck_tasks_internal(
    db: AsyncSession = Depends(get_db),
):
    """
    Process stuck tasks.

    This endpoint is called by Cloud Scheduler periodically.
    """
    service = AIResumeEvalService(db)

    # Process stuck tasks
    stuck_count = await service.process_stuck_tasks()

    # Process retry-scheduled tasks
    retry_count = await service.process_retry_scheduled_tasks()

    await db.commit()

    return {
        "success": True,
        "stuck_tasks_reset": stuck_count,
        "retry_tasks_reset": retry_count,
    }


@router.post("/internal/process-local")
async def process_local_tasks(
    max_tasks: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """
    Process pending evaluation tasks (development only).

    This endpoint processes evaluation tasks that are pending in the database.
    Used for local development when Cloud Tasks is not available.

    Args:
        max_tasks: Maximum number of tasks to process (default 10)
    """
    from sqlalchemy import select

    from app.models.ai_resume_eval_task import AIResumeEvalTask

    service = AIResumeEvalService(db)

    # Get pending tasks from DB
    stmt = (
        select(AIResumeEvalTask)
        .where(AIResumeEvalTask.status.in_(["pending", "queued", "retry_scheduled"]))
        .order_by(AIResumeEvalTask.created_at)
        .limit(max_tasks)
    )
    result = await db.execute(stmt)
    pending_tasks = result.scalars().all()

    results = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
    }

    for task in pending_tasks:
        results["processed"] += 1

        try:
            process_result = await service.process_task(task.id)
            await db.commit()

            if process_result.get("success"):
                results["succeeded"] += 1
                logger.info(
                    f"Processed task {task.id}: "
                    f"score={process_result.get('score')}, tier={process_result.get('tier')}"
                )
            else:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "task_id": str(task.id),
                        "error": process_result.get("error", "Unknown error"),
                    }
                )
        except Exception as e:
            await db.rollback()
            results["failed"] += 1
            results["errors"].append(
                {
                    "task_id": str(task.id),
                    "error": str(e),
                }
            )
            logger.exception(f"Failed to process task {task.id}: {e}")

    # Count remaining pending tasks
    count_stmt = select(AIResumeEvalTask).where(AIResumeEvalTask.status.in_(["pending", "queued"]))
    remaining_result = await db.execute(count_stmt)
    remaining_count = len(remaining_result.scalars().all())

    return {
        "success": True,
        "pending_remaining": remaining_count,
        **results,
    }


@router.get("/internal/debug-batch/{batch_id}")
async def debug_batch_tasks(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Debug endpoint to see all tasks in a batch.
    """
    from sqlalchemy import func, select

    from app.models.ai_resume_eval_task import AIResumeEvalTask

    # Get all tasks for this batch
    stmt = select(AIResumeEvalTask).where(AIResumeEvalTask.batch_id == batch_id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    # Count by status
    status_stmt = (
        select(AIResumeEvalTask.status, func.count(AIResumeEvalTask.id))
        .where(AIResumeEvalTask.batch_id == batch_id)
        .group_by(AIResumeEvalTask.status)
    )
    status_result = await db.execute(status_stmt)
    status_counts = dict(status_result.all())

    return {
        "batch_id": str(batch_id),
        "total_tasks": len(tasks),
        "status_counts": status_counts,
        "tasks": [
            {
                "id": str(t.id),
                "status": t.status,
                "attempt_count": t.attempt_count,
                "last_error": t.last_error,
                "application_id": str(t.application_id),
            }
            for t in tasks
        ],
    }
