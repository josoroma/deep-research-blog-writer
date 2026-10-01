"""US-3.1: run id derivation, workspace creation, and persisted input."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.requests import ResearchRequest
from schemas.workspace import RunWorkspace
from services.workspace import create_run_workspace, run_id_for, slugify

FIXED = datetime(2026, 10, 1, 8, 30, 0, tzinfo=UTC)


def test_slug_is_lowercase_ascii_words_joined_by_hyphens() -> None:
    assert slugify("2026 Agentic AI Frameworks") == "2026-agentic-ai-frameworks"
    assert slugify("LangGraph vs CrewAI: A 2026 Comparison") == (
        "langgraph-vs-crewai-a-2026-comparison"
    )
    assert slugify("Café — Résumé!") == "cafe-resume"


def test_slug_is_capped_and_falls_back_for_non_ascii() -> None:
    assert len(slugify("word " * 40)) <= 60
    assert slugify("日本語のトピック") == "topic"


def test_run_id_is_slug_hyphen_utc_timestamp() -> None:
    assert run_id_for("2026 agentic AI frameworks", FIXED) == (
        "2026-agentic-ai-frameworks-20261001T083000Z"
    )


def test_run_id_converts_offsets_to_utc() -> None:
    from datetime import timedelta, timezone

    offset = timezone(timedelta(hours=2))
    assert run_id_for("topic", datetime(2026, 10, 1, 10, 30, tzinfo=offset)).endswith(
        "-20261001T083000Z"
    )


def test_run_id_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        run_id_for("topic", datetime(2026, 10, 1, 8, 30))


def test_workspace_is_created_and_request_is_persisted(tmp_path: Path) -> None:
    request = ResearchRequest(topic="  2026 agentic AI frameworks  ")
    workspace = create_run_workspace(request, tmp_path, now=FIXED)
    assert isinstance(workspace, RunWorkspace)
    assert workspace.run_id == "2026-agentic-ai-frameworks-20261001T083000Z"
    assert workspace.root == tmp_path / workspace.run_id
    assert workspace.root.is_dir()
    stored = ResearchRequest.model_validate_json(
        (workspace.root / "request.json").read_text(encoding="utf-8")
    )
    assert stored == request
    assert stored.topic == "2026 agentic AI frameworks"


def test_workspace_never_overwrites_an_existing_run(tmp_path: Path) -> None:
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    create_run_workspace(request, tmp_path, now=FIXED)
    with pytest.raises(FileExistsError):
        create_run_workspace(request, tmp_path, now=FIXED)


def test_invalid_topic_creates_no_directory(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(topic="ab")
    assert list(tmp_path.iterdir()) == []
