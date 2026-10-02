"""Acceptance checks on actual SDK data and run-owned execution boundaries."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from opentelemetry.exporter.otlp.proto.common.metrics_encoder import encode_metrics
from pydantic import ValidationError

from evaluations.epic9_demo import run_demo
from evaluations.observability_fixtures import RecordingMetricExporter, RecordingTraceClient
from evaluations.otlp_receiver import decode_metrics, metric_points
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.search import QueryVariants
from services.execution_log import ExecutionLog
from services.observability import RunObservability, observability_scope
from services.run_metrics import RunMetrics
from services.search_provider import FakeSearchProvider
from workflows.search_run import run_search


@pytest.mark.parametrize("scenario", ["failure", "success"])
def test_actual_graph_tools_usage_retries_and_otlp_data(
    tmp_path: Path, scenario: Literal["failure", "success"]
) -> None:
    exporter = RecordingMetricExporter()
    metrics = RunMetrics("http://offline.test", 1, exporter=exporter)
    settings = RunSettings(
        _env_file=None, langsmith_tracing=True, otel_exporter_otlp_endpoint="http://offline.test"
    )
    client = RecordingTraceClient()
    observer = RunObservability(settings, "demo", client=client, metrics=metrics)
    evidence = run_demo(tmp_path, observer=observer, scenario=scenario)
    assert evidence["telemetry"]["metrics_flushed"]
    assert exporter.closed and exporter.batches
    points = metric_points(decode_metrics(encode_metrics(exporter.batches[-1]).SerializeToString()))
    assert points["research_tokens"][0]["as_int"] == "90"
    assert points["research_retries"][0]["as_int"] == ("5" if scenario == "failure" else "2")
    assert points["research_dangling_citations"][0]["as_int"] == (
        "2" if scenario == "failure" else "0"
    )
    assert float(points["research_cost_usd"][0]["as_double"]) == pytest.approx(0.06)
    assert {
        "research_run_duration",
        "research_phase_duration",
        "research_tool_duration",
        "research_runs",
        "research_tool_calls",
        "research_url_outcomes",
    } <= points.keys()
    root = observer.root
    assert root is not None
    assert root.error == ("run_failed" if scenario == "failure" else None)
    assert evidence["report_status"] == ("failed" if scenario == "failure" else "succeeded")
    records = client.records
    assert sum(row["parent_run_id"] is None for row in records.values()) == 1
    assert any(row["run_type"] == "llm" for row in records.values())
    assert any(row["name"] == "task" for row in records.values())
    assert any(row["name"] == "search_agent" for row in records.values())
    assert all(row["ended"] for row in records.values())
    assert any(row["name"] == "collect_source" for row in records.values())
    for row in records.values():
        assert row["metadata"]["run_id"] == observer.workspace.name  # type: ignore[union-attr]
        assert row["metadata"]["topic"] == "EPIC-9 observability evidence"
        current = row
        while current["parent_run_id"]:
            current = records[current["parent_run_id"]]
        assert current["id"] == str(root.id)


@pytest.mark.parametrize(
    "endpoint", ["ftp://host", "http://u:p@host", "https://host?key=x", "https://host#x"]
)
def test_bad_endpoints_are_rejected_without_disclosing_inputs(endpoint: str) -> None:
    with pytest.raises(ValidationError) as error:
        RunSettings(_env_file=None, otel_exporter_otlp_endpoint=endpoint)
    assert endpoint not in str(error.value)


def test_missing_trace_key_fails_preflight(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
        run_search(
            ResearchRequest(topic="Tracing key preflight"),
            RunSettings(_env_file=None, langsmith_tracing=True),
            runs_root=tmp_path,
            variants=QueryVariants(variants=["first variant", "second variant"]),
            search_provider=FakeSearchProvider(),
        )
    assert not list(tmp_path.iterdir())


def test_metrics_disabled_creates_no_sdk_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Disabled metrics constructed an exporter")

    monkeypatch.setattr("services.run_metrics.OTLPMetricExporter", denied)
    metrics = RunMetrics(None, 1)
    metrics.add("runs", 1, {})
    metrics.duration("phase", 0.1, {})
    assert metrics.provider is None and metrics.exporter is None and metrics.close(1)


def test_export_failure_preserves_workflow_result(tmp_path: Path) -> None:
    exporter = RecordingMetricExporter(fails=True)
    observer = RunObservability(
        RunSettings(_env_file=None),
        "search",
        metrics=RunMetrics("http://offline.test", 1, exporter=exporter),
    )
    with observability_scope(observer):
        result = run_search(
            ResearchRequest(topic="Exporter outage"),
            observer.settings,
            runs_root=tmp_path,
            search_provider=FakeSearchProvider(),
            variants=QueryVariants(variants=["first query", "second query"]),
        )
        observer.finish(result)
    assert result.status == "completed"
    log = Path(result.workspace) / "logs/execution.log"
    assert any(
        json.loads(row)["event"] == "metrics_export_failed" for row in log.read_text().splitlines()
    )
    assert not json.loads((Path(result.workspace) / "logs/telemetry.json").read_text())[
        "metrics_flushed"
    ]


def test_concurrent_logs_are_valid_isolated_and_redact_secrets(tmp_path: Path) -> None:
    first, second = (
        ExecutionLog(tmp_path / "first", "first"),
        ExecutionLog(tmp_path / "second", "second"),
    )

    def append(index: int) -> None:
        logger = first if index % 2 else second
        logger.event(
            "fetch",
            "source_failed",
            url="https://user:pass@host/path?api_key=private&q=public#secret",
            reason="http_404",
            api_key="private",
            run_id="forged",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, range(100)))
    for logger in (first, second):
        rows = [json.loads(line) for line in logger.path.read_text().splitlines()]
        assert len(rows) == 50
        assert all(row["run_id"] == logger.run_id for row in rows)
        assert all(row["api_key"] == "[REDACTED]" for row in rows)
        assert (
            "private" not in logger.path.read_text() and "user:pass" not in logger.path.read_text()
        )
        assert all("q=public" in row["url"] for row in rows)


def test_log_symlink_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = tmp_path / "run"
    workspace.mkdir()
    (workspace / "logs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        ExecutionLog(workspace, "run")


def test_usage_callback_deduplicates_and_marks_unknown_cost(tmp_path: Path) -> None:
    from uuid import uuid4

    observer = RunObservability(RunSettings(_env_file=None), "unit")
    observer.bind(tmp_path, "Usage evidence")
    result = LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(
                        content="unused", response_metadata={"usage": {"total_tokens": 4}}
                    )
                )
            ]
        ]
    )
    identity = uuid4()
    observer.callback.on_llm_end(result, run_id=identity)
    observer.callback.on_llm_end(result, run_id=identity)
    observer.finish()
    snapshot = json.loads((tmp_path / "logs/telemetry.json").read_text())
    assert snapshot["tokens_used"] == 4 and not snapshot["cost_available"]


def test_tracing_export_exception_does_not_replace_tool_result(tmp_path: Path) -> None:
    class FailingClient(RecordingTraceClient):
        def create_run(
            self, name: str, inputs: dict[str, Any], run_type: Any, **kwargs: Any
        ) -> None:
            raise RuntimeError("offline exporter outage")

    observer = RunObservability(
        RunSettings(_env_file=None, langsmith_tracing=True), "search", client=FailingClient()
    )
    with observability_scope(observer):
        result = run_search(
            ResearchRequest(topic="Tracing outage"),
            observer.settings,
            runs_root=tmp_path,
            search_provider=FakeSearchProvider(),
            variants=QueryVariants(variants=["first query", "second query"]),
        )
        observer.finish(result)
    assert result.status == "completed"
    assert (
        json.loads((Path(result.workspace) / "logs/telemetry.json").read_text())[
            "trace_export_error"
        ]
        == "RuntimeError"
    )


def test_recovered_source_updates_final_outcome_without_losing_failure_log(tmp_path: Path) -> None:
    import httpx
    from pydantic import HttpUrl

    from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock
    from schemas.responses import SearchResult
    from schemas.state import RunState, UrlOutcome
    from services.extraction_service import ExtractionService
    from services.fetch_service import FetchService
    from tools.corpus_tools import CorpusSession
    from tools.registry import create_tool_registry
    from workflows.search_run import tool_runtime

    class RecoveredHTTP(FixtureHTTP):
        async def respond(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/article" and not self.counts["first-failure"]:
                self.counts["first-failure"] += 1
                return httpx.Response(404)
            return await super().respond(request)

    settings = RunSettings(_env_file=None, crawler_contact="https://example.org/contact")
    observer = RunObservability(settings, "recovery")
    url = HttpUrl("https://fixture.test/article")
    run = RunState(
        run_id=tmp_path.name,
        topic="Source recovery evidence",
        clean_results=[
            SearchResult(url=url, title="Fixture", snippet="Fixture", rank=1, query="evidence")
        ],
        url_outcomes={str(url): UrlOutcome(rank=1, url=url)},
    )
    with observability_scope(observer):
        observer.bind(tmp_path, run.topic)
        transport, clock = RecoveredHTTP(), VirtualClock()
        with FetchService(
            settings, client=transport.client(), clock=clock, sleep=clock.sleep, jitter=lambda: 0
        ) as fetcher:
            extractor = ExtractionService()
            registry = create_tool_registry(
                fetcher=fetcher,
                extractor=extractor,
                corpus_session=CorpusSession(tmp_path, run, fetcher, extractor),
            )
            registry["collect_source"].invoke({"rank": 1, "url": url}, tool_runtime(run))
            assert dict(observer.outcomes) == {"unreachable": 1}
            registry["collect_source"].invoke({"rank": 1, "url": url}, tool_runtime(run))
            assert dict(observer.outcomes) == {"extracted": 1}
        observer.finish()
    events = [
        json.loads(line)["event"]
        for line in (tmp_path / "logs/execution.log").read_text().splitlines()
    ]
    assert "source_failed" in events and "source_extracted" in events
