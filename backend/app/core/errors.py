import logging
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class KnowledgeHubException(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class TenantAccessForbiddenException(KnowledgeHubException):
    def __init__(self, message: str = "Access to the requested workspace is forbidden."):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN)


class ResourceNotFoundException(KnowledgeHubException):
    def __init__(self, message: str = "The requested resource was not found."):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(KnowledgeHubException)
    async def app_exception_handler(request: Request, exc: KnowledgeHubException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error": exc.message, "details": exc.details, "status_code": exc.status_code},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error": exc.detail, "status_code": exc.status_code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Validation error", "details": exc.errors(), "status_code": 422},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled exception during request processing: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal server error occurred.", "status_code": 500},
        )
