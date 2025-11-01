"""Logging helper functions.

This module provides utility functions for manual logging in endpoints:
- get_correlation_id(): Get current request correlation ID
- log_business_event(): Log business-level events (e.g., job created)
- log_security_event(): Log security-related events (e.g., login failed)
- log_performance_event(): Log performance metrics
- mask_sensitive_data(): Mask sensitive fields in logs

See vibe-plan/logging.md for complete documentation.
"""

import logging
from typing import Any

from app.dependencies import get_correlation_id
from app.logging_config import mask_sensitive_data as _mask_sensitive_data

logger = logging.getLogger(__name__)


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
    log_data = {
        "correlation_id": get_correlation_id(),
        "event_type": "business",
        "event": event,
        "description": description,
    }

    if user_id:
        log_data["user_id"] = user_id
    if company_id:
        log_data["company_id"] = company_id
    if resource_id:
        log_data["resource_id"] = resource_id
    if resource_type:
        log_data["resource_type"] = resource_type
    if metadata:
        log_data["metadata"] = _mask_sensitive_data(metadata)

    logger.info(description, extra=log_data)


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
    log_data = {
        "correlation_id": get_correlation_id(),
        "event_type": "security",
        "event": event,
        "description": description,
        "success": success,
    }

    if user_id:
        log_data["user_id"] = user_id
    if company_id:
        log_data["company_id"] = company_id
    if ip_address:
        log_data["ip_address"] = ip_address
    if user_agent:
        log_data["user_agent"] = user_agent
    if reason:
        log_data["reason"] = reason
    if metadata:
        log_data["metadata"] = _mask_sensitive_data(metadata)

    # Log as warning for failures, info for success
    if success:
        logger.info(description, extra=log_data)
    else:
        logger.warning(description, extra=log_data)


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
    log_data = {
        "correlation_id": get_correlation_id(),
        "event_type": "performance",
        "operation": operation,
        "duration_ms": duration_ms,
        "success": success,
    }

    if resource_count is not None:
        log_data["resource_count"] = resource_count
    if metadata:
        log_data["metadata"] = _mask_sensitive_data(metadata)

    # Log as warning if slow (> 1 second)
    if duration_ms > 1000:
        logger.warning(
            f"Slow operation: {operation} took {duration_ms}ms",
            extra=log_data,
        )
    else:
        logger.info(
            f"Performance: {operation} took {duration_ms}ms",
            extra=log_data,
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
    log_data = {
        "correlation_id": get_correlation_id(),
        "event_type": "external_service",
        "service": service,
        "operation": operation,
        "duration_ms": duration_ms,
        "success": success,
    }

    if status_code:
        log_data["status_code"] = status_code
    if error:
        log_data["error"] = error
    if metadata:
        log_data["metadata"] = _mask_sensitive_data(metadata)

    if success:
        logger.info(
            f"External service call: {service}.{operation}",
            extra=log_data,
        )
    else:
        logger.error(
            f"External service call failed: {service}.{operation} - {error}",
            extra=log_data,
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
    log_data = {
        "correlation_id": get_correlation_id(),
        "event_type": "database",
        "operation": operation,
        "table": table,
        "duration_ms": duration_ms,
        "success": success,
    }

    if record_count is not None:
        log_data["record_count"] = record_count
    if error:
        log_data["error"] = error

    if success:
        logger.info(
            f"Database operation: {operation} on {table}",
            extra=log_data,
        )
    else:
        logger.error(
            f"Database operation failed: {operation} on {table} - {error}",
            extra=log_data,
        )


def mask_sensitive_data(data: Any) -> Any:
    """Mask sensitive data in logs.

    Re-exports mask_sensitive_data from logging_config for convenience.

    Args:
        data: Data to mask (dict, list, or primitive)

    Returns:
        Masked copy of data
    """
    return _mask_sensitive_data(data)
