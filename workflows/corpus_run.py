"""EPIC-6 milestone: collect immutable sources and index them.

Consumes an EPIC-4 workspace through the registered tools. One URL's failure is
recorded and skipped; the index is still written from whatever was collected.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from schemas.common import Contract
from schemas.config import RunSettings
from schemas.state import RunState, UrlOutcome
from schemas.tool_io import BuildIndexOutput, CollectSourceOutput, SourceMetadata
from services.artifacts import write_json
from services.extraction_service import ExtractionService, create_extraction_service
from services.fetch_service import Fetcher, FetchService, crawler_user_agent
from tools.corpus_tools import CorpusSession
from tools.registry import ToolRegistry, create_tool_registry
from workflows.fetch_run import load_search_workspace
from workflows.search_run import tool_runtime

CORPUS_STATE = "corpus_state.json"


class CorpusSummary(Contract):
    run_id: str
    workspace: str
    status: Literal["completed", "failed"]
    urls_processed: int
    sources_written: int
    sources_indexed: int
    outcomes: dict[str, int]
    index_path: str | None = None
    files: list[str] = []
    error: str | None = None


def _collect_one(
    registry: ToolRegistry, run: RunState, rank: int
) -> tuple[SourceMetadata | None, UrlOutcome]:
    result = next(item for item in run.clean_results if item.rank == rank)
    try:
        output = registry["collect_source"].invoke(
            {"rank": rank, "url": str(result.url)}, tool_runtime(run)
        )
    except Exception as error:  # noqa: BLE001 - containment is the requirement
        return None, UrlOutcome(
            rank=rank, url=result.url, outcome="failed", reason=type(error).__name__
        )
    assert isinstance(output, CollectSourceOutput)
    outcome = output.run.url_outcomes[str(result.url)]
    return output.source, outcome


def run_corpus(
    workspace: Path,
    settings: RunSettings,
    *,
    fetcher: Fetcher | None = None,
    extractor: ExtractionService | None = None,
) -> CorpusSummary:
    """Collect every clean URL, then index the files that were written."""
    run = load_search_workspace(workspace)
    crawler_user_agent(settings)
    if (workspace / CORPUS_STATE).is_symlink():
        raise ValueError(f"Artifact destination is a symlink: {CORPUS_STATE}")
    extraction = extractor if extractor is not None else create_extraction_service(settings)
    owned = FetchService(settings) if fetcher is None else None
    bound = owned if owned is not None else fetcher
    assert bound is not None
    session = CorpusSession(workspace, run, bound, extraction)
    registry = create_tool_registry(fetcher=bound, extractor=extraction, corpus_session=session)
    summary = CorpusSummary(
        run_id=run.run_id,
        workspace=str(workspace),
        status="failed",
        urls_processed=0,
        sources_written=0,
        sources_indexed=0,
        outcomes={},
    )
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            ranks = range(1, len(run.clean_results) + 1)
            collected = list(pool.map(lambda rank: _collect_one(registry, run, rank), ranks))
        outcomes = {str(outcome.url): outcome for _, outcome in collected}
        progressed = run.replaced(
            completed_phases=[*run.completed_phases, "fetch"], url_outcomes=outcomes
        )
        indexed = registry["build_index"].invoke({}, tool_runtime(progressed))
        assert isinstance(indexed, BuildIndexOutput)
        final = indexed.run
        write_json(workspace / CORPUS_STATE, final.model_dump(mode="json"))
        written = [source for source, _ in collected if source is not None]
        summary = CorpusSummary(
            run_id=run.run_id,
            workspace=str(workspace),
            status="completed",
            urls_processed=len(run.clean_results),
            sources_written=len(written),
            sources_indexed=indexed.sources_indexed,
            outcomes=dict(Counter(outcome.outcome for outcome in outcomes.values())),
            index_path=indexed.index_path,
            files=[source.path for source in written] + [indexed.index_path, CORPUS_STATE],
        )
    except Exception as error:  # noqa: BLE001 - the CLI reports the type, never the text
        summary = summary.model_copy(update={"error": type(error).__name__})
    finally:
        if owned is not None:
            owned.close()
    return summary
