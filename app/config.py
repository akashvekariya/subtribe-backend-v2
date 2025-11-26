"""Application configuration using Pydantic Settings."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str

    # Supabase Auth
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    supabase_jwt_secret: str

    # Backend JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 20

    # Cookie Configuration
    cookie_secure: bool = False  # False for dev (HTTP), True for prod (HTTPS)
    cookie_samesite: str = "Lax"  # CSRF protection
    cookie_domain: str = ""  # Empty for dev, .thesubtribe.com for prod
    cookie_max_age: int = 2592000  # 30 days in seconds

    # Google Cloud Storage
    gcs_bucket_name: str
    gcs_project_id: str
    google_application_credentials: str = (
        "/dev/null"  # Not needed in Cloud Run (uses service account)
    )

    # Email Service
    email_enabled: bool = True
    email_provider: str = "stub"  # "sendgrid" or "stub"
    email_from_address: str = "noreply@thesubtribe.com"
    email_from_name: str = "Subtribe ATS"
    sendgrid_api_key: str = "dummy-api-key"  # Required even for stub mode
    sendgrid_sandbox_mode: bool = True
    gcp_cloud_tasks_queue: str = "email-queue"
    gcp_cloud_tasks_location: str = "asia-south1"
    email_send_time_ist: str = "17:00"  # 5 PM IST

    # Backend URL (for Cloud Tasks callbacks)
    # Auto-detected from K_SERVICE env var in Cloud Run, or set manually
    backend_url: str = ""  # Empty = auto-detect in Cloud Run

    # App Config
    cors_allowed_origins: str = (
        "http://localhost:3000,http://localhost:3001"  # Comma-separated list of allowed origins
    )
    environment: str = "development"
    debug: bool = True

    # Logging Configuration
    log_mode: str = "smart"  # full, smart, or minimal
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR (for app.* loggers)
    log_format: str = "console"  # console or json (auto-set based on environment)
    log_sampling_rate: float = 1.0  # 0.0-1.0 (fraction of requests to log)
    log_request_body: bool = True  # Log request bodies (can override per route)
    log_response_body: bool = True  # Log response bodies (can override per route)
    third_party_log_level: str = "WARNING"  # Log level for ALL third-party libraries

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('ENVIRONMENT', 'development')}",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
