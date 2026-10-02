"""US-10.2: the whole pipeline runs on fixtures, and survives failed fixtures.

Search, corpus collection, authoring, and reporting run in order against a fake
provider, a mock transport, and a scripted model. No socket is opened and no
credential is read.
"""

from pathlib import Path

import httpx
from langchain_core.messages import AIMessage

from evaluations.fakes import ScriptedChatModel
from evaluations.fetch_fixtures import VirtualClock
from evaluations.workflow_fixtures import (
    EXTRACTED_COUNT,
    TOPIC,
    URL_COUNT,
    VARIANTS,
    WorkflowHTTP,
    authoring_script,
    planner_script,
    search_pages,
)
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import RunReport
from services.authoring import validate_citations
from services.corpus import read_corpus
from services.fetch_service import FetchService
from services.llm_service import LLMService
from services.reporting import RunLedger
from services.search_provider import FakeSearchProvider
from workflows.authoring_run import load_corpus_run, run_authoring
from workflows.corpus_run import run_corpus
from workflows.reporting_run import run_report
from workflows.search_run import run_search


def settings() -> RunSettings:
    return RunSettings(
        _env_file=None,
        crawler_contact="https://example.org/offline-workflow-contact",
        max_urls=URL_COUNT,
    )


def run_pipeline(tmp_path: Path, *, unreachable: bool = True, thin: bool = True) -> Path:
    """Drive search → corpus → authoring → report and return the workspace."""
    resolved = settings()
    request = ResearchRequest(topic=TOPIC, pages=3, max_urls=URL_COUNT)
    search = run_search(
        request,
        resolved,
        runs_root=tmp_path / "runs",
        variants=None,
        search_provider=FakeSearchProvider(search_pages()),
        fake_model=ScriptedChatModel(script=planner_script()),
    )
    assert search.status == "completed", search.error
    workspace = Path(search.workspace)
    assert search.counts is not None and search.counts.kept == URL_COUNT

    transport, clock = WorkflowHTTP(unreachable=unreachable, thin=thin), VirtualClock()
    with FetchService(
        resolved,
        client=transport.client(),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as fetcher:
        corpus = run_corpus(workspace, resolved, fetcher=fetcher)
    assert corpus.status == "completed", corpus.error

    authoring = run_authoring(
        workspace,
        resolved,
        llm=LLMService(resolved, fake_model=ScriptedChatModel(script=authoring_script(workspace))),
    )
    assert authoring.status == "completed", authoring.error
    ledger = RunLedger(resolved.models.orchestrator)
    ledger.phase_timings = {"search": 0.1, "fetch": 0.2, "index": 0.1}
    report = run_report(
        workspace,
        load_corpus_run(workspace),
        resolved,
        ledger,
        blog_path="output/blog.md",
        duration_seconds=0.4,
    )
    assert isinstance(report, RunReport)
    return workspace


def test_pipeline_writes_every_expected_artifact(tmp_path: Path) -> None:
    """Scenario: run the pipeline on fixtures."""
    workspace = run_pipeline(tmp_path, unreachable=False, thin=False)
    sources = read_corpus(workspace)
    assert len(sources) == URL_COUNT
    assert (workspace / "research/index.md").is_file()
    assert (workspace / "research/summary.md").is_file()
    assert (workspace / "output/blog.md").is_file()
    assert (workspace / "output/run.json").is_file()
    assert validate_citations(workspace).passed
    assert validate_citations(workspace).dangling_source_ids == []


def test_pipeline_report_matches_the_corpus(tmp_path: Path) -> None:
    """The written report is a valid RunReport whose counts match the files."""
    workspace = run_pipeline(tmp_path, unreachable=False, thin=False)
    report = RunReport.model_validate_json((workspace / "output/run.json").read_text())
    assert report.urls_clean == URL_COUNT
    assert report.urls_extracted == URL_COUNT
    assert report.citation_count > 0
    assert report.status == "succeeded"


def test_pipeline_survives_failed_fixtures(tmp_path: Path) -> None:
    """Scenario: survive failed fixtures. One unreachable and one thin page."""
    workspace = run_pipeline(tmp_path)
    report = RunReport.model_validate_json((workspace / "output/run.json").read_text())
    assert report.urls_extracted == EXTRACTED_COUNT
    assert report.urls_thin == 1
    assert len(read_corpus(workspace)) == EXTRACTED_COUNT
    outcomes = {entry.outcome for entry in report.url_outcomes}
    assert "unreachable" in outcomes and "too_thin" in outcomes
    assert report.status == "succeeded"


def test_pipeline_keeps_going_when_every_fixture_fails(tmp_path: Path) -> None:
    """A run with no extractable source still completes and reports the failure."""
    resolved = settings()
    request = ResearchRequest(topic=TOPIC, pages=3, max_urls=URL_COUNT)
    search = run_search(
        request,
        resolved,
        runs_root=tmp_path / "runs",
        search_provider=FakeSearchProvider(search_pages()),
        fake_model=ScriptedChatModel(script=planner_script()),
    )
    workspace = Path(search.workspace)
    clock = VirtualClock()

    class AllMissing(WorkflowHTTP):
        async def respond(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return await super().respond(request)
            return httpx.Response(404)

    with FetchService(
        resolved,
        client=AllMissing().client(),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as fetcher:
        corpus = run_corpus(workspace, resolved, fetcher=fetcher)
    assert corpus.status == "completed"
    assert corpus.sources_written == 0
    assert corpus.outcomes.get("unreachable") == URL_COUNT
    assert (workspace / "research/index.md").is_file()


def test_workflow_fixture_variants_are_distinct_from_the_topic() -> None:
    """The planner fixture satisfies the same rule the real planner enforces."""
    assert all(variant.casefold() != TOPIC.casefold() for variant in VARIANTS)
    assert len(set(VARIANTS)) == len(VARIANTS)


def test_scripted_model_is_the_only_model_used(tmp_path: Path) -> None:
    """The pipeline never constructs a provider client: the fake answers every call."""
    model = ScriptedChatModel(script=[AIMessage(content="offline")])
    service = LLMService(settings(), fake_model=model)
    assert service.for_agent("writer_agent") is model
