"""The research worker: claim, execute, record, shut down.

One worker processes one job at a time. It owns an execution context per attempt,
heartbeats its lease while running, and records a terminal outcome on the job. The
workspace OS lock is the second ownership gate, so an expired lease alone never
lets a second process write into the same run directory.
"""

from __future__ import annotations

import signal
import threading
import time
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from application.context import ExecutionContext
from application.ports import JobStore, JobStoreError
from application.run_service import AuthoringMode, ExecutionOutcome, RunService
from schemas.config import ApiSettings, RunSettings, run_settings_for_api
from schemas.jobs import JobRecord
from schemas.requests import ResearchRequest
from schemas.state import RunState
from services.checkpoints import postgres_checkpointer
from services.extraction_service import ExtractionService
from services.fetch_service import Fetcher
from services.llm_service import LLMService
from services.search_provider import SearchProvider, create_search_provider
from services.workspace import allocate_run_id, create_run_workspace
from services.workspace_lock import WorkspaceBusy


class WorkerError(RuntimeError):
    """A worker-level failure that ends the attempt with a safe reason."""


class CheckpointerFactory(Protocol):
    def __call__(self, root: Path) -> BaseCheckpointSaver[Any] | None: ...


@dataclass
class WorkerOutcome:
    job_id: str
    state: str
    run_id: str | None
    error: str | None = None


def _fixture_execution(
    settings: RunSettings, request: ResearchRequest
) -> tuple[SearchProvider, Fetcher, ExtractionService, BaseChatModel]:
    """Fake provider, fetcher, extractor and model for the fixture profile."""
    from application.fixtures import (
        FixtureExtractionService,
        FixtureFetcher,
        fixture_model,
        fixture_search_provider,
    )

    del settings
    provider: SearchProvider = fixture_search_provider(
        request.topic, pages=request.pages, per_page=request.per_page
    )
    fetcher: Fetcher = FixtureFetcher()
    extractor: ExtractionService = FixtureExtractionService()
    model: BaseChatModel = fixture_model()
    return provider, fetcher, extractor, model


class ResearchWorker:
    def __init__(
        self,
        store: JobStore,
        api: ApiSettings,
        *,
        identity: str,
        runs_root: Path | None = None,
        settings: RunSettings | None = None,
        checkpointer_factory: CheckpointerFactory | None = None,
        once: bool = False,
    ) -> None:
        self.store = store
        self.api = api
        self.identity = identity
        self.settings = settings if settings is not None else run_settings_for_api(api)
        if self.api.run_profile == "fixture" and self.settings.crawler_contact is None:
            # The fixture fetcher never contacts a host, but the corpus phase still
            # builds a User-Agent string, so a placeholder contact keeps it honest.
            self.settings = self.settings.model_copy(
                update={"crawler_contact": "fixture@example.test"}
            )
        self.runs_root = runs_root if runs_root is not None else Path(self.settings.runs_dir)
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.once = once
        self._stop = threading.Event()
        self._checkpointer_factory = checkpointer_factory

    # -- lifecycle -------------------------------------------------------------
    def request_stop(self) -> None:
        self._stop.set()

    def install_signal_handlers(self) -> None:
        def handler(signum: int, frame: object) -> None:
            del signum, frame
            self.request_stop()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def run_forever(self) -> None:
        self.install_signal_handlers()
        while not self._stop.is_set():
            outcome = self.run_once()
            if outcome is None and self.once:
                return
            if outcome is None:
                self._stop.wait(self.api.worker_poll_seconds)

    # -- one claim -------------------------------------------------------------
    def run_once(self) -> WorkerOutcome | None:
        now = datetime.now(UTC)
        try:
            self.store.recover_expired(now=now)
            job = self.store.claim(
                worker_identity=self.identity,
                now=now,
                lease_seconds=self.api.worker_lease_seconds,
            )
        except JobStoreError:
            return None
        if job is None:
            return None
        return self._execute(job)

    def _execute(self, job: JobRecord) -> WorkerOutcome:
        heartbeat = _Heartbeat(self.store, job.job_id, self.identity, self.api)
        context: ExecutionContext | None = None
        try:
            heartbeat.start()
            context, checkpointer_scope = self._prepare(job)
            outcome = self._run(context, job, checkpointer_scope)
            self.store.finish(
                job_id=job.job_id,
                state=outcome.terminal_state,  # type: ignore[arg-type]
                now=datetime.now(UTC),
                run_id=context.workspace.run_id,
                phase="report" if not outcome.search_only else "search",
                status_reasons=outcome.status_reasons,
                error=outcome.error,
            )
            return WorkerOutcome(
                job_id=job.job_id,
                state=outcome.terminal_state,
                run_id=context.workspace.run_id,
                error=outcome.error,
            )
        except WorkspaceBusy:
            # Another process owns this workspace; leave the job interrupted.
            self._finish_safely(job.job_id, "interrupted", "workspace_busy")
            return WorkerOutcome(
                job_id=job.job_id, state="interrupted", run_id=job.run_id, error="workspace_busy"
            )
        except Exception as error:  # noqa: BLE001 - never leak exception text to the job
            self._finish_safely(job.job_id, "failed", type(error).__name__)
            return WorkerOutcome(
                job_id=job.job_id, state="failed", run_id=job.run_id, error=type(error).__name__
            )
        finally:
            heartbeat.stop()
            if context is not None:
                context.close()

    def _finish_safely(self, job_id: str, state: str, reason: str) -> None:
        try:
            self.store.finish(
                job_id=job_id,
                state=state,  # type: ignore[arg-type]
                now=datetime.now(UTC),
                error=reason,
            )
        except JobStoreError:
            pass

    # -- preparation -----------------------------------------------------------
    def _prepare(self, job: JobRecord) -> tuple[ExecutionContext, BaseCheckpointSaver[Any] | None]:
        request = ResearchRequest(
            topic=str(job.payload["topic"]),
            pages=int(job.payload["pages"]),
            per_page=int(job.payload["per_page"]),
            max_urls=int(job.payload["max_urls"]),
        )
        fixture = self.api.run_profile == "fixture"
        fake_model: BaseChatModel | None = None
        fetcher: Fetcher | None = None
        extractor: ExtractionService | None = None
        variants: object | None = None
        if fixture:
            from application.fixtures import fixture_variants

            provider, fetcher, extractor, fake_model = _fixture_execution(self.settings, request)
            variants = fixture_variants()
        else:
            provider = create_search_provider(self.settings)
        provider.preflight(request.per_page)

        if job.run_id is not None:
            run_id = job.run_id
            workspace = create_run_workspace(request, self.runs_root, run_id=run_id, create=False)
        elif job.state == "interrupted" or job.attempt > 1:
            raise WorkerError("Interrupted job has no run workspace to resume")
        else:
            run_id = allocate_run_id(request.topic, self.runs_root)
            workspace = create_run_workspace(request, self.runs_root, run_id=run_id, create=False)
        self.store.set_progress(
            job_id=job.job_id, run_id=run_id, phase="starting", now=datetime.now(UTC)
        )
        run = RunState(run_id=run_id, topic=request.topic)
        context = ExecutionContext.open(
            run=run,
            workspace=workspace,
            settings=self.settings,
            search_provider=provider,
            llm=LLMService(self.settings, fake_model=fake_model),
            fetcher=fetcher,
            extractor=extractor,
            variants=variants,
            pages=request.pages,
            per_page=request.per_page,
            max_urls=request.max_urls,
        )
        checkpointer_scope = self._checkpointer_scope()
        checkpointer = (
            context.manage(checkpointer_scope) if checkpointer_scope is not None else None
        )
        return context, checkpointer

    def _checkpointer_scope(self) -> AbstractContextManager[BaseCheckpointSaver[Any]] | None:
        """A context-managed saver: PostgreSQL when configured, or the test factory.

        The fixture profile also uses PostgreSQL when a DSN is present, so the
        fixture integration check exercises the real checkpoint backend.
        """
        if self._checkpointer_factory is not None:
            saver = self._checkpointer_factory(self.runs_root)
            return nullcontext(saver) if saver is not None else None
        dsn = self.api.database_dsn()
        if dsn is None:
            return None
        return postgres_checkpointer(dsn)

    def _run(
        self,
        context: ExecutionContext,
        job: JobRecord,
        checkpointer_scope: BaseCheckpointSaver[Any] | None,
    ) -> ExecutionOutcome:
        observer = context.observer("research" if job.operation == "research" else "search")
        context.scope(observer)
        synthesize = None
        authoring_mode: AuthoringMode = "agent"
        if self.api.run_profile == "fixture":
            from application.fixtures import fixture_authoring

            authoring_mode = "fixture"
            synthesize = fixture_authoring
        service = RunService(
            context,
            production=self.api.run_profile != "fixture",
            authoring_mode=authoring_mode,
            synthesize=synthesize,
            checkpointer=checkpointer_scope,
        )
        try:
            if job.attempt > 1 and _has_state(context.workspace.root):
                outcome = service.resume()
            else:
                outcome = service.execute(operation=job.operation)
            failure = None if outcome.error is None else WorkerError(outcome.error)
            observer.finish(outcome.report, failure)
            return outcome
        except Exception as error:  # noqa: BLE001 - the observer records the failure
            observer.finish(None, error)
            raise

    # -- helpers ---------------------------------------------------------------
    def observe_readiness(self) -> tuple[bool, str]:
        try:
            _ = self.store.count_active()
        except JobStoreError:
            return False, "store_unavailable"
        return True, "ready"


class _Heartbeat(threading.Thread):
    def __init__(self, store: JobStore, job_id: str, identity: str, api: ApiSettings) -> None:
        super().__init__(daemon=True)
        self.store = store
        self.job_id = job_id
        self.identity = identity
        self.api = api
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()
        self.join(timeout=self.api.worker_heartbeat_seconds)

    def run(self) -> None:
        while not self._halt.wait(self.api.worker_heartbeat_seconds):
            try:
                if not self.store.heartbeat(
                    job_id=self.job_id,
                    worker_identity=self.identity,
                    now=datetime.now(UTC),
                    lease_seconds=self.api.worker_lease_seconds,
                ):
                    return
            except JobStoreError:
                return


def _has_state(root: Path) -> bool:
    return any(
        (root / name).is_file()
        for name in ("search_state.json", "fetch_state.json", "corpus_state.json")
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - process entry point
    import argparse

    from application.migrations import apply_migrations
    from services.job_store import MemoryJobStore

    parser = argparse.ArgumentParser(prog="research-worker", description=__doc__)
    parser.add_argument("--once", action="store_true", help="Claim and run one job, then exit.")
    args = parser.parse_args(argv)

    api = ApiSettings()
    fixture = api.run_profile == "fixture"
    if fixture:
        store: JobStore = MemoryJobStore()
    else:
        dsn = api.database_dsn()
        if dsn is None:
            print("API_DATABASE is required unless API_RUN_PROFILE=fixture")
            return 2
        import psycopg

        from services.postgres_jobs import PostgresJobStore

        with psycopg.connect(dsn) as connection:
            apply_migrations(connection)
        store = PostgresJobStore(dsn)
    identity = api.worker_identity or f"worker-{int(time.time())}"
    worker = ResearchWorker(store, api, identity=identity, once=args.once)
    if args.once:
        worker.run_once()
        return 0
    worker.run_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
