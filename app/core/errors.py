from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger


class AppException(Exception):
    """Base application exception with standardized code and status."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Any] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "RESOURCE_NOT_FOUND"):
        super().__init__(code=code, message=message, status_code=status.HTTP_404_NOT_FOUND)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHORIZED"):
        super().__init__(code=code, message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Access forbidden", code: str = "FORBIDDEN"):
        super().__init__(code=code, message=message, status_code=status.HTTP_403_FORBIDDEN)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT"):
        super().__init__(code=code, message=message, status_code=status.HTTP_409_CONFLICT)


class PayloadTooLargeException(AppException):
    def __init__(self, message: str = "File too large", code: str = "FILE_TOO_LARGE"):
        super().__init__(code=code, message=message, status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413))


class ValidationException(AppException):
    def __init__(self, message: str = "Validation failed", code: str = "VALIDATION_ERROR", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class JobNotRetryableException(AppException):
    def __init__(self, message: str = "Job is not retryable", code: str = "JOB_NOT_RETRYABLE", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class InvalidStateTransitionException(AppException):
    def __init__(self, message: str = "Invalid state transition", code: str = "INVALID_STATE_TRANSITION", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_409_CONFLICT, details=details)


class FeatureNotConfiguredException(AppException):
    def __init__(self, message: str = "Feature is not configured", code: str = "FEATURE_NOT_CONFIGURED", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class EnvironmentProtectedException(AppException):
    def __init__(self, message: str = "Environment is protected against this operation", code: str = "ENVIRONMENT_PROTECTED", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_403_FORBIDDEN, details=details)


class ProviderUnavailableException(AppException):
    def __init__(self, message: str = "AI Provider is unavailable", code: str = "PROVIDER_UNAVAILABLE", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


class QuotaExceededException(AppException):
    def __init__(self, message: str = "AI Provider quota exceeded", code: str = "QUOTA_EXCEEDED", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, details=details)


class ConfigurationInvalidException(AppException):
    def __init__(self, message: str = "Configuration item is invalid", code: str = "CONFIGURATION_INVALID", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class WorkerUnavailableException(AppException):
    def __init__(self, message: str = "Worker is unavailable", code: str = "WORKER_UNAVAILABLE", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


class QueueUnavailableException(AppException):
    def __init__(self, message: str = "Queue is unavailable", code: str = "QUEUE_UNAVAILABLE", details: Any = None):
        super().__init__(code=code, message=message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


def register_error_handlers(app: FastAPI) -> None:
    """Register uniform error handlers formatting all errors into {'error': {'code': ..., 'message': ...}}"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        content = {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        }
        if exc.details is not None:
            content["error"]["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code_map = {
            status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
            status.HTTP_403_FORBIDDEN: "FORBIDDEN",
            status.HTTP_404_NOT_FOUND: "NOT_FOUND",
            status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
            status.HTTP_409_CONFLICT: "CONFLICT",
            413: "FILE_TOO_LARGE",
            status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Format Pydantic validation errors nicely
        errors = []
        for err in exc.errors():
            loc = ".".join(str(loc_part) for loc_part in err.get("loc", []))
            errors.append(f"{loc}: {err.get('msg')}")
        message = "; ".join(errors) if errors else "Invalid request data"
        status_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        return JSONResponse(
            status_code=status_422,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            },
        )
