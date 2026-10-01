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


class UrlOutcomeEntry(Contract):
    """One clean URL as recorded in the run report (PD-018)."""

    rank: int = Field(ge=1)
    url: HTTPURL
    outcome: str = Field(min_length=1)
    reason: str | None = None
    source_id: SourceID | None = None


class RunReport(Contract):
    """PRD §8 report plus the FR-10 counts and the PD-018 fields."""

    run_id: str = Field(min_length=1)
    topic: Topic
    model: str = Field(min_length=1)
    status: Literal["succeeded", "degraded", "failed"]
    status_reasons: list[str] = Field(default_factory=list)
    phase_timings_seconds: dict[str, float] = Field(default_factory=dict)
    urls_found: int = Field(ge=0)
    urls_clean: int = Field(default=0, ge=0)
    urls_fetched: int = Field(default=0, ge=0)
    urls_extracted: int = Field(ge=0)
    urls_thin: int = Field(default=0, ge=0)
    urls_failed: int = Field(default=0, ge=0)
    extraction_failures: int = Field(ge=0)
    url_outcomes: list[UrlOutcomeEntry] = Field(default_factory=list)
    blog_path: str
    citation_count: int = Field(ge=0)
    tokens_used: int = Field(ge=0)
    cost_usd: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    retries: int = Field(default=0, ge=0)
