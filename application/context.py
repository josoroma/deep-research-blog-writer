"""Resources owned by one execution attempt, and their cleanup.

The worker builds a context per attempt so providers, the fetch service, the graph,
the checkpoint saver, the ledger and the observer cannot leak across jobs.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from schemas.config import RunSettings
from schemas.state import RunState
from schemas.workspace import RunWorkspace
from services.extraction_service import ExtractionService, create_extraction_service
from services.fetch_service import Fetcher, FetchService
from services.llm_service import LLMService
from services.observability import RunObservability, observability_scope
from services.reporting import RunLedger
from services.search_provider import SearchProvider
from services.workspace_lock import WorkspaceLock

OWNERSHIP_MANIFEST = "job.json"


@dataclass
class ExecutionContext:
    """One attempt's owned resources. Close it in reverse creation order."""

    run: RunState
    workspace: RunWorkspace
    settings: RunSettings
    ledger: RunLedger
    llm: LLMService
    search_provider: SearchProvider
    fetcher: Fetcher | None
    extractor: ExtractionService
    lock: WorkspaceLock
    variants: object | None = None
    pages: int | None = None
    per_page: int | None = None
    max_urls: int | None = None
    _stack: ExitStack = field(default_factory=ExitStack)

    @classmethod
    def open(
        cls,
        *,
        run: RunState,
        workspace: RunWorkspace,
        settings: RunSettings,
        search_provider: SearchProvider,
        llm: LLMService,
        fetcher: Fetcher | None = None,
        extractor: ExtractionService | None = None,
        acquire_lock: bool = True,
        variants: object | None = None,
        pages: int | None = None,
        per_page: int | None = None,
        max_urls: int | None = None,
    ) -> ExecutionContext:
        """Acquire the workspace lock and build the attempt's owned resources.

        Raises:
            WorkspaceBusy: When another process already holds the workspace lock.
        """
        lock = WorkspaceLock(workspace.root)
        if acquire_lock:
            lock.acquire()
        bound_fetcher = fetcher if fetcher is not None else FetchService(settings)
        return cls(
            run=run,
            workspace=workspace,
            settings=settings,
            ledger=RunLedger(settings.models.orchestrator),
            llm=llm,
            search_provider=search_provider,
            fetcher=bound_fetcher,
            extractor=extractor if extractor is not None else create_extraction_service(settings),
            lock=lock,
            variants=variants,
            pages=pages,
            per_page=per_page,
            max_urls=max_urls,
        )

    def observer(self, mode: str = "research") -> RunObservability:
        """A fresh observer for this attempt; never reused between attempts."""
        return RunObservability(self.settings, mode, ledger=self.ledger)

    def scope(self, observer: RunObservability) -> RunObservability:
        """Make ``observer`` current until :meth:`close`, and return it."""
        self._stack.enter_context(observability_scope(observer))
        return observer

    def manage(
        self, resource: AbstractContextManager[BaseCheckpointSaver[Any]]
    ) -> BaseCheckpointSaver[Any]:
        """Enter a context-managed checkpointer owned by this attempt.

        The PostgreSQL saver is opened through a context manager, so its connection
        is closed with the attempt rather than left to the process exit.
        """
        return self._stack.enter_context(resource)

    def close(self) -> None:
        """Release resources in reverse order; the lock is always released last."""
        try:
            if isinstance(self.fetcher, FetchService):
                self.fetcher.close()
        finally:
            self._stack.close()
            self.lock.release()
