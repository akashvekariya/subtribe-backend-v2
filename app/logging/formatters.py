"""Logging formatters for JSON and console output."""

import logging
from datetime import datetime, timezone

from pythonjsonlogger import jsonlogger

from app.logging.utils import format_source_location


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

        # Add source location (file:line:function) for debugging
        log_record["source"] = format_source_location(record)

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

        # Add source location (file:line:function)
        parts.append(f"[{format_source_location(record)}]")

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
