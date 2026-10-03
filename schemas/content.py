"""Validated fetch and extraction outcomes; raw HTML is an internal hand-off."""

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from schemas.common import HTTPURL, Contract
from schemas.responses import FetchedPage, Source


class FetchResult(Contract):
    url: HTTPURL
    final_url: HTTPURL
    outcome: Literal["fetched", "unreachable", "robots_disallowed", "unsupported_content"]
    page: FetchedPage | None = None
    reason: str | None = None
    attempts: int = Field(ge=0, le=4)
    status: int | None = Field(default=None, ge=100, le=599)
    fetched_at: AwareDatetime

    @model_validator(mode="after")
    def consistent_page(self) -> Self:
        if self.outcome == "fetched":
            if self.page is None or self.page.status != 200 or self.status != 200:
                raise ValueError("fetched requires a successful HTML page")
            if self.page.final_url != self.final_url or self.reason is not None:
                raise ValueError("fetched page URL/reason mismatch")
        elif self.page is not None or not self.reason:
            raise ValueError("failed fetch requires a reason and no page")
        return self


class ParsedArticle(Contract):
    title: str
    body_markdown: str
    author: str | None = None
    published: str | None = None
    canonical_url: HTTPURL | None = None


class ParserAttempt(Contract):
    parser: str
    outcome: Literal["empty", "too_thin", "error", "extracted"]
    word_count: int = Field(default=0, ge=0)
    error: str | None = None


class ExtractionResult(Contract):
    outcome: Literal["extracted", "too_thin", "extraction_failed"]
    source: Source | None = None
    attempts: list[ParserAttempt] = Field(min_length=1)
    reason: str | None = None

    @model_validator(mode="after")
    def consistent_source(self) -> Self:
        if self.outcome == "extracted":
            if self.source is None or self.source.word_count < 200 or self.reason is not None:
                raise ValueError("extracted requires a source with at least 200 words")
        elif self.source is not None or not self.reason:
            raise ValueError("failed extraction requires a reason and no source")
        return self


class FetchEvent(Contract):
    """Request timing evidence without response bodies or credentials."""

    url: str
    host: str
    kind: Literal["robots", "page"]
    started: float
    status: int | None = None
    error: str | None = None


class RetryEvent(Contract):
    kind: Literal["robots", "page"]
    attempt: int
    delay: float


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
