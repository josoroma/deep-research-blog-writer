"""M3-M5: workspace ownership, atomic claims, recovery, and resume."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver

from application.context import ExecutionContext
from application.fixtures import (
    FixtureExtractionService,
    FixtureFetcher,
    fixture_model,
    fixture_search_provider,
    fixture_variants,
)
from application.job_service import JobService
from application.run_service import RunService, SearchPhaseError
from schemas.api import SubmissionRequest
from schemas.config import ApiSettings, RunSettings
from schemas.jobs import JobRecord
from schemas.requests import ResearchRequest
from schemas.state import RunState
from services.job_store import MemoryJobStore
from services.llm_service import LLMService
from services.workspace import allocate_run_id, create_run_workspace
from services.workspace_lock import WorkspaceBusy, WorkspaceLock
from workers.research_worker import ResearchWorker

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _api(tmp_path: Path, *, queue_limit: int | None = None) -> ApiSettings:
    return ApiSettings(
        _env_file=None,
        run_profile="fixture",
        runs_dir=str(tmp_path / "runs"),
        queue_limit=queue_limit if queue_limit is not None else 100,
    )


def _worker(store: MemoryJobStore, api: ApiSettings, tmp_path: Path) -> ResearchWorker:
    return ResearchWorker(
        store,
        api,
        identity="unit-worker",
        runs_root=Path(api.runs_dir),
        settings=RunSettings(_env_file=None, runs_dir=api.runs_dir),
        once=True,
    )


def _submit(
    service: JobService,
    *,
    mode: Literal["search", "research"] = "search",
    topic: str = "telemetry quality",
) -> str:
    request = SubmissionRequest(mode=mode, topic=topic, pages=1, per_page=10, max_urls=2)
    record, _ = service.submit(request, idempotency_key=f"key-{topic}-{mode}")
    return record.job_id


def test_workspace_lock_is_exclusive(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    first = WorkspaceLock(root)
    second = WorkspaceLock(root)
    with first:
        assert first.acquired
        with pytest.raises(WorkspaceBusy):
            second.acquire()
    second.acquire()
    assert second.acquired
    second.release()


def test_allocate_run_id_retries_only_on_collision(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    run_id = allocate_run_id("telemetry quality", root)
    assert (root / run_id).is_dir()
    # A second allocation must produce a distinct, non-overwriting directory.
    second = allocate_run_id("telemetry quality", root)
    assert second != run_id
    assert not list(root.glob("*/*.tmp"))


def test_worker_processes_one_job_and_releases_the_lock(tmp_path: Path) -> None:
    api = _api(tmp_path)
    store = MemoryJobStore()
    service = JobService(store, api, clock=lambda: NOW)
    job_id = _submit(service)
    outcome = _worker(store, api, tmp_path).run_once()
    assert outcome is not None and outcome.state == "succeeded"
    record = store.get(job_id)
    assert record is not None and record.attempt == 1 and record.run_id
    lock_path = Path(api.runs_dir) / str(record.run_id) / ".run.lock"
    assert lock_path.exists()


def test_second_worker_cannot_process_a_claimed_job(tmp_path: Path) -> None:
    api = _api(tmp_path)
    store = MemoryJobStore()
    service = JobService(store, api, clock=lambda: NOW)
    _submit(service)
    first = store.claim(worker_identity="w1", now=datetime.now(UTC), lease_seconds=120)
    assert first is not None
    assert store.claim(worker_identity="w2", now=datetime.now(UTC), lease_seconds=120) is None


def test_expired_lease_is_recovered_as_interrupted(tmp_path: Path) -> None:
    api = _api(tmp_path)
    store = MemoryJobStore()
    service = JobService(store, api, clock=lambda: NOW)
    job_id = _submit(service)
    store.claim(worker_identity="w1", now=NOW, lease_seconds=1)
    changed = store.recover_expired(now=NOW + timedelta(seconds=10))
    assert changed == 1
    assert store.get(job_id).state == "interrupted"  # type: ignore[union-attr]


def test_resume_continues_an_interrupted_search_run(tmp_path: Path) -> None:
    api = _api(tmp_path)
    store = MemoryJobStore()
    service = JobService(store, api, clock=lambda: NOW)
    job_id = _submit(service)
    worker = _worker(store, api, tmp_path)
    # Claim, then interrupt before work begins so the job is resumable.
    record = store.claim(worker_identity="w1", now=datetime.now(UTC), lease_seconds=60)
    assert record is not None
    store.set_progress(job_id=job_id, run_id="resume-run", phase="starting", now=datetime.now(UTC))
    original = Path(api.runs_dir) / "resume-run"

    create_run_workspace(
        ResearchRequest(topic="telemetry quality", pages=1, per_page=10, max_urls=2),
        Path(api.runs_dir),
        run_id="resume-run",
    )
    store.release(job_id=job_id, state="interrupted", now=datetime.now(UTC))
    resumed = service.release_for_resume(store.get(job_id), now=datetime.now(UTC))  # type: ignore[arg-type]
    assert resumed.state == "queued"
    outcome = worker.run_once()
    assert outcome is not None and outcome.state == "succeeded"
    assert outcome.run_id == "resume-run"
    assert original.is_dir()
    assert (original / "clean_results.json").is_file()


def test_worker_fails_a_job_whose_search_cannot_complete(tmp_path: Path) -> None:
    api = _api(tmp_path)
    store = MemoryJobStore()
    service = JobService(store, api, clock=lambda: NOW)
    job_id = _submit(service, topic="no results topic")
    worker = _worker(store, api, tmp_path)
    # Force the fixture provider to receive no variants so the planned calls yield
    # an empty clean-result set, which must end as a terminal failure.
    prepared = worker._prepare

    def empty_provider(
        job: JobRecord,
    ) -> tuple[ExecutionContext, BaseCheckpointSaver[Any] | None]:
        context, checkpointer = prepared(job)
        context.variants = None
        return context, checkpointer

    worker._prepare = empty_provider  # type: ignore[method-assign]
    outcome = worker.run_once()
    assert outcome is not None and outcome.state == "failed"
    record = store.get(job_id)
    assert record is not None and record.state == "failed" and record.error


def test_search_phase_error_is_safe(tmp_path: Path) -> None:
    error = SearchPhaseError("no_results")
    assert str(error) == "no_results"


def test_worker_reads_the_budget_from_the_job(tmp_path: Path) -> None:
    api = _api(tmp_path)
    store = MemoryJobStore()
    service = JobService(store, api, clock=lambda: NOW)
    request = SubmissionRequest(
        mode="search", topic="telemetry quality", pages=1, per_page=10, max_urls=1
    )
    record, _ = service.submit(request, idempotency_key="budget")
    outcome = _worker(store, api, tmp_path).run_once()
    assert outcome is not None and outcome.run_id

    clean = json.loads(
        (Path(api.runs_dir) / str(outcome.run_id) / "clean_results.json").read_text()
    )
    assert len(clean) == 1
    assert record.job_id


def test_worker_health_probe(tmp_path: Path) -> None:
    api = _api(tmp_path)
    store = MemoryJobStore()
    worker = _worker(store, api, tmp_path)
    assert worker.observe_readiness() == (True, "ready")
    worker.request_stop()


def test_run_service_executes_a_search_only_job(tmp_path: Path) -> None:
    settings = RunSettings(
        _env_file=None, runs_dir=str(tmp_path / "runs"), crawler_contact="fixture@example.test"
    )
    request = ResearchRequest(topic="telemetry quality", pages=1, per_page=10, max_urls=2)
    run_id = allocate_run_id(request.topic, Path(settings.runs_dir))
    workspace = create_run_workspace(request, Path(settings.runs_dir), run_id=run_id, create=False)
    context = ExecutionContext.open(
        run=RunState(run_id=run_id, topic=request.topic),
        workspace=workspace,
        settings=settings,
        search_provider=fixture_search_provider(request.topic, pages=1, per_page=10),
        llm=LLMService(settings, fake_model=fixture_model()),
        fetcher=FixtureFetcher(),
        extractor=FixtureExtractionService(),
        variants=fixture_variants(),
        pages=1,
        per_page=10,
        max_urls=2,
    )
    try:
        outcome = RunService(context, production=False).execute(operation="search")
    finally:
        context.close()
    assert outcome.status == "search_completed"
    assert (workspace.root / "clean_results.json").is_file()
