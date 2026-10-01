"""Runnable search milestone, planner boundaries, CLI, and opt-in live test."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from agents.search_planner import derive_query_variants
from evaluations.epic4_demo import TOPIC, VARIANTS, demo_provider
from evaluations.fakes import ScriptedChatModel
from evaluations.search_live_smoke import main as smoke
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.search import QueryVariants, SearchCall
from services.llm_service import LLMService
from services.search_provider import FakeSearchProvider, MissingSearchKey, SearchProviderError
from workflows import cli
from workflows.research_run import run_research
from workflows.search_run import run_search


def planner_model(variants: list[str]) -> ScriptedChatModel:
    return ScriptedChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "QueryVariants",
                        "args": {"variants": variants},
                        "id": "planner",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )


def test_orchestrator_derives_typed_variants_through_llm_service() -> None:
    model = planner_model(VARIANTS)
    llm = LLMService(RunSettings(_env_file=None), fake_model=model)
    assert derive_query_variants(ResearchRequest(topic=TOPIC), llm).variants == VARIANTS


@pytest.mark.parametrize("variants", [[TOPIC.upper(), "other query"], ["only one"], ["one", "ONE"]])
def test_orchestrator_rejects_invalid_model_plan(variants: list[str]) -> None:
    model = planner_model(variants)
    model.script *= 2
    llm = LLMService(RunSettings(_env_file=None), fake_model=model)
    with pytest.raises((ValueError, ValidationError)):
        derive_query_variants(ResearchRequest(topic=TOPIC), llm)


def test_search_milestone_uses_planner_and_registered_tools(tmp_path: Path) -> None:
    provider = demo_provider()
    summary = run_search(
        ResearchRequest(topic=TOPIC),
        RunSettings(_env_file=None),
        runs_root=tmp_path,
        fake_model=planner_model(VARIANTS),
        search_provider=provider,
    )
    assert summary.status == "completed" and summary.counts is not None
    assert summary.counts.raw == 50 and summary.counts.kept == 30
    assert [(call.query, call.page) for call in provider.calls] == [
        (TOPIC, 1),
        *((query, 1) for query in VARIANTS),
        (TOPIC, 2),
        (TOPIC, 3),
    ]
    assert Path(summary.clean_results_path).is_file()
    assert not (Path(summary.workspace) / "output/blog.md").exists()


def test_missing_provider_key_fails_before_workspace_or_model(tmp_path: Path) -> None:
    configured = RunSettings(_env_file=None)
    with pytest.raises(MissingSearchKey, match="SERPAPI_API_KEY"):
        run_search(ResearchRequest(topic=TOPIC), configured, runs_root=tmp_path / "runs")
    with pytest.raises(MissingSearchKey, match="SERPAPI_API_KEY"):
        run_research(
            ResearchRequest(topic=TOPIC),
            configured,
            runs_root=tmp_path / "runs",
            fake_model=ScriptedChatModel(script=[AIMessage(content="done")]),
        )
    assert not (tmp_path / "runs").exists()


def test_invalid_manual_plan_fails_before_creating_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="differ"):
        run_search(
            ResearchRequest(topic=TOPIC),
            RunSettings(_env_file=None),
            runs_root=tmp_path / "runs",
            variants=QueryVariants(variants=[TOPIC, "other query"]),
            search_provider=FakeSearchProvider(),
        )
    assert not (tmp_path / "runs").exists()


class FailingProvider(FakeSearchProvider):
    def search(self, call: SearchCall) -> list[SearchResult]:
        raise SearchProviderError("Search provider returned HTTP 429")


def test_provider_failure_preserves_plan_without_claiming_clean_results(tmp_path: Path) -> None:
    summary = run_search(
        ResearchRequest(topic=TOPIC),
        RunSettings(_env_file=None),
        runs_root=tmp_path,
        variants=QueryVariants(variants=VARIANTS),
        search_provider=FailingProvider(),
    )
    assert summary.status == "failed" and "HTTP 429" in (summary.error or "")
    assert Path(summary.search_plan_path).exists()
    assert not Path(summary.clean_results_path).exists()


def test_cli_search_only_prints_artifact_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def offline(*args: object, **kwargs: object) -> object:
        return run_search(
            ResearchRequest(topic=TOPIC),
            RunSettings(_env_file=None),
            runs_root=tmp_path,
            variants=QueryVariants(variants=VARIANTS),
            search_provider=demo_provider(),
        )

    monkeypatch.setattr(cli, "run_search", offline)
    assert cli.main([TOPIC, "--search-only"], settings=RunSettings(_env_file=None)) == 0
    output = capsys.readouterr().out
    assert '"status": "completed"' in output and '"clean_results_path"' in output


@pytest.mark.parametrize(
    "args",
    [
        [TOPIC, "--query-variant", "one", "--query-variant", "two"],
        [TOPIC, "--search-only", "--query-variant", "one"],
    ],
)
def test_cli_rejects_incompatible_or_invalid_variant_arguments(args: list[str]) -> None:
    assert cli.main(args, settings=RunSettings(_env_file=None)) == 2


def test_cli_search_only_missing_key_and_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([TOPIC, "--search-only"], settings=RunSettings(_env_file=None)) == 2
    assert "SERPAPI_API_KEY" in capsys.readouterr().err
    monkeypatch.setenv("SEARCH_PROVIDER", "unknown")
    assert cli.main([TOPIC]) == 2
    assert "search_provider" in capsys.readouterr().err


def test_live_smoke_missing_key_is_explicit(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke(RunSettings(_env_file=None)) == 2
    assert "SERPAPI_API_KEY" in capsys.readouterr().out


@pytest.mark.live
def test_live_selected_search_provider_page_two() -> None:
    # Explicit selection only: uv run pytest -m live tests/test_search_workflow.py --no-cov
    # Missing credentials fail; they are never silently skipped or treated as passing.
    assert smoke() == 0


def test_orchestrator_repairs_one_invalid_plan_without_searching() -> None:
    invalid = planner_model([TOPIC, "another query"])
    invalid.script.extend(planner_model(VARIANTS).script)
    llm = LLMService(RunSettings(_env_file=None), fake_model=invalid)
    assert derive_query_variants(ResearchRequest(topic=TOPIC), llm).variants == VARIANTS
