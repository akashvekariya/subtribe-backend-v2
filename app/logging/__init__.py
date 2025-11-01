"""Logging module - Provides structured logging for the application.

Public API:
- setup_logging(): Configure logging with formatters and suppressions
- LoggingMiddleware: Request/response logging middleware
- log_business_event(): Log business operations
- log_security_event(): Log auth/authz events
- log_performance_event(): Log performance metrics
- log_external_service_call(): Log external service calls
- log_database_event(): Log database operations
- mask_sensitive_data(): Mask sensitive data in logs

Usage:
    from app.logging import setup_logging, LoggingMiddleware
    from app.logging import log_business_event, log_security_event

See vibe-plan/logging.md for complete documentation.
"""

# Configuration
from app.logging.config import setup_logging

# Helper functions
from app.logging.helpers import (
    log_business_event,
    log_database_event,
    log_external_service_call,
    log_performance_event,
    log_security_event,
)

# Middleware
from app.logging.middleware import LoggingMiddleware

# Utilities
from app.logging.utils import mask_sensitive_data

# Re-export for backward compatibility
__all__ = [
    # Configuration
    "setup_logging",
    # Middleware
    "LoggingMiddleware",
    # Helpers
    "log_business_event",
    "log_security_event",
    "log_performance_event",
    "log_external_service_call",
    "log_database_event",
    # Utilities
    "mask_sensitive_data",
]
