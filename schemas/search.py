"""Planning, provider requests, and normalized Search milestone output."""

from typing import Annotated, Self

from pydantic import BeforeValidator, Field, model_validator

from schemas.common import Contract, Topic, trim_topic
from schemas.responses import SearchResult
from schemas.state import RunStateUpdate

SearchQuery = Annotated[str, BeforeValidator(trim_topic), Field(min_length=1, max_length=500)]


class QueryVariants(Contract):
    """Two or three alternative search phrasings, in derivation order."""

    variants: list[SearchQuery] = Field(
        min_length=2,
        max_length=3,
        description="Two or three distinct alternative queries; never repeat the topic.",
    )

    @model_validator(mode="after")
    def distinct_variants(self) -> Self:
        if len({query.casefold() for query in self.variants}) != len(self.variants):
            raise ValueError("variants must be distinct")
        return self


class SearchCall(Contract):
    query: SearchQuery
    page: int = Field(ge=1)
    per_page: int = Field(ge=1)


class SearchPlan(Contract):
    topic: Topic
    variants: list[SearchQuery]
    provider: str
    calls: list[SearchCall]
    max_urls: int = Field(ge=1)


class SearchPlanOutput(RunStateUpdate):
    plan: SearchPlan


class NormalizationCounts(Contract):
    raw: int = Field(ge=0)
    denied: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    capped: int = Field(ge=0)
    kept: int = Field(ge=0)


class NormalizedResults(Contract):
    clean_results: list[SearchResult]
    counts: NormalizationCounts
