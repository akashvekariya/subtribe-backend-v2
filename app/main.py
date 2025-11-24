"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import register_exception_handlers
from app.logging import LoggingMiddleware, setup_logging
from app.routers import applications, auth, companies, dashboard, jobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events (startup and shutdown)."""
    # Startup: Initialize logging
    # Use JSON format for any cloud deployment (cleaner, no color codes)
    # Use console format only for local development (colored output in terminal)
    # Detection: K_SERVICE (GCP Cloud Run) or AWS_EXECUTION_ENV (AWS Lambda/ECS)
    import os

    is_cloud_deployment = os.getenv("K_SERVICE") or os.getenv("AWS_EXECUTION_ENV")
    log_format = "json" if is_cloud_deployment else settings.log_format

    setup_logging(
        log_format=log_format,
        log_level=settings.log_level,
        third_party_log_level=settings.third_party_log_level,
    )

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
    title="Subtribe ATS",
    description="Multi-tenant Applicant Tracking System",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,  # Add lifespan event
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
# 1. CORS (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight responses for 1 hour (reduces OPTIONS spam)
)

# 2. Logging middleware (executes for all requests)
app.add_middleware(
    LoggingMiddleware,
    log_mode=settings.log_mode,
    sampling_rate=settings.log_sampling_rate,
)

# Exception handlers
register_exception_handlers(app)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "environment": settings.environment}


app.include_router(auth.router, prefix="/auth")
app.include_router(companies.router, prefix="/companies")
app.include_router(jobs.router, prefix="/jobs")
app.include_router(jobs.public_router, prefix="/public/jobs")
app.include_router(applications.public_router, prefix="/public")
app.include_router(applications.router, prefix="/applications")
app.include_router(dashboard.router, prefix="/dashboard")
