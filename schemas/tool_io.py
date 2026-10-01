"""Typed contracts for implemented Search and the remaining pipeline stub tools."""

from pydantic import Field

from schemas.common import HTTPURL, Contract, SourceID
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


class CollectSourceInput(Contract):
    rank: int = Field(ge=1)
    url: HTTPURL


class SourceMetadata(Contract):
    """What `collect_source` returns: metadata only, never the page body."""

    source_id: SourceID
    path: str
    title: str
    word_count: int = Field(ge=0)


class BuildIndexInput(Contract):
    """No arguments; the run workspace is implicit."""


class BuildIndexOutput(Contract):
    index_path: str
    sources_indexed: int = Field(ge=0)


class ValidateCitationsInput(Contract):
    """No arguments; the run workspace is implicit."""


class ValidateCitationsOutput(Contract):
    citations_checked: int = Field(ge=0)
    dangling_source_ids: list[SourceID]


class WriteRunReportInput(Contract):
    """No arguments; the run workspace is implicit."""


class WriteRunReportOutput(Contract):
    report_path: str
