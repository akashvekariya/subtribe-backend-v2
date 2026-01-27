"""
AI Resume Evaluation Service Package.

This package provides automated resume-to-JD matching evaluation against job frameworks.
It evaluates candidate resumes against the Job Description using the calibrated evaluation framework.

Components:
    - config: Configuration and environment variables
    - scheduler: Batch creation and task queueing
    - worker: Task execution and AI evaluation
    - retry: Retry strategy and error classification
    - notifications: Email notifications on completion
    - service: Main orchestration service (primary entry point)

Usage:
    from app.services.evaluation import AIResumeEvalService

    # Start evaluation for a job
    service = AIResumeEvalService(db)
    batch = await service.start_job_evaluation(job_id, triggered_by=user_id)

    # Get evaluation status
    status = await service.get_batch_status(batch_id)

    # Process a single task (called by Cloud Tasks)
    result = await service.process_task(task_id)

Quick Start:
    from app.services.evaluation import (
        start_job_evaluation,
        process_evaluation_task,
        get_batch_status,
    )

    # Start evaluation
    batch = await start_job_evaluation(db, job_id, triggered_by=user_id)

    # Check status
    status = await get_batch_status(db, batch.id)

Architecture:
    See docs/ai_resume_eval_architecture.md for full documentation.

Scaling:
    Configuration is via environment variables. See config.py for details.
    To increase throughput, adjust AI_RESUME_EVAL_CONCURRENT_* and AI_RESUME_EVAL_GLOBAL_MAX_CONCURRENT.

Note:
    This is specifically for AI resume-to-JD matching. Other AI evaluation types
    (video interview evaluations, GitHub evaluations, etc.) will have their own services.
"""

from app.services.evaluation.auto_trigger import (
    trigger_evaluation_for_application,
    trigger_evaluation_for_job,
)
from app.services.evaluation.cloud_tasks import (
    CloudTasksManager,
    LocalTaskQueue,
    create_evaluation_cloud_task,
    delete_cloud_task,
    get_cloud_tasks_manager,
    get_local_queue,
    queue_evaluation_tasks,
)
from app.services.evaluation.config import (
    CLOUD_TASKS_CONFIG,
    CONCURRENCY_CONFIG,
    RETRY_CONFIG,
    TIMING_CONFIG,
    AIResumeEvalConfig,
    CompanyPlan,
    config,
)
from app.services.evaluation.notifications import (
    AIResumeEvalNotifier,
    notify_batch_completion,
)
from app.services.evaluation.retry import (
    ClassifiedError,
    ErrorCode,
    calculate_next_retry_time,
    calculate_retry_delay,
    classify_error,
    should_retry,
)
from app.services.evaluation.scheduler import AIResumeEvalScheduler
from app.services.evaluation.service import (
    AIResumeEvalService,
    get_batch_status,
    process_evaluation_task,
    start_job_evaluation,
)
from app.services.evaluation.worker import AIResumeEvalWorker

__all__ = [
    # Config
    "AIResumeEvalConfig",
    "CompanyPlan",
    "config",
    "RETRY_CONFIG",
    "CONCURRENCY_CONFIG",
    "TIMING_CONFIG",
    "CLOUD_TASKS_CONFIG",
    # Service (main entry point)
    "AIResumeEvalService",
    "start_job_evaluation",
    "process_evaluation_task",
    "get_batch_status",
    # Scheduler
    "AIResumeEvalScheduler",
    # Worker
    "AIResumeEvalWorker",
    # Retry
    "ErrorCode",
    "ClassifiedError",
    "classify_error",
    "calculate_retry_delay",
    "calculate_next_retry_time",
    "should_retry",
    # Notifications
    "AIResumeEvalNotifier",
    "notify_batch_completion",
    # Cloud Tasks
    "CloudTasksManager",
    "get_cloud_tasks_manager",
    "create_evaluation_cloud_task",
    "queue_evaluation_tasks",
    "delete_cloud_task",
    "LocalTaskQueue",
    "get_local_queue",
    # Auto-trigger
    "trigger_evaluation_for_application",
    "trigger_evaluation_for_job",
]
