"""PostgreSQL adapter for the application's ``JobStore`` port.

The jobs table is the queue. Claiming uses ``FOR UPDATE SKIP LOCKED`` so two
workers never take the same row, and every transition is validated in the same
transaction that writes it. Connections are short-lived per operation; the store
holds only the DSN, never an open pool across requests.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from application.ports import IdempotencyConflict, JobStoreError, QueueFull
from schemas.jobs import JobOperation, JobRecord, JobState, transition_allowed


def _record_from_row(row: dict[str, Any]) -> JobRecord:
    payload = row["payload"]
    reasons = row["status_reasons"]
    return JobRecord(
        job_id=str(row["job_id"]),
        operation=row["operation"],
        state=row["state"],
        request_hash=row["request_hash"],
        idempotency_key=row["idempotency_key"],
        payload=payload if isinstance(payload, dict) else json.loads(payload or "{}"),
        run_id=row["run_id"],
        phase=row["phase"],
        attempt=row["attempt"],
        worker_identity=row["worker_identity"],
        lease_expires_at=row["lease_expires_at"],
        heartbeat_at=row["heartbeat_at"],
        status_reasons=list(reasons) if reasons else [],
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_COLUMNS = (
    "job_id, operation, state, request_hash, idempotency_key, payload, run_id, phase, "
    "attempt, worker_identity, lease_expires_at, heartbeat_at, status_reasons, error, "
    "created_at, updated_at"
)


class PostgresJobStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        try:
            connection = psycopg.connect(self.dsn, row_factory=dict_row)
        except psycopg.Error as error:  # pragma: no cover - requires a live database
            raise JobStoreError("Database is unavailable") from error
        try:
            yield connection
        finally:
            connection.close()

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
        with self._connect() as connection, connection.transaction():
            found = connection.execute(
                f"SELECT {_COLUMNS} FROM jobs WHERE idempotency_key = %s FOR UPDATE",
                (idempotency_key,),
            ).fetchone()
            if found is not None:
                existing = _record_from_row(found)
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "Idempotency-Key was reused with a different request payload"
                    )
                return existing, False
            active = connection.execute(
                "SELECT count(*) AS n FROM jobs WHERE state IN ('queued', 'running', 'interrupted')"
            ).fetchone()
            if active is not None and int(active["n"]) >= queue_limit:
                raise QueueFull("Submission queue is full")
            job_id = str(uuid4())
            row = connection.execute(
                f"""
                INSERT INTO jobs (
                    job_id, operation, state, request_hash, idempotency_key, payload,
                    created_at, updated_at
                ) VALUES (%s, %s, 'queued', %s, %s, %s, %s, %s)
                RETURNING {_COLUMNS}
                """,
                (job_id, operation, request_hash, idempotency_key, json.dumps(payload), now, now),
            ).fetchone()
            assert row is not None
            return _record_from_row(row), True

    # -- reads -----------------------------------------------------------------
    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM jobs WHERE job_id = %s", (job_id,)
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    def count_active(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT count(*) AS n FROM jobs WHERE state IN ('queued', 'running', 'interrupted')"
            ).fetchone()
        return int(row["n"]) if row is not None else 0

    def latest_for_run(self, run_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM jobs WHERE run_id = %s ORDER BY updated_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    # -- claiming --------------------------------------------------------------
    def claim(self, *, worker_identity: str, now: datetime, lease_seconds: int) -> JobRecord | None:
        deadline = now + timedelta(seconds=lease_seconds)
        with self._connect() as connection, connection.transaction():
            row = connection.execute(
                f"""
                SELECT {_COLUMNS} FROM jobs
                WHERE state = 'queued'
                   OR (state = 'running' AND lease_expires_at IS NOT NULL
                       AND lease_expires_at <= %s)
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                return None
            claimable = _record_from_row(row)
            if not transition_allowed(claimable.state, "running"):
                raise JobStoreError(f"Illegal job transition {claimable.state} -> running")
            updated = connection.execute(
                f"""
                UPDATE jobs
                SET state = 'running', worker_identity = %s, attempt = attempt + 1,
                    heartbeat_at = %s, lease_expires_at = %s, updated_at = %s
                WHERE job_id = %s
                RETURNING {_COLUMNS}
                """,
                (worker_identity, now, deadline, now, claimable.job_id),
            ).fetchone()
            assert updated is not None
            return _record_from_row(updated)

    def heartbeat(
        self, *, job_id: str, worker_identity: str, now: datetime, lease_seconds: int
    ) -> bool:
        deadline = now + timedelta(seconds=lease_seconds)
        with self._connect() as connection, connection.transaction():
            row = connection.execute(
                """
                UPDATE jobs
                SET heartbeat_at = %s, lease_expires_at = %s, updated_at = %s
                WHERE job_id = %s AND worker_identity = %s AND state = 'running'
                RETURNING job_id
                """,
                (now, deadline, now, job_id, worker_identity),
            ).fetchone()
        return row is not None

    # -- transitions -----------------------------------------------------------
    def set_progress(
        self, *, job_id: str, run_id: str | None, phase: str | None, now: datetime
    ) -> JobRecord:
        with self._connect() as connection, connection.transaction():
            row = connection.execute(
                f"""
                UPDATE jobs SET run_id = %s, phase = %s, updated_at = %s
                WHERE job_id = %s
                RETURNING {_COLUMNS}
                """,
                (run_id, phase, now, job_id),
            ).fetchone()
            assert row is not None
            return _record_from_row(row)

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
        with self._connect() as connection, connection.transaction():
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM jobs WHERE job_id = %s FOR UPDATE", (job_id,)
            ).fetchone()
            if row is None:
                raise JobStoreError(f"Unknown job: {job_id}")
            current = _record_from_row(row)
            if not transition_allowed(current.state, state):
                raise JobStoreError(f"Illegal job transition {current.state} -> {state}")
            effective_reasons = (
                status_reasons if status_reasons is not None else current.status_reasons
            )
            updated = connection.execute(
                f"""
                UPDATE jobs
                SET state = %s,
                    run_id = COALESCE(%s, run_id),
                    phase = COALESCE(%s, phase),
                    status_reasons = %s,
                    error = %s,
                    lease_expires_at = NULL,
                    heartbeat_at = NULL,
                    updated_at = %s
                WHERE job_id = %s
                RETURNING {_COLUMNS}
                """,
                (
                    state,
                    run_id,
                    phase,
                    json.dumps(effective_reasons),
                    error,
                    now,
                    job_id,
                ),
            ).fetchone()
            assert updated is not None
            return _record_from_row(updated)

    def recover_expired(self, *, now: datetime) -> int:
        with self._connect() as connection, connection.transaction():
            rows = connection.execute(
                """
                UPDATE jobs
                SET state = 'interrupted', error = 'worker_lease_expired',
                    lease_expires_at = NULL, updated_at = %s
                WHERE state = 'running' AND lease_expires_at IS NOT NULL
                  AND lease_expires_at <= %s
                RETURNING job_id
                """,
                (now, now),
            ).fetchall()
        return len(rows)
