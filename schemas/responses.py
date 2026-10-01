"""Pydantic v2 hand-offs from PRD.md sections 8 and 9."""

from typing import Literal

from pydantic import AwareDatetime, Field

from schemas.common import HTTPURL, Contract, SourceID, Topic


class SearchResult(Contract):
    url: HTTPURL
    title: str
    snippet: str
    rank: int = Field(ge=1)
    query: str


class FetchedPage(Contract):
    """A fetched HTML response, including the URL after redirects."""

    html: str
    status: int = Field(ge=100, le=599)
    final_url: HTTPURL


class Source(Contract):
    source_id: SourceID
    url: HTTPURL
    title: str
    author: str | None
    published: str | None
    body_markdown: str
    word_count: int = Field(ge=0)
    fetched_at: AwareDatetime


class RunReport(Contract):
    """Initial PRD report; FR-10 and PD-018 extensions belong to US-8.1."""

    run_id: str = Field(min_length=1)
    topic: Topic
    status: Literal["succeeded", "degraded", "failed"]
    urls_found: int = Field(ge=0)
    urls_extracted: int = Field(ge=0)
    extraction_failures: int = Field(ge=0)
    blog_path: str
    citation_count: int = Field(ge=0)
    tokens_used: int = Field(ge=0)
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
