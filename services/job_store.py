"""In-memory job store implementing the application's ``JobStore`` port.

This is the reference implementation of the queue semantics: idempotency, a
bounded queue, transactional claim, lease expiry and legal transitions. It backs
offline tests and the fixture profile. The PostgreSQL adapter mirrors it exactly.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from uuid import uuid4

from application.ports import IdempotencyConflict, JobStoreError, QueueFull
from schemas.jobs import JobOperation, JobRecord, JobState, transition_allowed


class MemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._by_key: dict[str, str] = {}
        self._lock = threading.RLock()

    # -- reads -----------------------------------------------------------------
    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def latest_for_run(self, run_id: str) -> JobRecord | None:
        with self._lock:
            matches = [job for job in self._jobs.values() if job.run_id == run_id]
        if not matches:
            return None
        return max(matches, key=lambda job: job.updated_at)

    def count_active(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if not job.terminal)

    def _active(self) -> list[JobRecord]:
        return [job for job in self._jobs.values() if job.state == "queued"]

    # -- admission -------------------------------------------------------------
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
        with self._lock:
            existing_id = self._by_key.get(idempotency_key)
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "Idempotency-Key was reused with a different request payload"
                    )
                return existing, False
            if len(self._active()) >= queue_limit:
                raise QueueFull("Submission queue is full")
            job_id = str(uuid4())
            record = JobRecord(
                job_id=job_id,
                operation=operation,
                state="queued",
                request_hash=request_hash,
                idempotency_key=idempotency_key,
                payload=dict(payload),
                created_at=now,
                updated_at=now,
            )
            self._jobs[job_id] = record
            self._by_key[idempotency_key] = job_id
            return record, True

    # -- worker lifecycle ------------------------------------------------------
    def claim(self, *, worker_identity: str, now: datetime, lease_seconds: int) -> JobRecord | None:
        with self._lock:
            for job in sorted(self._jobs.values(), key=lambda item: item.created_at):
                if job.state == "queued" or (
                    job.state == "running"
                    and (job.lease_expires_at is None or job.lease_expires_at <= now)
                ):
                    return self._renew(
                        job, worker_identity=worker_identity, now=now, lease_seconds=lease_seconds
                    )
            return None

    def heartbeat(
        self, *, job_id: str, worker_identity: str, now: datetime, lease_seconds: int
    ) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.worker_identity != worker_identity or job.state != "running":
                return False
            self._renew(job, worker_identity=worker_identity, now=now, lease_seconds=lease_seconds)
            return True

    def _renew(
        self, job: JobRecord, *, worker_identity: str, now: datetime, lease_seconds: int
    ) -> JobRecord:
        updated = job.model_copy(
            update={
                "state": "running",
                "worker_identity": worker_identity,
                "attempt": job.attempt + 1,
                "heartbeat_at": now,
                "lease_expires_at": now + timedelta(seconds=lease_seconds),
                "updated_at": now,
            }
        )
        self._jobs[job.job_id] = updated
        return updated

    def set_progress(
        self, *, job_id: str, run_id: str | None, phase: str | None, now: datetime
    ) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            updated = job.model_copy(update={"run_id": run_id, "phase": phase, "updated_at": now})
            self._jobs[job_id] = updated
            return updated

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
        return self._transition(
            job_id,
            state,
            now=now,
            run_id=run_id,
            phase=phase,
            status_reasons=status_reasons,
            error=error,
        )

    def release(
        self, *, job_id: str, state: JobState, now: datetime, error: str | None = None
    ) -> JobRecord:
        return self._transition(job_id, state, now=now, error=error)

    def _transition(
        self,
        job_id: str,
        state: JobState,
        *,
        now: datetime,
        run_id: str | None = None,
        phase: str | None = None,
        status_reasons: list[str] | None = None,
        error: str | None = None,
    ) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            if not transition_allowed(job.state, state):
                raise JobStoreError(f"Illegal job transition {job.state} -> {state}")
            updated = job.model_copy(
                update={
                    "state": state,
                    "run_id": run_id if run_id is not None else job.run_id,
                    "phase": phase if phase is not None else job.phase,
                    "status_reasons": status_reasons
                    if status_reasons is not None
                    else job.status_reasons,
                    "error": error,
                    "lease_expires_at": None,
                    "heartbeat_at": None,
                    "updated_at": now,
                }
            )
            self._jobs[job_id] = updated
            return updated

    def recover_expired(self, *, now: datetime) -> int:
        changed = 0
        with self._lock:
            for job in list(self._jobs.values()):
                if (
                    job.state == "running"
                    and job.lease_expires_at is not None
                    and job.lease_expires_at <= now
                ):
                    self._jobs[job.job_id] = job.model_copy(
                        update={
                            "state": "interrupted",
                            "error": "worker_lease_expired",
                            "lease_expires_at": None,
                            "updated_at": now,
                        }
                    )
                    changed += 1
        return changed
