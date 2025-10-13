"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import register_exception_handlers
from app.routers import applications, auth, companies, jobs

app = FastAPI(
    title="Subtribe ATS",
    description="Multi-tenant Applicant Tracking System",
    version="1.0.0",
    debug=settings.debug,
    # Disable docs in production for security
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
