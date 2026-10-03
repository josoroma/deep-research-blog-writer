"""Shared application use cases for the CLI and the HTTP worker.

Modules here own admission and execution policy. They must not import FastAPI
request/response types, psycopg, or any HTTP client; concrete adapters live in
``api/``, ``workers/`` and ``services/``.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from schemas.jobs import JobOperation, JobRecord, JobState

Clock = Callable[[], datetime]


class JobStoreError(RuntimeError):
    """A durable-store failure that is safe to report as an unavailable service."""


class IdempotencyConflict(JobStoreError):
    """The same idempotency key was reused with a different payload."""


class QueueFull(JobStoreError):
    """The bounded submission queue already holds the configured maximum."""


class JobStore(Protocol):
    """A transactional job queue plus its metadata.

    The same table is the queue and the record of truth, so acceptance and
    idempotency agree inside one transaction and there is no broker dual-write gap.
    """

    def enqueue(
        self,
        *,
        operation: JobOperation,
        payload: dict[str, object],
        request_hash: str,
        idempotency_key: str,
        now: datetime,
        queue_limit: int,
    ) -> tuple[JobRecord, bool]:
        """Admit a job. Returns (record, created); an exact replay returns created=False."""
        ...

    def get(self, job_id: str) -> JobRecord | None: ...

    def latest_for_run(self, run_id: str) -> JobRecord | None:
        """The most recent job bound to a run, for status and resume eligibility."""
        ...

    def claim(self, *, worker_identity: str, now: datetime, lease_seconds: int) -> JobRecord | None:
        """Atomically claim one queued or lease-expired job, or return None."""
        ...

    def heartbeat(
        self, *, job_id: str, worker_identity: str, now: datetime, lease_seconds: int
    ) -> bool: ...

    def set_progress(
        self, *, job_id: str, run_id: str | None, phase: str | None, now: datetime
    ) -> JobRecord: ...

    def finish(
        self,
        *,
        job_id: str,
        state: JobState,
        now: datetime,
        run_id: str | None = None,
        phase: str | None = None,
        status_reasons: list[str] | None = None,
        error: str | None = None,
    ) -> JobRecord: ...

    def release(
        self, *, job_id: str, state: JobState, now: datetime, error: str | None = None
    ) -> JobRecord:
        """Return a claimed job to a non-terminal state (used for interrupt)."""
        ...

    def recover_expired(self, *, now: datetime) -> int:
        """Mark lease-expired running jobs interrupted; returns how many changed."""
        ...

    def count_active(self) -> int: ...


class ArtifactReaderPort(Protocol):
    """Authorized, bounded reads under the configured run workspace root."""

    def list_artifacts(self, run_id: str) -> list[dict[str, object]]: ...

    def read_bytes(self, run_id: str, artifact_id: str) -> tuple[str, str, bytes]: ...

    def read_log_page(
        self, run_id: str, *, cursor: int, limit: int
    ) -> tuple[list[dict[str, object]], int | None]: ...
