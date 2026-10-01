"""EPIC-5 milestone: consume EPIC-4 clean URLs through registered internal tools."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from schemas.common import Contract
from schemas.config import RunSettings
from schemas.content import ExtractionResult, FetchResult, utc_now
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.state import RunState, UrlOutcome
from services.artifacts import write_json
from services.extraction_service import ExtractionService, create_extraction_service
from services.fetch_service import Fetcher, FetchService, crawler_user_agent
from tools.registry import ToolRegistry, create_tool_registry

ARTIFACT_NAMES = ("fetch_outcomes.json", "extraction_results.json", "fetch_state.json")


class FetchSummary(Contract):
    run_id: str
    workspace: str
    status: Literal["completed", "failed"]
    urls_processed: int
    outcomes: dict[str, int]
    extractor_strategy: str
    files: list[str]
    error: str | None = None


def load_search_workspace(workspace: Path) -> RunState:
    try:
        request = ResearchRequest.model_validate_json((workspace / "request.json").read_text())
        clean = TypeAdapter(list[SearchResult]).validate_json(
            (workspace / "clean_results.json").read_text()
        )
    except OSError as error:
        raise ValueError("Workspace must contain request.json and clean_results.json") from error
    if len(clean) > request.max_urls or [row.rank for row in clean] != list(
        range(1, len(clean) + 1)
    ):
        raise ValueError("Clean results must have contiguous ranks within the saved URL budget")
    return RunState(
        run_id=workspace.name,
        topic=request.topic,
        completed_phases=["plan", "search", "normalize"],
        clean_results=clean,
        url_outcomes={str(row.url): UrlOutcome(rank=row.rank, url=row.url) for row in clean},
    )


def _collect(
    registry: ToolRegistry,
    row: SearchResult,
) -> tuple[FetchResult, ExtractionResult | None, UrlOutcome]:
    try:
        fetched = registry["fetch_url"].invoke({"url": row.url})
        assert isinstance(fetched, FetchResult)
    except Exception as error:
        fetched = FetchResult(
            url=row.url,
            final_url=row.url,
            outcome="unreachable",
            attempts=0,
            reason=f"fetch_error:{type(error).__name__}",
            fetched_at=utc_now(),
        )
    if fetched.page is None:
        return (
            fetched,
            None,
            UrlOutcome.model_validate(
                {
                    "rank": row.rank,
                    "url": row.url,
                    "outcome": fetched.outcome,
                    "reason": fetched.reason,
                }
            ),
        )
    try:
        extracted = registry["extract_markdown"].invoke(
            {
                "page": fetched.page.model_dump(),
                "source_id": f"S-{row.rank:02d}",
                "fetched_at": fetched.fetched_at,
            }
        )
        assert isinstance(extracted, ExtractionResult)
    except Exception as error:
        return (
            fetched,
            None,
            UrlOutcome(
                rank=row.rank,
                url=row.url,
                outcome="extraction_failed",
                reason=f"extraction_error:{type(error).__name__}",
            ),
        )
    return (
        fetched,
        extracted,
        UrlOutcome(
            rank=row.rank,
            url=row.url,
            outcome=extracted.outcome,
            reason=extracted.reason,
            source_id=extracted.source.source_id if extracted.source else None,
        ),
    )


def run_fetch(
    workspace: Path,
    settings: RunSettings,
    *,
    fetcher: Fetcher | None = None,
    extractor: ExtractionService | None = None,
) -> FetchSummary:
    # Validate/preflight everything before opening the client or writing artifacts.
    run = load_search_workspace(workspace)
    crawler_user_agent(settings)
    for name in ARTIFACT_NAMES:
        if (workspace / name).is_symlink():
            raise ValueError(f"Artifact destination is a symlink: {name}")
    extraction = extractor if extractor is not None else create_extraction_service(settings)
    owned = FetchService(settings) if fetcher is None else None
    bound = owned if owned is not None else fetcher
    registry = create_tool_registry(fetcher=bound, extractor=extraction)
    outcomes: dict[str, int] = {}
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda row: _collect(registry, row), run.clean_results))
        completed = run.replaced(
            completed_phases=[*run.completed_phases, "fetch"],
            url_outcomes={str(outcome.url): outcome for _, _, outcome in results},
        )
        outcomes = dict(Counter(outcome.outcome for _, _, outcome in results))
        write_json(
            workspace / ARTIFACT_NAMES[0],
            [
                {"rank": row.rank, **fetched.model_dump(mode="json", exclude={"page"})}
                for row, (fetched, _, _) in zip(run.clean_results, results, strict=True)
            ],
        )
        write_json(
            workspace / ARTIFACT_NAMES[1],
            [
                {"rank": row.rank, "url": str(row.url), **extracted.model_dump(mode="json")}
                for row, (_, extracted, _) in zip(run.clean_results, results, strict=True)
                if extracted is not None
            ],
        )
        write_json(workspace / ARTIFACT_NAMES[2], completed.model_dump(mode="json"))
    except Exception as error:
        return FetchSummary(
            run_id=run.run_id,
            workspace=str(workspace),
            status="failed",
            urls_processed=0,
            outcomes=outcomes,
            extractor_strategy=settings.extractor_strategy,
            files=[],
            error=type(error).__name__,
        )
    finally:
        if owned is not None:
            owned.close()
    return FetchSummary(
        run_id=run.run_id,
        workspace=str(workspace),
        status="completed",
        urls_processed=len(run.clean_results),
        outcomes=outcomes,
        extractor_strategy=settings.extractor_strategy,
        files=list(ARTIFACT_NAMES),
    )
