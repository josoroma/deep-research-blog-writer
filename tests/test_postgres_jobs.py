"""PostgreSQL job store adapter, exercised through a fake connection.

These tests validate the store's SQL shape, transition rules, and idempotency
handling without a live database. Real database claim/constraint behavior runs as
an explicit integration command outside the offline suite (see the runbook).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from application.ports import IdempotencyConflict, JobStoreError, QueueFull
from services import postgres_jobs
from services.postgres_jobs import PostgresJobStore

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "job_id": "11111111-1111-1111-1111-111111111111",
        "operation": "research",
        "state": "queued",
        "request_hash": "hash",
        "idempotency_key": "key",
        "payload": {"topic": "telemetry quality"},
        "run_id": None,
        "phase": None,
        "attempt": 0,
        "worker_identity": None,
        "lease_expires_at": None,
        "heartbeat_at": None,
        "status_reasons": [],
        "error": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(overrides)
    return row


class _Cursor:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection
        self._result: dict[str, Any] | None = None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _Cursor:
        normalized = " ".join(sql.split())
        self.connection.statements.append((normalized, params))
        for canned in self.connection.responses:
            if canned[0] in normalized:
                self._result = canned[1]
                return self
        self._result = None
        return self

    def fetchone(self) -> dict[str, Any] | None:
        return self._result

    def fetchall(self) -> list[dict[str, Any]]:
        return self._result if isinstance(self._result, list) else []


class _Transaction:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[Any, ...]]] = []
        self.responses: list[tuple[str, Any]] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _Cursor:
        return _Cursor(self).execute(sql, params)

    def transaction(self) -> _Transaction:
        return _Transaction()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        pass


class _FakePsycopg:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def connect(self, *args: object, **kwargs: object) -> _Connection:
        del args, kwargs
        return self.connection

    Error = Exception


def _store(monkeypatch: pytest.MonkeyPatch, connection: _Connection) -> PostgresJobStore:
    monkeypatch.setattr(postgres_jobs, "psycopg", _FakePsycopg(connection))
    return PostgresJobStore("postgresql://example/db")


def test_enqueue_inserts_and_returns_created(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("INSERT INTO jobs", _row())]
    store = _store(monkeypatch, connection)
    record, created = store.enqueue(
        operation="research",
        payload={"topic": "telemetry quality"},
        request_hash="hash",
        idempotency_key="key",
        now=NOW,
        queue_limit=10,
    )
    assert created is True
    assert record.job_id == "11111111-1111-1111-1111-111111111111"


def test_enqueue_returns_existing_on_exact_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("SELECT", _row())]
    store = _store(monkeypatch, connection)
    record, created = store.enqueue(
        operation="research",
        payload={"topic": "telemetry quality"},
        request_hash="hash",
        idempotency_key="key",
        now=NOW,
        queue_limit=10,
    )
    assert created is False
    assert record.request_hash == "hash"


def test_enqueue_conflicts_on_changed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("SELECT", _row(request_hash="different"))]
    store = _store(monkeypatch, connection)
    with pytest.raises(IdempotencyConflict):
        store.enqueue(
            operation="research",
            payload={"topic": "telemetry quality"},
            request_hash="hash",
            idempotency_key="key",
            now=NOW,
            queue_limit=10,
        )


def test_enqueue_rejects_a_full_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("FOR UPDATE", None), ("count(*)", {"n": 5})]
    store = _store(monkeypatch, connection)
    with pytest.raises(QueueFull):
        store.enqueue(
            operation="research",
            payload={"topic": "telemetry quality"},
            request_hash="hash",
            idempotency_key="key",
            now=NOW,
            queue_limit=5,
        )


def test_claim_uses_skip_locked_and_bumps_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    claimed = _row(state="running", attempt=1, worker_identity="w1")
    connection.responses = [("FOR UPDATE SKIP LOCKED", _row()), ("UPDATE jobs", claimed)]
    store = _store(monkeypatch, connection)
    record = store.claim(worker_identity="w1", now=NOW, lease_seconds=30)
    assert record is not None and record.attempt == 1 and record.state == "running"
    assert any("FOR UPDATE SKIP LOCKED" in sql for sql, _ in connection.statements)


def test_claim_returns_none_when_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("FOR UPDATE SKIP LOCKED", None)]
    store = _store(monkeypatch, connection)
    assert store.claim(worker_identity="w1", now=NOW, lease_seconds=30) is None


def test_heartbeat_returns_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("UPDATE jobs", {"job_id": "id"})]
    store = _store(monkeypatch, connection)
    assert store.heartbeat(job_id="id", worker_identity="w1", now=NOW, lease_seconds=30) is True
    connection.responses = [("UPDATE jobs", None)]
    assert store.heartbeat(job_id="id", worker_identity="w1", now=NOW, lease_seconds=30) is False


def test_get_and_latest_for_run(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("WHERE job_id = %s", _row())]
    store = _store(monkeypatch, connection)
    assert store.get("id") is not None
    connection.responses = [("WHERE run_id = %s", _row(run_id="run-1"))]
    latest = store.latest_for_run("run-1")
    assert latest is not None and latest.run_id == "run-1"


def test_count_active(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("count(*)", {"n": 3})]
    store = _store(monkeypatch, connection)
    assert store.count_active() == 3


def test_finish_enforces_transitions(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [
        ("WHERE job_id = %s FOR UPDATE", _row(state="running")),
        ("UPDATE jobs", _row(state="succeeded")),
    ]
    store = _store(monkeypatch, connection)
    finished = store.finish(job_id="id", state="succeeded", now=NOW)
    assert finished.state == "succeeded"

    connection.responses = [
        ("WHERE job_id = %s FOR UPDATE", _row(state="succeeded")),
        ("UPDATE jobs", _row(state="running")),
    ]
    with pytest.raises(JobStoreError):
        store.finish(job_id="id", state="running", now=NOW)


def test_finish_unknown_job_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("WHERE job_id = %s FOR UPDATE", None)]
    store = _store(monkeypatch, connection)
    with pytest.raises(JobStoreError):
        store.finish(job_id="missing", state="succeeded", now=NOW)


def test_release_and_set_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [
        ("WHERE job_id = %s FOR UPDATE", _row(state="running")),
        ("UPDATE jobs", _row(state="queued")),
    ]
    store = _store(monkeypatch, connection)
    assert store.release(job_id="id", state="queued", now=NOW).state == "queued"

    connection.responses = [("UPDATE jobs", _row(run_id="run-1", phase="write"))]
    progress = store.set_progress(job_id="id", run_id="run-1", phase="write", now=NOW)
    assert progress.run_id == "run-1" and progress.phase == "write"


def test_recover_expired_counts_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    connection.responses = [("lease_expires_at <= %s", [{"job_id": "a"}, {"job_id": "b"}])]
    store = _store(monkeypatch, connection)
    assert store.recover_expired(now=NOW + timedelta(seconds=120)) == 2


def test_connect_failure_is_a_store_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Broken:
        Error = Exception

        def connect(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("no database")

    monkeypatch.setattr(postgres_jobs, "psycopg", _Broken())
    store = PostgresJobStore("postgresql://example/db")
    with pytest.raises(JobStoreError):
        store.count_active()
