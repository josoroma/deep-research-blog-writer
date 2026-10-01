"""Resume an interrupted run from its last completed phase (US-8.4, PD-019)."""

import json
from pathlib import Path

from schemas.common import Phase
from schemas.state import RunState

PHASE_ORDER: tuple[Phase, ...] = (
    "plan",
    "search",
    "normalize",
    "fetch",
    "index",
    "synthesize",
    "write",
    "citations",
    "report",
)


def checkpoint_path(workspace: Path) -> Path:
    return workspace / "checkpoints.sqlite"


def load_saved_run(workspace: Path) -> RunState:
    """The newest state file the milestones leave behind."""
    for name in ("corpus_state.json", "fetch_state.json", "search_state.json"):
        path = workspace / name
        if path.exists():
            return RunState.model_validate(json.loads(path.read_text()))
    raise ValueError(f"No saved run state in {workspace}")


def next_phase(completed: list[Phase]) -> Phase | None:
    """The first phase the run has not recorded, in pipeline order."""
    done = set(completed)
    return next((phase for phase in PHASE_ORDER if phase not in done), None)
