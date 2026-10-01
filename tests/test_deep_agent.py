"""US-3.2: stub tools, sub-agent wiring, and the end-to-end skeleton."""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from agents.deep_research import (
    ORCHESTRATOR_TOOLS,
    SUBAGENT_TOOLS,
    UnsupportedModelProvider,
    build_deep_agent,
)
from evaluations.fakes import ScriptedChatModel
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import FetchedPage, Source
from schemas.tool_io import SourceMetadata
from services.llm_service import LLMService
from services.workspace import create_run_workspace
from tools.registry import TOOLS
from tools.stubs import RAW_HTML_MARKER
from workflows.research_run import invoke_agent

PHASES = (
    "plan",
    "search",
    "normalize",
    "fetch",
    "index",
    "synthesize",
    "write",
    "citations",
    "report",
)


def _call(name: str, args: dict[str, Any], index: int) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call-{index}", "type": "tool_call"}],
    )


def _script() -> list[AIMessage]:
    return [
        _call("write_todos", {"todos": [{"content": p, "status": "pending"} for p in PHASES]}, 1),
        _call("task", {"subagent_type": "search_agent", "description": "search"}, 2),
        AIMessage(content="search done"),
        _call("task", {"subagent_type": "research_agent", "description": "collect"}, 3),
        AIMessage(content="collect done"),
        _call("task", {"subagent_type": "analyst_agent", "description": "synthesize"}, 4),
        _call("write_file", {"file_path": "/research/summary.md", "content": "# Summary"}, 5),
        AIMessage(content="summary written"),
        _call("task", {"subagent_type": "writer_agent", "description": "write"}, 6),
        _call("write_file", {"file_path": "/output/blog.md", "content": "# Blog"}, 7),
        AIMessage(content="blog written"),
        _call("task", {"subagent_type": "general-purpose", "description": "should not exist"}, 8),
        AIMessage(content="skeleton complete"),
    ]


def _build(tmp_path: Path) -> tuple[Any, Any, dict[str, list[str]], list[str]]:
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    settings = RunSettings(_env_file=None)
    workspace = create_run_workspace(request, tmp_path)
    bound: dict[str, list[str]] = {}
    contexts: list[str] = []

    def on_call(tools: list[str], messages: list[BaseMessage]) -> None:
        contexts.extend(str(message.content) for message in messages)
        if tools:
            bound["|".join(tools)] = tools

    fake = ScriptedChatModel(script=_script(), on_call=on_call)
    agent = build_deep_agent(LLMService(settings, fake_model=fake), workspace)
    return agent, workspace, bound, contexts


def test_stub_tools_are_registered_with_typed_contracts() -> None:
    for name in (
        "google_search",
        "normalize_results",
        "fetch_url",
        "extract_markdown",
        "collect_source",
        "build_index",
        "validate_citations",
        "write_run_report",
    ):
        assert name in TOOLS


def test_collect_source_returns_metadata_only_and_composes_fetch_and_extract() -> None:
    output = TOOLS["collect_source"].invoke({"rank": 7, "url": "https://example.com/a"})
    assert isinstance(output, SourceMetadata)
    assert output.source_id == "S-07"
    assert output.path.startswith("research/007_")
    assert "body_markdown" not in output.model_dump()


def test_fetch_stub_carries_the_marker_and_extract_stub_does_not() -> None:
    page = TOOLS["fetch_url"].invoke({"url": "https://example.com/a"})
    assert isinstance(page, FetchedPage)
    assert RAW_HTML_MARKER in page.html
    source = TOOLS["extract_markdown"].invoke({"page": page.model_dump(), "source_id": "S-01"})
    assert isinstance(source, Source)
    assert RAW_HTML_MARKER not in source.body_markdown


def test_build_fails_when_the_model_provider_cannot_be_resolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    workspace = create_run_workspace(request, tmp_path)
    fake = ScriptedChatModel(script=[AIMessage(content="x")])
    monkeypatch.setattr("agents.deep_research.get_model_provider", lambda model: None)
    with pytest.raises(UnsupportedModelProvider):
        build_deep_agent(LLMService(RunSettings(_env_file=None), fake_model=fake), workspace)


def test_skeleton_runs_end_to_end_with_the_four_subagents(tmp_path: Path) -> None:
    agent, workspace, bound, contexts = _build(tmp_path)
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    result = invoke_agent(agent, request, RunSettings(_env_file=None))

    orchestrator = next(tools for tools in bound.values() if "task" in tools)
    for name in ORCHESTRATOR_TOOLS:
        assert name in orchestrator
    for absent in ("fetch_url", "extract_markdown", "collect_source"):
        assert absent not in orchestrator

    search = next(tools for tools in bound.values() if "google_search" in tools)
    assert "task" not in search and "write_todos" not in search
    research = next(tools for tools in bound.values() if "collect_source" in tools)
    assert "task" not in research
    assert any(
        "collect_source" in tools and "google_search" not in tools for tools in bound.values()
    )

    assert [todo["content"] for todo in result["todos"]] == list(PHASES)
    assert not any(RAW_HTML_MARKER in text for text in contexts)
    assert (workspace.root / "research/summary.md").exists()
    assert (workspace.root / "output/blog.md").exists()


def test_general_purpose_subagent_is_not_available(tmp_path: Path) -> None:
    agent, _, _, _ = _build(tmp_path)
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    result = invoke_agent(agent, request, RunSettings(_env_file=None))
    task_messages = [
        str(message.content)
        for message in result["messages"]
        if getattr(message, "name", "") == "task"
    ]
    assert any("general-purpose" in text for text in task_messages)


def test_subagent_tool_assignment_matches_pd_005() -> None:
    assert SUBAGENT_TOOLS["search_agent"] == ("google_search",)
    assert SUBAGENT_TOOLS["research_agent"] == ("collect_source",)
    assert SUBAGENT_TOOLS["analyst_agent"] == ()
    assert SUBAGENT_TOOLS["writer_agent"] == ()
