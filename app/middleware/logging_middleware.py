"""Logging middleware for request/response tracking.

This middleware:
- Generates/extracts correlation IDs for request tracking
- Captures request and response metadata and bodies
- Applies route-specific logging rules with pattern matching
- Logs single consolidated entry per request
- Adds X-Request-ID header to responses
- Implements sampling and status-code-based filtering

See vibe-plan/logging.md for complete documentation.
"""

import logging
import random
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from app.dependencies import set_correlation_id
from app.logging_config import (
    determine_log_level,
    find_matching_rule,
    mask_sensitive_data,
)

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging.

    Features:
    - Correlation ID tracking
    - Route-specific rules
    - Status-code-based filtering
    - Sampling support
    - Sensitive data masking
    """

    def __init__(self, app, log_mode: str = "smart", sampling_rate: float = 1.0):
        """Initialize logging middleware.

        Args:
            app: FastAPI application
            log_mode: Logging mode (full/smart/minimal)
            sampling_rate: Fraction of requests to log (0.0-1.0)
        """
        super().__init__(app)
        self.log_mode = log_mode
        self.sampling_rate = sampling_rate

    async def dispatch(self, request: Request, call_next):
        """Process request and log consolidated entry.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint handler

        Returns:
            Response with X-Request-ID header
        """
        # 1. Generate/extract correlation ID
        correlation_id = self._get_or_create_correlation_id(request)
        set_correlation_id(correlation_id)

        # 2. Start timer
        start_time = time.time()

        # 3. Find matching logging rule for this path
        path = request.url.path
        rule = find_matching_rule(path)

        # 4. Determine if we should log (sampling)
        should_log = self._should_log_request(rule)

        # 5. Capture request data
        request_data = await self._capture_request(request, rule)

        # 6. Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log exception
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_exception(
                correlation_id=correlation_id,
                request_data=request_data,
                duration_ms=duration_ms,
                exception=exc,
            )
            raise  # Re-raise to be handled by exception handlers

        # 7. Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # 8. Capture response data
        response_data = await self._capture_response(response, rule)

        # 9. Determine effective log mode (rule can override global)
        effective_mode = rule.get("mode") or self.log_mode

        # 10. Determine log level based on status code
        status_code = response.status_code
        log_level = determine_log_level(effective_mode, status_code)

        # 11. Log consolidated entry (if sampling allows)
        # Always log errors, even if sampling would skip
        if should_log or status_code >= 400:
            self._log_request_response(
                correlation_id=correlation_id,
                request_data=request_data,
                response_data=response_data,
                duration_ms=duration_ms,
                status_code=status_code,
                log_level=log_level,
                rule=rule,
            )

        # 12. Add correlation ID to response headers
        response.headers["X-Request-ID"] = correlation_id

        return response

    def _get_or_create_correlation_id(self, request: Request) -> str:
        """Get correlation ID from header or generate new one.

        Checks for X-Request-ID header. If not present, generates UUID.

        Args:
            request: Incoming request

        Returns:
            Correlation ID (UUID string)
        """
        # Check if client provided correlation ID
        correlation_id = request.headers.get("X-Request-ID")

        if correlation_id:
            return correlation_id

        # Generate new UUID
        return str(uuid.uuid4())

    def _should_log_request(self, rule: dict) -> bool:
        """Determine if request should be logged based on sampling.

        Args:
            rule: Route-specific logging rule

        Returns:
            True if request should be logged
        """
        # Check log_on_error_only flag
        if rule.get("log_on_error_only"):
            return False  # Will log later if error occurs

        # Get sampling rate (rule-specific or global)
        sample_rate = rule.get("sample_rate")
        if sample_rate is None:
            sample_rate = self.sampling_rate

        # Sample based on rate
        if sample_rate >= 1.0:
            return True  # Log all

        if sample_rate <= 0.0:
            return False  # Log none (except errors)

        # Random sampling
        return random.random() < sample_rate

    async def _capture_request(self, request: Request, rule: dict) -> dict:
        """Capture request metadata and body.

        Args:
            request: Incoming request
            rule: Route-specific logging rule

        Returns:
            Dict with request data
        """
        data = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params) if request.query_params else None,
        }

        # Add headers if configured
        if rule.get("log_headers"):
            data["headers"] = dict(request.headers)

        # Add user context if authenticated
        user_context = self._get_user_context(request)
        if user_context:
            data.update(user_context)

        # Add request body if configured
        if rule.get("log_request_body"):
            body = await self._read_request_body(request)
            if body:
                data["request_body"] = mask_sensitive_data(body)

        return data

    async def _capture_response(self, response: Response, rule: dict) -> dict:
        """Capture response metadata and body.

        Args:
            response: Outgoing response
            rule: Route-specific logging rule

        Returns:
            Dict with response data
        """
        data = {
            "status_code": response.status_code,
        }

        # Add headers if configured
        if rule.get("log_headers"):
            data["headers"] = dict(response.headers)

        # Add response body if configured
        if rule.get("log_response_body"):
            body = await self._read_response_body(response)
            if body:
                data["response_body"] = mask_sensitive_data(body)

        return data

    def _get_user_context(self, request: Request) -> dict | None:
        """Extract user context from request state.

        User context is added by get_current_user dependency.

        Args:
            request: Incoming request

        Returns:
            Dict with user_id, company_id, role, or None if unauthenticated
        """
        # Check if user is authenticated (added by get_current_user)
        if hasattr(request.state, "current_user"):
            user = request.state.current_user
            return {
                "user_id": user.get("user_id"),
                "company_id": user.get("company_id"),
                "role": user.get("role"),
            }
        return None

    async def _read_request_body(self, request: Request) -> dict | None:
        """Read and parse request body.

        Attempts to parse as JSON. Returns None if not JSON or empty.

        Args:
            request: Incoming request

        Returns:
            Parsed JSON dict or None
        """
        try:
            # Check content type
            content_type = request.headers.get("content-type", "")
            if "application/json" not in content_type:
                return None

            # Read body
            body_bytes = await request.body()
            if not body_bytes:
                return None

            # Parse JSON
            import json

            return json.loads(body_bytes)

        except Exception:
            # If parsing fails, don't log body
            return None

    async def _read_response_body(self, response: Response) -> dict | None:
        """Read and parse response body.

        Attempts to parse as JSON. Returns None if not JSON or empty.
        Note: This only works for non-streaming responses.

        Args:
            response: Outgoing response

        Returns:
            Parsed JSON dict or None
        """
        try:
            # Skip streaming responses
            if isinstance(response, StreamingResponse):
                return None

            # Check content type
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return None

            # Read body
            if hasattr(response, "body"):
                body_bytes = response.body
                if not body_bytes:
                    return None

                # Parse JSON
                import json

                return json.loads(body_bytes)

        except Exception:
            # If parsing fails, don't log body
            return None

        return None

    def _log_request_response(
        self,
        correlation_id: str,
        request_data: dict,
        response_data: dict,
        duration_ms: int,
        status_code: int,
        log_level: str,
        rule: dict,
    ):
        """Log single consolidated entry for request/response.

        Args:
            correlation_id: Request correlation ID
            request_data: Request metadata and body
            response_data: Response metadata and body
            duration_ms: Request duration in milliseconds
            status_code: HTTP status code
            log_level: "full" or "metadata"
            rule: Route-specific logging rule
        """
        # Build log entry
        log_entry = {
            "correlation_id": correlation_id,
            "duration_ms": duration_ms,
            **request_data,  # method, path, user context
            **response_data,  # status_code
        }

        # Add bodies if log_level is "full"
        if log_level == "metadata":
            # Remove bodies for metadata-only logging
            log_entry.pop("request_body", None)
            log_entry.pop("response_body", None)

        # Determine Python log level
        if status_code >= 500:
            python_log_level = logging.ERROR
        elif status_code >= 400:
            python_log_level = logging.WARNING
        else:
            python_log_level = logging.INFO

        # Log consolidated entry
        logger.log(
            python_log_level,
            f"Request completed: {request_data['method']} {request_data['path']}",
            extra=log_entry,
        )

    def _log_exception(
        self,
        correlation_id: str,
        request_data: dict,
        duration_ms: int,
        exception: Exception,
    ):
        """Log exception that occurred during request processing.

        Args:
            correlation_id: Request correlation ID
            request_data: Request metadata and body
            duration_ms: Request duration before exception
            exception: Exception that occurred
        """
        log_entry = {
            "correlation_id": correlation_id,
            "duration_ms": duration_ms,
            **request_data,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
        }

        logger.error(
            f"Request failed: {request_data['method']} {request_data['path']}",
            extra=log_entry,
            exc_info=True,  # Include traceback
        )
