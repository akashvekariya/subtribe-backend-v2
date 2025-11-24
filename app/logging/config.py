"""Logging configuration and setup.

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
import sys

from app.logging.constants import THIRD_PARTY_INFO_LOGGERS, THIRD_PARTY_LOGGERS
from app.logging.formatters import ColoredConsoleFormatter, CustomJsonFormatter


def setup_logging(
    log_format: str = "json",
    log_level: str = "INFO",
    third_party_log_level: str = "WARNING",
):
    """Setup logging configuration with whitelist approach.

    Strategy:
    1. Set root logger to third_party_log_level (WARNING) - suppresses ALL libraries
    2. Whitelist our app loggers (app.*) to log_level (INFO/DEBUG)
    3. Explicitly suppress known verbose libraries for extra safety

    This ensures ANY new third-party library is automatically suppressed,
    preventing verbose logging from unexpected sources.

    Args:
        log_format: "json" for production, "console" for development
        log_level: Minimum log level for OUR app loggers (DEBUG, INFO, WARNING, ERROR)
        third_party_log_level: Log level for ALL third-party libraries (default: WARNING)
    """
    # ============================================================================
    # STEP 1: Configure root logger (affects ALL loggers by default)
    # ============================================================================
    # Set root logger to third_party_log_level (WARNING by default)
    # This automatically suppresses ALL third-party libraries
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, third_party_log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler (stdout for Cloud Run compatibility)
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on format
    if log_format == "json":
        formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(message)s")
    else:  # console
        formatter = ColoredConsoleFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # ============================================================================
    # STEP 2: Whitelist our application loggers
    # ============================================================================
    # Enable our app loggers to the configured log_level (INFO/DEBUG)
    # All loggers starting with "app." will log at this level
    app_logger = logging.getLogger("app")
    app_logger.setLevel(getattr(logging, log_level.upper()))

    # ============================================================================
    # STEP 3: Explicit suppressions for known problematic libraries
    # ============================================================================
    # Even though root logger suppresses everything, we explicitly set these
    # for extra safety and documentation purposes

    # Suppress all third-party loggers to WARNING
    for logger_name in THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Keep some loggers at INFO (e.g., uvicorn.error)
    for logger_name in THIRD_PARTY_INFO_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.INFO)
