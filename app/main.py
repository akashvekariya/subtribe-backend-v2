"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import register_exception_handlers
from app.logging import LoggingMiddleware, setup_logging
from app.routers import (
    ai,
    ai_resume_eval,
    applications,
    auth,
    companies,
    dashboard,
    emails,
    invites,
    jobs,
)

logger = logging.getLogger(__name__)


def _configure_subtribe_ai():
    """Configure the subtribe-ai package with settings from backend config."""
    try:
        import subtribe_ai

        subtribe_ai.configure(
            google_api_key=settings.subtribe_ai_google_api_key,
            openai_api_key=settings.subtribe_ai_openai_api_key,
            default_model=settings.subtribe_ai_default_model,
            langfuse_enabled=settings.subtribe_ai_langfuse_enabled,
            langfuse_public_key=settings.subtribe_ai_langfuse_public_key,
            langfuse_secret_key=settings.subtribe_ai_langfuse_secret_key,
        )
        logger.info("subtribe-ai configured successfully")
    except ImportError:
        logger.warning("subtribe-ai not installed, AI features will be unavailable")
    except Exception as e:
        logger.error(f"Failed to configure subtribe-ai: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events (startup and shutdown)."""
    # Startup: Initialize logging
    # Use JSON format for any cloud deployment (cleaner, no color codes)
    # Use console format only for local development (colored output in terminal)
    # Detection: K_SERVICE (GCP Cloud Run) or AWS_EXECUTION_ENV (AWS Lambda/ECS)
    is_cloud_deployment = os.getenv("K_SERVICE") or os.getenv("AWS_EXECUTION_ENV")
    log_format = "json" if is_cloud_deployment else settings.log_format

    setup_logging(
        log_format=log_format,
        log_level=settings.log_level,
        third_party_log_level=settings.third_party_log_level,
    )

    # Configure subtribe-ai package
    _configure_subtribe_ai()

    logger.info(
        "Application starting",
        extra={
            "environment": settings.environment,
            "log_mode": settings.log_mode,
            "log_format": log_format,
            "log_level": settings.log_level,
        },
    )

    yield

    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="Subtribe",
    description="Multi-tenant Applicant Tracking System",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,  # Add lifespan event for logging initialization
    # Disable docs in production for security
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)


# Custom OpenAPI schema to ensure Bearer token auth shows in Swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add Bearer token security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token (without 'Bearer' prefix)",
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Middleware (order matters: last added = first executed)
# 1. Logging middleware (wraps all requests with correlation ID)
app.add_middleware(
    LoggingMiddleware,
    log_mode=settings.log_mode,
    sampling_rate=settings.log_sampling_rate,
)

# 2. CORS - Parse comma-separated origins from environment variable
allowed_origins = [
    origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # Cache CORS preflight for 1 hour (reduces OPTIONS spam)
)

# Exception handlers
register_exception_handlers(app)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.environment}


app.include_router(auth.router, prefix="/auth")
app.include_router(invites.router, prefix="/invites")
app.include_router(companies.router, prefix="/companies")
app.include_router(dashboard.router, prefix="/dashboard")
app.include_router(jobs.router, prefix="/jobs")
app.include_router(jobs.public_router, prefix="/public/jobs")
app.include_router(applications.public_router, prefix="/public")
app.include_router(applications.router, prefix="/applications")
app.include_router(emails.internal_router, prefix="/internal/emails")
app.include_router(emails.email_router, prefix="/emails")
app.include_router(emails.router, prefix="/emails")
app.include_router(ai.router, prefix="/api/ai")
app.include_router(ai_resume_eval.router, prefix="/api")
