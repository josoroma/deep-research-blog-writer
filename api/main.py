"""The FastAPI application factory.

Importing this module must not start workers, create run directories, or contact
providers. ``create_app`` is passed to Uvicorn with ``--factory``; the lifespan
opens settings and short-lived database access, validates schema compatibility,
and closes process resources on shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI

from api.dependencies import AppState
from api.errors import install_handlers
from api.middleware import install_middleware
from api.routers import health, jobs, runs
from application.job_service import JobService
from application.migrations import apply_migrations
from application.ports import JobStore
from schemas.config import ApiSettings
from services.artifact_reader import ArtifactReader
from services.job_store import MemoryJobStore
from services.postgres_jobs import CONNECT_TIMEOUT_SECONDS, PostgresJobStore

APP_NAME = "deep-research-blog-api"


def _build_store(settings: ApiSettings) -> tuple[JobStore, bool, str]:
    """Create the durable store, falling back to memory only in the fixture profile.

    A configured database always wins, so the fixture integration profile can
    exercise a real database, API process, and worker with no model or search
    calls. Without a database, production reports an unavailable store through
    readiness rather than raising at import.
    """
    if settings.uses_memory_store():
        return MemoryJobStore(), True, "ready"
    dsn = settings.database_dsn()
    if dsn is None:
        return MemoryJobStore(), False, "database_not_configured"
    postgres = PostgresJobStore(dsn)
    try:
        with psycopg.connect(dsn, connect_timeout=CONNECT_TIMEOUT_SECONDS) as connection:
            apply_migrations(connection)
    except Exception as error:  # noqa: BLE001 - readiness reports the reason, never raises
        return postgres, False, f"schema_unavailable:{type(error).__name__}"
    return postgres, True, "ready"


def create_app(settings: ApiSettings | None = None, *, store: JobStore | None = None) -> FastAPI:
    """Build the API application without starting a worker or contacting a provider.

    Args:
        settings: Server settings; read from the environment when omitted.
        store: An injected job store, used by tests and the fixture demo. When
            omitted the store is built from ``settings``.

    Returns:
        A configured FastAPI app whose lifespan attaches :class:`AppState`.
    """
    resolved = settings if settings is not None else ApiSettings()
    if store is not None:
        resolved_store, ready, reason = store, True, "ready"
    else:
        resolved_store, ready, reason = _build_store(resolved)
    resources = AppState(
        settings=resolved,
        store=resolved_store,
        jobs=JobService(resolved_store, resolved),
        reader=ArtifactReader(
            Path(resolved.runs_dir),
            max_bytes=resolved.artifact_max_bytes,
            log_page_limit=resolved.log_page_max_limit,
        ),
        token=resolved.bearer_token(),
        store_ready=ready,
        store_reason=reason,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        app.state.resources = resources
        try:
            yield
        finally:
            close = getattr(resolved_store, "close", None)
            if callable(close):
                close()

    app = FastAPI(title=APP_NAME, version="0.1.0", lifespan=lifespan)
    install_handlers(app)
    install_middleware(app, allowed_origins=resolved.origins)
    app.include_router(health.HealthRouter.router)
    app.include_router(jobs.router)
    app.include_router(runs.router)
    return app
