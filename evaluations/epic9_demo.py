"""Actual graph/tools with scripted usage, mock HTTP, and recorded SDK traces."""

import argparse
import json
import time
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import AIMessage
from pydantic import HttpUrl

from agents.deep_research import build_deep_agent
from evaluations.epic4_demo import call
from evaluations.fakes import ScriptedChatModel
from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock
from evaluations.observability_fixtures import RecordingTraceClient
from evaluations.otlp_receiver import local_receiver, metric_points
from schemas.config import RunSettings
from schemas.content import ExtractionResult
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.state import RunState
from schemas.tool_io import ExtractMarkdownInput
from services.artifacts import write_json
from services.authoring import validate_citations
from services.corpus import read_corpus
from services.extraction_service import ExtractionService
from services.fetch_service import FetchService
from services.llm_service import LLMService
from services.observability import RunObservability, observability_scope, observed_config
from services.reliability import run_phase
from services.search_provider import FakeSearchProvider
from services.search_session import SearchSession
from services.workspace import create_run_workspace
from tools.registry import create_tool_registry
from workflows.authoring_run import load_corpus_run
from workflows.corpus_run import run_corpus
from workflows.reporting_run import run_report

PATHS = ["/article", "/retry", "/missing", "/blocked", "/pdf", "/thin", "/exhaust", "/failure"]
VARIANTS = ["observability implementation evidence", "research telemetry quality checks"]


class FailureExtraction(ExtractionService):
    def extract(self, request: ExtractMarkdownInput) -> ExtractionResult:
        if request.page.final_url.path == "/failure":
            raise RuntimeError("Deliberate offline extraction failure")
        return super().extract(request)


def run_demo(
    runs_root: Path,
    *,
    endpoint: str | None = None,
    observer: RunObservability | None = None,
    scenario: Literal["failure", "success"] = "failure",
) -> dict[str, Any]:
    """Exercise failure observability by default, or a successful hosted smoke."""
    paths = PATHS if scenario == "failure" else ["/article", "/retry"]
    settings = RunSettings(
        _env_file=None,
        crawler_contact="https://example.org/offline-contact",
        max_urls=len(paths),
        otel_exporter_otlp_endpoint=endpoint,
        langsmith_tracing=True,
    )
    client = RecordingTraceClient()
    active = observer or RunObservability(settings, "demo", client=client)
    request = ResearchRequest(topic="EPIC-9 observability evidence", pages=1, max_urls=len(paths))
    started = time.monotonic()
    report = None
    error = None
    with observability_scope(active):
        try:
            workspace = create_run_workspace(request, runs_root)
            clean = [
                SearchResult(
                    url=HttpUrl(f"https://fixture.test{path}"),
                    title=f"Fixture {path}",
                    snippet="Offline fixture",
                    query=request.topic,
                    rank=rank,
                )
                for rank, path in enumerate(paths, 1)
            ]
            provider = FakeSearchProvider({(request.topic, 1): clean})
            session = SearchSession(request, workspace, provider)
            script = [
                call("plan_search", {"variants": VARIANTS}, 0),
                call(
                    "task",
                    {"subagent_type": "search_agent", "description": "Execute search plan."},
                    1,
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "google_search",
                            "args": {"query": query, "page": 1},
                            "id": f"search-{index}",
                            "type": "tool_call",
                        }
                        for index, query in enumerate([request.topic, *VARIANTS])
                    ],
                ),
                AIMessage(content="All searches completed."),
                call("normalize_results", {"max_urls": request.max_urls}, 5),
                AIMessage(content="Saved search artifacts."),
            ]
            for message in script:
                message.usage_metadata = {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                }
                message.response_metadata = {"token_usage": {"total_tokens": 15, "cost": 0.01}}
            model = ScriptedChatModel(script=script)
            agent = build_deep_agent(
                LLMService(settings, fake_model=model),
                workspace,
                tool_registry=create_tool_registry(session),
            )
            agent.invoke(
                {
                    "messages": [{"role": "user", "content": request.model_dump_json()}],
                    "run": RunState(run_id=workspace.run_id, topic=request.topic),
                },
                config=observed_config(settings.recursion_limit),
            )
            transport, clock = FixtureHTTP(), VirtualClock()
            with FetchService(
                settings,
                client=transport.client(),
                clock=clock,
                sleep=clock.sleep,
                jitter=lambda: 0.0,
            ) as fetcher:
                corpus = run_corpus(
                    workspace.root, settings, fetcher=fetcher, extractor=FailureExtraction()
                )
            assert corpus.status == "completed", corpus.error
            attempts = 0

            def flaky() -> str:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("Offline phase retry")
                return "recovered"

            assert run_phase("synthesize", flaky, workspace.root / "logs/execution.log") == (
                "recovered",
                1,
            )
            (workspace.root / "output").mkdir(exist_ok=True)
            blog = "Evidence [S-98] and [S-99].\n"
            if scenario == "success":
                sources = [record.source for record in read_corpus(workspace.root)]
                assert len(sources) == len(paths)
                citations = " and ".join(f"[{source.source_id}]" for source in sources)
                references = "\n".join(
                    f"- [{source.source_id}] {source.title} {source.url}" for source in sources
                )
                blog = (
                    f"# Observability smoke\n\nEvidence {citations}.\n\n"
                    f"## References\n\n{references}\n"
                )
            (workspace.root / "output/blog.md").write_text(blog, encoding="utf-8")
            if scenario == "success":
                assert validate_citations(workspace.root).passed
            report = run_report(
                workspace.root,
                load_corpus_run(workspace.root),
                settings,
                active.ledger,
                blog_path="output/blog.md",
                duration_seconds=time.monotonic() - started,
            )
            if scenario == "failure":
                assert report.status == "failed" and "dangling_citations" in report.status_reasons
            else:
                assert report.status == "succeeded" and not report.status_reasons
        except Exception as failure:
            error = failure
            raise
        finally:
            active.finish(report, error)
    assert active.workspace is not None
    telemetry = json.loads((active.workspace / "logs/telemetry.json").read_text())
    records = list(client.records.values()) if observer is None else []
    if records:
        root_id = telemetry["trace_id"]
        assert len([row for row in records if row["parent_run_id"] is None]) == 1
        assert any(row["run_type"] == "llm" for row in records)
        assert any(row["name"] == "task" for row in records)
        assert any(row["name"] == "collect_source" for row in records)
        assert all(
            row["metadata"].get("run_id") == active.workspace.name
            and row["metadata"].get("topic") == request.topic
            for row in records
        )
        parents = {row["id"]: row["parent_run_id"] for row in records}
        for row in records:
            current = row["id"]
            while parents[current] is not None:
                current = parents[current]
            assert current == root_id
        write_json(active.workspace / "logs/trace_evidence.json", records)
    logs = [
        json.loads(line)
        for line in (active.workspace / "logs/execution.log").read_text().splitlines()
    ]
    assert all({"timestamp", "level", "run_id", "phase", "event"} <= row.keys() for row in logs)
    failures = {row["outcome"] for row in logs if row["event"] == "source_failed"}
    if scenario == "failure":
        assert {
            "unreachable",
            "robots_disallowed",
            "unsupported_content",
            "too_thin",
            "failed",
        } <= failures
    else:
        assert telemetry["url_outcomes"] == {"extracted": len(paths)}
    assert telemetry["tokens_used"] == 90 and abs(telemetry["cost_usd"] - 0.06) < 0.000001
    assert telemetry["retries"] == (5 if scenario == "failure" else 2)
    assert telemetry["dangling_citations"] == (2 if scenario == "failure" else 0)
    result = {
        "mode": "scripted model usage/cost; mock HTTP; actual agent, tools, SDKs",
        "scenario": scenario,
        "workspace": str(active.workspace),
        "telemetry": telemetry,
        "trace_spans": len(records),
        "log_records": len(logs),
        "failure_categories_verified": sorted(failures),
        "report_status": report.status,
        "report_status_reasons": report.status_reasons,
    }
    write_json(active.workspace / "demo_evidence.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", help="Send metrics to an OTLP/HTTP endpoint")
    args = parser.parse_args()
    if args.endpoint:
        result = run_demo(Path("runs"), endpoint=args.endpoint)
    else:
        with local_receiver() as (endpoint, received):
            result = run_demo(Path("runs"), endpoint=endpoint)
        assert received, "OTLP exporter did not deliver protobuf metrics"
        points = metric_points(received[-1])
        assert points["research_tokens"][0]["as_int"] == "90"
        assert points["research_dangling_citations"][0]["as_int"] == "2"
        assert float(points["research_cost_usd"][0]["as_double"]) > 0.0599
        write_json(Path(result["workspace"]) / "logs/otlp_evidence.json", received[-1])
        result["otlp_protobuf_received"] = True
        result["metric_names"] = sorted(points)
        write_json(Path(result["workspace"]) / "demo_evidence.json", result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
