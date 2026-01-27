"""
AI Resume Evaluation Retry Strategy.

Handles error classification and exponential backoff calculations
for the AI resume evaluation system.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

from app.services.evaluation.config import RETRY_CONFIG

if TYPE_CHECKING:
    pass


class ErrorCode(str, Enum):
    """Error codes for AI resume evaluation failures."""

    RATE_LIMIT = "rate_limit"  # 429 errors
    TIMEOUT = "timeout"  # Request timeout
    API_ERROR = "api_error"  # 5xx errors
    PARSE_ERROR = "parse_error"  # Invalid response
    AUTH_ERROR = "auth_error"  # 401/403 errors (not retryable)
    VALIDATION_ERROR = "validation_error"  # Invalid input (not retryable)
    NOT_FOUND = "not_found"  # Resource not found (not retryable)
    UNKNOWN = "unknown"  # Unclassified errors


# Non-retryable error codes
NON_RETRYABLE_ERRORS = {
    ErrorCode.AUTH_ERROR,
    ErrorCode.VALIDATION_ERROR,
    ErrorCode.NOT_FOUND,
}


@dataclass
class ClassifiedError:
    """Result of error classification."""

    code: ErrorCode
    message: str
    is_retryable: bool
    base_delay: int  # seconds


def classify_error(exception: Exception) -> ClassifiedError:
    """
    Classify an exception into an error code with retry information.

    Args:
        exception: The exception to classify

    Returns:
        ClassifiedError with code, message, retryability, and base delay
    """
    error_message = str(exception)
    error_type = type(exception).__name__

    # Check for HTTP status codes in error message
    if "429" in error_message or "rate limit" in error_message.lower():
        return ClassifiedError(
            code=ErrorCode.RATE_LIMIT,
            message=f"Rate limited: {error_message}",
            is_retryable=True,
            base_delay=RETRY_CONFIG.rate_limit_delay,
        )

    if "timeout" in error_message.lower() or "timed out" in error_message.lower():
        return ClassifiedError(
            code=ErrorCode.TIMEOUT,
            message=f"Timeout: {error_message}",
            is_retryable=True,
            base_delay=RETRY_CONFIG.timeout_delay,
        )

    if any(code in error_message for code in ["500", "502", "503", "504"]):
        return ClassifiedError(
            code=ErrorCode.API_ERROR,
            message=f"API error: {error_message}",
            is_retryable=True,
            base_delay=RETRY_CONFIG.api_error_delay,
        )

    if "401" in error_message or "403" in error_message or "unauthorized" in error_message.lower():
        return ClassifiedError(
            code=ErrorCode.AUTH_ERROR,
            message=f"Authentication error: {error_message}",
            is_retryable=False,
            base_delay=0,
        )

    if "404" in error_message or "not found" in error_message.lower():
        return ClassifiedError(
            code=ErrorCode.NOT_FOUND,
            message=f"Not found: {error_message}",
            is_retryable=False,
            base_delay=0,
        )

    if "validation" in error_message.lower() or "invalid" in error_message.lower():
        # Check if it's a parse error (retryable) or validation error (not retryable)
        if "json" in error_message.lower() or "parse" in error_message.lower():
            return ClassifiedError(
                code=ErrorCode.PARSE_ERROR,
                message=f"Parse error: {error_message}",
                is_retryable=True,
                base_delay=RETRY_CONFIG.parse_error_delay,
            )
        return ClassifiedError(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Validation error: {error_message}",
            is_retryable=False,
            base_delay=0,
        )

    # Default to unknown (retryable with base delay)
    return ClassifiedError(
        code=ErrorCode.UNKNOWN,
        message=f"{error_type}: {error_message}",
        is_retryable=True,
        base_delay=RETRY_CONFIG.base_retry_delay,
    )


def calculate_retry_delay(base_delay: int, attempt: int) -> int:
    """
    Calculate retry delay with exponential backoff and jitter.

    Formula: delay = min(base_delay * 2^attempt + jitter, max_delay)

    Args:
        base_delay: Base delay in seconds
        attempt: Current attempt number (0-indexed)

    Returns:
        Delay in seconds
    """
    # Exponential backoff
    delay = base_delay * (2**attempt)

    # Add jitter (±20%)
    jitter_range = delay * RETRY_CONFIG.jitter_percent
    jitter = random.uniform(-jitter_range, jitter_range)
    delay = delay + jitter

    # Cap at max delay
    delay = min(delay, RETRY_CONFIG.max_retry_delay)

    return int(delay)


def calculate_next_retry_time(base_delay: int, attempt: int) -> datetime:
    """
    Calculate the next retry time.

    Args:
        base_delay: Base delay in seconds
        attempt: Current attempt number

    Returns:
        Datetime for next retry
    """
    delay = calculate_retry_delay(base_delay, attempt)
    return datetime.now(timezone.utc) + timedelta(seconds=delay)


def should_retry(error_code: ErrorCode, attempt_count: int, max_attempts: int) -> bool:
    """
    Determine if a task should be retried.

    Args:
        error_code: The classified error code
        attempt_count: Current attempt count
        max_attempts: Maximum allowed attempts

    Returns:
        True if should retry, False otherwise
    """
    if error_code in NON_RETRYABLE_ERRORS:
        return False

    return attempt_count < max_attempts


def get_error_summary(error_code: ErrorCode) -> str:
    """
    Get a human-readable summary of the error code.

    Args:
        error_code: The error code

    Returns:
        Human-readable description
    """
    summaries = {
        ErrorCode.RATE_LIMIT: "API rate limit exceeded. Will retry after cooldown.",
        ErrorCode.TIMEOUT: "Request timed out. Will retry.",
        ErrorCode.API_ERROR: "API returned server error. Will retry.",
        ErrorCode.PARSE_ERROR: "Failed to parse response. Will retry.",
        ErrorCode.AUTH_ERROR: "Authentication failed. Cannot retry.",
        ErrorCode.VALIDATION_ERROR: "Invalid input data. Cannot retry.",
        ErrorCode.NOT_FOUND: "Resource not found. Cannot retry.",
        ErrorCode.UNKNOWN: "Unknown error occurred. Will retry.",
    }
    return summaries.get(error_code, "Unknown error")
