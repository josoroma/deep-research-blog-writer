"""M2-M5: the HTTP contract, safe errors, and the worker read path."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from schemas.config import ApiSettings, RunSettings
from services.job_store import MemoryJobStore
from workers.research_worker import ResearchWorker

SUBMIT = {
    "mode": "research",
    "topic": "Research telemetry quality",
    "pages": 1,
    "per_page": 10,
    "max_urls": 3,
}


def _settings(
    tmp_path: Path,
    *,
    run_profile: Literal["production", "fixture"] = "fixture",
    queue_limit: int | None = None,
    max_max_urls: int | None = None,
    token: str | None = None,
) -> ApiSettings:
    return ApiSettings(
        _env_file=None,
        run_profile=run_profile,
        runs_dir=str(tmp_path / "runs"),
        queue_limit=queue_limit if queue_limit is not None else 100,
        max_max_urls=max_max_urls if max_max_urls is not None else 30,
        token=token,
    )


def _worker_settings(tmp_path: Path) -> RunSettings:
    """Clean run settings so the offline suite never reads a developer .env."""
    return RunSettings(_env_file=None, runs_dir=str(tmp_path / "runs"))


def _client(settings: ApiSettings) -> tuple[TestClient, MemoryJobStore, ResearchWorker]:
    store = MemoryJobStore()
    app = create_app(settings, store=store)
    worker = ResearchWorker(
        store,
        settings,
        identity="http-test-worker",
        runs_root=Path(settings.runs_dir),
        settings=RunSettings(_env_file=None, runs_dir=settings.runs_dir),
        once=True,
    )
    return TestClient(app), store, worker


def test_app_import_has_no_side_effects(tmp_path: Path) -> None:
    runs_dir = tmp_path / "untouched"
    settings = ApiSettings(_env_file=None, run_profile="fixture", runs_dir=str(runs_dir))
    app = create_app(settings)
    assert app.title
    # Creating the app must not create run directories or contact providers.
    assert not runs_dir.exists()


def test_health_live_and_ready(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/health/ready").status_code == 200


def test_readiness_reports_missing_database(tmp_path: Path) -> None:
    settings = ApiSettings(
        _env_file=None, run_profile="production", runs_dir=str(tmp_path / "runs")
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["reason"] == "database_not_configured"


def test_submit_returns_202_with_location_and_no_run_yet(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        response = client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["run_id"] is None
    assert response.headers["location"] == f"/v1/jobs/{body['job_id']}"


def test_idempotent_replay_returns_the_same_job(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        first = client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
        second = client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]


def test_changed_payload_conflicts(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
        changed = client.post(
            "/v1/runs",
            json={**SUBMIT, "topic": "A different topic"},
            headers={"Idempotency-Key": "k1"},
        )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_conflict"


def test_submission_requires_an_idempotency_key(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        response = client.post("/v1/runs", json=SUBMIT)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "missing_idempotency_key"


def test_admission_enforces_server_budget(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path, max_max_urls=2))
    with client:
        response = client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "budget_exceeded"


def test_queue_full_returns_429_with_retry_after(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path, queue_limit=1))
    with client:
        client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
        response = client.post(
            "/v1/runs", json={**SUBMIT, "topic": "Second topic"}, headers={"Idempotency-Key": "k2"}
        )
    assert response.status_code == 429
    assert response.headers["retry-after"]


def test_unknown_job_is_404_with_an_envelope(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        response = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "not_found"
    assert body["request_id"]


def test_request_id_is_echoed_or_generated(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        echoed = client.get("/health/live", headers={"X-Request-ID": "abc-123"})
        generated = client.get("/health/live")
    assert echoed.headers["x-request-id"] == "abc-123"
    assert generated.headers["x-request-id"]


def test_validation_error_is_422(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        response = client.post("/v1/runs", json={"topic": "x"}, headers={"Idempotency-Key": "k1"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_bearer_token_is_enforced_when_configured(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path, token="s3cret"))
    with client:
        assert client.get("/v1/runs").status_code == 401
        assert client.get("/v1/runs", headers={"Authorization": "Bearer wrong"}).status_code == 401
        ok = client.get("/v1/runs", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


def test_worker_no_op_when_the_queue_is_empty(tmp_path: Path) -> None:
    client, _, worker = _client(_settings(tmp_path))
    with client:
        assert worker.run_once() is None


def test_full_fixture_run_through_http(tmp_path: Path) -> None:
    client, store, worker = _client(_settings(tmp_path))
    with client:
        accepted = client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
        job_id = accepted.json()["job_id"]
        outcome = worker.run_once()
        assert outcome is not None and outcome.state == "succeeded"
        status = client.get(f"/v1/jobs/{job_id}").json()
        assert status["status"] == "succeeded"
        assert status["run_id"]
        run_id = status["run_id"]

        report = client.get(f"/v1/runs/{run_id}/report")
        assert report.status_code == 200
        assert report.json()["report"]["status"] == "succeeded"

        run_status = client.get(f"/v1/runs/{run_id}").json()
        assert run_status["report_available"] is True
        assert "report" in run_status["completed_phases"]

        artifacts = client.get(f"/v1/runs/{run_id}/artifacts").json()["artifacts"]
        ids = {entry["artifact_id"] for entry in artifacts}
        assert "output/blog.md" in ids and "output/run.json" in ids

        blog = client.get(f"/v1/runs/{run_id}/artifacts/output/blog.md")
        assert blog.status_code == 200
        assert "attachment" in blog.headers["content-disposition"]

        logs = client.get(f"/v1/runs/{run_id}/logs", params={"limit": 3}).json()
        assert len(logs["records"]) <= 3

        runs = client.get("/v1/runs").json()["runs"]
        assert any(item["run_id"] == run_id for item in runs)


def test_report_not_ready_is_409(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        accepted = client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
        assert accepted.status_code == 202
        workdir = Path(client.app.state.resources.reader.runs_root)  # type: ignore[attr-defined]
        run_root = workdir / "pending-run"
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "request.json").write_text('{"topic": "pending"}\n', encoding="utf-8")
        response = client.get("/v1/runs/pending-run/report")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "report_not_ready"


def test_unknown_run_is_404(tmp_path: Path) -> None:
    client, _, _ = _client(_settings(tmp_path))
    with client:
        assert client.get("/v1/runs/does-not-exist").status_code == 404
        assert client.get("/v1/runs/does-not-exist/artifacts").status_code == 404


def test_resume_rejects_a_completed_run(tmp_path: Path) -> None:
    client, _, worker = _client(_settings(tmp_path))
    with client:
        client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
        outcome = worker.run_once()
        assert outcome is not None and outcome.run_id
        response = client.post(
            f"/v1/runs/{outcome.run_id}/resume", headers={"Idempotency-Key": "resume-1"}
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_resumable"


@pytest.mark.parametrize("artifact", ["agent.py", "checkpoints.sqlite", "../request.json"])
def test_disallowed_artifacts_are_not_downloadable(tmp_path: Path, artifact: str) -> None:
    client, _, worker = _client(_settings(tmp_path))
    with client:
        client.post("/v1/runs", json=SUBMIT, headers={"Idempotency-Key": "k1"})
        outcome = worker.run_once()
        assert outcome is not None and outcome.run_id
        response = client.get(f"/v1/runs/{outcome.run_id}/artifacts/{artifact}")
    assert response.status_code == 404
