"""Checkpoint support for the explicit state building block."""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from schemas.state import RunState


def _serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=[(RunState.__module__, RunState.__name__)])


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
