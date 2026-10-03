"""Durable job records and their state machine (server submission).

A job is the operator's acceptance of work. It is distinct from a run: a job may
be queued or interrupted while no run workspace exists yet, and a graph checkpoint
is not proof that a job was ever accepted (see the migration plan).

These records are stored by ``services.postgres_jobs`` and by the in-memory store
used in offline tests. They intentionally contain no provider secrets: the stored
payload is the validated request only.
"""

from typing import Any, Literal

from pydantic import AwareDatetime, Field

from schemas.common import Contract

JobOperation = Literal["search", "research"]
JobState = Literal["queued", "running", "succeeded", "degraded", "failed", "interrupted"]

TERMINAL_STATES: frozenset[str] = frozenset({"succeeded", "degraded", "failed"})
ACTIVE_STATES: frozenset[str] = frozenset({"queued", "running", "interrupted"})

# Only these transitions are valid; anything else is a conflict, not a silent write.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "interrupted", "failed"}),
    "running": frozenset({"succeeded", "degraded", "failed", "interrupted", "queued"}),
    "interrupted": frozenset({"running", "queued", "failed"}),
    "succeeded": frozenset(),
    "degraded": frozenset(),
    "failed": frozenset(),
}


def transition_allowed(current: JobState, target: JobState) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


class JobRecord(Contract):
    """One accepted job. ``payload`` is the validated request, never a secret."""

    job_id: str = Field(min_length=1)
    operation: JobOperation
    state: JobState
    request_hash: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None
    phase: str | None = None
    attempt: int = Field(default=0, ge=0)
    worker_identity: str | None = None
    lease_expires_at: AwareDatetime | None = None
    heartbeat_at: AwareDatetime | None = None
    status_reasons: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_STATES
