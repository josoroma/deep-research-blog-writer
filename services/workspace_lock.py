"""Exclusive single-host workspace ownership for one worker attempt.

Database ownership alone cannot authorize a second process to write into the same
run directory: a crashed process may still hold open file handles. The OS lock is
the second gate, so an expired heartbeat can never let two writers race.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import TracebackType
from typing import Self

from schemas.errors import ConflictError

try:  # pragma: no cover - platform import guard
    import fcntl
except ImportError:  # pragma: no cover - Windows has no fcntl
    fcntl = None  # type: ignore[assignment]

LOCK_FILENAME = ".run.lock"


class WorkspaceBusy(ConflictError):
    """Another process currently owns this workspace."""

    code = "workspace_busy"


class WorkspaceLock:
    """An advisory exclusive lock on one run workspace directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / LOCK_FILENAME
        self._handle: object | None = None
        self._acquired = False

    def acquire(self) -> None:
        if self._acquired:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+", encoding="utf-8")  # noqa: SIM115 - held for the lock
        if fcntl is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                handle.close()
                raise WorkspaceBusy(f"Workspace is locked: {self.root.name}") from error
        self._handle = handle
        self._acquired = True

    @property
    def acquired(self) -> bool:
        return self._acquired

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        if fcntl is not None:
            # Closing the handle below drops the lock anyway; an unlock failure here
            # is not actionable.
            with contextlib.suppress(OSError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
        handle.close()  # type: ignore[attr-defined]
        self._handle = None
        self._acquired = False

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
