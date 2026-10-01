"""US-3.3: real-disk persistence and workspace containment."""

from pathlib import Path

import pytest
from deepagents.backends import FilesystemBackend
from langchain_core.messages import AIMessage, BaseMessage

from agents.deep_research import build_deep_agent
from evaluations.fakes import ScriptedChatModel
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from services.llm_service import LLMService
from services.workspace import create_run_workspace
from workflows.research_run import invoke_agent


def _call(name: str, args: dict[str, object], index: int) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call-{index}", "type": "tool_call"}],
    )


def test_agent_file_reaches_disk_before_the_next_model_step(tmp_path: Path) -> None:
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    workspace = create_run_workspace(request, tmp_path)
    summary = workspace.root / "research/summary.md"
    seen: list[bool] = []

    def on_call(tools: list[str], messages: list[BaseMessage]) -> None:
        seen.append(summary.exists())

    script = [
        _call("task", {"subagent_type": "analyst_agent", "description": "synthesize"}, 1),
        _call("write_file", {"file_path": "/research/summary.md", "content": "# Summary"}, 2),
        AIMessage(content="summary written"),
        AIMessage(content="skeleton complete"),
    ]
    fake = ScriptedChatModel(script=script, on_call=on_call)
    agent = build_deep_agent(LLMService(RunSettings(_env_file=None), fake_model=fake), workspace)
    invoke_agent(agent, request, RunSettings(_env_file=None))

    assert summary.read_text(encoding="utf-8") == "# Summary"
    # The write is on disk by the time the orchestrator's next model call happens.
    assert seen[-1] is True


def test_traversal_and_symlink_escapes_are_refused(tmp_path: Path) -> None:
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    workspace = create_run_workspace(request, tmp_path)
    backend = FilesystemBackend(root_dir=workspace.root, virtual_mode=True)

    with pytest.raises(ValueError, match="traversal"):
        backend.write("/../escape.md", "x")

    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace.root / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="outside root"):
        backend.write("/link/escape.md", "x")

    assert not (tmp_path / "escape.md").exists()
    assert not (outside / "escape.md").exists()
    assert not (Path.home() / "escape.md").exists()
