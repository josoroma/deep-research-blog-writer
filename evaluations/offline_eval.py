"""Offline golden-topic pipeline for `make eval --offline` and the eval tests.

It runs the same phases as the live path against the US-10.2 fixtures, so the
scoring and release-gate logic is exercised without credentials or network.
"""

from __future__ import annotations

from pathlib import Path

from evaluations.fakes import ScriptedChatModel
from evaluations.fetch_fixtures import VirtualClock
from evaluations.run_eval import GoldenTopic
from evaluations.workflow_fixtures import (
    TOPIC,
    URL_COUNT,
    WorkflowHTTP,
    authoring_script,
    planner_script,
    search_pages,
)
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from services.fetch_service import FetchService
from services.llm_service import LLMService
from services.reporting import RunLedger
from services.search_provider import FakeSearchProvider
from workflows.authoring_run import load_corpus_run, run_authoring
from workflows.corpus_run import run_corpus
from workflows.reporting_run import run_report
from workflows.search_run import run_search


def run_offline_topic(topic: GoldenTopic, runs_root: Path) -> Path:
    """Run one golden topic through the fixture pipeline and return its workspace."""
    settings = RunSettings(
        _env_file=None,
        crawler_contact="https://example.org/offline-eval-contact",
        max_urls=topic.max_urls,
    )
    # The fixture provider only answers the fixture topic, so the offline path uses
    # it for every golden topic id; the id still keys the score.
    request = ResearchRequest(
        topic=TOPIC, pages=topic.pages, per_page=topic.per_page, max_urls=topic.max_urls
    )
    search = run_search(
        request,
        settings,
        runs_root=runs_root,
        search_provider=FakeSearchProvider(search_pages()),
        fake_model=ScriptedChatModel(script=planner_script()),
    )
    if search.status != "completed":
        raise RuntimeError(f"Offline search failed for {topic.id}: {search.error}")
    workspace = Path(search.workspace)
    transport, clock = WorkflowHTTP(unreachable=False, thin=False), VirtualClock()
    with FetchService(
        settings,
        client=transport.client(),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as fetcher:
        corpus = run_corpus(workspace, settings, fetcher=fetcher)
    if corpus.status != "completed":
        raise RuntimeError(f"Offline corpus failed for {topic.id}: {corpus.error}")
    run_authoring(
        workspace,
        settings,
        llm=LLMService(settings, fake_model=ScriptedChatModel(script=authoring_script(workspace))),
    )
    ledger = RunLedger(settings.models.orchestrator)
    run_report(
        workspace,
        load_corpus_run(workspace),
        settings,
        ledger,
        blog_path="output/blog.md",
        duration_seconds=0.0,
    )
    return workspace


def fixture_topic(topic_id: str = "agentic-ai-frameworks") -> GoldenTopic:
    """A golden topic whose topic string matches the workflow fixtures."""
    return GoldenTopic(id=topic_id, topic=TOPIC, pages=3, per_page=10, max_urls=URL_COUNT)
