"""Checkpoint support: local SQLite for CLI runs, PostgreSQL for the server.

Local execution keeps the per-run SQLite checkpointer (PD-019). Server execution
uses PostgreSQL savers so a worker restart resumes a run instead of restarting it.
Both share one restricted serializer: typed ``RunState`` round-trips without a
general pickle fallback.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from schemas.state import RunState


def _allowed_modules() -> list[tuple[str, str]]:
    from schemas.state import RunStateUpdate, UrlOutcome

    return [
        (RunState.__module__, RunState.__name__),
        (UrlOutcome.__module__, UrlOutcome.__name__),
        (RunStateUpdate.__module__, RunStateUpdate.__name__),
    ]


def _serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=_allowed_modules())


def make_sqlite_checkpointer(path: Path) -> SqliteSaver:
    """Per-run SQLite checkpoint (PD-019). The caller owns the connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(connection, serde=_serializer())


def make_checkpointer() -> InMemorySaver:
    """Preserve RunState's type without pickle or an unrestricted module allowlist.

    The durable per-run SQLite lifecycle is implemented separately in US-8.4.
    """
    return InMemorySaver(serde=_serializer())


@contextmanager
def postgres_checkpointer(conn_string: str) -> Iterator[BaseCheckpointSaver[Any]]:
    """A PostgreSQL saver bound to its own connection, closed on exit."""
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(conn_string) as saver:
        saver.serde = _serializer()
        yield saver


def prepare_postgres_checkpointer(conn_string: str) -> None:
    """Create or migrate the checkpoint tables once at startup, never per request."""
    with postgres_checkpointer(conn_string) as saver:
        setup = getattr(saver, "setup", None)
        if not callable(setup):
            raise TypeError("The PostgreSQL checkpointer does not provide setup()")
        setup()
