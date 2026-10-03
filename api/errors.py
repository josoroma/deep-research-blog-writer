"""Typed error envelope and FastAPI exception handlers.

Business failures that belong to the durable job result are never raised here; raw
exceptions and secret-bearing configuration must never reach a client. Every error
carries a stable code, a safe message, and the request correlation id.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from application.job_service import AdmissionError

TERMINAL_MESSAGES: dict[str, str] = {}


class ApiError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, *, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after = retry_after


def not_found(what: str = "resource") -> ApiError:
    return ApiError(404, "not_found", f"Unknown {what}")


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def unavailable(
    code: str, message: str = "A required server dependency is unavailable"
) -> ApiError:
    return ApiError(503, code, message)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "")


def _envelope(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": _request_id(request)}},
    )


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, error: ApiError) -> JSONResponse:
        response = _envelope(request, error.status_code, error.code, error.message)
        if error.retry_after is not None:
            response.headers["Retry-After"] = str(error.retry_after)
        return response

    @app.exception_handler(AdmissionError)
    async def _admission(request: Request, error: AdmissionError) -> JSONResponse:
        status = 429 if error.code == "queue_full" else 409
        response = _envelope(request, status, error.code, error.message)
        if error.retry_after is not None:
            response.headers["Retry-After"] = str(error.retry_after)
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, error: RequestValidationError) -> JSONResponse:
        del error
        return _envelope(request, 422, "invalid_request", "The request payload was rejected")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, error: Exception) -> JSONResponse:
        # Never leak exception text or configuration to a client.
        del error
        return _envelope(request, 500, "internal_error", "An internal error occurred")
