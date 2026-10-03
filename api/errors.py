"""Typed error envelope and FastAPI exception handlers.

Business failures that belong to the durable job result are never raised here; raw
exceptions and secret-bearing configuration must never reach a client. Every error
carries a stable code, a safe message, and the request correlation id.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from schemas.api import ErrorResponse
from schemas.errors import ErrorCategory, ResearchError

logger = logging.getLogger(__name__)

#: The single place where an error category becomes an HTTP status. Routers raise
#: domain errors; they never choose a status code themselves.
STATUS_BY_CATEGORY: Final[dict[ErrorCategory, int]] = {
    ErrorCategory.INVALID_INPUT: 422,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.CONFLICT: 409,
    ErrorCategory.LIMIT_EXCEEDED: 429,
    ErrorCategory.UNAVAILABLE: 503,
    ErrorCategory.CONTRACT_VIOLATION: 500,
    ErrorCategory.INTERNAL: 500,
}

#: Codes whose category default is wrong for HTTP. A budget above the cap will
#: never succeed on retry, and an oversized artifact is a size refusal, so neither
#: is a 429.
STATUS_BY_CODE: Final[dict[str, int]] = {
    "budget_exceeded": 422,
    "artifact_too_large": 413,
    "unauthorized": 401,
}

_SAFE_INTERNAL_MESSAGE: Final = "An internal error occurred"

#: OpenAPI declarations so clients see the envelope for every status we emit.
ERROR_RESPONSES: Final[dict[int | str, dict[str, Any]]] = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (401, "Missing or wrong bearer token"),
        (404, "Unknown run, job, or artifact"),
        (409, "Conflicts with current state"),
        (413, "Artifact exceeds the download bound"),
        (422, "Rejected input"),
        (429, "Queue full; see Retry-After"),
        (500, "Internal error; message withheld"),
        (503, "Store or configuration unavailable"),
    )
}


class ApiError(ResearchError):
    """A transport-only failure with no domain equivalent, such as a bad token.

    Prefer raising a domain error from :mod:`schemas.errors`; use this only when
    the failure exists purely at the HTTP boundary.

    Args:
        category: Selects the HTTP status through :data:`STATUS_BY_CATEGORY`.
        code: A stable machine-readable code.
        message: A safe message for the client.
        retry_after: Seconds before a retry may succeed, sent as ``Retry-After``.
    """

    def __init__(  # noqa: D107 - documented on the class
        self,
        category: ErrorCategory,
        code: str,
        message: str,
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, code=code)
        # Shadows the class-level default for this instance only.
        self.category = category  # type: ignore[misc]
        self.retry_after = retry_after


def not_found(what: str = "resource") -> ApiError:
    """Build a 404 for an unknown or hidden resource, without echoing its id."""
    return ApiError(ErrorCategory.NOT_FOUND, "not_found", f"Unknown {what}")


def conflict(code: str, message: str) -> ApiError:
    """Build a 409 for a request that clashes with current state."""
    return ApiError(ErrorCategory.CONFLICT, code, message)


def unavailable(
    code: str, message: str = "A required server dependency is unavailable"
) -> ApiError:
    """Build a 503 for a dependency that cannot serve the request right now."""
    return ApiError(ErrorCategory.UNAVAILABLE, code, message)


def unauthorized() -> ApiError:
    """Build a 401 for a missing or wrong bearer token."""
    return ApiError(ErrorCategory.INVALID_INPUT, "unauthorized", "A valid bearer token is required")


def status_for(error: ResearchError) -> int:
    """Return the HTTP status for a project error.

    A code-level override wins over the category so a few codes can carry a more
    specific status without a new category.
    """
    if error.code in STATUS_BY_CODE:
        return STATUS_BY_CODE[error.code]
    return STATUS_BY_CATEGORY[error.category]


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "")


def _envelope(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": _request_id(request)}},
    )


def _research_response(request: Request, error: ResearchError) -> JSONResponse:
    status = status_for(error)
    # A 5xx means our code or a dependency failed; its text may name internals, so
    # the client gets a fixed message and the detail goes to the server log only.
    message = _SAFE_INTERNAL_MESSAGE if status >= 500 and status != 503 else error.message
    if status >= 500:
        logger.warning(
            "request failed",
            extra={
                "request_id": _request_id(request),
                "error_code": error.code,
                "error_type": type(error).__name__,
                "status": status,
            },
        )
    response = _envelope(request, status, error.code, message)
    retry_after = getattr(error, "retry_after", None)
    if isinstance(retry_after, int):
        response.headers["Retry-After"] = str(retry_after)
    return response


def install_handlers(app: FastAPI) -> None:
    """Register the typed error envelope for project, validation, and unknown errors."""

    @app.exception_handler(ResearchError)
    async def _research(request: Request, error: ResearchError) -> JSONResponse:
        return _research_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, error: RequestValidationError) -> JSONResponse:
        del error
        return _envelope(request, 422, "invalid_request", "The request payload was rejected")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, error: Exception) -> JSONResponse:
        # Never leak exception text or configuration to a client; log the type
        # with the request id so an operator can find the server-side traceback.
        logger.exception(
            "unhandled error",
            extra={"request_id": _request_id(request), "error_type": type(error).__name__},
        )
        return _envelope(request, 500, "internal_error", _SAFE_INTERNAL_MESSAGE)
