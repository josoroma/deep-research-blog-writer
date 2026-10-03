"""M5: bounded, contained artifact reads and safe project of log records."""

from pathlib import Path

import pytest

from services.artifact_reader import (
    ArtifactNotFound,
    ArtifactReader,
    ArtifactTooLarge,
    UnsafePath,
)


def _reader(root: Path, *, max_bytes: int = 1024) -> ArtifactReader:
    return ArtifactReader(root, max_bytes=max_bytes, log_page_limit=10)


def _run(root: Path, run_id: str = "my-run") -> Path:
    run = root / run_id
    (run / "output").mkdir(parents=True)
    (run / "research").mkdir()
    (run / "logs").mkdir()
    (run / "request.json").write_text('{"topic": "telemetry quality"}\n', encoding="utf-8")
    (run / "output" / "blog.md").write_text("# Draft\n\nbody\n", encoding="utf-8")
    (run / "output" / "run.json").write_text(
        '{"run_id":"my-run","topic":"telemetry quality","model":"openrouter:x",'
        '"status":"succeeded","urls_found":1,"urls_extracted":1,"extraction_failures":0,'
        '"blog_path":"output/blog.md","citation_count":1,"tokens_used":10,'
        '"duration_seconds":0.1}\n',
        encoding="utf-8",
    )
    return run


def test_lists_only_allowlisted_artifacts_and_skips_symlinks(tmp_path: Path) -> None:
    run = _run(tmp_path)
    (run / "secrets.env").write_text("API_KEY=leak\n", encoding="utf-8")
    (run / "output" / "escape.md").symlink_to("/etc/hosts")
    reader = _reader(tmp_path)
    ids = {entry["artifact_id"] for entry in reader.list_artifacts("my-run")}
    assert "output/blog.md" in ids
    assert "secrets.env" not in ids
    assert "output/escape.md" not in ids


def test_unknown_run_and_disallowed_path_are_not_found(tmp_path: Path) -> None:
    _run(tmp_path)
    reader = _reader(tmp_path)
    with pytest.raises(ArtifactNotFound):
        reader.run_root("nope")
    with pytest.raises(ArtifactNotFound):
        reader.read_bytes("my-run", "secrets.env")


@pytest.mark.parametrize("attempt", ["../request.json", "output/../../request.json", "knowledge"])
def test_disallowed_paths_are_rejected(tmp_path: Path, attempt: str) -> None:
    _run(tmp_path)
    reader = _reader(tmp_path)
    with pytest.raises((ArtifactNotFound, UnsafePath)):
        reader.read_bytes("my-run", attempt)


def test_symlinked_directory_inside_a_run_is_rejected(tmp_path: Path) -> None:
    run = _run(tmp_path)
    (run / "output" / "link.md").symlink_to(run / "output" / "blog.md")
    reader = _reader(tmp_path)
    with pytest.raises(UnsafePath):
        reader.read_bytes("my-run", "output/link.md")


def test_oversized_artifact_is_refused(tmp_path: Path) -> None:
    run = _run(tmp_path)
    (run / "output" / "huge.md").write_text("x" * 5000, encoding="utf-8")
    reader = _reader(tmp_path, max_bytes=1024)
    with pytest.raises(ArtifactTooLarge):
        reader.read_bytes("my-run", "output/huge.md")


def test_report_round_trips_and_topic_resolves(tmp_path: Path) -> None:
    _run(tmp_path)
    reader = _reader(tmp_path)
    report = reader.read_report("my-run")
    assert report is not None and report.status == "succeeded"
    assert reader.run_topic("my-run") == "telemetry quality"
    assert reader.read_run_state("my-run") == {}


def test_log_page_is_bounded_and_pages(tmp_path: Path) -> None:
    run = _run(tmp_path)
    lines = [
        '{"timestamp":"t","level":"INFO","phase":"search","event":"tool_started","tool":"x"}',
        '{"timestamp":"t","level":"WARNING","phase":"fetch","event":"source_failed","url":"u"}',
        "not json",
    ]
    (run / "logs" / "execution.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    reader = _reader(tmp_path)
    first, cursor = reader.read_log_page("my-run", cursor=0, limit=2)
    assert len(first) == 2 and cursor == 2
    rest, cursor2 = reader.read_log_page("my-run", cursor=cursor, limit=2)
    assert cursor2 is None
    assert rest[0]["event"] == "[unparseable]"


def test_missing_log_returns_empty(tmp_path: Path) -> None:
    _run(tmp_path)
    reader = _reader(tmp_path)
    assert reader.read_log_page("my-run", cursor=0, limit=5) == ([], None)
