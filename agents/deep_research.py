"""Assemble the orchestrator deep agent and its four sub-agents (PD-005).

Agents orchestrate; tools execute. This module wires the prompt catalog, the LLM
service, the typed tool registry, and the real-disk workspace backend. It never
imports an HTTP client, constructs a provider client, or passes an inline prompt.
"""

from collections.abc import Sequence
from typing import Any

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    SubAgent,
    create_deep_agent,
)
from deepagents._models import get_model_provider
from deepagents.backends import FilesystemBackend
from deepagents.profiles import register_harness_profile
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from prompts.catalog import load_prompt
from schemas.config import AgentName
from schemas.state import ResearchAgentState
from schemas.workspace import RunWorkspace
from services.llm_service import LLMService
from tools.registry import TOOLS, ToolRegistry

ORCHESTRATOR_TOOLS: tuple[str, ...] = (
    "plan_search",
    "normalize_results",
    "build_index",
    "validate_citations",
    "write_run_report",
)
SUBAGENT_TOOLS: dict[AgentName, tuple[str, ...]] = {
    "search_agent": ("google_search",),
    "research_agent": ("collect_source",),
    "analyst_agent": (),
    "writer_agent": (),
}
SUBAGENT_DESCRIPTIONS: dict[AgentName, str] = {
    "search_agent": "Run paged searches and collect candidate URLs.",
    "research_agent": "Fetch each clean URL and write one immutable source file.",
    "analyst_agent": "Read the corpus and synthesize themes into research/summary.md.",
    "writer_agent": "Draft the cited blog from the corpus and summary.",
}


class UnsupportedModelProvider(ValueError):
    """The model's provider cannot be resolved, so the harness cannot be configured."""


def _tools_for(names: Sequence[str], registry: ToolRegistry) -> list[BaseTool]:
    """Resolve registered tools by name; a missing name fails at build time."""
    return [registry[name].as_langchain_tool() for name in names]


def _disable_general_purpose_subagent(model: BaseChatModel) -> None:
    """Remove the auto-added fifth agent so only the four PD-005 sub-agents exist.

    DeepAgents adds a `general-purpose` sub-agent that inherits the orchestrator's
    tools. That would contradict PD-005 and PD-006, so it is disabled through a
    harness profile registered for the model's provider.
    """
    provider = get_model_provider(model)
    if not provider:
        raise UnsupportedModelProvider(
            f"Cannot resolve a provider for {type(model).__name__}; "
            "the general-purpose sub-agent cannot be disabled"
        )
    register_harness_profile(
        provider,
        HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)),
    )


def build_deep_agent(
    llm: LLMService, workspace: RunWorkspace, *, tool_registry: ToolRegistry = TOOLS
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build the orchestrator with its four sub-agents and the run workspace backend."""
    orchestrator_model = llm.for_agent("orchestrator")
    _disable_general_purpose_subagent(orchestrator_model)
    subagents: list[SubAgent] = [
        {
            "name": agent,
            "description": SUBAGENT_DESCRIPTIONS[agent],
            "system_prompt": load_prompt(agent),
            "tools": _tools_for(SUBAGENT_TOOLS[agent], tool_registry),
            "model": llm.for_agent(agent),
        }
        for agent in SUBAGENT_TOOLS
    ]
    return create_deep_agent(
        model=orchestrator_model,
        tools=_tools_for(ORCHESTRATOR_TOOLS, tool_registry),
        system_prompt=load_prompt("orchestrator"),
        middleware=[TodoListMiddleware()],
        subagents=subagents,
        backend=FilesystemBackend(root_dir=workspace.root, virtual_mode=True),
        state_schema=ResearchAgentState,
    )
