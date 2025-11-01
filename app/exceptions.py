"""Custom exceptions and global exception handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found", code: str = "not_found", **kwargs):
        super().__init__(message, code, status.HTTP_404_NOT_FOUND, **kwargs)


class ConflictError(AppException):
    """Resource conflict."""

    def __init__(self, message: str = "Resource conflict", code: str = "conflict", **kwargs):
        super().__init__(message, code, status.HTTP_409_CONFLICT, **kwargs)


class UnauthorizedError(AppException):
    """Authentication failed."""

    def __init__(self, message: str = "Unauthorized", code: str = "unauthorized", **kwargs):
        super().__init__(message, code, status.HTTP_401_UNAUTHORIZED, **kwargs)


class ForbiddenError(AppException):
    """Authorization failed."""

    def __init__(self, message: str = "Forbidden", code: str = "forbidden", **kwargs):
        super().__init__(message, code, status.HTTP_403_FORBIDDEN, **kwargs)


class ValidationError(AppException):
    """Validation error."""

    def __init__(self, message: str = "Validation error", code: str = "validation_error", **kwargs):
        super().__init__(message, code, status.HTTP_422_UNPROCESSABLE_ENTITY, **kwargs)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers with FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        # Lazy import to avoid circular dependency
        from app.dependencies import get_correlation_id

        # Log application exception
        logger.warning(
            f"Application error: {exc.__class__.__name__}",
            extra={
                "correlation_id": get_correlation_id(),
                "exception_type": exc.__class__.__name__,
                "code": exc.code,
                "message": exc.message,
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "method": request.method,
                "details": exc.details,
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": exc.__class__.__name__.replace("Error", "").lower() + "_error",
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Lazy import to avoid circular dependency
        from app.dependencies import get_correlation_id

        # Clean up errors to make them JSON serializable
        errors = []
        for error in exc.errors():
            error_dict = {
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", "Validation error"),
                "type": error.get("type", "unknown"),
            }
            # Convert input to string if present (for debugging)
            if "input" in error:
                error_dict["input"] = str(error["input"])
            errors.append(error_dict)

        # Log validation error
        logger.warning(
            "Request validation failed",
            extra={
                "correlation_id": get_correlation_id(),
                "exception_type": "RequestValidationError",
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "path": str(request.url.path),
                "method": request.method,
                "validation_errors": errors,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "type": "validation_error",
                    "code": "invalid_request",
                    "message": "Request validation failed",
                    "details": {"errors": errors},
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        """
        Catch-all for unhandled database integrity errors.
        Most database errors should be caught and converted to proper exceptions
        in the endpoint/service layer.
        """
        # Lazy import to avoid circular dependency
        from app.dependencies import get_correlation_id

        raw_error = str(exc.orig) if hasattr(exc, "orig") else str(exc)

        # Log database integrity error
        logger.error(
            "Database integrity error (unhandled)",
            extra={
                "correlation_id": get_correlation_id(),
                "exception_type": "IntegrityError",
                "status_code": status.HTTP_409_CONFLICT,
                "path": str(request.url.path),
                "method": request.method,
                "raw_error": raw_error,
            },
            exc_info=True,  # Include traceback
        )

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "type": "conflict_error",
                    "code": "database_constraint",
                    "message": (
                        "Database constraint violation. "
                        "This error should be handled in the endpoint."
                    ),
                    "details": {"raw_error": raw_error},
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        # Lazy import to avoid circular dependency
        from app.dependencies import get_correlation_id

        # Log unexpected exception with full traceback
        logger.error(
            f"Unexpected error: {exc.__class__.__name__}",
            extra={
                "correlation_id": get_correlation_id(),
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "path": str(request.url.path),
                "method": request.method,
            },
            exc_info=True,  # Include full traceback
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "type": "internal_error",
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )
