"""Run workspace creation: topic slug, UTC run id, and the persisted request."""

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from schemas.requests import ResearchRequest
from schemas.workspace import RunWorkspace

MAX_SLUG_LENGTH = 60
REQUEST_FILENAME = "request.json"


def slugify(topic: str) -> str:
    """Lowercase ASCII words joined by hyphens, at most 60 characters."""
    ascii_topic = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_topic.lower()).strip("-")
    return slug[:MAX_SLUG_LENGTH].strip("-") or "topic"


def run_id_for(topic: str, now: datetime) -> str:
    """`<slug>-<YYYYMMDDTHHMMSSZ>`; naive timestamps are rejected."""
    if now.tzinfo is None:
        raise ValueError("run id timestamps must be timezone-aware")
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{slugify(topic)}-{stamp}"


def create_run_workspace(
    request: ResearchRequest, runs_root: Path, *, now: datetime | None = None
) -> RunWorkspace:
    """Create `runs/<run_id>/` and persist the validated request.

    The request is already validated, so an invalid topic never reaches this call.
    `exist_ok=False` guarantees a run never overwrites another run's workspace.
    """
    moment = now if now is not None else datetime.now(UTC)
    run_id = run_id_for(request.topic, moment)
    root = runs_root / run_id
    root.mkdir(parents=True, exist_ok=False)
    (root / REQUEST_FILENAME).write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return RunWorkspace(run_id=run_id, root=root)
