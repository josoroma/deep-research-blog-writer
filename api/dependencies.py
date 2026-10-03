"""App-state dependencies: settings, stores, reader and bearer authentication.

Everything is created once in the lifespan. These callables only read
``request.app.state``, so importing an API module never opens a connection or
contacts a provider. Annotated aliases keep the FastAPI dependency wiring typed
without calling ``Depends`` in argument defaults.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from api.errors import unauthorized
from application.job_service import JobService
from application.ports import JobStore
from schemas.config import ApiSettings
from services.artifact_reader import ArtifactReader


@dataclass
class AppState:
    """Process-wide resources built once by :func:`api.main.create_app`.

    Attributes:
        settings: Server configuration.
        store: The durable job queue.
        jobs: Admission and status use cases over ``store``.
        reader: Contained, bounded artifact reads.
        token: The shared bearer token, or ``None`` for loopback-only use.
        store_ready: Whether the store and schema were usable at startup.
        store_reason: A stable reason code when ``store_ready`` is false.
    """

    settings: ApiSettings
    store: JobStore
    jobs: JobService
    reader: ArtifactReader
    token: str | None
    store_ready: bool
    store_reason: str


def state(request: Request) -> AppState:
    """Return the resources the lifespan attached to the application."""
    resolved: AppState = request.app.state.resources
    return resolved


def settings(request: Request) -> ApiSettings:
    """FastAPI dependency: the server settings."""
    return state(request).settings


def job_service(request: Request) -> JobService:
    """FastAPI dependency: the admission and status service."""
    return state(request).jobs


def store(request: Request) -> JobStore:
    """FastAPI dependency: the durable job store."""
    return state(request).store


def reader(request: Request) -> ArtifactReader:
    """FastAPI dependency: the contained artifact reader."""
    return state(request).reader


async def require_token(request: Request) -> None:
    """Enforce the shared bearer token when one is configured.

    Loopback development with no token is allowed; any non-empty configured token
    is required for every business endpoint. The comparison is constant-time so
    response timing does not reveal how much of a guessed token matched.

    Raises:
        ApiError: ``401 unauthorized`` for a missing or wrong token.
    """
    resources = state(request)
    if resources.token is None:
        return
    header = request.headers.get("Authorization", "")
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        credentials.strip().encode(), resources.token.encode()
    ):
        raise unauthorized()


SettingsDep = Annotated[ApiSettings, Depends(settings)]
JobServiceDep = Annotated[JobService, Depends(job_service)]
StoreDep = Annotated[JobStore, Depends(store)]
ReaderDep = Annotated[ArtifactReader, Depends(reader)]
TokenDep = Annotated[None, Depends(require_token)]
