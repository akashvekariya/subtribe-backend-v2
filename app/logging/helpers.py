"""Logging helper functions.

This module provides utility functions for manual logging in endpoints:
- log_business_event(): Log business-level events (e.g., job created)
- log_security_event(): Log security-related events (e.g., login failed)
- log_performance_event(): Log performance metrics
- log_external_service_call(): Log external service calls
- log_database_event(): Log database operations

See vibe-plan/logging.md for complete documentation.
"""

import logging
from typing import Any

from app.dependencies import get_correlation_id
from app.logging.utils import build_log_data, mask_sensitive_data

logger = logging.getLogger(__name__)


def _log_event(
    description: str,
    event_type: str,
    base_fields: dict[str, Any],
    optional_fields: dict[str, Any] | None = None,
    level: int = logging.INFO,
    mask_metadata: bool = True,
):
    """Base helper for logging events with common pattern.

    Args:
        description: Human-readable description
        event_type: Type of event (business, security, performance, etc.)
        base_fields: Required fields (event, etc.)
        optional_fields: Optional fields to include if not None
        level: Python log level (INFO, WARNING, ERROR)
        mask_metadata: Whether to mask sensitive data in metadata
    """
    # Mask metadata if present and masking enabled
    if (
        mask_metadata
        and optional_fields
        and "metadata" in optional_fields
        and optional_fields["metadata"] is not None
    ):
        optional_fields["metadata"] = mask_sensitive_data(optional_fields["metadata"])

    # Build log data with correlation ID
    log_data = build_log_data(
        correlation_id=get_correlation_id(),
        event_type=event_type,
        base_data={**base_fields, "description": description},
        optional_fields=optional_fields,
    )

    # Log at specified level
    logger.log(level, description, extra=log_data)


def log_business_event(
    event: str,
    description: str,
    user_id: str | None = None,
    company_id: str | None = None,
    resource_id: str | None = None,
    resource_type: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Log a business-level event.

    Use this for important business operations like:
    - Job created/updated/deleted
    - Application submitted
    - Candidate status changed
    - Company profile updated

    Args:
        event: Event name (e.g., "job_created", "application_submitted")
        description: Human-readable description
        user_id: User who triggered the event
        company_id: Company context
        resource_id: ID of affected resource (e.g., job_id, application_id)
        resource_type: Type of resource (e.g., "job", "application")
        metadata: Additional event-specific data

    Example:
        log_business_event(
            event="job_created",
            description="New job posting created",
            user_id=str(current_user["user_id"]),
            company_id=str(current_user["company_id"]),
            resource_id=str(job.id),
            resource_type="job",
            metadata={"title": job.title, "status": job.status}
        )
    """
    _log_event(
        description=description,
        event_type="business",
        base_fields={"event": event},
        optional_fields={
            "user_id": user_id,
            "company_id": company_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "metadata": metadata,
        },
        level=logging.INFO,
    )


def log_security_event(
    event: str,
    description: str,
    user_id: str | None = None,
    company_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Log a security-related event.

    Use this for authentication/authorization events like:
    - Login attempt (success/failure)
    - Registration
    - Token refresh
    - Unauthorized access attempt
    - Permission denied

    Args:
        event: Event name (e.g., "login_success", "login_failed", "unauthorized_access")
        description: Human-readable description
        user_id: User involved (if known)
        company_id: Company context (if known)
        ip_address: Client IP address
        user_agent: Client user agent
        success: Whether the operation succeeded
        reason: Failure reason (if applicable)
        metadata: Additional event-specific data

    Example:
        # Successful login
        log_security_event(
            event="login_success",
            description="User logged in successfully",
            user_id=str(user.id),
            company_id=str(user.company_id),
            ip_address=request.client.host,
            success=True
        )

        # Failed login
        log_security_event(
            event="login_failed",
            description="Login attempt failed",
            ip_address=request.client.host,
            success=False,
            reason="Invalid credentials",
            metadata={"email": email}
        )
    """
    _log_event(
        description=description,
        event_type="security",
        base_fields={"event": event, "success": success},
        optional_fields={
            "user_id": user_id,
            "company_id": company_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "reason": reason,
            "metadata": metadata,
        },
        level=logging.INFO if success else logging.WARNING,
    )


def log_performance_event(
    operation: str,
    duration_ms: int,
    success: bool = True,
    resource_count: int | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Log a performance-related event.

    Use this for tracking slow operations or performance metrics:
    - Database queries
    - External API calls
    - File uploads/downloads
    - Batch operations

    Args:
        operation: Operation name (e.g., "db_query", "gcs_upload", "api_call")
        duration_ms: Operation duration in milliseconds
        success: Whether the operation succeeded
        resource_count: Number of resources processed (if applicable)
        metadata: Additional operation-specific data

    Example:
        # Track database query
        start = time.time()
        results = await db.execute(query)
        duration_ms = int((time.time() - start) * 1000)

        log_performance_event(
            operation="db_query_applications",
            duration_ms=duration_ms,
            success=True,
            resource_count=len(results),
            metadata={"job_id": str(job_id)}
        )

        # Track slow operation
        if duration_ms > 1000:
            log_performance_event(
                operation="slow_query",
                duration_ms=duration_ms,
                metadata={"query": "SELECT applications..."}
            )
    """
    # Build description based on duration
    if duration_ms > 1000:
        description = f"Slow operation: {operation} took {duration_ms}ms"
        level = logging.WARNING
    else:
        description = f"Performance: {operation} took {duration_ms}ms"
        level = logging.INFO

    _log_event(
        description=description,
        event_type="performance",
        base_fields={"operation": operation, "duration_ms": duration_ms, "success": success},
        optional_fields={
            "resource_count": resource_count,
            "metadata": metadata,
        },
        level=level,
    )


def log_external_service_call(
    service: str,
    operation: str,
    duration_ms: int,
    success: bool = True,
    status_code: int | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Log an external service call.

    Use this for tracking calls to external services:
    - GCS operations
    - Supabase queries
    - Third-party APIs

    Args:
        service: Service name (e.g., "gcs", "supabase", "sendgrid")
        operation: Operation name (e.g., "upload", "query", "send_email")
        duration_ms: Operation duration in milliseconds
        success: Whether the operation succeeded
        status_code: HTTP status code (if applicable)
        error: Error message (if failed)
        metadata: Additional operation-specific data

    Example:
        log_external_service_call(
            service="gcs",
            operation="resume_upload",
            duration_ms=450,
            success=True,
            metadata={
                "bucket": bucket_name,
                "file_size": file_size,
                "application_id": str(application_id)
            }
        )
    """
    # Build description
    if success:
        description = f"External service call: {service}.{operation}"
        level = logging.INFO
    else:
        description = f"External service call failed: {service}.{operation} - {error}"
        level = logging.ERROR

    _log_event(
        description=description,
        event_type="external_service",
        base_fields={
            "service": service,
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
        },
        optional_fields={
            "status_code": status_code,
            "error": error,
            "metadata": metadata,
        },
        level=level,
    )


def log_database_event(
    operation: str,
    table: str,
    duration_ms: int,
    record_count: int | None = None,
    success: bool = True,
    error: str | None = None,
):
    """Log a database operation.

    Use this for tracking database operations:
    - SELECT queries
    - INSERT operations
    - UPDATE operations
    - DELETE operations
    - Transactions

    Args:
        operation: Operation type (e.g., "select", "insert", "update", "delete")
        table: Table name
        duration_ms: Operation duration in milliseconds
        record_count: Number of records affected
        success: Whether the operation succeeded
        error: Error message (if failed)

    Example:
        log_database_event(
            operation="select",
            table="applications",
            duration_ms=45,
            record_count=50,
            success=True
        )
    """
    # Build description
    if success:
        description = f"Database operation: {operation} on {table}"
        level = logging.INFO
    else:
        description = f"Database operation failed: {operation} on {table} - {error}"
        level = logging.ERROR

    _log_event(
        description=description,
        event_type="database",
        base_fields={
            "operation": operation,
            "table": table,
            "duration_ms": duration_ms,
            "success": success,
        },
        optional_fields={
            "record_count": record_count,
            "error": error,
        },
        level=level,
        mask_metadata=False,  # No metadata in database events
    )
