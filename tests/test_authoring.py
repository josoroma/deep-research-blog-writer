"""US-7.1 to US-7.4: summary, cited draft, citation gate, and repair."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from pydantic import HttpUrl

from agents.deep_research import SUBAGENT_TOOLS, build_deep_agent
from evaluations.fakes import ScriptedChatModel
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult, Source
from schemas.state import RunState, UrlOutcome
from services.authoring import (
    REQUIRED_HEADINGS,
    check_blog,
    check_summary,
    validate_citations,
)
from services.corpus import CorpusSource, write_index, write_source
from services.llm_service import LLMService
from services.workspace import create_run_workspace
from tools.authoring_tools import AuthoringSession
from tools.registry import create_tool_registry
from workflows import cli
from workflows.authoring_run import load_corpus_run, run_authoring
from workflows.search_run import tool_runtime

FETCHED_AT = datetime(2026, 10, 1, tzinfo=UTC)
HEADINGS = "\n\n".join(f"## {title}\n\nSection body." for title in REQUIRED_HEADINGS)


def settings() -> RunSettings:
    return RunSettings(_env_file=None, crawler_contact="https://example.org/contact")


def source(rank: int, title: str = "Kept") -> CorpusSource:
    return CorpusSource(
        source=Source(
            source_id=f"S-{rank:02d}",
            url=HttpUrl(f"https://example.com/post/{rank}"),
            title=title,
            author=None,
            published=None,
            body_markdown="Evidence body.",
            word_count=2,
            fetched_at=FETCHED_AT,
        ),
        path=f"research/{rank:03d}_kept.md",
        rank=rank,
    )


def corpus(tmp_path: Path, ranks: list[int] | None = None) -> Path:
    ranks = ranks or [1, 2]
    request = ResearchRequest(topic="Authoring fixtures")
    workspace = create_run_workspace(request, tmp_path)
    records = [source(rank) for rank in ranks]
    for record in records:
        write_source(workspace.root, record)
    write_index(workspace.root, records)
    clean = [
        SearchResult(
            url=record.source.url,
            title=record.source.title,
            snippet="Fixture",
            rank=record.rank,
            query=request.topic,
        )
        for record in records
    ]
    run = RunState(
        run_id=workspace.run_id,
        topic=request.topic,
        completed_phases=["index"],
        clean_results=clean,
        url_outcomes={
            str(record.source.url): UrlOutcome(
                rank=record.rank,
                url=record.source.url,
                outcome="extracted",
                source_id=record.source.source_id,
            )
            for record in records
        },
    )
    (workspace.root / "corpus_state.json").write_text(run.model_dump_json(), encoding="utf-8")
    return workspace.root


def summary_text() -> str:
    return "\n\n".join(
        [
            "## Recurring themes",
            "### Theme: Agents coordinate\n\nSources agree on orchestration [S-01].",
            "## Named frameworks",
            "LangGraph appears throughout [S-02].",
            "## Points of agreement",
            "Both sources accept typed state [S-01].",
            "## Points of disagreement",
            "They differ on planning [S-02].",
            "## Gaps",
            "No source covers cost.",
            "## Suggested outline",
            "Introduction, then analysis.",
        ]
    )


def blog_text(citation: str = "S-01", url: str = "https://example.com/post/1") -> str:
    body = " ".join(["word"] * 400)
    cited = REQUIRED_HEADINGS[:-1]
    sections = "\n\n".join(f"## {title}\n\n{body} [{citation}]." for title in cited)
    references = f"## References\n\n- [{citation}] Kept — {url}\n"
    return f"# Cited draft\n\n{sections}\n\n{references}"


def test_summary_requires_sections_and_real_sources(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    assert not check_summary(root).passed
    (root / "research/summary.md").write_text(summary_text(), encoding="utf-8")
    checked = check_summary(root)
    assert checked.passed
    assert checked.referenced_source_ids == ["S-01", "S-02"]


def test_summary_rejects_a_theme_without_a_source(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    text = summary_text().replace("[S-01].", "no citation.")
    (root / "research/summary.md").write_text(text, encoding="utf-8")
    checked = check_summary(root)
    assert not checked.passed
    assert checked.themes_without_sources


def test_summary_rejects_an_unknown_source(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    text = summary_text().replace("[S-02]", "[S-31]")
    (root / "research/summary.md").write_text(text, encoding="utf-8")
    assert check_summary(root).unknown_source_ids == ["S-31"]


def test_blog_headings_and_length(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(blog_text(), encoding="utf-8")
    checked = check_blog(root)
    assert checked.headings_valid
    assert checked.within_length
    assert checked.reason is None


def test_short_draft_is_kept_and_records_blog_length(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(HEADINGS.join(["# Short\n\n", ""]), encoding="utf-8")
    checked = check_blog(root)
    assert checked.headings_valid
    assert not checked.within_length
    assert checked.reason == "blog_length"
    assert (root / "output/blog.md").exists()


def test_resolved_citations_pass(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(blog_text(), encoding="utf-8")
    finding = validate_citations(root)
    assert finding.passed
    assert finding.citations_checked == 1


def test_dangling_citation_is_reported(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(blog_text("S-31"), encoding="utf-8")
    finding = validate_citations(root)
    assert not finding.passed
    assert finding.dangling_source_ids == ["S-31"]


def test_missing_reference_is_a_mismatch(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    text = blog_text().replace("- [S-01] Kept — https://example.com/post/1\n", "")
    (root / "output/blog.md").write_text(text, encoding="utf-8")
    finding = validate_citations(root)
    assert finding.mismatched_source_ids == ["S-01"]


def test_reference_with_a_different_url_is_a_mismatch(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(
        blog_text(url="https://example.com/other"), encoding="utf-8"
    )
    assert validate_citations(root).mismatched_source_ids == ["S-01"]


def test_validate_citations_tool_records_the_phase(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(blog_text(), encoding="utf-8")
    run = load_corpus_run(root)
    registry = create_tool_registry(authoring_session=AuthoringSession(root, run))
    output = registry["validate_citations"].invoke({}, tool_runtime(run))
    assert output.passed  # type: ignore[attr-defined]
    assert output.run.completed_phases[-1] == "citations"  # type: ignore[attr-defined]


def test_writer_has_no_network_tool() -> None:
    assert "collect_source" not in SUBAGENT_TOOLS["writer_agent"]
    assert "google_search" not in SUBAGENT_TOOLS["writer_agent"]
    assert SUBAGENT_TOOLS["analyst_agent"] == ()


def test_agent_writes_the_summary_but_not_a_source(tmp_path: Path) -> None:
    root = corpus(tmp_path)
    before = (root / "research/001_kept.md").read_bytes()
    script = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"file_path": "/research/summary.md", "content": summary_text()},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"file_path": "/research/001_kept.md", "content": "overwrite"},
                    "id": "call-2",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="done"),
    ]
    agent = build_deep_agent(
        LLMService(settings(), fake_model=ScriptedChatModel(script=script)),
        create_run_workspace(ResearchRequest(topic="Authoring probe"), tmp_path),
    )
    agent.invoke(
        {"messages": [{"role": "user", "content": "summarize"}], "run": load_corpus_run(root)},
        config={"recursion_limit": 20},
    )
    assert (root / "research/001_kept.md").read_bytes() == before


def test_repair_loop_stops_after_two_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = corpus(tmp_path)
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(blog_text("S-31"), encoding="utf-8")
    calls: list[str] = []

    def fake_invoke(self: object, payload: dict[str, object], config: object) -> dict[str, object]:
        calls.append(str(payload["messages"]))
        return {}

    monkeypatch.setattr("langgraph.graph.state.CompiledStateGraph.invoke", fake_invoke)
    model = ScriptedChatModel(script=[])
    summary = run_authoring(root, settings(), llm=LLMService(settings(), fake_model=model))
    assert summary.status == "failed"
    assert summary.reason == "dangling_citations"
    assert summary.repair_passes == 2
    assert summary.dangling_source_ids == ["S-31"]
    report = json.loads((root / "output/authoring.json").read_text())
    assert report["dangling_source_ids"] == ["S-31"]
    assert "[S-31]" in (root / "output/blog.md").read_text(encoding="utf-8")


def test_clean_draft_passes_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = corpus(tmp_path)
    (root / "research/summary.md").write_text(summary_text(), encoding="utf-8")
    (root / "output").mkdir()
    (root / "output/blog.md").write_text(blog_text(), encoding="utf-8")
    monkeypatch.setattr(
        "langgraph.graph.state.CompiledStateGraph.invoke",
        lambda self, payload, config: {},
    )
    summary = run_authoring(
        root, settings(), llm=LLMService(settings(), fake_model=ScriptedChatModel(script=[]))
    )
    assert summary.status == "completed"
    assert summary.repair_passes == 0
    assert summary.citations_checked == 1


def test_author_cli_rejects_a_workspace_without_a_corpus() -> None:
    assert cli.main(["--author-only"], settings=settings()) == 2
