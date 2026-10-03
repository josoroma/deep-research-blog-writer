"""The golden evaluation dataset contract.

Kept apart from ``evaluations.run_eval`` because both the live runner and the
offline fixture pipeline need ``GoldenTopic``, and ``run_eval`` imports the
offline pipeline. A shared leaf module removes that cycle.
"""

from pathlib import Path

from pydantic import Field

from schemas.common import Contract

GOLDEN_DATASET = Path("evaluations/golden_dataset.json")


class GoldenTopic(Contract):
    """One topic to evaluate, with the search budget it runs under."""

    id: str = Field(min_length=1)
    topic: str = Field(min_length=3)
    pages: int = Field(default=3, ge=1)
    per_page: int = Field(default=10, ge=1)
    max_urls: int = Field(default=30, ge=1)


class GoldenDataset(Contract):
    """The versioned list of golden topics in ``evaluations/golden_dataset.json``."""

    version: int = Field(ge=1)
    source: str
    topics: list[GoldenTopic] = Field(min_length=1)


def load_dataset(path: Path = GOLDEN_DATASET) -> GoldenDataset:
    """Read and validate the golden dataset."""
    return GoldenDataset.model_validate_json(path.read_text(encoding="utf-8"))
