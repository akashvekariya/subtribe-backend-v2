# Error Handling Architecture

> **TLDR**: Framework-level error handling using FastAPI exception handlers, database transaction patterns, and consistent error responses. Handles validation, auth, database, storage, and external service failures automatically. **Goal**: Write business logic, let framework handle errors.

---

## 1. Error Response Format

**Consistent JSON structure** (from api-design.md):

```json
{
  "error": {
    "type": "validation_error",
    "code": "invalid_email",
    "message": "The email address provided is invalid",
    "param": "email"
  }
}
```

**HTTP Status Codes**:
- `400` - Validation errors
- `401` - Authentication required
- `403` - Insufficient permissions
- `404` - Resource not found
- `409` - Conflict (duplicate)
- `422` - Business logic error
- `500` - Server error

---

## 2. Global Exception Handlers

**Create**: `app/exceptions.py`

```python
"""
Global exception handlers for FastAPI.
Centralizes error handling and response formatting.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from google.cloud.exceptions import GoogleCloudError
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base exception for application errors."""
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        param: str | None = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.param = param
        super().__init__(message)


class AuthenticationError(AppException):
    """Authentication failures."""
    def __init__(self, message: str = "Authentication required", code: str = "auth_required"):
        super().__init__(message, code, status_code=401)


class PermissionError(AppException):
    """Authorization failures."""
    def __init__(self, message: str = "Insufficient permissions", code: str = "forbidden"):
        super().__init__(message, code, status_code=403)


class NotFoundError(AppException):
    """Resource not found."""
    def __init__(self, message: str = "Resource not found", code: str = "not_found"):
        super().__init__(message, code, status_code=404)


class ConflictError(AppException):
    """Resource conflicts (duplicates)."""
    def __init__(self, message: str = "Resource already exists", code: str = "conflict"):
        super().__init__(message, code, status_code=409)


def register_exception_handlers(app: FastAPI):
    """Register all exception handlers."""
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Handle custom application exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": exc.__class__.__name__.replace("Error", "").lower() + "_error",
                    "code": exc.code,
                    "message": exc.message,
                    "param": exc.param
                }
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(x) for x in error["loc"][1:]),  # Skip 'body'
                "code": error["type"],
                "message": error["msg"]
            })
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "type": "validation_error",
                    "code": "validation_failed",
                    "message": "Request validation failed",
                    "errors": errors
                }
            }
        )
    
    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        """Handle database integrity errors (unique constraints, foreign keys)."""
        logger.error(f"Database integrity error: {exc}")
        
        # Parse common errors
        if "duplicate key" in str(exc).lower():
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "error": {
                        "type": "conflict_error",
                        "code": "duplicate_entry",
                        "message": "A record with this value already exists"
                    }
                }
            )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "type": "database_error",
                    "code": "integrity_constraint",
                    "message": "Database constraint violation"
                }
            }
        )
    
    @app.exception_handler(OperationalError)
    async def operational_exception_handler(request: Request, exc: OperationalError):
        """Handle database operational errors (connection, timeout)."""
        logger.error(f"Database operational error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "type": "server_error",
                    "code": "database_unavailable",
                    "message": "Database temporarily unavailable"
                }
            }
        )
    
    @app.exception_handler(GoogleCloudError)
    async def gcs_exception_handler(request: Request, exc: GoogleCloudError):
        """Handle Google Cloud Storage errors."""
        logger.error(f"GCS error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "type": "server_error",
                    "code": "storage_unavailable",
                    "message": "File storage temporarily unavailable"
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Catch-all for unexpected errors."""
        logger.exception(f"Unexpected error: {exc}")
        
        # In production, hide details
        if settings.ENVIRONMENT == "production":
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "type": "server_error",
                        "code": "internal_error",
                        "message": "An unexpected error occurred"
                    }
                }
            )
        
        # In development, show details
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "type": "server_error",
                    "code": "internal_error",
                    "message": str(exc)
                }
            }
        )
```

**Register in `app/main.py`**:
```python
from app.exceptions import register_exception_handlers

app = FastAPI(title="Subtribe ATS")
register_exception_handlers(app)
```

---

## 3. Database Transaction Pattern

**Pattern**: Wrap multi-step operations in transactions

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.exceptions import AppException

async def create_application_with_resume(
    db: AsyncSession,
    job: Job,
    form_data: dict,
    resume_file: UploadFile
) -> Application:
    """
    Create application with resume upload.
    Rollback DB if upload fails.
    """
    async with db.begin():  # Automatic rollback on exception
        # 1. Create application
        full_name = f"{form_data['first_name']} {form_data['last_name']}"
        application = Application(
            job_id=job.id,
            company_id=job.company_id,
            first_name=form_data["first_name"],
            last_name=form_data["last_name"],
            email=form_data["email"],
            status="applied"
        )
        db.add(application)
        await db.flush()  # Get application.id
        
        try:
            # 2. Upload to GCS (external service)
            resume_uri = await storage_service.upload_resume(
                file=resume_file.file,
                company_id=str(job.company_id),
                job_id=str(job.id),
                application_id=str(application.id),
                full_name=full_name,
                content_type=resume_file.content_type
            )
            
            # 3. Update application
            application.resume_url = resume_uri
            application.resume_filename = resume_file.filename
            
        except Exception as e:
            # GCS upload failed - transaction will rollback
            logger.error(f"Resume upload failed: {e}")
            raise AppException(
                message="Failed to upload resume",
                code="upload_failed",
                status_code=503
            )
    
    # Transaction committed successfully
    return application
```

**Key points**:
- `async with db.begin()`: Auto-rollback on exception
- External calls inside transaction: Atomic operation
- Specific exceptions: Better error messages

---

## 4. Auth Error Handling

**Automatic via dependency**:

```python
# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Validate JWT and return user claims.
    Raises 401 automatically on failure.
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(
            message="Token has expired",
            code="token_expired"
        )
    except JWTError:
        raise AuthenticationError(
            message="Invalid authentication token",
            code="invalid_token"
        )


def require_role(*allowed_roles: str):
    """Require specific role(s)."""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise PermissionError(
                message=f"Requires role: {', '.join(allowed_roles)}",
                code="insufficient_permissions"
            )
        return current_user
    return role_checker
```

**Usage** (framework handles errors):
```python
@router.post("/jobs")
async def create_job(
    data: JobCreate,
    current_user: dict = Depends(require_role("admin", "recruiter")),
    db: AsyncSession = Depends(get_db)
):
    # If user lacks role, 403 returned automatically
    # If token invalid, 401 returned automatically
    job = Job(**data.dict(), created_by=current_user["user_id"])
    db.add(job)
    await db.commit()
    return job
```

---

## 5. File Upload Error Handling

**Validation before upload**:

```python
from app.exceptions import AppException

async def validate_resume_file(file: UploadFile):
    """Validate file type and size."""
    # Check content type
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    if file.content_type not in allowed_types:
        raise AppException(
            message="Only PDF and DOCX files are allowed",
            code="invalid_file_type",
            param="resume"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset
    
    if size > settings.max_resume_size_bytes:
        raise AppException(
            message=f"File too large (max {settings.MAX_RESUME_SIZE_MB}MB)",
            code="file_too_large",
            param="resume"
        )
    
    return file
```

**Graceful upload failure**:
```python
# In storage.py
async def upload_resume(self, file, **kwargs) -> str:
    """Upload with retries."""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            blob = self.bucket.blob(path)
            blob.upload_from_file(file, timeout=60)
            return f"gs://{self.bucket.name}/{path}"
        
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Upload failed after {max_retries} attempts: {e}")
                raise GoogleCloudError(f"Failed to upload file: {str(e)}")
            
            logger.warning(f"Upload attempt {attempt + 1} failed, retrying...")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## 6. Validation Error Examples

**Pydantic handles automatically**:

```python
from pydantic import BaseModel, EmailStr, Field, field_validator

class ApplicationCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    
    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
```

**Framework returns**:
```json
{
  "error": {
    "type": "validation_error",
    "code": "validation_failed",
    "message": "Request validation failed",
    "errors": [
      {
        "field": "email",
        "code": "value_error.email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

---

## 7. Business Logic Errors

**Use custom exceptions**:

```python
# Check duplicate application
existing = await db.execute(
    select(Application).where(
        Application.job_id == job.id,
        Application.email == data.email
    )
)
if existing.scalar_one_or_none():
    raise ConflictError(
        message="You have already applied to this job",
        code="duplicate_application"
    )

# Check job active
if job.status != "active":
    raise NotFoundError(
        message="Job not found or no longer accepting applications",
        code="job_not_active"
    )
```

---

## 8. Logging Strategy

**Structured logging**:

```python
# app/logging_config.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for Cloud Logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

# Setup
logging.basicConfig(level=settings.LOG_LEVEL)
if settings.LOG_FORMAT == "json":
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
```

**Usage**:
```python
logger.info("Application submitted", extra={
    "application_id": str(application.id),
    "job_id": str(job.id),
    "company_id": str(company.id)
})

logger.error("Resume upload failed", extra={
    "application_id": str(application.id),
    "error": str(e)
})
```

---

## 9. Monitoring Integration

**Sentry setup** (`app/main.py`):

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration()
        ]
    )
```

**Automatic error tracking**: All unhandled exceptions sent to Sentry with context (user, request, database queries).

---

## 10. Summary

**Framework handles**:
✅ Validation errors (Pydantic)  
✅ Auth errors (JWT dependencies)  
✅ Database errors (global handlers)  
✅ Storage errors (global handlers)  
✅ Unexpected errors (catch-all handler)

**You write**:
- Business logic exceptions (duplicate, not found, forbidden)
- Transaction boundaries (`async with db.begin()`)
- Input validation (Pydantic models)

**Result**: Clean code, consistent errors, automatic logging/monitoring.

---

**Implementation**: Copy exception handlers to `app/exceptions.py`, register in `main.py`, use throughout API.

