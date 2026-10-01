"""One retry per phase, logged to the run's own JSON Lines file (US-8.3)."""

import json
from collections.abc import Callable
from pathlib import Path


def run_phase[T](name: str, call: Callable[[], T], log_path: Path) -> tuple[T, int]:
    """Run a phase, and retry it exactly once when it raises.

    Returns the result and the number of retries used. A second failure
    propagates so the caller can end the run and still write the report.
    """
    try:
        return call(), 0
    except Exception as first:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            record = {"phase": name, "retry": 1, "error": type(first).__name__}
            handle.write(json.dumps(record) + "\n")
        return call(), 1
