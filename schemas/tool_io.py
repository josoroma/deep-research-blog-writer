"""Typed contracts for implemented Search and the remaining pipeline stub tools."""

from pydantic import AwareDatetime, Field

from schemas.common import HTTPURL, Contract, SourceID
from schemas.content import utc_now
from schemas.responses import FetchedPage, SearchResult
from schemas.search import NormalizationCounts, SearchQuery
from schemas.state import RunStateUpdate


class GoogleSearchInput(Contract):
    query: SearchQuery
    page: int = Field(ge=1)


class GoogleSearchOutput(Contract):
    results: list[SearchResult]


class NormalizeResultsInput(Contract):
    max_urls: int = Field(ge=1)


class NormalizeResultsOutput(RunStateUpdate):
    clean_results: list[SearchResult]
    counts: NormalizationCounts


class FetchUrlInput(Contract):
    url: HTTPURL


class ExtractMarkdownInput(Contract):
    page: FetchedPage
    source_id: SourceID
    fetched_at: AwareDatetime = Field(default_factory=utc_now)


class CollectSourceInput(Contract):
    rank: int = Field(ge=1)
    url: HTTPURL


class SourceMetadata(Contract):
    """What `collect_source` returns: metadata only, never the page body."""

    source_id: SourceID
    path: str
    title: str
    word_count: int = Field(ge=0)


class CollectSourceOutput(RunStateUpdate):
    """Metadata when a source file was written or already existed; otherwise none.

    A failed URL still returns a validated run-state replacement, so one bad source
    never drops the run's recorded progress.
    """

    source: SourceMetadata | None = None


class BuildIndexInput(Contract):
    """No arguments; the run workspace is implicit."""


class BuildIndexOutput(RunStateUpdate):
    index_path: str
    sources_indexed: int = Field(ge=0)


class BuildIndexStubOutput(Contract):
    """M1 stub output. The real tool returns BuildIndexOutput, which updates run state."""

    index_path: str
    sources_indexed: int = Field(ge=0)


class ValidateCitationsInput(Contract):
    """No arguments; the run workspace is implicit."""


class ValidateCitationsOutput(RunStateUpdate):
    """Citation gate result. `passed` is true only when both lists are empty."""

    citations_checked: int = Field(ge=0)
    dangling_source_ids: list[SourceID]
    mismatched_source_ids: list[SourceID] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.dangling_source_ids and not self.mismatched_source_ids


class ValidateCitationsStubOutput(Contract):
    """M1 stub output. The real tool returns ValidateCitationsOutput and updates state."""

    citations_checked: int = Field(ge=0)
    dangling_source_ids: list[SourceID]


class WriteRunReportInput(Contract):
    """No arguments; the run workspace is implicit."""


class WriteRunReportOutput(Contract):
    report_path: str
