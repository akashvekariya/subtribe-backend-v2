"""Cloud Tasks integration for scheduling email sends."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudTasksScheduler:
    """Scheduler for creating Cloud Tasks to send emails at specific times.

    Cloud Tasks will call our internal API endpoint to actually send the email
    when the scheduled time arrives.
    """

    def __init__(self):
        """Initialize Cloud Tasks client."""
        self.project_id = settings.gcs_project_id
        self.location = settings.gcp_cloud_tasks_location
        self.queue_name = settings.gcp_cloud_tasks_queue

        # Lazy import to avoid requiring google-cloud-tasks when using stub
        try:
            from google.cloud import tasks_v2

            self.client = tasks_v2.CloudTasksClient()
            self.queue_path = self.client.queue_path(
                self.project_id, self.location, self.queue_name
            )
        except ImportError:
            logger.warning(
                "google-cloud-tasks not installed. Cloud Tasks scheduling disabled. "
                "Install with: pip install google-cloud-tasks"
            )
            self.client = None
            self.queue_path = None
        except Exception as e:
            logger.warning(
                f"Failed to initialize Cloud Tasks client: {str(e)}. "
                f"Cloud Tasks scheduling disabled."
            )
            self.client = None
            self.queue_path = None

    def create_email_task(
        self,
        scheduled_email_id: UUID,
        scheduled_for: datetime,
        target_url: str,
    ) -> str | None:
        """Create a Cloud Task to send an email at the scheduled time.

        Args:
            scheduled_email_id: ID of the ScheduledEmail record
            scheduled_for: When to send the email (UTC datetime)
            target_url: Full URL of the internal API endpoint to call

        Returns:
            Task name if created successfully, None otherwise
        """
        if not self.client or not self.queue_path:
            logger.warning(
                "⚠️  Cloud Tasks client not initialized. Email will need to be sent manually."
            )
            return None

        try:
            from google.cloud import tasks_v2
            from google.protobuf import timestamp_pb2

            # Build task payload
            payload = {
                "scheduled_email_id": str(scheduled_email_id),
            }

            # Convert scheduled_for to protobuf Timestamp
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(scheduled_for)

            # Create HTTP POST task
            task = tasks_v2.Task(
                http_request=tasks_v2.HttpRequest(
                    http_method=tasks_v2.HttpMethod.POST,
                    url=target_url,
                    headers={
                        "Content-Type": "application/json",
                    },
                    body=json.dumps(payload).encode(),
                ),
                schedule_time=timestamp,
            )

            # Create the task
            response = self.client.create_task(request={"parent": self.queue_path, "task": task})

            task_name = response.name
            logger.info(
                f"✅ Created Cloud Task: {task_name} "
                f"for email {scheduled_email_id} "
                f"at {scheduled_for.isoformat()}"
            )

            return task_name

        except Exception as e:
            logger.error(f"❌ Failed to create Cloud Task for email {scheduled_email_id}: {str(e)}")
            return None

    def delete_task(self, task_name: str) -> bool:
        """Delete a Cloud Task.

        Args:
            task_name: Full task name returned by create_email_task

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.client:
            logger.warning("Cloud Tasks client not initialized")
            return False

        try:
            self.client.delete_task(name=task_name)
            logger.info(f"🗑️  Deleted Cloud Task: {task_name}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete Cloud Task {task_name}: {str(e)}")
            return False


# Global instance
cloud_tasks_scheduler = CloudTasksScheduler()
