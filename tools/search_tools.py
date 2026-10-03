"""Search tools bound to one run, with validated LangGraph state updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from schemas.search import QueryVariants, SearchPlanOutput
from schemas.state import RunState, UrlOutcome
from schemas.tool_io import (
    GoogleSearchInput,
    GoogleSearchOutput,
    NormalizeResultsInput,
    NormalizeResultsOutput,
)
from tools.base import TypedTool

if TYPE_CHECKING:
    from services.search_session import SearchSession
    from tools.base import Runtime, ToolRegistry


def register_search_tools(registry: ToolRegistry, session: SearchSession | None) -> None:
    def current_run(runtime: Runtime | None) -> tuple[SearchSession, RunState]:
        if session is None or runtime is None:
            raise ValueError("Search tools require a per-run SearchSession and ToolRuntime")
        current = RunState.model_validate(runtime.state["run"])
        if current.run_id != session.workspace.run_id or current.topic != session.request.topic:
            raise ValueError("SearchSession does not match the active run")
        return session, current

    def plan_search(request: QueryVariants, runtime: Runtime | None) -> SearchPlanOutput:
        bound, current = current_run(runtime)
        plan = bound.plan(request)
        phases = list(current.completed_phases)
        if "plan" not in phases:
            phases.append("plan")
        return SearchPlanOutput(
            plan=plan,
            run=current.replaced(query_variants=plan.variants, completed_phases=phases),
        )

    def google_search(request: GoogleSearchInput, runtime: Runtime | None) -> GoogleSearchOutput:
        bound, _ = current_run(runtime)
        # Pages may be called together in one model turn. Keep page outputs stateless
        # so parallel tools cannot issue competing writes to LangGraph's run channel.
        return GoogleSearchOutput(results=bound.search(request.query, request.page))

    def normalize(
        request: NormalizeResultsInput, runtime: Runtime | None
    ) -> NormalizeResultsOutput:
        bound, current = current_run(runtime)
        normalized = bound.normalize(request.max_urls)
        phases = list(current.completed_phases)
        for phase in ("search", "normalize"):
            if phase not in phases:
                phases.append(phase)
        outcomes = {
            str(result.url): UrlOutcome(rank=result.rank, url=result.url)
            for result in normalized.clean_results
        }
        return NormalizeResultsOutput(
            **normalized.model_dump(),
            run=current.replaced(
                clean_results=normalized.clean_results,
                url_outcomes=outcomes,
                completed_phases=phases,
            ),
        )

    registry.register(
        TypedTool[QueryVariants, SearchPlanOutput](
            name="plan_search",
            input_model=QueryVariants,
            output_model=SearchPlanOutput,
            handler=plan_search,
            updates_state=True,
            description="Save 2 or 3 distinct variants and the bounded plan before searching.",
        )
    )
    registry.register(
        TypedTool[GoogleSearchInput, GoogleSearchOutput](
            name="google_search",
            input_model=GoogleSearchInput,
            output_model=GoogleSearchOutput,
            handler=google_search,
            description="Search a planned query/page through the configured API; save raw results.",
        )
    )
    registry.register(
        TypedTool[NormalizeResultsInput, NormalizeResultsOutput](
            name="normalize_results",
            input_model=NormalizeResultsInput,
            output_model=NormalizeResultsOutput,
            handler=normalize,
            updates_state=True,
            description="Canonicalize, filter, deduplicate, cap and save all planned results.",
        )
    )
