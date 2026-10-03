"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.dependencies import state


class HealthRouter:
    router = APIRouter(tags=["health"])

    @staticmethod
    @router.get("/health/live")
    def live() -> dict[str, str]:
        """Process health only; makes no provider or database call."""
        return {"status": "alive"}

    @staticmethod
    @router.get("/health/ready")
    def ready(request: Request) -> JSONResponse:
        """Database/schema and worker readiness; 503 when submission cannot proceed."""
        resources = state(request)
        if not resources.store_ready:
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "reason": resources.store_reason},
            )
        ok, reason = resources.jobs.ready()
        if not ok:
            return JSONResponse(
                status_code=503, content={"status": "unavailable", "reason": reason}
            )
        return JSONResponse(status_code=200, content={"status": "ready"})
