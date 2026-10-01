"""US-3.4: the run command, its budgets, its summary, and its exit statuses."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from evaluations.fakes import ScriptedChatModel
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from services.llm_service import LLMService
from services.search_provider import FakeSearchProvider
from services.workspace import create_run_workspace
from workflows import cli
from workflows.research_run import run_research


def _settings(tmp_path: Path) -> RunSettings:
    return RunSettings(_env_file=None, runs_dir=str(tmp_path / "runs"))


def _fake() -> ScriptedChatModel:
    return ScriptedChatModel(script=[AIMessage(content="skeleton complete")])


def test_run_research_prints_the_summary_and_completes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    summary = run_research(
        request,
        settings,
        runs_root=tmp_path / "runs",
        fake_model=_fake(),
        search_provider=FakeSearchProvider(),
    )
    assert summary.status == "completed"
    assert summary.run_id.startswith("2026-agentic-ai-frameworks-")
    assert Path(summary.workspace).is_dir()
    assert summary.blog_path.endswith("output/blog.md")


def test_budget_override_is_stored_in_the_request(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    request = ResearchRequest(topic="2026 agentic AI frameworks", pages=2, per_page=5, max_urls=10)
    summary = run_research(
        request,
        settings,
        runs_root=tmp_path / "runs",
        fake_model=_fake(),
        search_provider=FakeSearchProvider(),
    )
    stored = ResearchRequest.model_validate_json(
        (Path(summary.workspace) / "request.json").read_text(encoding="utf-8")
    )
    assert (stored.pages, stored.per_page, stored.max_urls) == (2, 5, 10)


def test_cli_rejects_an_invalid_topic_without_creating_a_workspace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _settings(tmp_path)
    assert cli.main(["ab"], settings=settings) == cli.EXIT_INVALID_INPUT
    assert "Invalid input" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_cli_rejects_invalid_budgets(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert cli.main(["valid topic", "--pages", "0"], settings=settings) == cli.EXIT_INVALID_INPUT
    assert not (tmp_path / "runs").exists()


def test_cli_reports_a_missing_model_key_as_invalid_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _settings(tmp_path)
    assert cli.main(["valid topic"], settings=settings) == cli.EXIT_INVALID_INPUT
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_cli_prints_the_summary_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(cli, "run_research", _stub_run_research)
    assert cli.main(["2026 agentic AI frameworks"], settings=settings) == cli.EXIT_COMPLETED
    out = capsys.readouterr().out
    for field in ("run_id:", "workspace:", "status:", "blog_path:"):
        assert field in out


def _stub_run_research(
    request: ResearchRequest, settings: RunSettings, *, runs_root: Path, fake_model: object = None
) -> object:
    from workflows.research_run import RunSummary

    return RunSummary(
        run_id="stub-run",
        workspace=str(runs_root / "stub-run"),
        status="completed",
        blog_path=str(runs_root / "stub-run/output/blog.md"),
        blog_exists=False,
    )


def test_llm_service_is_preflighted_before_the_workspace_is_created(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    with pytest.raises(Exception, match="OPENROUTER_API_KEY"):
        run_research(request, settings, runs_root=tmp_path / "runs")
    assert not (tmp_path / "runs").exists()


def test_workspace_helper_is_used_by_the_runner(tmp_path: Path) -> None:
    request = ResearchRequest(topic="2026 agentic AI frameworks")
    workspace = create_run_workspace(request, tmp_path)
    assert (workspace.root / "request.json").exists()
    assert (
        LLMService(RunSettings(_env_file=None), fake_model=_fake()).for_agent("orchestrator")
        is not None
    )
