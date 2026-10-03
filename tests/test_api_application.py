"""M1/M2: shared application boundary, job admission, and settings profiles."""

from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest

from application.job_service import (
    AdmissionError,
    JobService,
    enforce_budget,
    normalize_payload,
    request_hash,
)
from application.migrations import (
    MigrationError,
    _split_statements,
    apply_migrations,
    discover,
)
from application.ports import JobStoreError
from schemas.api import SubmissionRequest
from schemas.config import ApiSettings, run_settings_for_api
from schemas.jobs import transition_allowed
from services.job_store import MemoryJobStore

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _api(
    *,
    run_profile: Literal["production", "fixture"] = "fixture",
    queue_limit: int = 100,
    max_pages: int = 3,
    max_per_page: int = 10,
    max_max_urls: int = 30,
) -> ApiSettings:
    return ApiSettings(
        _env_file=None,
        run_profile=run_profile,
        queue_limit=queue_limit,
        max_pages=max_pages,
        max_per_page=max_per_page,
        max_max_urls=max_max_urls,
    )


def _submit(**overrides: object) -> SubmissionRequest:
    payload: dict[str, object] = {
        "mode": "research",
        "topic": "telemetry quality",
        "pages": 1,
        "per_page": 10,
        "max_urls": 5,
    }
    payload.update(overrides)
    return SubmissionRequest(**payload)  # type: ignore[arg-type]


def test_api_settings_defaults_and_secret_masking() -> None:
    settings = ApiSettings(_env_file=None, database="postgresql://user:pass@host/db", token="abc")
    assert settings.queue_limit > 0
    assert settings.database_dsn() == "postgresql://user:pass@host/db"
    assert settings.bearer_token() == "abc"
    assert "pass" not in repr(settings)
    assert settings.origins == []


def test_api_settings_parses_origin_list() -> None:
    settings = ApiSettings(_env_file=None, allowed_origins="https://a.test, https://b.test ")
    assert settings.origins == ["https://a.test", "https://b.test"]


def test_run_settings_for_api_uses_a_separate_root() -> None:
    settings = ApiSettings(_env_file=None, runs_dir="runs-api")
    resolved = run_settings_for_api(settings)
    assert resolved.runs_dir == "runs-api"


def test_domain_settings_have_no_fastapi_import() -> None:
    import application.job_service as module

    source = module.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()
    assert "fastapi" not in text


def test_budget_caps_reject_oversized_requests() -> None:
    settings = _api(max_pages=2, max_per_page=10, max_max_urls=20)
    with pytest.raises(AdmissionError, match="pages"):
        enforce_budget(_submit(pages=3), settings)
    with pytest.raises(AdmissionError, match="max_urls"):
        enforce_budget(_submit(max_urls=21), settings)
    enforce_budget(_submit(pages=2, max_urls=20), settings)


def test_request_hash_is_stable_and_payload_specific() -> None:
    first = normalize_payload(_submit())
    second = normalize_payload(_submit())
    assert request_hash(first) == request_hash(second)
    assert request_hash(normalize_payload(_submit(topic="another topic"))) != request_hash(first)


def test_submission_is_idempotent_and_conflicts_on_change() -> None:
    store = MemoryJobStore()
    service = JobService(store, _api(), clock=NOW)
    record, created = service.submit(_submit(), idempotency_key="k1")
    assert created
    replay, created_again = service.submit(_submit(), idempotency_key="k1")
    assert not created_again
    assert replay.job_id == record.job_id
    with pytest.raises(AdmissionError) as error:
        service.submit(_submit(topic="different topic"), idempotency_key="k1")
    assert error.value.code == "idempotency_conflict"


def test_submission_requires_an_idempotency_key() -> None:
    service = JobService(MemoryJobStore(), _api(), clock=NOW)
    with pytest.raises(AdmissionError) as error:
        service.submit(_submit(), idempotency_key="   ")
    assert error.value.code == "missing_idempotency_key"


def test_bounded_queue_rejects_when_full() -> None:
    store = MemoryJobStore()
    service = JobService(store, _api(queue_limit=1), clock=NOW)
    service.submit(_submit(), idempotency_key="a")
    with pytest.raises(AdmissionError) as error:
        service.submit(_submit(topic="second topic"), idempotency_key="b")
    assert error.value.code == "queue_full"


def test_claim_renews_and_recovers_expired_leases() -> None:
    store = MemoryJobStore()
    service = JobService(store, _api(), clock=NOW)
    record, _ = service.submit(_submit(), idempotency_key="a")
    claimed = store.claim(worker_identity="w1", now=NOW, lease_seconds=30)
    assert claimed is not None and claimed.state == "running" and claimed.attempt == 1
    wrong_worker = store.heartbeat(
        job_id=record.job_id, worker_identity="w2", now=NOW, lease_seconds=30
    )
    assert wrong_worker is False
    assert store.heartbeat(job_id=record.job_id, worker_identity="w1", now=NOW, lease_seconds=30)
    changed = store.recover_expired(now=NOW + timedelta(seconds=120))
    assert changed == 1
    assert store.get(record.job_id).state == "interrupted"  # type: ignore[union-attr]


def test_latest_for_run_and_resume_release() -> None:
    store = MemoryJobStore()
    service = JobService(store, _api(), clock=NOW)
    record, _ = service.submit(_submit(), idempotency_key="a")
    store.claim(worker_identity="w1", now=NOW, lease_seconds=1)
    store.release(job_id=record.job_id, state="interrupted", now=NOW)
    store.set_progress(job_id=record.job_id, run_id="run-1", phase="write", now=NOW)
    latest = service.latest_for_run("run-1")
    assert latest is not None and latest.job_id == record.job_id
    assert service.eligible_for_resume(latest)
    released = service.release_for_resume(latest, now=NOW)
    assert released.state == "queued"


def test_illegal_transition_is_rejected() -> None:
    assert not transition_allowed("succeeded", "running")
    assert transition_allowed("queued", "running")
    store = MemoryJobStore()
    service = JobService(store, _api(), clock=NOW)
    record, _ = service.submit(_submit(), idempotency_key="a")
    store.claim(worker_identity="w1", now=NOW, lease_seconds=30)
    store.finish(job_id=record.job_id, state="succeeded", now=NOW)
    with pytest.raises(JobStoreError):
        store.finish(job_id=record.job_id, state="running", now=NOW)


def test_ready_reports_queue_saturation() -> None:
    store = MemoryJobStore()
    service = JobService(store, _api(queue_limit=1), clock=NOW)
    assert service.ready() == (True, "ready")
    service.submit(_submit(), idempotency_key="a")
    assert service.ready() == (False, "queue_saturated")


def test_job_record_terminal_flag() -> None:
    store = MemoryJobStore()
    record, _ = JobService(store, _api(), clock=NOW).submit(_submit(), idempotency_key="a")
    assert record.terminal is False
    store.claim(worker_identity="w1", now=NOW, lease_seconds=30)
    finished = store.finish(job_id=record.job_id, state="degraded", now=NOW)
    assert finished.terminal is True


class _RecordingCursor:
    def __init__(self, log: list[str], applied: dict[str, str]) -> None:
        self.log = log
        self.applied = applied
        self.rows: list[tuple[str, str]] = []

    def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
        self.log.append(" ".join(sql.split()))
        if params is not None and "INSERT INTO schema_migrations" in sql:
            self.applied[str(params[0])] = str(params[1])
        if "SELECT version, checksum FROM schema_migrations" in sql:
            self.rows = sorted(self.applied.items())

    def fetchall(self) -> list[tuple[str, str]]:
        return self.rows


class _RecordingConnection:
    def __init__(self, applied: dict[str, str] | None = None) -> None:
        self.log: list[str] = []
        self.applied = applied if applied is not None else {}

    def cursor(self) -> _RecordingCursor:
        return _RecordingCursor(self.log, self.applied)

    def commit(self) -> None:
        self.log.append("COMMIT")

    def rollback(self) -> None:
        self.log.append("ROLLBACK")


def test_migration_discovery_is_ordered_and_checksummed() -> None:
    migrations = discover()
    assert [migration.version for migration in migrations] == sorted(
        migration.version for migration in migrations
    )
    assert all(len(migration.checksum) == 64 for migration in migrations)


def test_apply_migrations_is_idempotent_with_a_fake_connection() -> None:
    connection = _RecordingConnection()
    first = apply_migrations(connection)
    assert first
    second = apply_migrations(connection)
    assert second == []


def test_migration_checksum_drift_is_detected() -> None:
    connection = _RecordingConnection(applied={"0001": "stale-checksum"})
    with pytest.raises(MigrationError):
        apply_migrations(connection)


def test_split_statements_splits_on_semicolons() -> None:
    statements = _split_statements("CREATE TABLE a (id int);\n\nCREATE INDEX b ON a (id);")
    assert len(statements) == 2


def test_split_statements_ignores_semicolons_inside_comments() -> None:
    sql = "-- keep it an index-only walk; this semicolon is prose\nCREATE INDEX b ON a (id);"
    statements = _split_statements(sql)
    assert len(statements) == 1
    assert statements[0].startswith("CREATE INDEX")
