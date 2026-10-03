"""Request correlation and short-request HTTP telemetry.

The API measures transport time only. Research execution and queue wait are
measured by the worker, so an HTTP span never pretends to cover a long job.
"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        request_id = incoming[:128] if incoming else str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Process-Time-Ms"] = f"{(time.monotonic() - started) * 1000:.2f}"
        return response


def install_middleware(app: FastAPI, *, allowed_origins: list[str]) -> None:
    app.add_middleware(RequestContextMiddleware)
    if allowed_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
            expose_headers=[REQUEST_ID_HEADER, "Location", "Retry-After"],
        )
