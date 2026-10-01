"""The per-run workspace contract."""

from pathlib import Path

from pydantic import Field

from schemas.common import Contract


class RunWorkspace(Contract):
    """A run's identifier and its on-disk root under `runs/`."""

    run_id: str = Field(min_length=1)
    root: Path
