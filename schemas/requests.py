"""Validated inputs for research and state-changing tools."""

from pydantic import Field

from schemas.common import Contract, Phase, Topic


class ResearchRequest(Contract):
    topic: Topic
    pages: int = Field(default=3, ge=1)
    per_page: int = Field(default=10, ge=1)
    max_urls: int = Field(default=30, ge=1)


class CompletePhaseInput(Contract):
    """Record that the deterministic work for a phase has completed."""

    phase: Phase
