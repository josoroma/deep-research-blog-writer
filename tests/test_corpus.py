"""US-6.1 to US-6.3: source files, the corpus index, and contained failures."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from pydantic import HttpUrl

from agents.deep_research import build_deep_agent
from evaluations.epic6_demo import run_demo
from evaluations.fakes import ScriptedChatModel
from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock, fixture_html
from schemas.config import RunSettings
from schemas.content import ExtractionResult
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult, Source
from schemas.state import RunState
from schemas.tool_io import CollectSourceOutput, ExtractMarkdownInput, SourceMetadata
from services.artifacts import write_json
from services.corpus import (
    CorpusSource,
    parse_source,
    render_index,
    render_source,
    source_path,
    source_slug,
    write_source,
)
from services.extraction_service import ExtractionService
from services.fetch_service import FetchService
from services.llm_service import LLMService
from services.workspace import create_run_workspace
from tools.corpus_tools import CorpusSession
from tools.registry import create_tool_registry
from workflows import cli
from workflows.corpus_run import run_corpus
from workflows.fetch_run import load_search_workspace
from workflows.search_run import tool_runtime

FETCHED_AT = datetime(2026, 10, 1, tzinfo=UTC)


def settings() -> RunSettings:
    return RunSettings(_env_file=None, crawler_contact="https://example.org/contact")


def workspace_with(tmp_path: Path, paths: list[str]) -> tuple[Path, RunState]:
    request = ResearchRequest(topic="Research corpus fixtures")
    workspace = create_run_workspace(request, tmp_path)
    clean = [
        SearchResult(
            url=HttpUrl(f"https://fixture.test{path}"),
            title=f"Fixture {path.strip('/')}",
            snippet="Fixture",
            rank=rank,
            query=request.topic,
        )
        for rank, path in enumerate(paths, 1)
    ]
    write_json(
        workspace.root / "clean_results.json", [row.model_dump(mode="json") for row in clean]
    )
    return workspace.root, load_search_workspace(workspace.root)


def test_title_slug_and_url_fallback() -> None:
    url = HttpUrl("https://fixture.test/non-ascii")
    assert source_slug("LangGraph vs CrewAI: A 2026 Comparison", url) == (
        "langgraph-vs-crewai-a-2026-comparison"
    )
    assert source_slug("标题", url) == "fixture-test-non-ascii"
    assert source_path(7, "langgraph") == "research/007_langgraph.md"


def test_front_matter_round_trips_and_keeps_the_body(tmp_path: Path) -> None:
    source = Source(
        source_id="S-07",
        url=HttpUrl("https://example.com/post?id=7"),
        title="LangGraph vs CrewAI: A 2026 Comparison",
        author=None,
        published=None,
        body_markdown="Clean body kept verbatim.\n\nSecond paragraph.",
        word_count=6,
        fetched_at=FETCHED_AT,
    )
    record = CorpusSource(source=source, path="research/007_langgraph.md", rank=7)
    text = render_source(record)
    assert text.startswith("---\n")
    assert "author: null\n" in text
    assert "fetched: '2026-10-01T00:00:00Z'\n" in text
    assert text.index("# LangGraph vs CrewAI: A 2026 Comparison\n") < text.index("Clean body")
    destination = tmp_path / record.path
    destination.parent.mkdir(parents=True)
    destination.write_text(text, encoding="utf-8")
    parsed = parse_source(destination, text)
    assert parsed.source.body_markdown.strip() == source.body_markdown
    assert parsed.source.author is None and parsed.source.published is None
    assert parsed.source.source_id == "S-07"


def test_demo_proves_acceptance(tmp_path: Path) -> None:
    report = run_demo(tmp_path)
    assert report["rank_gaps"] == [3, 4, 5, 6, 9]
    assert report["title_slug"].endswith("polite-evidence-collection.md")
    assert report["url_slug_fallback"].endswith("fixture-test-non-ascii.md")
    assert report["immutable_source_refused"] is True
    assert report["index_rows"] == 5
    workspace = Path(report["workspace"])
    rank_four = workspace / "research/004_fixture-blocked.md"
    assert not rank_four.exists()
    assert not (workspace / "research/003_fixture-missing.md").exists()
    kept = next(workspace.glob("research/004_*.md"), None)
    assert kept is None


def test_rank_gaps_follow_clean_rank(tmp_path: Path) -> None:
    root, run = workspace_with(tmp_path, ["/missing", "/article"])
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as fetcher:
        summary = run_corpus(root, settings(), fetcher=fetcher)
    assert summary.outcomes == {"unreachable": 1, "extracted": 1}
    files = sorted(path.name for path in (root / "research").glob("*.md"))
    assert files == ["002_polite-evidence-collection.md", "index.md"]
    text = (root / "research/002_polite-evidence-collection.md").read_text(encoding="utf-8")
    assert "source_id: S-02\n" in text


def test_collect_source_returns_metadata_only(tmp_path: Path) -> None:
    root, run = workspace_with(tmp_path, ["/article"])
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as fetcher:
        session = CorpusSession(root, run, fetcher, ExtractionService())
        registry = create_tool_registry(
            fetcher=fetcher, extractor=ExtractionService(), corpus_session=session
        )
        output = registry["collect_source"].invoke(
            {"rank": 1, "url": "https://fixture.test/article"}, tool_runtime(run)
        )
    assert isinstance(output, CollectSourceOutput)
    assert isinstance(output.source, SourceMetadata)
    assert set(output.source.model_dump()) == {"source_id", "path", "title", "word_count"}
    assert output.source.source_id == "S-01"
    assert "body_markdown" not in output.model_dump_json()


def test_failed_rank_records_outcome_without_a_file(tmp_path: Path) -> None:
    root, run = workspace_with(tmp_path, ["/thin"])
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as fetcher:
        summary = run_corpus(root, settings(), fetcher=fetcher)
    assert summary.sources_written == 0
    assert summary.outcomes == {"too_thin": 1}
    state = RunState.model_validate_json((root / "corpus_state.json").read_text())
    outcome = next(iter(state.url_outcomes.values()))
    assert outcome.outcome == "too_thin" and outcome.source_id is None
    assert list((root / "research").glob("[0-9][0-9][0-9]_*.md")) == []


def test_extraction_exception_is_contained(tmp_path: Path) -> None:
    root, run = workspace_with(tmp_path, ["/article", "/retry"])

    class Exploding:
        def extract(self, request: ExtractMarkdownInput) -> ExtractionResult:
            if "retry" in str(request.page.final_url):
                raise RuntimeError("sensitive parser detail")
            return ExtractionService().extract(request)

    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as fetcher:
        summary = run_corpus(root, settings(), fetcher=fetcher, extractor=Exploding())  # type: ignore[arg-type]
    assert summary.sources_written == 1
    assert summary.outcomes == {"extracted": 1, "failed": 1}
    state = RunState.model_validate_json((root / "corpus_state.json").read_text())
    failed = next(item for item in state.url_outcomes.values() if item.outcome == "failed")
    assert failed.reason == "RuntimeError"
    assert "sensitive" not in (root / "corpus_state.json").read_text()


def test_index_rows_match_front_matter(tmp_path: Path) -> None:
    root, _ = workspace_with(tmp_path, ["/article", "/missing-metadata"])
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as fetcher:
        run_corpus(root, settings(), fetcher=fetcher)
    index = (root / "research/index.md").read_text(encoding="utf-8")
    assert "| source_id | title | host | word_count | url |" in index
    assert index.count("\n| S-") == 2
    record = parse_source(
        root / "research/001_polite-evidence-collection.md",
        (root / "research/001_polite-evidence-collection.md").read_text(encoding="utf-8"),
    )
    assert f"| {record.source.source_id} | {record.source.title} | fixture.test |" in index


def test_index_escapes_table_breaking_titles(tmp_path: Path) -> None:
    source = Source(
        source_id="S-03",
        url=HttpUrl("https://example.com/a"),
        title="A | B",
        author=None,
        published=None,
        body_markdown="body",
        word_count=1,
        fetched_at=FETCHED_AT,
    )
    record = CorpusSource(source=source, path="research/003_a-b.md", rank=3)
    write_source(tmp_path, record)

    assert r"A \| B" in render_index([record])


def test_existing_source_is_not_fetched_again(tmp_path: Path) -> None:
    root, run = workspace_with(tmp_path, ["/article"])
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as fetcher:
        run_corpus(root, settings(), fetcher=fetcher)
        before = transport.counts.copy()
        session = CorpusSession(root, run, fetcher, ExtractionService())
        registry = create_tool_registry(
            fetcher=fetcher, extractor=ExtractionService(), corpus_session=session
        )
        output = registry["collect_source"].invoke(
            {"rank": 1, "url": "https://fixture.test/article"}, tool_runtime(run)
        )
    assert isinstance(output, CollectSourceOutput)
    assert output.source is not None and output.source.source_id == "S-01"
    assert transport.counts == before


def test_agent_cannot_overwrite_or_edit_a_source_file(tmp_path: Path) -> None:
    request = ResearchRequest(topic="Immutable source probe")
    workspace = create_run_workspace(request, tmp_path)
    source = Source(
        source_id="S-01",
        url=HttpUrl("https://example.com/a"),
        title="Kept",
        author=None,
        published=None,
        body_markdown="original body",
        word_count=2,
        fetched_at=FETCHED_AT,
    )
    record = CorpusSource(source=source, path="research/001_kept.md", rank=1)
    write_source(workspace.root, record)
    before = (workspace.root / record.path).read_bytes()
    script = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"file_path": "/research/001_kept.md", "content": "overwrite"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "edit_file",
                    "args": {
                        "file_path": "/research/001_kept.md",
                        "old_string": "original body",
                        "new_string": "changed",
                    },
                    "id": "call-2",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="done"),
    ]
    agent = build_deep_agent(
        LLMService(settings(), fake_model=ScriptedChatModel(script=script)), workspace
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "edit the source"}]},
        config={"recursion_limit": 20},
    )
    assert (workspace.root / record.path).read_bytes() == before
    messages = " ".join(str(message.content) for message in result["messages"])
    assert "immutable" in messages


def test_agent_can_still_write_the_summary(tmp_path: Path) -> None:
    request = ResearchRequest(topic="Summary still writable")
    workspace = create_run_workspace(request, tmp_path)
    script = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"file_path": "/research/summary.md", "content": "# Summary"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="done"),
    ]
    agent = build_deep_agent(
        LLMService(settings(), fake_model=ScriptedChatModel(script=script)), workspace
    )
    agent.invoke(
        {"messages": [{"role": "user", "content": "summarize"}]}, config={"recursion_limit": 20}
    )
    assert (workspace.root / "research/summary.md").read_text(encoding="utf-8") == "# Summary"


def test_symlink_source_destination_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("unchanged")
    research = tmp_path / "research"
    research.mkdir()
    (research / "001_kept.md").symlink_to(outside)
    source = Source(
        source_id="S-01",
        url=HttpUrl("https://example.com/a"),
        title="Kept",
        author=None,
        published=None,
        body_markdown="body",
        word_count=1,
        fetched_at=FETCHED_AT,
    )
    with pytest.raises(ValueError, match="symlink"):
        write_source(tmp_path, CorpusSource(source=source, path="research/001_kept.md", rank=1))
    assert outside.read_text() == "unchanged"


def test_corpus_cli_uses_saved_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = workspace_with(tmp_path, ["/article", "/thin"])
    transport, clock = FixtureHTTP(), VirtualClock()
    service = FetchService(settings(), client=transport.client(), clock=clock, sleep=clock.sleep)
    monkeypatch.setattr("workflows.corpus_run.FetchService", lambda _: service)
    assert cli.main(["--corpus-only", "--workspace", str(root)], settings=settings()) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["outcomes"] == {"extracted": 1, "too_thin": 1}
    assert output["sources_indexed"] == 1
    assert service._closed


def test_corpus_cli_rejects_missing_workspace() -> None:
    assert cli.main(["--corpus-only"], settings=settings()) == 2


def test_fixture_html_is_packaged() -> None:
    assert "标题" in fixture_html("non-ascii")
