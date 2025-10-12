"""
E2E test configuration.

Allows switching between local and staging/production environments.
"""

import os

# E2E test configuration
E2E_CONFIG = {
    # Base URL for E2E tests (configurable via environment variable)
    "base_url": os.getenv("E2E_BASE_URL", "http://localhost:8000"),
    # Test credentials for staging/production
    "test_company_code": os.getenv("E2E_COMPANY_CODE", "FIRSTINVITE"),
    "test_email": os.getenv("E2E_TEST_EMAIL", "e2e_test@example.com"),
    "test_password": os.getenv("E2E_TEST_PASSWORD", "TestPass123!"),
    # Timeout settings
    "request_timeout": 30,  # seconds
}


def get_base_url() -> str:
    """Get the base URL for E2E tests."""
    return E2E_CONFIG["base_url"]


def is_local_environment() -> bool:
    """Check if running against local environment."""
    return "localhost" in E2E_CONFIG["base_url"]


# Usage:
# - Local testing: python -m pytest tests/e2e/
# - Staging testing: E2E_BASE_URL=https://staging.api.com python -m pytest tests/e2e/
# - Production testing: E2E_BASE_URL=https://api.subtribe.com python -m pytest tests/e2e/
