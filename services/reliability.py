"""One retry per phase, logged to the run's own JSON Lines file (US-8.3)."""

from collections.abc import Callable
from pathlib import Path

from services.execution_log import ExecutionLog
from services.observability import current_observer


def run_phase[T](name: str, call: Callable[[], T], log_path: Path) -> tuple[T, int]:
    """Run a phase, and retry it exactly once when it raises.

    Returns the result and the number of retries used. A second failure
    propagates so the caller can end the run and still write the report.
    """
    try:
        return call(), 0
    except Exception as first:  # noqa: BLE001 - retry-once applies to any phase error
        observer = current_observer()
        if observer is not None:
            observer.retry(name, type(first).__name__, error=type(first).__name__)
        else:
            ExecutionLog(log_path.parent.parent, log_path.parent.parent.name).event(
                name,
                "retry",
                level="WARNING",
                retry=1,
                reason=type(first).__name__,
                error=type(first).__name__,
            )
        return call(), 1
