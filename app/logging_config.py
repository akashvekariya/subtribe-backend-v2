"""Logging configuration module.

This module provides:
- Route-specific logging rules with pattern matching
- Status-code-based filtering (full vs metadata-only logs)
- Three logging modes: full, smart, minimal
- Sensitive data masking
- JSON and console formatters
- Cost optimization through sampling and compression

See vibe-plan/logging.md for complete documentation.
"""

import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from pythonjsonlogger import jsonlogger

# Sensitive fields to mask in logs (security)
SENSITIVE_FIELDS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "private_key",
    "credential",
    "authorization",
}

# Fields to keep (NOT masked)
KEEP_FIELDS = {
    "email",
    "phone",
    "phone_number",
    "first_name",
    "last_name",
    "name",
}


def mask_sensitive_data(data: Any, depth: int = 0) -> Any:
    """Recursively mask sensitive data in logs.

    Args:
        data: Data to mask (dict, list, or primitive)
        depth: Current recursion depth (prevents infinite recursion)

    Returns:
        Masked copy of data
    """
    if depth > 10:  # Prevent infinite recursion
        return "***MAX_DEPTH***"

    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            # Check if field should be masked
            should_mask = any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS)
            should_keep = any(keep in key_lower for keep in KEEP_FIELDS)
            if should_mask and not should_keep:
                masked[key] = "***REDACTED***"
                continue
            # Recursively mask nested structures
            masked[key] = mask_sensitive_data(value, depth + 1)
        return masked

    elif isinstance(data, (list, tuple)):
        return [mask_sensitive_data(item, depth + 1) for item in data]

    elif isinstance(data, str):
        # Don't mask string values unless they're field values (handled above)
        return data

    else:
        # Primitives (int, float, bool, None)
        return data


def matches_pattern(path: str, pattern: str) -> bool:
    """Check if path matches a wildcard pattern.

    Patterns:
    - /exact/path: Exact match only
    - /path/*: Matches single segment (e.g., /path/123)
    - /path/**: Matches multiple segments (e.g., /path/123/sub/deep)
    - /path/*/sub: Wildcard in middle

    Args:
        path: Request path (e.g., "/jobs/123/applications")
        pattern: Pattern with wildcards (e.g., "/jobs/*/applications")

    Returns:
        True if path matches pattern
    """
    if pattern == "*":
        return True  # Global wildcard

    # Escape special regex chars except * and /
    pattern_escaped = re.escape(pattern)

    # Replace wildcards with regex
    # /** matches any path segments
    pattern_escaped = pattern_escaped.replace(r"\*\*", ".*")
    # /* matches single path segment
    pattern_escaped = pattern_escaped.replace(r"\*", r"[^/]+")

    # Ensure full match (not partial)
    pattern_regex = f"^{pattern_escaped}$"

    return bool(re.match(pattern_regex, path))


# Route-specific logging rules
# Priority: Exact match > Specific wildcard > General wildcard > Default (*)
ROUTE_LOGGING_RULES = {
    # Default (applies to all routes unless overridden)
    "*": {
        "mode": None,  # Use global LOG_MODE
        "log_request_body": True,
        "log_response_body": True,
        "log_headers": False,  # Too verbose
        "log_on_error_only": False,
        "sample_rate": None,  # Use global sampling rate
    },
    # Health check (minimal logging, sampled)
    "/health": {
        "mode": "minimal",
        "log_request_body": False,
        "log_response_body": False,
        "sample_rate": 0.01,  # Log 1% only (reduces noise)
    },
    # Auth endpoints (don't log sensitive bodies)
    "/auth/login": {
        "log_request_body": False,  # Contains password
        "log_response_body": False,  # Contains tokens
    },
    "/auth/register": {
        "log_request_body": False,  # Contains password
        "log_response_body": False,  # Contains tokens
    },
    "/auth/refresh": {
        "log_request_body": False,  # Contains refresh token
        "log_response_body": False,  # Contains new tokens
    },
    # Public job listing (high traffic, sample in production)
    "/public/jobs": {
        "mode": "minimal",
        "log_request_body": False,
        "log_response_body": False,
        "sample_rate": 0.1,  # Log 10% (high traffic endpoint)
    },
    # Public job applications (always log, sensitive data)
    "/public/jobs/*/apply": {
        "mode": "full",  # Always log applications
        "log_request_body": True,  # Need form data for debugging
        "log_response_body": True,
        "log_on_error_only": False,
    },
    # Dashboard (always full logging for analytics)
    "/dashboard/**": {
        "mode": "full",
        "log_request_body": True,
        "log_response_body": True,
    },
    # Resume endpoints (log metadata, not file contents)
    "/applications/*/resume/**": {
        "log_request_body": False,  # Binary file data
        "log_response_body": False,  # Signed URLs
    },
}


def find_matching_rule(path: str) -> dict:
    """Find the most specific logging rule for a path.

    Priority:
    1. Exact match (/auth/login)
    2. Specific wildcards (/jobs/*/applications)
    3. General wildcards (/jobs/**)
    4. Default (*)

    Args:
        path: Request path (e.g., "/jobs/123/applications")

    Returns:
        Logging rule dict
    """
    # 1. Try exact match first
    if path in ROUTE_LOGGING_RULES:
        return ROUTE_LOGGING_RULES[path]

    # 2. Try wildcard patterns (sorted by specificity)
    # Sort patterns by: specificity (segment count), then by pattern length
    patterns = [
        (pattern, rule)
        for pattern, rule in ROUTE_LOGGING_RULES.items()
        if pattern != "*" and "*" in pattern
    ]

    # Sort by specificity (more segments = more specific)
    patterns.sort(
        key=lambda x: (
            -x[0].count("/"),  # More slashes = more specific
            -len(x[0]),  # Longer pattern = more specific
            x[0].count("*"),  # Fewer wildcards = more specific
        )
    )

    for pattern, rule in patterns:
        if matches_pattern(path, pattern):
            return rule

    # 3. Fall back to default
    return ROUTE_LOGGING_RULES["*"]


def determine_log_level(mode: str, status_code: int) -> str:
    """Determine what to log based on mode and status code.

    Modes:
    - full: Log everything (bodies + metadata)
    - smart: Log metadata for 2xx, full for 4xx/5xx
    - minimal: Log metadata only

    Args:
        mode: Logging mode (full/smart/minimal)
        status_code: HTTP response status code

    Returns:
        Log level: "full" or "metadata"
    """
    if mode == "full":
        return "full"

    if mode == "smart":
        # Success: metadata only (save 70% log size)
        if 200 <= status_code < 300:
            return "metadata"
        # Errors: full details (debugging needed)
        else:
            return "full"

    if mode == "minimal":
        return "metadata"

    # Unknown mode, default to full
    return "full"


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter for structured logging.

    Outputs logs in JSON format with ISO timestamps and structured fields.
    Used in production for GCP Cloud Logging integration.

    Example output:
    {
        "timestamp": "2025-11-01T10:23:45.123Z",
        "level": "INFO",
        "correlation_id": "abc-123",
        "message": "Request completed",
        "method": "POST",
        "path": "/jobs",
        "status_code": 200,
        "duration_ms": 145
    }
    """

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add ISO timestamp
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Add log level
        log_record["level"] = record.levelname

        # Add logger name (optional, for debugging)
        if record.name != "root":
            log_record["logger"] = record.name

        # Move message to top level
        if "message" in message_dict:
            log_record["message"] = message_dict["message"]


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for development.

    Outputs human-readable logs with colors for different log levels.
    Used in development for easy reading.

    Example output:
    2025-11-01 10:23:45 | INFO | correlation_id=abc-123 | POST /jobs | status=200 | duration=145ms
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        """Format log record with colors."""
        # Get color for log level
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Build log message
        parts = [
            f"{timestamp}",
            f"{color}{record.levelname}{reset}",
        ]

        # Add correlation ID if present
        if hasattr(record, "correlation_id") and record.correlation_id:
            parts.append(f"correlation_id={record.correlation_id}")

        # Add method and path if present
        if hasattr(record, "method") and hasattr(record, "path"):
            parts.append(f"{record.method} {record.path}")

        # Add status code if present
        if hasattr(record, "status_code"):
            parts.append(f"status={record.status_code}")

        # Add duration if present
        if hasattr(record, "duration_ms"):
            parts.append(f"duration={record.duration_ms}ms")

        # Add main message
        parts.append(record.getMessage())

        return " | ".join(parts)


def setup_logging(log_format: str = "json", log_level: str = "INFO"):
    """Setup logging configuration.

    Args:
        log_format: "json" for production, "console" for development
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create handler (stdout for Cloud Run compatibility)
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on format
    if log_format == "json":
        formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(message)s")
    else:  # console
        formatter = ColoredConsoleFormatter()

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
