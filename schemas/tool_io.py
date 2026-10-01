"""Typed inputs and outputs for the EPIC-3 skeleton stub tools.

These contracts are the M1 shape of the pipeline tools. The story that replaces a
stub owns the final contract; until then every stub validates both sides of its call.
"""

from pydantic import Field

from schemas.common import HTTPURL, Contract, SourceID
from schemas.responses import FetchedPage, SearchResult


class GoogleSearchInput(Contract):
    query: str = Field(min_length=1)
    page: int = Field(ge=1)


class GoogleSearchOutput(Contract):
    results: list[SearchResult]


class NormalizeResultsInput(Contract):
    max_urls: int = Field(ge=1)


class NormalizeResultsOutput(Contract):
    clean_results: list[SearchResult]


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
