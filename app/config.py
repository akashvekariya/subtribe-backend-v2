"""Application configuration using Pydantic Settings."""

import json
import os

from pydantic import field_validator
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
    cors_origins: list[str] | str = ["http://localhost:3000"]
    environment: str = "development"
    debug: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from JSON string or comma-separated string."""
        if isinstance(v, str):
            # Try JSON first
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [parsed]
            except (json.JSONDecodeError, ValueError):
                # Fallback to comma-separated or single value
                return [v.strip()] if v.strip() else ["*"]
        return v

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('ENVIRONMENT', 'development')}",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
