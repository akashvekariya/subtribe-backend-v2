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

    # Google Cloud Storage
    gcs_bucket_name: str
    gcs_project_id: str
    google_application_credentials: str = (
        "/dev/null"  # Not needed in Cloud Run (uses service account)
    )

    # App Config
    cors_allowed_origins: str  # Regex pattern from env
    environment: str = "development"
    debug: bool = True


    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('ENVIRONMENT', 'development')}",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
