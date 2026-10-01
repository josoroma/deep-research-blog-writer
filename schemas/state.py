"""Explicit run progress carried by a DeepAgentState subclass."""

from typing import Literal, Self

from deepagents import DeepAgentState
from pydantic import Field, model_validator

from schemas.common import HTTPURL, Contract, Phase, SourceID, Topic
from schemas.responses import SearchResult


class UrlOutcome(Contract):
    rank: int = Field(ge=1)
    url: HTTPURL
    outcome: Literal[
        "pending",
        "extracted",
        "unreachable",
        "too_thin",
        "robots_disallowed",
        "unsupported_content",
        "extraction_failed",
    ] = "pending"
    reason: str | None = None
    source_id: SourceID | None = None


class RunState(Contract):
    run_id: str = Field(min_length=1)
    topic: Topic
    completed_phases: list[Phase] = Field(default_factory=list)
    clean_results: list[SearchResult] = Field(default_factory=list)
    url_outcomes: dict[str, UrlOutcome] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_progress(self) -> Self:
        if len(set(self.completed_phases)) != len(self.completed_phases):
            raise ValueError("completed_phases must not contain duplicates")
        results = {str(result.url): result for result in self.clean_results}
        if len(results) != len(self.clean_results):
            raise ValueError("clean_results must contain unique URLs")
        if set(results) != set(self.url_outcomes):
            raise ValueError("url_outcomes must include exactly one entry for every clean URL")
        for url, outcome in self.url_outcomes.items():
            if str(outcome.url) != url or outcome.rank != results[url].rank:
                raise ValueError(f"url_outcomes URL/rank mismatch: {url}")
        return self

    def replaced(self, **changes: object) -> Self:
        """Validate a replacement; model_copy(update=...) bypasses validation."""
        return self.model_validate({**self.model_dump(), **changes})


class ResearchAgentState(DeepAgentState):
    run: RunState


class RunStateUpdate(Contract):
    """Typed tool output converted to a framework Command only by the adapter."""

    run: RunState
