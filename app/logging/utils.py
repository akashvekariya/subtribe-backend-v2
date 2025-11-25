"""Logging utility functions."""

import logging
import re
from typing import Any

from app.logging.constants import KEEP_FIELDS, SENSITIVE_FIELDS


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


def find_matching_rule(path: str, rules: dict) -> dict:
    """Find the most specific logging rule for a path.

    Priority:
    1. Exact match (/auth/login)
    2. Specific wildcards (/jobs/*/applications)
    3. General wildcards (/jobs/**)
    4. Default (*)

    Args:
        path: Request path (e.g., "/jobs/123/applications")
        rules: Route logging rules dict

    Returns:
        Logging rule dict
    """
    # 1. Try exact match first
    if path in rules:
        return rules[path]

    # 2. Try wildcard patterns (sorted by specificity)
    # Sort patterns by: specificity (segment count), then by pattern length
    patterns = [
        (pattern, rule) for pattern, rule in rules.items() if pattern != "*" and "*" in pattern
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
    return rules["*"]


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


def format_source_location(record: logging.LogRecord) -> str:
    """Format source location from log record.

    Args:
        record: Python logging LogRecord

    Returns:
        Formatted source location string (file:line:function)
    """
    return f"{record.pathname}:{record.lineno}:{record.funcName}"


def build_log_data(
    correlation_id: str | None,
    event_type: str,
    base_data: dict[str, Any],
    optional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build log data dictionary with optional fields.

    Args:
        correlation_id: Request correlation ID
        event_type: Type of event (business, security, performance, etc.)
        base_data: Required fields (event, description, etc.)
        optional_fields: Optional fields to include if not None

    Returns:
        Complete log data dictionary
    """
    log_data = {
        "correlation_id": correlation_id,
        "event_type": event_type,
        **base_data,
    }

    if optional_fields:
        # Only include non-None values
        log_data.update({k: v for k, v in optional_fields.items() if v is not None})

    return log_data


def parse_json_body(
    body_bytes: bytes | None,
    content_type: str | None,
) -> dict | None:
    """Parse JSON body from bytes.

    Args:
        body_bytes: Raw body bytes
        content_type: Content-Type header value

    Returns:
        Parsed JSON dict or None if not JSON/empty/invalid
    """
    try:
        # Check content type
        if not content_type or "application/json" not in content_type:
            return None

        # Check if body is empty
        if not body_bytes:
            return None

        # Parse JSON
        import json

        return json.loads(body_bytes)

    except Exception:
        # If parsing fails, don't log body
        return None
