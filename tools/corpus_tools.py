"""Deterministic corpus tools bound to one run.

`collect_source` fetches, extracts, and writes one immutable source file, then
returns metadata only. `build_index` rebuilds the corpus table from those files.
Neither tool lets a single URL abort the run (BR-005, US-6.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from schemas.content import ExtractionResult, FetchResult
from schemas.responses import SearchResult
from schemas.state import RunState
from schemas.tool_io import (
    BuildIndexInput,
    BuildIndexOutput,
    CollectSourceInput,
    CollectSourceOutput,
    ExtractMarkdownInput,
    FetchUrlInput,
    SourceMetadata,
)
from services.corpus import (
    INDEX_PATH,
    CorpusSource,
    SourceExistsError,
    corpus_state,
    outcome_for,
    read_corpus,
    source_id_for,
    source_path,
    source_slug,
    write_index,
    write_source,
)

if TYPE_CHECKING:
    from services.extraction_service import ExtractionService
    from services.fetch_service import Fetcher
    from tools.registry import Runtime, ToolRegistry


class CorpusSession:
    """One run's clean URLs, fetcher, and extractor. Never shared across runs."""

    def __init__(
        self, root: Path, run: RunState, fetcher: Fetcher, extractor: ExtractionService
    ) -> None:
        self.root = root
        self.run = run
        self.fetcher = fetcher
        self.extractor = extractor
        self._by_rank = {result.rank: result for result in run.clean_results}

    def result_for(self, rank: int, url: str) -> SearchResult:
        result = self._by_rank.get(rank)
        if result is None or str(result.url) != url:
            raise ValueError(f"Rank {rank} is not a clean URL in this run")
        return result

    def existing(self, result: SearchResult) -> CorpusSource | None:
        """A source file already written for this rank, if its URL matches."""
        for record in read_corpus(self.root):
            # Rank is the identity: the stored URL may be the post-redirect final URL.
            if record.rank == result.rank:
                return record
        return None


def _metadata(record: CorpusSource) -> SourceMetadata:
    return SourceMetadata(
        source_id=record.source.source_id,
        path=record.path,
        title=record.source.title,
        word_count=record.source.word_count,
    )


def register_corpus_tools(registry: ToolRegistry, session: CorpusSession | None) -> None:
    from tools.registry import TypedTool

    def current(runtime: Runtime | None) -> tuple[CorpusSession, RunState]:
        if session is None or runtime is None:
            raise ValueError("Corpus tools require a per-run CorpusSession and ToolRuntime")
        run = RunState.model_validate(runtime.state["run"])
        if run.run_id != session.run.run_id or run.topic != session.run.topic:
            raise ValueError("CorpusSession does not match the active run")
        return session, run

    def collect(request: CollectSourceInput, runtime: Runtime | None) -> CollectSourceOutput:
        bound, run = current(runtime)
        result = bound.result_for(request.rank, str(request.url))
        outcomes = dict(run.url_outcomes)
        existing = bound.existing(result)
        if existing is not None:
            # US-8.4 skips a URL whose source file already exists. The file is
            # immutable, so returning its metadata is also the only safe behavior.
            url, outcome = outcome_for(
                result, outcome="extracted", source_id=existing.source.source_id
            )
            outcomes[url] = outcome
            return CollectSourceOutput(source=_metadata(existing), run=corpus_state(run, outcomes))
        try:
            fetched = registry["fetch_url"].invoke(FetchUrlInput(url=result.url), runtime)
            assert isinstance(fetched, FetchResult)
            if fetched.page is None:
                url, outcome = outcome_for(result, outcome=fetched.outcome, reason=fetched.reason)
                outcomes[url] = outcome
                return CollectSourceOutput(source=None, run=corpus_state(run, outcomes))
            extracted = registry["extract_markdown"].invoke(
                ExtractMarkdownInput(
                    page=fetched.page,
                    source_id=source_id_for(result.rank),
                    fetched_at=fetched.fetched_at,
                ),
                runtime,
            )
            assert isinstance(extracted, ExtractionResult)
        except Exception as error:  # noqa: BLE001 - one URL must never abort the run
            url, outcome = outcome_for(result, outcome="failed", reason=type(error).__name__)
            outcomes[url] = outcome
            return CollectSourceOutput(source=None, run=corpus_state(run, outcomes))
        if extracted.source is None:
            url, outcome = outcome_for(result, outcome=extracted.outcome, reason=extracted.reason)
            outcomes[url] = outcome
            return CollectSourceOutput(source=None, run=corpus_state(run, outcomes))
        record = CorpusSource(
            source=extracted.source,
            path=source_path(result.rank, source_slug(extracted.source.title, result.url)),
            rank=result.rank,
        )
        try:
            write_source(bound.root, record)
        except SourceExistsError:
            record = bound.existing(result) or record
        url, outcome = outcome_for(result, outcome="extracted", source_id=record.source.source_id)
        outcomes[url] = outcome
        return CollectSourceOutput(source=_metadata(record), run=corpus_state(run, outcomes))

    def build_index(request: BuildIndexInput, runtime: Runtime | None) -> BuildIndexOutput:
        bound, run = current(runtime)
        pending = [url for url, outcome in run.url_outcomes.items() if outcome.outcome == "pending"]
        if pending:
            raise ValueError("Cannot index a corpus while clean URLs are still pending")
        records = read_corpus(bound.root)
        expected = {
            outcome.source_id
            for outcome in run.url_outcomes.values()
            if outcome.outcome == "extracted"
        }
        found = {record.source.source_id for record in records}
        if found != expected:
            raise ValueError("Source files do not match the recorded extracted outcomes")
        write_index(bound.root, records)
        phases = list(run.completed_phases)
        if "index" not in phases:
            phases.append("index")
        return BuildIndexOutput(
            index_path=INDEX_PATH,
            sources_indexed=len(records),
            run=run.replaced(completed_phases=phases),
        )

    registry.register(
        TypedTool[CollectSourceInput, CollectSourceOutput](
            name="collect_source",
            input_model=CollectSourceInput,
            output_model=CollectSourceOutput,
            handler=collect,
            updates_state=True,
            description=(
                "Fetch one clean URL, extract it, write one immutable source file, "
                "and return metadata only. Records and skips failures."
            ),
        )
    )
    registry.register(
        TypedTool[BuildIndexInput, BuildIndexOutput](
            name="build_index",
            input_model=BuildIndexInput,
            output_model=BuildIndexOutput,
            handler=build_index,
            updates_state=True,
            description="Write research/index.md from source-file front-matter, one row per file.",
        )
    )
