"""Logging constants and configuration."""

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

# Third-party loggers to suppress (set to WARNING level)
THIRD_PARTY_LOGGERS = [
    # Database & ORM (extremely verbose with query details)
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "sqlalchemy.dialects",
    "sqlalchemy.orm",
    # Web Server (duplicate access logs)
    "uvicorn",
    "uvicorn.access",
    # HTTP Clients (verbose request/response details)
    "httpx",
    "httpcore",
    "urllib3",
    # Cloud Services (auth flows, API calls)
    "google",
    "google.auth",
    "google.cloud",
    # Framework Internals
    "fastapi",
    "starlette",
    # System
    "asyncio",
]

# Keep uvicorn.error at INFO level
THIRD_PARTY_INFO_LOGGERS = [
    "uvicorn.error",
]

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
