"""Shared application use cases for the CLI and the HTTP worker.

Modules here own admission and execution policy. They must not import FastAPI
request/response types, psycopg, or any HTTP client; concrete adapters live in
``api/``, ``workers/`` and ``services/``.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from schemas.errors import ConflictError, ErrorCategory, LimitExceededError, UnavailableError
from schemas.jobs import JobOperation, JobRecord, JobState

Clock = Callable[[], datetime]


class JobStoreError(UnavailableError):
    """A durable-store failure that is safe to report as an unavailable service."""

    code = "store_unavailable"


class IdempotencyConflict(JobStoreError, ConflictError):
    """The same idempotency key was reused with a different payload."""

    category = ErrorCategory.CONFLICT
    code = "idempotency_conflict"


class QueueFull(JobStoreError, LimitExceededError):
    """The bounded submission queue already holds the configured maximum."""

    category = ErrorCategory.LIMIT_EXCEEDED
    code = "queue_full"


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

    def get(self, job_id: str) -> JobRecord | None:
        """Return the job with this id, or ``None``."""

    def latest_for_run(self, run_id: str) -> JobRecord | None:
        """The most recent job bound to a run, for status and resume eligibility."""

    def claim(self, *, worker_identity: str, now: datetime, lease_seconds: int) -> JobRecord | None:
        """Atomically claim one queued or lease-expired job, or return None."""

    def heartbeat(
        self, *, job_id: str, worker_identity: str, now: datetime, lease_seconds: int
    ) -> bool:
        """Extend the lease; ``False`` when this worker no longer owns the job."""

    def set_progress(
        self, *, job_id: str, run_id: str | None, phase: str | None, now: datetime
    ) -> JobRecord:
        """Record the allocated run id and the current phase."""

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
    ) -> JobRecord:
        """Move a job to a terminal state.

        Raises:
            JobStoreError: For an unknown job or a transition the state machine
                forbids.
        """

    def release(
        self, *, job_id: str, state: JobState, now: datetime, error: str | None = None
    ) -> JobRecord:
        """Return a claimed job to a non-terminal state (used for interrupt)."""

    def recover_expired(self, *, now: datetime) -> int:
        """Mark lease-expired running jobs interrupted; returns how many changed."""

    def count_active(self) -> int:
        """Return how many jobs are queued or running, for admission and readiness."""
