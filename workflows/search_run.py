"""Executable Search milestone using registered tools and typed state."""

from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel

from agents.search_planner import derive_query_variants
from schemas.common import Contract
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.search import NormalizationCounts, QueryVariants, SearchPlanOutput
from schemas.state import RunState
from schemas.tool_io import GoogleSearchOutput, NormalizeResultsOutput
from services.llm_service import LLMService
from services.observability import (
    observed_config,
    observed_workflow,
)
from services.search_provider import SearchProvider, SearchProviderError, create_search_provider
from services.search_session import SearchSession
from services.workspace import create_run_workspace
from tools.registry import Runtime, create_tool_registry


class SearchSummary(Contract):
    run_id: str
    workspace: str
    status: Literal["completed", "failed"]
    provider: str
    search_plan_path: str
    raw_results_path: str
    clean_results_path: str
    counts: NormalizationCounts | None = None
    error: str | None = None


def tool_runtime(run: RunState) -> Runtime:
    """Application-owned runtime for the deterministic milestone command."""
    return Runtime(
        state={"run": run, "messages": []},
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="search-milestone",
        store=None,
    )


@observed_workflow("search")
def run_search(
    request: ResearchRequest,
    settings: RunSettings,
    *,
    runs_root: Path,
    variants: QueryVariants | None = None,
    search_provider: SearchProvider | None = None,
    fake_model: BaseChatModel | None = None,
) -> SearchSummary:
    provider = search_provider if search_provider is not None else create_search_provider(settings)
    provider.preflight(request.per_page)
    llm = LLMService(settings, fake_model=fake_model) if variants is None else None
    if llm is not None:
        llm.for_agent("orchestrator")
    if variants and any(
        query.casefold() == request.topic.casefold() for query in variants.variants
    ):
        raise ValueError("variants must differ from the topic")
    workspace = create_run_workspace(request, runs_root)
    planned_variants = variants
    if planned_variants is None:
        assert llm is not None
        planned_variants = derive_query_variants(
            request, llm, config=observed_config(settings.recursion_limit)
        )
    session = SearchSession(request, workspace, provider)
    registry = create_tool_registry(session)
    run = RunState(run_id=workspace.run_id, topic=request.topic)
    counts = None
    error = None
    try:
        planned = registry["plan_search"].invoke(planned_variants, tool_runtime(run))
        assert isinstance(planned, SearchPlanOutput)
        run = planned.run
        for call in planned.plan.calls:
            output = registry["google_search"].invoke(
                {"query": call.query, "page": call.page}, tool_runtime(run)
            )
            assert isinstance(output, GoogleSearchOutput)
        normalized = registry["normalize_results"].invoke(
            {"max_urls": request.max_urls}, tool_runtime(run)
        )
        assert isinstance(normalized, NormalizeResultsOutput)
        counts = normalized.counts
    except Exception as failure:  # noqa: BLE001 - credential-safe CLI boundary
        error = str(failure) if isinstance(failure, SearchProviderError) else type(failure).__name__
    return SearchSummary(
        run_id=workspace.run_id,
        workspace=str(workspace.root),
        provider=provider.name,
        status="failed" if error is not None else "completed",
        error=error,
        counts=counts,
        search_plan_path=str(workspace.root / "search_plan.json"),
        raw_results_path=str(workspace.root / "search_results.json"),
        clean_results_path=str(workspace.root / "clean_results.json"),
    )
