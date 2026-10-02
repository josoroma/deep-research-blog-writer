"""Run-owned logs, LangSmith hierarchy, model accounting and optional OTLP metrics."""

from __future__ import annotations

import inspect
import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.runnables import RunnableConfig
from langsmith import Client, get_current_run_tree, tracing_context
from langsmith.run_trees import RunTree
from pydantic import BaseModel

from schemas.config import RunSettings
from schemas.responses import RunReport
from services.artifacts import write_json
from services.execution_log import ExecutionLog
from services.reporting import RunLedger, UsageRecord
from services.run_metrics import RunMetrics

ACTIVE: ContextVar[RunObservability | None] = ContextVar("research_observability", default=None)
PHASES = {
    "plan_search": "plan",
    "google_search": "search",
    "normalize_results": "normalize",
    "fetch_url": "fetch",
    "extract_markdown": "fetch",
    "collect_source": "fetch",
    "build_index": "index",
    "validate_citations": "citations",
    "write_run_report": "report",
}


def current_observer() -> RunObservability | None:
    return ACTIVE.get()


def observed_config(recursion_limit: int) -> RunnableConfig:
    observer = current_observer()
    config: RunnableConfig = {"recursion_limit": recursion_limit}
    if observer is not None:
        config["callbacks"] = [observer.callback]
        config["metadata"] = observer.metadata
    return config


class UsageCallback(BaseCallbackHandler):
    """Observe framework responses once; never store message bodies or headers."""

    def __init__(self, observer: RunObservability) -> None:
        self.observer = observer
        self._seen: set[UUID] = set()
        self._lock = RLock()

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        del kwargs
        with self._lock:
            if run_id in self._seen:
                return
            self._seen.add(run_id)
        for generations in response.generations:
            if not generations or not isinstance(generations[0], ChatGeneration):
                continue
            message = generations[0].message
            if not isinstance(message, AIMessage):
                continue
            usage: dict[str, Any] = dict(message.usage_metadata or {})
            raw = (
                message.response_metadata.get("token_usage")
                or message.response_metadata.get("usage")
                or {}
            )
            if not isinstance(raw, dict):
                raw = {}
            tokens = usage.get("total_tokens", raw.get("total_tokens", 0))
            cost = raw.get("cost", message.response_metadata.get("cost"))
            valid_tokens = (
                tokens
                if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0
                else 0
            )
            valid_cost = (
                float(cost)
                if isinstance(cost, (int, float))
                and not isinstance(cost, bool)
                and 0 <= cost < float("inf")
                else None
            )
            self.observer.model_usage(valid_tokens, valid_cost)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del input_str, run_id, kwargs
        name = str(serialized.get("name", "tool"))
        # Registered application tools count at their typed boundary. Built-in
        # filesystem/task tools are observed here so the complete graph is counted.
        if name not in PHASES and name != "record_phase_completion":
            self.observer.builtin_tool(name, inputs or {})

    def on_retry(self, retry_state: Any, **kwargs: Any) -> None:
        del retry_state, kwargs
        self.observer.retry("model", "model_retry")


class RunObservability:
    def __init__(
        self,
        settings: RunSettings,
        mode: str,
        *,
        ledger: RunLedger | None = None,
        client: Client | None = None,
        metrics: RunMetrics | None = None,
    ) -> None:
        if settings.langsmith_tracing and client is None and not settings.langsmith_api_key:
            raise ValueError("Set LANGSMITH_API_KEY when LANGSMITH_TRACING=true")
        self.settings, self.mode = settings, mode
        self.ledger = ledger or RunLedger(settings.models.orchestrator)
        self.client = client
        self.metrics = metrics
        self.root: RunTree | None = None
        self.workspace: Path | None = None
        self.log: ExecutionLog | None = None
        self.metadata: dict[str, Any] = {}
        self.callback = UsageCallback(self)
        self.tools: Counter[str] = Counter()
        self.outcomes: Counter[str] = Counter()
        self._outcome_urls: dict[str, tuple[str, str | None]] = {}
        self._phase_windows: dict[str, tuple[float, float]] = {}
        self._lock = RLock()
        self._contexts: list[Any] = []
        self._started = time.monotonic()
        self._dangling = 0
        self._trace_error: str | None = None

    def bind(self, workspace: Path, topic: str) -> None:
        if self.workspace is not None:
            if self.workspace != workspace:
                raise ValueError("Observer cannot cross run workspaces")
            return
        self.workspace = workspace
        self.metadata = {"run_id": workspace.name, "topic": topic, "mode": self.mode}
        self.log = ExecutionLog(workspace, workspace.name)
        self.metrics = self.metrics or RunMetrics(
            self.settings.otel_exporter_otlp_endpoint,
            self.settings.telemetry_timeout_seconds,
        )
        if self.settings.langsmith_tracing:
            self.client = self.client or Client(
                api_url=self.settings.langsmith_endpoint,
                api_key=self.settings.langsmith_api_key.get_secret_value()
                if self.settings.langsmith_api_key
                else None,
                timeout_ms=int(self.settings.telemetry_timeout_seconds * 1000),
                hide_inputs=True,
                hide_outputs=True,
                tracing_error_callback=self._tracing_error,
            )
            self.root = RunTree(
                name=f"research.{self.mode}",
                run_type="chain",
                inputs={},
                extra={"metadata": self.metadata},
                project_name=self.settings.langsmith_project,
                ls_client=self.client,
            )
            try:
                self.root.post()
            except Exception as error:
                self._tracing_error(error)
        context = tracing_context(
            enabled=self.settings.langsmith_tracing,
            parent=self.root,
            client=self.client,
            project_name=self.settings.langsmith_project,
            metadata=self.metadata,
        )
        context.__enter__()
        self._contexts.append(context)
        self.event(
            self.mode,
            "run_started",
            trace_id=str(self.root.id) if self.root else None,
            metrics_enabled=self.settings.otel_exporter_otlp_endpoint is not None,
        )

    def event(self, phase: str, name: str, *, level: str = "INFO", **fields: object) -> None:
        if self.log is not None:
            self.log.event(phase, name, level=level, **fields)

    def _tracing_error(self, error: Exception) -> None:
        self._trace_error = type(error).__name__
        self.event(self.mode, "trace_export_failed", level="WARNING", reason=self._trace_error)

    def _attributes(self, **labels: str) -> dict[str, str]:
        return {"run_id": str(self.metadata.get("run_id", "")), "mode": self.mode, **labels}

    def model_usage(self, tokens: int, cost: float | None) -> None:
        with self._lock:
            self.ledger.usage.append(UsageRecord(tokens, cost))
        self.event(
            self.mode,
            "model_usage",
            tokens_used=tokens,
            cost_usd=cost,
            cost_available=cost is not None,
        )

    def builtin_tool(self, name: str, inputs: dict[str, Any]) -> None:
        with self._lock:
            self.tools[name] += 1
        self.event(self.mode, "tool_started", tool=name)
        if name == "task":
            self.event(
                self.mode, "subagent_started", subagent=str(inputs.get("subagent_type", "unknown"))
            )

    def retry(self, phase: str, reason: str, **fields: object) -> None:
        with self._lock:
            self.ledger.retries += 1
        self.event(phase, "retry", level="WARNING", reason=reason, retry=1, **fields)

    @contextmanager
    def operation(self, name: str, request: BaseModel) -> Iterator[None]:
        phase = PHASES.get(name, self.mode)
        started = time.monotonic()
        with self._lock:
            self.tools[name] += 1
        url = getattr(request, "url", None)
        self.event(phase, "tool_started", tool=name, url=str(url) if url else None)
        parent = get_current_run_tree() or self.root
        span = None
        if self.settings.langsmith_tracing and parent is not None:
            span = parent.create_child(
                name, run_type="tool", inputs={}, extra={"metadata": self.metadata}
            )
            try:
                span.post()
            except Exception as failure:
                self._tracing_error(failure)
        context = tracing_context(
            enabled=self.settings.langsmith_tracing,
            parent=span or parent,
            client=self.client,
            metadata=self.metadata,
        )
        failure_name = None
        try:
            with context:
                yield
        except Exception as error:
            failure_name = type(error).__name__
            self.event(
                phase,
                "tool_failed",
                level="ERROR",
                tool=name,
                reason=type(error).__name__,
                url=str(url) if url else None,
            )
            raise
        finally:
            if span is not None:
                try:
                    span.end(error=failure_name)
                    span.patch()
                except Exception as failure:
                    self._tracing_error(failure)
            elapsed = time.monotonic() - started
            with self._lock:
                first, last = self._phase_windows.get(phase, (started, started))
                self._phase_windows[phase] = (min(first, started), max(last, started + elapsed))
            if self.metrics:
                self.metrics.duration("tool", elapsed, self._attributes(tool=name, phase=phase))
            self.event(phase, "tool_finished", tool=name, duration_seconds=elapsed)

    def inspect_output(self, result: BaseModel) -> None:
        run = getattr(result, "run", None)
        if run is not None:
            for outcome in run.url_outcomes.values():
                self.source_outcome(str(outcome.url), outcome.outcome, outcome.reason)
        if hasattr(result, "dangling_source_ids"):
            self.record_citations(len(result.dangling_source_ids))

    def record_citations(self, count: int) -> None:
        self._dangling = count
        self.event("citations", "citations_checked", dangling_citations=count)

    def source_outcome(self, url: str, outcome: str, reason: str | None) -> None:
        if outcome == "pending":
            return
        with self._lock:
            previous = self._outcome_urls.get(url)
            if previous == (outcome, reason):
                return
            if previous is not None:
                self.outcomes[previous[0]] -= 1
                if not self.outcomes[previous[0]]:
                    del self.outcomes[previous[0]]
            self._outcome_urls[url] = (outcome, reason)
            self.outcomes[outcome] += 1
        self.event(
            "fetch",
            "source_extracted" if outcome == "extracted" else "source_failed",
            level="INFO" if outcome == "extracted" else "WARNING",
            url=url,
            outcome=outcome,
            reason=reason or ("extracted" if outcome == "extracted" else "unspecified"),
        )

    def finish(self, result: object = None, error: Exception | None = None) -> None:
        if self.workspace is None:
            return
        status = "failed" if error else str(getattr(result, "status", "completed"))
        elapsed = time.monotonic() - self._started
        for phase, (start, end) in self._phase_windows.items():
            self.ledger.phase_timings[phase] = end - start
        self.ledger.phase_timings.setdefault(self.mode, elapsed)
        tokens, cost = self.ledger.cost()
        if isinstance(result, RunReport):
            result.phase_timings_seconds.update(self.ledger.phase_timings)
            result.tokens_used, result.cost_usd, result.retries = tokens, cost, self.ledger.retries
            from services.reporting import write_run_report

            write_run_report(self.workspace, result)
            for outcome in result.url_outcomes:
                self.source_outcome(str(outcome.url), outcome.outcome, outcome.reason)
        if self.metrics:
            attributes = self._attributes()
            for key, value in (
                ("tokens", tokens),
                ("cost", cost),
                ("retries", self.ledger.retries),
                ("dangling", self._dangling),
            ):
                self.metrics.add(key, value, attributes)
            self.metrics.add("runs", 1, self._attributes(status=status))
            self.metrics.duration("run", elapsed, attributes)
            for phase, duration in self.ledger.phase_timings.items():
                self.metrics.duration("phase", duration, self._attributes(phase=phase))
            for name, count in self.tools.items():
                self.metrics.add("tools", count, self._attributes(tool=name))
            for outcome_name, count in self.outcomes.items():
                self.metrics.add("urls", count, self._attributes(outcome=outcome_name))
        self.event(
            self.mode,
            "run_finished",
            level="ERROR" if status == "failed" else "INFO",
            status=status,
            duration_seconds=elapsed,
            reason=type(error).__name__ if error else None,
        )
        for context in reversed(self._contexts):
            context.__exit__(None, None, None)
        if self.root and self.client:
            try:
                self.root.end(
                    outputs={"status": status},
                    error=type(error).__name__
                    if error
                    else ("run_failed" if status == "failed" else None),
                )
                self.root.patch()
                self.client.flush(timeout=self.settings.telemetry_timeout_seconds)
                self.client.close(timeout=self.settings.telemetry_timeout_seconds)
            except Exception as failure:
                self._tracing_error(failure)
        flushed = (
            self.metrics.close(self.settings.telemetry_timeout_seconds) if self.metrics else True
        )
        if not flushed:
            self.event(self.mode, "metrics_export_failed", level="WARNING", reason="export_failed")
        write_json(
            self.workspace / "logs/telemetry.json",
            {
                **self.metadata,
                "status": status,
                "duration_seconds": elapsed,
                "phase_timings_seconds": self.ledger.phase_timings,
                "tool_calls": dict(self.tools),
                "tokens_used": tokens,
                "cost_usd": cost,
                "cost_available": all(item.reported_cost is not None for item in self.ledger.usage),
                "retries": self.ledger.retries,
                "url_outcomes": dict(self.outcomes),
                "dangling_citations": self._dangling,
                "metrics_enabled": self.settings.otel_exporter_otlp_endpoint is not None,
                "metrics_flushed": flushed,
                "trace_id": str(self.root.id) if self.root else None,
                "trace_export_error": self._trace_error,
            },
        )


@contextmanager
def observability_scope(observer: RunObservability) -> Iterator[RunObservability]:
    token = ACTIVE.set(observer)
    try:
        yield observer
    finally:
        ACTIVE.reset(token)


def bind_workspace(workspace: Path, topic: str) -> None:
    observer = current_observer()
    if observer is not None:
        observer.bind(workspace, topic)


def observed_workflow[**P, R](mode: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Keep observability lifecycle at workflow boundaries, including failures."""

    def decorate(operation: Callable[P, R]) -> Callable[P, R]:
        @wraps(operation)
        def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
            if current_observer() is not None:
                return operation(*args, **kwargs)
            bound = inspect.signature(operation).bind(*args, **kwargs).arguments
            settings = bound.get("settings")
            if not isinstance(settings, RunSettings):
                raise TypeError("Observed workflows require RunSettings")
            ledger = bound.get("ledger")
            observer = RunObservability(
                settings, mode, ledger=ledger if isinstance(ledger, RunLedger) else None
            )
            result: R | None = None
            error = None
            with observability_scope(observer):
                try:
                    result = operation(*args, **kwargs)
                    return result
                except Exception as failure:
                    error = failure
                    raise
                finally:
                    observer.finish(result, error)

        return invoke

    return decorate
