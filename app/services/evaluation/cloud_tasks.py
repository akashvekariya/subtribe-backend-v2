"""
Cloud Tasks Integration for AI Resume Evaluation.

Handles creating and managing Google Cloud Tasks for
background processing of evaluation tasks.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.services.evaluation.config import CLOUD_TASKS_CONFIG

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cloud Tasks client (lazy loaded)
_tasks_client = None


def _get_tasks_client():
    """Get or create Cloud Tasks client."""
    global _tasks_client
    if _tasks_client is None:
        try:
            from google.cloud import tasks_v2

            _tasks_client = tasks_v2.CloudTasksClient()
        except ImportError:
            logger.warning(
                "google-cloud-tasks not installed. "
                "Cloud Tasks integration will be disabled."
            )
            return None
        except Exception as e:
            logger.error(f"Failed to create Cloud Tasks client: {e}")
            return None
    return _tasks_client


def _get_queue_path() -> str:
    """Get the full queue path."""
    from app.config import settings

    project = settings.gcp_project_id
    location = CLOUD_TASKS_CONFIG.location
    queue = CLOUD_TASKS_CONFIG.queue_name

    return f"projects/{project}/locations/{location}/queues/{queue}"


class CloudTasksManager:
    """
    Manager for Cloud Tasks operations.

    Handles creating, scheduling, and managing evaluation tasks
    in Google Cloud Tasks.
    """

    def __init__(self):
        self.client = _get_tasks_client()
        self.service_url = CLOUD_TASKS_CONFIG.service_url
        self.task_deadline = CLOUD_TASKS_CONFIG.task_deadline_seconds

    @property
    def is_available(self) -> bool:
        """Check if Cloud Tasks is available."""
        return self.client is not None

    async def create_evaluation_task(
        self,
        task_id: UUID,
        delay_seconds: int = 0,
    ) -> str | None:
        """
        Create a Cloud Task for processing an evaluation task.

        Args:
            task_id: The evaluation task ID to process
            delay_seconds: Optional delay before executing

        Returns:
            Cloud Task name if created, None if failed
        """
        if not self.is_available:
            logger.warning("Cloud Tasks not available, skipping task creation")
            return None

        try:
            from google.cloud import tasks_v2
            from google.protobuf import duration_pb2, timestamp_pb2

            queue_path = _get_queue_path()

            # Build the request URL
            url = f"{self.service_url}/internal/ai-resume-eval/process/{task_id}"

            # Create task payload
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": url,
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": json.dumps({"task_id": str(task_id)}).encode(),
                },
                "dispatch_deadline": duration_pb2.Duration(seconds=self.task_deadline),
            }

            # Add schedule time if delayed
            if delay_seconds > 0:
                schedule_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(schedule_time)
                task["schedule_time"] = timestamp

            # Create the task
            request = tasks_v2.CreateTaskRequest(
                parent=queue_path,
                task=task,
            )

            response = self.client.create_task(request=request)
            task_name = response.name

            logger.info(
                f"Created Cloud Task for evaluation task {task_id}: {task_name}"
                + (f" (delayed {delay_seconds}s)" if delay_seconds > 0 else "")
            )

            return task_name

        except Exception as e:
            logger.error(f"Failed to create Cloud Task for {task_id}: {e}")
            return None

    async def delete_task(self, task_name: str) -> bool:
        """
        Delete a Cloud Task.

        Args:
            task_name: Full task name to delete

        Returns:
            True if deleted, False otherwise
        """
        if not self.is_available:
            return False

        try:
            from google.cloud import tasks_v2

            request = tasks_v2.DeleteTaskRequest(name=task_name)
            self.client.delete_task(request=request)

            logger.info(f"Deleted Cloud Task: {task_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete Cloud Task {task_name}: {e}")
            return False

    async def queue_batch_tasks(
        self,
        task_ids: list[UUID],
        stagger_seconds: int = 2,
    ) -> dict[str, Any]:
        """
        Queue multiple tasks with staggered execution.

        Args:
            task_ids: List of evaluation task IDs
            stagger_seconds: Seconds between each task

        Returns:
            Dict with queuing results
        """
        results = {
            "total": len(task_ids),
            "queued": 0,
            "failed": 0,
            "task_names": [],
        }

        for i, task_id in enumerate(task_ids):
            delay = i * stagger_seconds
            task_name = await self.create_evaluation_task(task_id, delay)

            if task_name:
                results["queued"] += 1
                results["task_names"].append(task_name)
            else:
                results["failed"] += 1

        logger.info(
            f"Queued {results['queued']}/{results['total']} tasks "
            f"(stagger: {stagger_seconds}s)"
        )

        return results


# Singleton instance
_manager: CloudTasksManager | None = None


def get_cloud_tasks_manager() -> CloudTasksManager:
    """Get the Cloud Tasks manager singleton."""
    global _manager
    if _manager is None:
        _manager = CloudTasksManager()
    return _manager


# =========================================================================
# Convenience Functions
# =========================================================================


async def create_evaluation_cloud_task(
    task_id: UUID,
    delay_seconds: int = 0,
) -> str | None:
    """Create a Cloud Task for an evaluation task."""
    manager = get_cloud_tasks_manager()
    return await manager.create_evaluation_task(task_id, delay_seconds)


async def queue_evaluation_tasks(
    task_ids: list[UUID],
    stagger_seconds: int = 2,
) -> dict[str, Any]:
    """Queue multiple evaluation tasks with staggered execution."""
    manager = get_cloud_tasks_manager()
    return await manager.queue_batch_tasks(task_ids, stagger_seconds)


async def delete_cloud_task(task_name: str) -> bool:
    """Delete a Cloud Task by name."""
    manager = get_cloud_tasks_manager()
    return await manager.delete_task(task_name)


# =========================================================================
# Local Development Fallback
# =========================================================================


class LocalTaskQueue:
    """
    Local task queue for development without Cloud Tasks.

    This allows testing the evaluation system locally by
    processing tasks synchronously or via a simple queue.
    """

    def __init__(self):
        self.queue: list[UUID] = []

    def add(self, task_id: UUID, delay_seconds: int = 0) -> str:
        """Add a task to the local queue."""
        self.queue.append(task_id)
        task_name = f"local-task-{task_id}"
        logger.info(f"Added to local queue: {task_name}")
        return task_name

    def pop(self) -> UUID | None:
        """Pop the next task from the queue."""
        if self.queue:
            return self.queue.pop(0)
        return None

    def clear(self) -> None:
        """Clear the queue."""
        self.queue.clear()


# Local queue for development
_local_queue: LocalTaskQueue | None = None


def get_local_queue() -> LocalTaskQueue:
    """Get the local task queue for development."""
    global _local_queue
    if _local_queue is None:
        _local_queue = LocalTaskQueue()
    return _local_queue
