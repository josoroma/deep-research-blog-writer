"""Fetch-only workflow, persistence, failure continuation and CLI validation."""

import json
from pathlib import Path

import pytest
from pydantic import HttpUrl

from evaluations.epic5_demo import run_demo
from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock
from schemas.config import RunSettings
from schemas.content import FetchResult
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.state import RunState
from services.artifacts import write_json
from services.fetch_service import FetchService, MissingCrawlerContact
from services.workspace import create_run_workspace
from workflows import cli
from workflows.fetch_run import load_search_workspace, run_fetch


def make_workspace(tmp_path: Path, paths: list[str]) -> Path:
    request = ResearchRequest(topic="Fetch workflow fixtures")
    workspace = create_run_workspace(request, tmp_path)
    clean = [
        SearchResult(
            url=HttpUrl(f"https://fixture.test/{path}"),
            title=path,
            snippet="Fixture",
            rank=rank,
            query=request.topic,
        )
        for rank, path in enumerate(paths, 1)
    ]
    write_json(
        workspace.root / "clean_results.json", [row.model_dump(mode="json") for row in clean]
    )
    return workspace.root


def settings() -> RunSettings:
    return RunSettings(_env_file=None, crawler_contact="https://example.org/contact")


def test_demo_proves_acceptance_and_preserves_ranked_outcomes(tmp_path: Path) -> None:
    report = run_demo(tmp_path)
    assert report["thirty_host_probe"]["max_active"] == 5
    workspace = Path(report["workspace"])
    state = RunState.model_validate_json((workspace / "fetch_state.json").read_text())
    assert len(state.url_outcomes) == 11
    assert state.completed_phases == ["plan", "search", "normalize", "fetch"]
    assert [item.rank for item in state.url_outcomes.values()] == list(range(1, 12))
    assert all(item.outcome != "pending" for item in state.url_outcomes.values())
    fetches = json.loads((workspace / "fetch_outcomes.json").read_text())
    assert "page" not in fetches[0]
    assert fetches[2]["attempts"] == 1
    assert fetches[8]["attempts"] == 4
    extractions = json.loads((workspace / "extraction_results.json").read_text())
    assert all(row["rank"] != 5 for row in extractions)
    no_metadata = next(row["source"] for row in extractions if row["rank"] == 7)
    assert no_metadata["author"] is None and no_metadata["published"] is None
    assert next(row for row in extractions if row["rank"] == 6)["source"] is None
    assert report["raw_html_absent_from_artifacts"] is True
    assert report["no_corpus_files_written"] is True


def test_missing_contact_preflights_before_network_or_artifacts(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path, ["article"])
    with pytest.raises(MissingCrawlerContact):
        run_fetch(workspace, RunSettings(_env_file=None))
    assert not (workspace / "fetch_outcomes.json").exists()


@pytest.mark.parametrize("invalid", ["missing", "rank", "duplicate", "budget", "json"])
def test_input_workspace_validation(tmp_path: Path, invalid: str) -> None:
    workspace = make_workspace(tmp_path, ["article", "thin"])
    path = workspace / "clean_results.json"
    rows = json.loads(path.read_text())
    if invalid == "missing":
        path.unlink()
    elif invalid == "json":
        path.write_text("invalid json")
    else:
        if invalid == "rank":
            rows[0]["rank"] = 4
        elif invalid == "duplicate":
            rows[1]["url"] = rows[0]["url"]
        else:
            request = ResearchRequest(topic="Fetch workflow fixtures", max_urls=1)
            (workspace / "request.json").write_text(request.model_dump_json())
        write_json(path, rows)
    with pytest.raises(ValueError):
        load_search_workspace(workspace)


def test_no_urls_completes_without_requests(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path, [])
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as service:
        summary = run_fetch(workspace, settings(), fetcher=service)
    assert summary.urls_processed == 0 and summary.status == "completed"
    assert transport.requests == []


def test_symlink_destination_is_rejected_before_fetch(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path, ["article"])
    target = tmp_path / "outside.json"
    target.write_text("unchanged")
    (workspace / "fetch_state.json").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        run_fetch(workspace, settings())
    assert target.read_text() == "unchanged"


class BrokenFetcher:
    def fetch(self, url: HttpUrl) -> FetchResult:
        raise RuntimeError("sensitive error")


def test_unexpected_fetch_errors_are_isolated_per_url(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path, ["first", "second"])
    summary = run_fetch(workspace, settings(), fetcher=BrokenFetcher())
    assert summary.urls_processed == 2 and summary.outcomes == {"unreachable": 2}
    assert "sensitive" not in (workspace / "fetch_state.json").read_text()


def test_artifact_failure_returns_failed_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = make_workspace(tmp_path, [])

    def fail(*args: object) -> None:
        raise OSError("sensitive filesystem data")

    monkeypatch.setattr("workflows.fetch_run.write_json", fail)
    summary = run_fetch(workspace, settings(), fetcher=BrokenFetcher())
    assert summary.status == "failed" and summary.error == "OSError"


def test_cli_fetch_only_uses_saved_topic_and_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = make_workspace(tmp_path, ["article", "thin", "missing"])
    transport, clock = FixtureHTTP(), VirtualClock()
    service = FetchService(settings(), client=transport.client(), clock=clock, sleep=clock.sleep)
    monkeypatch.setattr("workflows.fetch_run.FetchService", lambda _: service)
    assert cli.main(["--fetch-only", "--workspace", str(workspace)], settings=settings()) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["outcomes"] == {"extracted": 1, "too_thin": 1, "unreachable": 1}
    assert service._closed


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--fetch-only"],
        ["--workspace", "irrelevant"],
        ["--fetch-only", "--workspace", "irrelevant", "--pages", "1"],
        ["--fetch-only", "--workspace", "irrelevant", "--query-variant", "query"],
    ],
)
def test_cli_invalid_fetch_arguments(args: list[str]) -> None:
    assert cli.main(args, settings=settings()) == 2


def test_cli_fetch_contact_and_topic_errors(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path, ["article"])
    assert (
        cli.main(
            ["wrong topic", "--fetch-only", "--workspace", str(workspace)], settings=settings()
        )
        == 2
    )
    assert (
        cli.main(
            ["--fetch-only", "--workspace", str(workspace)], settings=RunSettings(_env_file=None)
        )
        == 2
    )


def test_cli_returns_one_for_fetch_fatal_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = make_workspace(tmp_path, [])

    def fail(*args: object) -> None:
        raise OSError("fixture")

    monkeypatch.setattr("workflows.fetch_run.write_json", fail)
    assert cli.main(["--fetch-only", "--workspace", str(workspace)], settings=settings()) == 1


def test_atomic_writer_rejects_symlink(tmp_path: Path) -> None:
    destination = tmp_path / "artifact.json"
    destination.symlink_to(tmp_path / "outside.json")
    with pytest.raises(ValueError, match="symlink"):
        write_json(destination, {})
