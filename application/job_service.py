"""Job admission, idempotency, and status queries.

Admission is the only place that turns a client request into durable work. It
enforces server-side budget caps, computes a stable request hash for idempotency,
and rejects submission when the bounded queue is full. No provider or filesystem
work happens here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from application.ports import IdempotencyConflict, JobStore, QueueFull
from schemas.api import SubmissionRequest
from schemas.config import ApiSettings
from schemas.jobs import JobOperation, JobRecord, JobState


class AdmissionError(ValueError):
    """A request that cannot be admitted, with a stable, safe code."""

    def __init__(self, code: str, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


def normalize_payload(request: SubmissionRequest) -> dict[str, object]:
    """A canonical payload used for both storage and the idempotency hash."""
    research = request.to_research_request()
    return {
        "mode": request.mode,
        "topic": research.topic,
        "pages": research.pages,
        "per_page": research.per_page,
        "max_urls": research.max_urls,
    }


def request_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enforce_budget(request: SubmissionRequest, settings: ApiSettings) -> None:
    """Server-side caps win over whatever the client sent."""
    if request.pages > settings.max_pages:
        raise AdmissionError("budget_exceeded", f"pages may not exceed {settings.max_pages}")
    if request.per_page > settings.max_per_page:
        raise AdmissionError("budget_exceeded", f"per_page may not exceed {settings.max_per_page}")
    if request.max_urls > settings.max_max_urls:
        raise AdmissionError("budget_exceeded", f"max_urls may not exceed {settings.max_max_urls}")


class JobService:
    def __init__(
        self, store: JobStore, settings: ApiSettings, *, clock: datetime | None = None
    ) -> None:
        self.store = store
        self.settings = settings
        self._clock = clock or datetime.now(UTC)

    def submit(self, request: SubmissionRequest, *, idempotency_key: str) -> tuple[JobRecord, bool]:
        key = idempotency_key.strip()
        if not key:
            raise AdmissionError("missing_idempotency_key", "Idempotency-Key is required")
        if len(key) > 200:
            raise AdmissionError("invalid_idempotency_key", "Idempotency-Key is too long")
        enforce_budget(request, self.settings)
        payload = normalize_payload(request)
        try:
            return self.store.enqueue(
                operation=request.mode,
                payload=payload,
                request_hash=request_hash(payload),
                idempotency_key=key,
                now=self._clock,
                queue_limit=self.settings.queue_limit,
            )
        except IdempotencyConflict as error:
            raise AdmissionError("idempotency_conflict", str(error)) from error
        except QueueFull as error:
            raise AdmissionError(
                "queue_full", str(error), retry_after=max(1, int(self.settings.worker_poll_seconds))
            ) from error

    def status(self, job_id: str) -> JobRecord | None:
        return self.store.get(job_id)

    def latest_for_run(self, run_id: str) -> JobRecord | None:
        return self.store.latest_for_run(run_id)

    def eligible_for_resume(self, job: JobRecord) -> bool:
        """Only interrupted jobs with an allocated run may be resumed."""
        return job.state == "interrupted" and job.run_id is not None

    def release_for_resume(self, job: JobRecord, *, now: datetime) -> JobRecord:
        """Re-queue an interrupted job so the worker re-claims the same run.

        The run workspace and its immutable sources are preserved; resume never
        allocates a new run id.
        """
        return self.store.release(job_id=job.job_id, state="queued", now=now)

    def ready(self) -> tuple[bool, str]:
        """Readiness: the store must answer and the queue must not be saturated."""
        try:
            active = self.store.count_active()
        except Exception:  # noqa: BLE001 - readiness must never raise
            return False, "store_unavailable"
        if active >= self.settings.queue_limit:
            return False, "queue_saturated"
        return True, "ready"


def terminal_state_for(report_status: str) -> JobState:
    mapping: dict[str, JobState] = {
        "succeeded": "succeeded",
        "degraded": "degraded",
        "failed": "failed",
    }
    if report_status not in mapping:
        raise ValueError(f"Unknown report status: {report_status}")
    return mapping[report_status]


__all__ = [
    "AdmissionError",
    "JobOperation",
    "JobService",
    "enforce_budget",
    "normalize_payload",
    "request_hash",
    "terminal_state_for",
]
