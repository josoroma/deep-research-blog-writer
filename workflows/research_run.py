"""Run the skeleton end to end: validate, preflight, create the workspace, invoke."""

from pathlib import Path
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from agents.deep_research import build_deep_agent
from schemas.common import Contract
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.state import RunState
from services.llm_service import LLMService
from services.observability import (
    observed_config,
    observed_workflow,
)
from services.search_provider import SearchProvider, SearchProviderError, create_search_provider
from services.search_session import SearchSession
from services.workspace import create_run_workspace
from tools.registry import create_tool_registry

BLOG_PATH = "output/blog.md"


class RunSummary(Contract):
    """What the run command prints on exit."""

    run_id: str
    workspace: str
    status: Literal["completed", "failed"]
    blog_path: str
    blog_exists: bool
    error: str | None = None


@observed_workflow("research")
def run_research(
    request: ResearchRequest,
    settings: RunSettings,
    *,
    runs_root: Path,
    fake_model: BaseChatModel | None = None,
    search_provider: SearchProvider | None = None,
) -> RunSummary:
    """Run the skeleton for an already-validated request.

    Order matters: the model service is preflighted before the workspace is created,
    so a missing key never leaves an empty run directory behind.
    """
    llm = LLMService(settings, fake_model=fake_model)
    llm.for_agent("orchestrator")
    provider = search_provider if search_provider is not None else create_search_provider(settings)
    provider.preflight(request.per_page)
    workspace = create_run_workspace(request, runs_root)
    session = SearchSession(request, workspace, provider)
    agent = build_deep_agent(llm, workspace, tool_registry=create_tool_registry(session))
    blog = workspace.root / BLOG_PATH
    try:
        agent.invoke(
            {
                "messages": [HumanMessage(content=request.model_dump_json())],
                "run": RunState(run_id=workspace.run_id, topic=request.topic),
            },
            config=observed_config(settings.recursion_limit),
        )
    except Exception as error:  # noqa: BLE001 - the CLI reports any invocation failure
        return RunSummary(
            run_id=workspace.run_id,
            workspace=str(workspace.root),
            status="failed",
            blog_path=str(blog),
            blog_exists=blog.exists(),
            error=str(error) if isinstance(error, SearchProviderError) else type(error).__name__,
        )
    return RunSummary(
        run_id=workspace.run_id,
        workspace=str(workspace.root),
        status="completed",
        blog_path=str(blog),
        blog_exists=blog.exists(),
    )


def invoke_agent(
    agent: CompiledStateGraph[Any, Any, Any, Any], request: ResearchRequest, settings: RunSettings
) -> dict[str, Any]:
    """Invoke a built agent with the validated request as its initial message."""
    return agent.invoke(
        {"messages": [HumanMessage(content=request.model_dump_json())]},
        config=observed_config(settings.recursion_limit),
    )


class RunInputError(Contract):
    """A rejected run request; the CLI maps this to exit status 2."""

    message: str = Field(min_length=1)
