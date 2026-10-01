"""Checkpoint support for the explicit state building block."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from schemas.state import RunState


def make_checkpointer() -> InMemorySaver:
    """Preserve RunState's type without pickle or an unrestricted module allowlist.

    The durable per-run SQLite lifecycle is implemented separately in US-8.4.
    """
    serializer = JsonPlusSerializer(
        allowed_msgpack_modules=[(RunState.__module__, RunState.__name__)]
    )
    return InMemorySaver(serde=serializer)
