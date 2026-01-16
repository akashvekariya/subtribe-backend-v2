"""
AI Resume Evaluation Worker.

Handles individual task execution - parsing resumes and
evaluating candidates against job frameworks.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_resume_eval_batch import AIResumeEvalBatch
from app.models.ai_resume_eval_task import AIResumeEvalTask
from app.models.application import Application
from app.models.job import Job
from app.services.evaluation.retry import (
    ClassifiedError,
    ErrorCode,
    calculate_next_retry_time,
    classify_error,
    should_retry,
)
from app.services.storage import storage_service

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF.

    Args:
        pdf_bytes: Raw PDF file bytes

    Returns:
        Extracted text from all pages
    """
    import fitz  # PyMuPDF

    text_parts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text()
            if text:
                text_parts.append(text)

    return "\n\n".join(text_parts)


class AIResumeEvalWorker:
    """
    Worker for executing AI resume evaluation tasks.

    Responsible for:
    - Processing individual evaluation tasks
    - Calling subtribe_ai for resume parsing and evaluation
    - Handling errors and updating task status
    - Updating application with results
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_task(self, task_id: UUID) -> dict[str, Any]:
        """
        Process a single evaluation task.

        Args:
            task_id: The task to process

        Returns:
            Dict with processing result
        """
        start_time = time.time()

        # Load task with related data
        task = await self._load_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"success": False, "error": "Task not found"}

        # Check if task should be processed
        if task.is_terminal:
            logger.info(f"Task {task_id} already in terminal state: {task.status}")
            return {"success": True, "skipped": True, "reason": "Already completed"}

        # Load application and job
        application = await self.db.get(Application, task.application_id)
        if not application:
            await self._mark_task_failed(task, "Application not found", ErrorCode.NOT_FOUND)
            return {"success": False, "error": "Application not found"}

        batch = await self.db.get(AIResumeEvalBatch, task.batch_id)
        if not batch:
            await self._mark_task_failed(task, "Batch not found", ErrorCode.NOT_FOUND)
            return {"success": False, "error": "Batch not found"}

        job = await self.db.get(Job, batch.job_id)
        if not job:
            await self._mark_task_failed(task, "Job not found", ErrorCode.NOT_FOUND)
            return {"success": False, "error": "Job not found"}

        if not job.evaluation_framework:
            await self._mark_task_failed(
                task, "Job has no evaluation framework", ErrorCode.VALIDATION_ERROR
            )
            return {"success": False, "error": "Job not calibrated"}

        # Check if resume is available
        if not application.resume_parsed_md and not application.resume_url:
            await self._mark_task_skipped(task, "No resume available")
            return {"success": True, "skipped": True, "reason": "No resume"}

        # Record attempt
        task.record_attempt()
        application.ai_resume_eval_status = "processing"
        await self.db.flush()

        try:
            # Execute evaluation
            result = await self._execute_evaluation(application, job)

            # Store results
            await self._store_results(application, task, result)

            elapsed = time.time() - start_time
            logger.info(
                f"Task {task_id} completed: score={result.get('final_score', 'N/A')} "
                f"tier={result.get('tier', 'N/A')} ({elapsed:.2f}s)"
            )

            return {
                "success": True,
                "score": result.get("final_score"),
                "tier": result.get("tier"),
                "elapsed_seconds": elapsed,
            }

        except Exception as e:
            return await self._handle_task_error(task, application, e)

    async def _load_task(self, task_id: UUID) -> AIResumeEvalTask | None:
        """Load task from database."""
        return await self.db.get(AIResumeEvalTask, task_id)

    async def _execute_evaluation(
        self,
        application: Application,
        job: Job,
    ) -> dict[str, Any]:
        """
        Execute the AI evaluation pipeline.

        Uses asyncio.to_thread() for blocking operations to avoid
        blocking the event loop and preventing other requests.

        Pipeline:
        1. If resume not parsed: Download PDF -> parse_resume() -> Save
        2. Evaluate candidate against framework

        Args:
            application: The application to evaluate
            job: The job with evaluation framework

        Returns:
            Evaluation result dict
        """
        # Import subtribe_ai functions
        try:
            from subtribe_ai import evaluate_candidate, parse_resume
        except ImportError as e:
            logger.error(f"Failed to import subtribe_ai: {e}")
            raise RuntimeError("subtribe_ai not available") from e

        # Step 1: Parse resume if not already done
        if not application.resume_parsed_json:
            if not application.resume_url:
                raise ValueError("No resume available for evaluation")

            logger.info(f"Step 1: Parsing resume for application {application.id}")

            # Download PDF from GCS (run in thread pool to avoid blocking)
            pdf_bytes = await asyncio.to_thread(
                storage_service.download_file, application.resume_url
            )

            try:
                # Use parse_resume() which handles all internal steps:
                # - Link extraction
                # - PDF to markdown (Gemini)
                # - Markdown to JSON (BAML)
                # - Post-processing
                parsed_result = await asyncio.to_thread(parse_resume, pdf_bytes)

                # Store both markdown and structured JSON - CHECKPOINT
                application.resume_parsed_md = parsed_result.get("markdown", "")
                application.resume_parsed_json = parsed_result
                await self.db.flush()

                logger.info(
                    f"Step 1 complete: Parsed and stored resume for application {application.id}"
                )

            except Exception as e:
                logger.error(f"Step 1 failed to parse resume: {e}")
                # Fallback to PyMuPDF text extraction for basic text
                try:
                    resume_text = await asyncio.to_thread(_extract_text_from_pdf, pdf_bytes)
                    if resume_text and resume_text.strip():
                        application.resume_parsed_md = resume_text
                        await self.db.flush()
                        logger.warning(
                            f"Fallback: Stored raw text for application {application.id}"
                        )
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                raise ValueError("Could not parse resume PDF") from e

        # Step 2: Evaluate candidate against framework
        parsed_resume = application.resume_parsed_json
        if not parsed_resume:
            raise ValueError("No parsed resume JSON available. Resume parsing may have failed.")

        logger.info(f"Step 2: Evaluating application {application.id} against framework")
        evaluation_result = await asyncio.to_thread(
            evaluate_candidate,
            parsed_resume,
            job.evaluation_framework,
        )

        return evaluation_result

    async def _store_results(
        self,
        application: Application,
        task: AIResumeEvalTask,
        result: dict[str, Any],
    ) -> None:
        """
        Store evaluation results in the application.

        Args:
            application: The application to update
            task: The task to mark complete
            result: The evaluation result from subtribe_ai.evaluate_candidate()

        Result structure:
            {
                "scores": {"final_score": 7.5, "tier": "good_match", ...},
                "manipulation_check": {"detected": false, ...},
                "blockers": [...],
                ...
            }
        """
        # Extract key fields from evaluation result
        scores = result.get("scores", {})
        final_score = scores.get("final_score")
        tier = scores.get("tier")

        # is_dealbreaker: True if there are any blockers
        blockers = result.get("blockers", [])
        is_dealbreaker = len(blockers) > 0 if blockers else False

        # is_flagged: True if manipulation was detected
        manipulation_check = result.get("manipulation_check", {})
        is_flagged = manipulation_check.get("detected", False) if manipulation_check else False

        # Update application
        application.evaluation_json = result
        application.evaluation_score = final_score
        application.evaluation_tier = tier
        application.is_dealbreaker = is_dealbreaker
        application.is_flagged = is_flagged
        application.evaluated_at = datetime.now(timezone.utc)
        application.ai_resume_eval_status = "completed"

        # Mark task completed
        task.mark_completed()

        await self.db.flush()

    async def _mark_task_failed(
        self,
        task: AIResumeEvalTask,
        error_message: str,
        error_code: ErrorCode,
    ) -> None:
        """Mark task as permanently failed."""
        task.mark_failed(error_message, error_code.value)

        # Update application status
        application = await self.db.get(Application, task.application_id)
        if application:
            application.ai_resume_eval_status = "failed"

        await self.db.flush()
        logger.warning(f"Task {task.id} failed permanently: {error_message}")

    async def _mark_task_skipped(
        self,
        task: AIResumeEvalTask,
        reason: str,
    ) -> None:
        """Mark task as skipped."""
        task.status = "skipped"
        task.last_error = reason
        task.completed_at = datetime.now(timezone.utc)

        # Update application status
        application = await self.db.get(Application, task.application_id)
        if application:
            application.ai_resume_eval_status = "skipped"

        await self.db.flush()
        logger.info(f"Task {task.id} skipped: {reason}")

    async def _handle_task_error(
        self,
        task: AIResumeEvalTask,
        application: Application,
        exception: Exception,
    ) -> dict[str, Any]:
        """
        Handle task processing error.

        Args:
            task: The failed task
            application: The application being processed
            exception: The exception that occurred

        Returns:
            Dict with error information
        """
        # Classify the error
        classified: ClassifiedError = classify_error(exception)

        logger.warning(
            f"Task {task.id} error (attempt {task.attempt_count}): "
            f"{classified.code.value} - {classified.message}"
        )

        # Check if we should retry
        if should_retry(classified.code, task.attempt_count, task.max_attempts):
            # Schedule retry
            retry_time = calculate_next_retry_time(classified.base_delay, task.attempt_count - 1)
            task.schedule_retry(
                classified.message,
                classified.code.value,
                retry_time,
            )
            application.ai_resume_eval_status = "pending"

            await self.db.flush()

            logger.info(
                f"Task {task.id} scheduled for retry at {retry_time} "
                f"(attempt {task.attempt_count}/{task.max_attempts})"
            )

            return {
                "success": False,
                "error": classified.message,
                "error_code": classified.code.value,
                "will_retry": True,
                "retry_at": retry_time.isoformat(),
            }
        else:
            # Mark as permanently failed
            await self._mark_task_failed(task, classified.message, classified.code)

            return {
                "success": False,
                "error": classified.message,
                "error_code": classified.code.value,
                "will_retry": False,
            }


async def process_evaluation_task(db: AsyncSession, task_id: UUID) -> dict[str, Any]:
    """
    Convenience function to process an evaluation task.

    Args:
        db: Database session
        task_id: Task ID to process

    Returns:
        Processing result
    """
    worker = AIResumeEvalWorker(db)
    return await worker.process_task(task_id)
