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
from typing import ClassVar

from application.ports import Clock, IdempotencyConflict, JobStore, QueueFull
from schemas.api import SubmissionRequest
from schemas.config import ApiSettings
from schemas.errors import (
    ConflictError,
    ErrorCategory,
    InvalidInputError,
    LimitExceededError,
    ResearchError,
)
from schemas.jobs import JobOperation, JobRecord, JobState

MAX_IDEMPOTENCY_KEY_LENGTH = 200


class AdmissionError(ResearchError, ValueError):
    """Base for every reason a submission is refused, each with a stable code.

    Subclasses fix the category, so transports never inspect ``code`` to choose a
    status. ``retry_after`` is set only when waiting can help.

    Args:
        message: A safe explanation for the client.
        code: Overrides the subclass default for one instance.
        retry_after: Seconds the client should wait before retrying.
    """

    category: ClassVar[ErrorCategory] = ErrorCategory.INVALID_INPUT
    code = "admission_rejected"

    def __init__(  # noqa: D107 - documented on the class
        self, message: str, *, code: str | None = None, retry_after: int | None = None
    ) -> None:
        super().__init__(message, code=code)
        self.retry_after = retry_after


class InvalidSubmission(AdmissionError, InvalidInputError):
    """The submission itself is malformed, such as a missing idempotency key."""

    category = ErrorCategory.INVALID_INPUT
    code = "invalid_submission"


class BudgetExceeded(AdmissionError, LimitExceededError):
    """A requested budget is above the server-side cap."""

    category = ErrorCategory.LIMIT_EXCEEDED
    code = "budget_exceeded"


class SubmissionConflict(AdmissionError, ConflictError):
    """An idempotency key was reused with a different payload."""

    category = ErrorCategory.CONFLICT
    code = "idempotency_conflict"


class QueueSaturated(AdmissionError, LimitExceededError):
    """The bounded queue is full; the client should retry after a delay."""

    category = ErrorCategory.LIMIT_EXCEEDED
    code = "queue_full"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_payload(request: SubmissionRequest) -> dict[str, object]:
    """Build the canonical payload used for both storage and the idempotency hash.

    Args:
        request: The validated submission body.

    Returns:
        A JSON-serializable mapping with the trimmed topic and resolved budgets.
    """
    research = request.to_research_request()
    return {
        "mode": request.mode,
        "topic": research.topic,
        "pages": research.pages,
        "per_page": research.per_page,
        "max_urls": research.max_urls,
    }


def request_hash(payload: dict[str, object]) -> str:
    """Hash a canonical payload so equal requests compare equal across processes.

    Args:
        payload: Output of :func:`normalize_payload`.

    Returns:
        A hex SHA-256 digest of the sorted, compact JSON encoding.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enforce_budget(request: SubmissionRequest, settings: ApiSettings) -> None:
    """Reject budgets above the server caps; the server, not the client, decides.

    Args:
        request: The validated submission body.
        settings: Server settings carrying the caps.

    Raises:
        BudgetExceeded: When pages, per_page, or max_urls is above its cap.
    """
    caps = (
        ("pages", request.pages, settings.max_pages),
        ("per_page", request.per_page, settings.max_per_page),
        ("max_urls", request.max_urls, settings.max_max_urls),
    )
    for name, value, cap in caps:
        if value > cap:
            raise BudgetExceeded(f"{name} may not exceed {cap}")


def validate_idempotency_key(raw: str | None) -> str:
    """Return a trimmed idempotency key, or raise if it is missing or too long.

    Args:
        raw: The header value as received, possibly ``None``.

    Returns:
        The trimmed key.

    Raises:
        InvalidSubmission: When the key is absent, blank, or longer than
            :data:`MAX_IDEMPOTENCY_KEY_LENGTH`.
    """
    key = (raw or "").strip()
    if not key:
        raise InvalidSubmission("Idempotency-Key is required", code="missing_idempotency_key")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise InvalidSubmission("Idempotency-Key is too long", code="invalid_idempotency_key")
    return key


class JobService:
    """Admission and status queries over a :class:`~application.ports.JobStore`.

    Args:
        store: The durable job queue.
        settings: Server caps and queue limits.
        clock: Returns the current UTC time. Called once per operation, so job
            timestamps reflect when each request arrived. Tests pass a fixed
            clock for deterministic records.
    """

    def __init__(  # noqa: D107 - documented on the class
        self, store: JobStore, settings: ApiSettings, *, clock: Clock | None = None
    ) -> None:
        self.store = store
        self.settings = settings
        self._clock: Clock = clock or _utc_now

    def submit(
        self, request: SubmissionRequest, *, idempotency_key: str | None
    ) -> tuple[JobRecord, bool]:
        """Admit a job, or return the original job for an exact replay.

        Args:
            request: The validated submission body.
            idempotency_key: The client's ``Idempotency-Key`` header value.

        Returns:
            ``(record, created)``; ``created`` is ``False`` for a replay.

        Raises:
            InvalidSubmission: When the idempotency key is missing or invalid.
            BudgetExceeded: When a budget is above the server cap.
            SubmissionConflict: When the key was used with a different payload.
            QueueSaturated: When the bounded queue is full.
            JobStoreError: When the store is unreachable.
        """
        key = validate_idempotency_key(idempotency_key)
        enforce_budget(request, self.settings)
        payload = normalize_payload(request)
        try:
            return self.store.enqueue(
                operation=request.mode,
                payload=payload,
                request_hash=request_hash(payload),
                idempotency_key=key,
                now=self._clock(),
                queue_limit=self.settings.queue_limit,
            )
        except IdempotencyConflict as error:
            raise SubmissionConflict(str(error)) from error
        except QueueFull as error:
            retry_after = max(1, int(self.settings.worker_poll_seconds))
            raise QueueSaturated(str(error), retry_after=retry_after) from error

    def status(self, job_id: str) -> JobRecord | None:
        """Return the job, or ``None`` when no job has this id."""
        return self.store.get(job_id)

    def latest_for_run(self, run_id: str) -> JobRecord | None:
        """Return the most recent job bound to ``run_id``, or ``None``."""
        return self.store.latest_for_run(run_id)

    def eligible_for_resume(self, job: JobRecord) -> bool:
        """Only interrupted jobs with an allocated run may be resumed."""
        return job.state == "interrupted" and job.run_id is not None

    def release_for_resume(self, job: JobRecord, *, now: datetime | None = None) -> JobRecord:
        """Re-queue an interrupted job so the worker re-claims the same run.

        The run workspace and its immutable sources are preserved; resume never
        allocates a new run id.

        Args:
            job: An interrupted job with an allocated run.
            now: Overrides the service clock for this call.

        Returns:
            The job record in the ``queued`` state.
        """
        moment = now if now is not None else self._clock()
        return self.store.release(job_id=job.job_id, state="queued", now=moment)

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
    """Map a final report status to the job state that records it.

    Raises:
        ValueError: For a status that no report can produce; this is a bug.
    """
    mapping: dict[str, JobState] = {
        "succeeded": "succeeded",
        "degraded": "degraded",
        "failed": "failed",
    }
    if report_status not in mapping:
        raise ValueError(f"Unknown report status: {report_status}")
    return mapping[report_status]


__all__ = [
    "MAX_IDEMPOTENCY_KEY_LENGTH",
    "AdmissionError",
    "BudgetExceeded",
    "InvalidSubmission",
    "JobOperation",
    "JobService",
    "QueueSaturated",
    "SubmissionConflict",
    "enforce_budget",
    "normalize_payload",
    "request_hash",
    "terminal_state_for",
    "validate_idempotency_key",
]
