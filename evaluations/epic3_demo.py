"""Offline PM demonstration of the EPIC-3 deep agent skeleton.

Runs the real CLI path with a scripted fake model into a temporary `runs/` root and
prints the acceptance facts: sub-agents and their tools, the orchestrator's tools,
prompt provenance, todos, files on disk, containment, and the marker's absence from
every model context.
"""

import tempfile
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend
from langchain_core.messages import AIMessage, BaseMessage

from agents.deep_research import ORCHESTRATOR_TOOLS, SUBAGENT_TOOLS, build_deep_agent
from evaluations.fakes import ScriptedChatModel
from prompts.catalog import load_prompt
from schemas.common import Contract
from schemas.config import AGENT_NAMES, RunSettings
from schemas.requests import ResearchRequest
from schemas.workspace import RunWorkspace
from services.llm_service import LLMService
from services.workspace import create_run_workspace
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


class DemoResult(Contract):
    mode: str = "offline; no provider request"
    topic: str
    run_id: str
    workspace: str
    subagents: dict[str, list[str]]
    orchestrator_tools: list[str]
    bound_tools: dict[str, list[str]]
    prompts_loaded: dict[str, int]
    todos: list[str]
    files_on_disk: list[str]
    marker_in_model_contexts: bool
    general_purpose_rejected: bool
    containment_refused: bool
    blog_exists: bool


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


def _containment_probe(workspace: RunWorkspace) -> bool:
    """A traversal write must be refused and must leave no file outside the workspace."""
    backend = FilesystemBackend(root_dir=workspace.root, virtual_mode=True)
    try:
        backend.write("/../escape.md", "x")
    except ValueError:
        return not (workspace.root.parent / "escape.md").exists()
    return False


def main() -> int:
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    settings = RunSettings(_env_file=None)
    bound: dict[str, list[str]] = {}
    contexts: list[str] = []

    def on_call(tools: list[str], messages: list[BaseMessage]) -> None:
        contexts.extend(str(message.content) for message in messages)
        if tools:
            bound["|".join(tools)] = tools

    with tempfile.TemporaryDirectory(prefix="epic3-demo-") as directory:
        runs_root = Path(directory) / "runs"
        runs_root.mkdir()
        workspace = create_run_workspace(request, runs_root)
        fake = ScriptedChatModel(script=_script(), on_call=on_call)
        agent = build_deep_agent(LLMService(settings, fake_model=fake), workspace)
        result = invoke_agent(agent, request, settings)
        files = sorted(
            str(path.relative_to(workspace.root))
            for path in workspace.root.rglob("*")
            if path.is_file()
        )
        blog_exists = (workspace.root / "output/blog.md").exists()
        containment = _containment_probe(workspace)

    tool_messages = [
        str(message.content)
        for message in result["messages"]
        if getattr(message, "name", "") == "task"
    ]
    output = DemoResult(
        topic=request.topic,
        run_id=workspace.run_id,
        workspace=str(workspace.root),
        subagents={agent: list(tools) for agent, tools in SUBAGENT_TOOLS.items()},
        orchestrator_tools=list(ORCHESTRATOR_TOOLS),
        bound_tools=bound,
        prompts_loaded={agent: len(load_prompt(agent)) for agent in AGENT_NAMES},
        todos=[todo["content"] for todo in result.get("todos", [])],
        files_on_disk=files,
        marker_in_model_contexts=any(RAW_HTML_MARKER in text for text in contexts),
        general_purpose_rejected=any("general-purpose" in text for text in tool_messages),
        containment_refused=containment,
        blog_exists=blog_exists,
    )
    print(output.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
