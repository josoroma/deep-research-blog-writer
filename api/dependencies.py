"""App-state dependencies: settings, stores, reader and bearer authentication.

Everything is created once in the lifespan. These callables only read
``request.app.state``, so importing an API module never opens a connection or
contacts a provider. Annotated aliases keep the FastAPI dependency wiring typed
without calling ``Depends`` in argument defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from api.errors import ApiError
from application.job_service import JobService
from application.ports import JobStore
from schemas.config import ApiSettings
from services.artifact_reader import ArtifactReader


@dataclass
class AppState:
    settings: ApiSettings
    store: JobStore
    jobs: JobService
    reader: ArtifactReader
    token: str | None
    store_ready: bool
    store_reason: str


def state(request: Request) -> AppState:
    resolved: AppState = request.app.state.resources
    return resolved


def settings(request: Request) -> ApiSettings:
    return state(request).settings


def job_service(request: Request) -> JobService:
    return state(request).jobs


def store(request: Request) -> JobStore:
    return state(request).store


def reader(request: Request) -> ArtifactReader:
    return state(request).reader


async def require_token(request: Request) -> None:
    """Enforce the shared bearer token when one is configured.

    Loopback development with no token is allowed; any non-empty configured token
    is required for every business endpoint.
    """
    resources = state(request)
    if resources.token is None:
        return
    header = request.headers.get("Authorization", "")
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() != "bearer" or credentials.strip() != resources.token:
        raise ApiError(401, "unauthorized", "A valid bearer token is required")


SettingsDep = Annotated[ApiSettings, Depends(settings)]
JobServiceDep = Annotated[JobService, Depends(job_service)]
StoreDep = Annotated[JobStore, Depends(store)]
ReaderDep = Annotated[ArtifactReader, Depends(reader)]
TokenDep = Annotated[None, Depends(require_token)]
