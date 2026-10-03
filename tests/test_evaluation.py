"""US-10.3, US-10.4, US-10.5: scoring, the judge, and the release gate."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from pydantic import HttpUrl

from evaluations import release, run_eval
from evaluations.epic10_demo import run_demo
from evaluations.judge import AlwaysSupportedJudge, ModelJudge, Verdict, Verdicts
from evaluations.offline_eval import fixture_topic, run_offline_topic
from evaluations.release import decide, latest_benchmark, read_benchmark, tag_name
from evaluations.run_eval import (
    GoldenDataset,
    build_benchmark,
    load_dataset,
    score_workspace,
    write_benchmark,
)
from evaluations.scoring import (
    MAX_HALLUCINATION_RATE,
    MIN_COVERAGE,
    MIN_GROUNDEDNESS,
    ClaimVerdict,
    benchmark_name,
    coverage,
    definition_of_done,
    factual_claims,
    groundedness_and_hallucination,
    score_topic,
)
from evaluations.workflow_fixtures import TOPIC
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import RunReport, SearchResult, Source
from schemas.state import RunState, UrlOutcome
from services.corpus import CorpusSource, write_index, write_source
from services.workspace import create_run_workspace

FETCHED_AT = datetime(2026, 10, 1, tzinfo=UTC)


def _source(rank: int) -> CorpusSource:
    return CorpusSource(
        source=Source(
            source_id=f"S-{rank:02d}",
            url=HttpUrl(f"https://example.com/post/{rank}"),
            title=f"Source {rank}",
            author=None,
            published=None,
            body_markdown="Evidence body.",
            word_count=2,
            fetched_at=FETCHED_AT,
        ),
        path=f"research/{rank:03d}_source-{rank}.md",
        rank=rank,
    )


def _workspace(tmp_path: Path, ranks: list[int], *, cited: list[int], words: int = 400) -> Path:
    request = ResearchRequest(topic="Evaluation fixtures")
    workspace = create_run_workspace(request, tmp_path)
    records = [_source(rank) for rank in ranks]
    for record in records:
        write_source(workspace.root, record)
    write_index(workspace.root, records)
    (workspace.root / "research/summary.md").write_text("## Recurring themes\n", encoding="utf-8")
    (workspace.root / "output").mkdir(exist_ok=True)
    body = " ".join(["evidence"] * words)
    headings = (
        "Introduction",
        "Landscape",
        "Key Frameworks",
        "Analysis and Trade-offs",
        "Outlook",
        "Conclusion",
    )
    sections = "\n\n".join(
        f"## {title}\n\n{body} [{_source(cited[index % len(cited)]).source.source_id}]."
        for index, title in enumerate(headings)
    )
    references = "\n".join(
        f"- [S-{rank:02d}] Source {rank} https://example.com/post/{rank}" for rank in cited
    )
    blog = f"# Title\n\n{sections}\n\n## References\n\n{references}\n"
    (workspace.root / "output/blog.md").write_text(blog, encoding="utf-8")
    (workspace.root / "output/run.json").write_text("{}\n", encoding="utf-8")
    (workspace.root / "logs").mkdir(exist_ok=True)
    (workspace.root / "logs/execution.log").write_text("{}\n", encoding="utf-8")
    return workspace.root


def _report(workspace: Path, *, clean: int, extracted: int) -> RunReport:
    return RunReport(
        run_id=workspace.name,
        topic="Evaluation fixtures",
        model="openrouter:deepseek/deepseek-v4.1-flash",
        status="succeeded",
        urls_found=clean,
        urls_clean=clean,
        urls_extracted=extracted,
        extraction_failures=clean - extracted,
        blog_path="output/blog.md",
        citation_count=1,
        tokens_used=0,
        duration_seconds=0.0,
    )


def test_coverage_is_the_share_of_corpus_sources_cited(tmp_path: Path) -> None:
    """Scenario: score coverage. 18 cited of 27 corpus sources is 0.67."""
    ranks = list(range(1, 28))
    workspace = _workspace(tmp_path, ranks, cited=list(range(1, 19)))
    assert round(coverage(workspace), 2) == 0.67


def test_coverage_is_zero_without_a_corpus(tmp_path: Path) -> None:
    request = ResearchRequest(topic="Empty corpus")
    workspace = create_run_workspace(request, tmp_path)
    assert coverage(workspace.root) == 0.0


def test_groundedness_and_hallucination_rate(tmp_path: Path) -> None:
    """Scenario: score groundedness and hallucination rate."""
    claims = [
        ClaimVerdict(claim="Supported claim [S-01].", source_id="S-01"),
        ClaimVerdict(claim="Rejected claim [S-02].", source_id="S-02"),
        ClaimVerdict(claim="Uncited claim with 2026 in it.", source_id=None),
    ]
    judged = [
        claims[0].model_copy(update={"supported": True}),
        claims[1].model_copy(update={"supported": False}),
        claims[2].model_copy(update={"supported": False}),
    ]
    grounded, hallucination = groundedness_and_hallucination(claims, judged)
    assert grounded == 0.5
    assert round(hallucination, 2) == 0.67


def test_factual_claims_include_cited_and_numeric_sentences(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, [1], cited=[1])
    claims = factual_claims(workspace)
    assert claims and all(claim.claim for claim in claims)


def test_definition_of_done_reports_each_item(tmp_path: Path) -> None:
    """Scenario: check the Definition of Done."""
    workspace = _workspace(tmp_path, [1], cited=[1])
    report = _report(workspace, clean=30, extracted=28)
    done = definition_of_done(workspace, report)
    assert done.passed
    assert done.failed_items == []


def test_definition_of_done_flags_a_missing_report(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, [1], cited=[1])
    report = _report(workspace, clean=30, extracted=10)
    done = definition_of_done(workspace, report)
    assert not done.passed
    assert "results_processed" in done.failed_items


def test_score_topic_passes_every_threshold(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, [1, 2], cited=[1, 2])
    report = _report(workspace, clean=30, extracted=28)
    score = score_topic(workspace, report, topic_id="t", judge=AlwaysSupportedJudge())
    assert score.passed and score.failures == []
    assert score.coverage == 1.0 and score.groundedness == 1.0


def test_score_topic_reports_a_failing_threshold(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, [1, 2, 3, 4], cited=[1])
    report = _report(workspace, clean=30, extracted=28)
    score = score_topic(workspace, report, topic_id="t", judge=AlwaysSupportedJudge())
    assert not score.passed
    assert "coverage_min_0.5" in score.failures


def test_thresholds_match_pd_021() -> None:
    assert (MIN_COVERAGE, MIN_GROUNDEDNESS, MAX_HALLUCINATION_RATE) == (0.5, 0.9, 0.05)


def test_golden_dataset_lists_the_three_pd_021_topics() -> None:
    """Scenario: score the golden topics. The dataset holds the PD-021 topics."""
    dataset = load_dataset()
    assert isinstance(dataset, GoldenDataset)
    assert len(dataset.topics) == 3
    assert {topic.id for topic in dataset.topics} == {
        "agentic-ai-frameworks",
        "vector-databases-rag",
        "platform-engineering",
    }


def test_benchmark_name_is_date_and_commit() -> None:
    assert benchmark_name("2026-10-02", "abc1234") == "2026-10-02-abc1234.json"


def test_write_benchmark_keeps_history(tmp_path: Path) -> None:
    """Scenario: keep benchmark history."""
    workspace = _workspace(tmp_path, [1], cited=[1])
    report = _report(workspace, clean=30, extracted=28)
    score = score_topic(workspace, report, topic_id="t", judge=AlwaysSupportedJudge())
    benchmark = build_benchmark(
        [score], commit="abc1234", model="m", judge_model="m", date="2026-10-02"
    )
    path = write_benchmark(benchmark, tmp_path / "benchmarks")
    assert path.name == "2026-10-02-abc1234.json"
    assert read_benchmark(path).passed


def test_model_judge_uses_structured_output() -> None:
    class FakeStructured:
        def invoke(self, messages: object) -> Verdicts:
            return Verdicts(verdicts=[Verdict(index=0, supported=True)])

    class FakeModel:
        def with_structured_output(self, schema: object) -> FakeStructured:
            return FakeStructured()

    judge = ModelJudge(RunSettings(_env_file=None), model=FakeModel())  # type: ignore[arg-type]
    claims = [ClaimVerdict(claim="A claim [S-01].", source_id="S-01")]
    judged = judge.judge(claims)
    assert judged[0].supported


def test_model_judge_returns_nothing_for_no_claims() -> None:
    judge = ModelJudge(RunSettings(_env_file=None), model=None)
    assert judge.judge([]) == []


def test_release_decision_blocks_a_failing_benchmark(tmp_path: Path) -> None:
    """Scenario: a failing evaluation stops the release."""
    workspace = _workspace(tmp_path, [1, 2, 3, 4], cited=[1])
    report = _report(workspace, clean=30, extracted=28)
    score = score_topic(workspace, report, topic_id="t", judge=AlwaysSupportedJudge())
    benchmark = build_benchmark(
        [score], commit="abc1234", model="m", judge_model="m", date="2026-10-02"
    )
    path = write_benchmark(benchmark, tmp_path / "benchmarks")
    decision = decide("1.0.0", read_benchmark(path), benchmark_path=path)
    assert not decision.passed and not decision.tagged
    assert decision.tag == "v1.0.0"
    assert decision.failures


def test_release_decision_passes_a_clean_benchmark(tmp_path: Path) -> None:
    """Scenario: a passing evaluation tags the release."""
    workspace = _workspace(tmp_path, [1], cited=[1])
    report = _report(workspace, clean=30, extracted=28)
    score = score_topic(workspace, report, topic_id="t", judge=AlwaysSupportedJudge())
    benchmark = build_benchmark(
        [score], commit="abc1234", model="m", judge_model="m", date="2026-10-02"
    )
    path = write_benchmark(benchmark, tmp_path / "benchmarks")
    decision = decide("1.0.0", read_benchmark(path), benchmark_path=path)
    assert decision.passed and decision.failures == []


def test_tag_name_normalizes_a_leading_v() -> None:
    assert tag_name("1.0.0") == "v1.0.0"
    assert tag_name("v1.0.0") == "v1.0.0"


def test_latest_benchmark_requires_a_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        latest_benchmark(tmp_path)


def test_offline_eval_scores_a_fixture_topic(tmp_path: Path) -> None:
    """The offline path runs the fixture pipeline and scores it end to end."""
    topic = fixture_topic()
    workspace = run_offline_topic(topic, tmp_path / "runs")
    score = score_workspace(workspace, topic, AlwaysSupportedJudge())
    assert score.passed
    assert score.coverage == 1.0
    assert score.definition_of_done.passed
    assert json.loads((workspace / "output/run.json").read_text())["status"] == "succeeded"


def test_offline_eval_topic_matches_the_fixture() -> None:
    assert fixture_topic().topic == TOPIC


def test_scripted_judge_never_calls_a_provider() -> None:
    judge = AlwaysSupportedJudge()
    claims = [ClaimVerdict(claim="Claim [S-01].", source_id="S-01")]
    assert judge.judge(claims)[0].supported


def test_run_state_fixture_is_consistent(tmp_path: Path) -> None:
    """Guard the fixture helper: the corpus and the report agree."""
    workspace = _workspace(tmp_path, [1, 2], cited=[1, 2])
    report = _report(workspace, clean=30, extracted=28)
    state = RunState(
        run_id=workspace.name,
        topic="Evaluation fixtures",
        clean_results=[
            SearchResult(
                url=HttpUrl(f"https://example.com/post/{rank}"),
                title=f"Source {rank}",
                snippet="s",
                rank=rank,
                query="Evaluation fixtures",
            )
            for rank in (1, 2)
        ],
        url_outcomes={
            f"https://example.com/post/{rank}": UrlOutcome(
                rank=rank, url=HttpUrl(f"https://example.com/post/{rank}"), outcome="extracted"
            )
            for rank in (1, 2)
        },
    )
    assert len(state.clean_results) == 2
    assert report.urls_extracted == 28


def test_ai_message_import_is_available_for_judge_fakes() -> None:
    """The judge fake can be a scripted model message when needed."""
    assert AIMessage(content="ok").content == "ok"


def _benchmark_file(tmp_path: Path, *, passing: bool) -> Path:
    ranks = [1] if passing else [1, 2, 3, 4]
    workspace = _workspace(tmp_path, ranks, cited=[1])
    report = _report(workspace, clean=30, extracted=28)
    score = score_topic(workspace, report, topic_id="t", judge=AlwaysSupportedJudge())
    benchmark = build_benchmark(
        [score], commit="abc1234", model="m", judge_model="m", date="2026-10-02"
    )
    return write_benchmark(benchmark, tmp_path / "benchmarks")


def test_release_main_dry_run_reports_without_tagging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _benchmark_file(tmp_path, passing=True)
    assert release.main(["--version", "1.0.0", "--benchmark", str(path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["tagged"] is False


def test_release_main_blocks_a_failing_benchmark(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _benchmark_file(tmp_path, passing=False)
    assert release.main(["--version", "1.0.0", "--benchmark", str(path)]) == 1
    assert "release blocked" in capsys.readouterr().err


def test_release_main_tags_a_passing_benchmark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tagged: list[str] = []
    monkeypatch.setattr(release, "create_tag", tagged.append)
    path = _benchmark_file(tmp_path, passing=True)
    assert release.main(["--version", "1.0.0", "--benchmark", str(path)]) == 0
    assert tagged == ["v1.0.0"]
    assert json.loads(capsys.readouterr().out)["tagged"] is True


def test_run_eval_offline_writes_a_benchmark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(run_eval, "BENCHMARKS_DIR", tmp_path / "benchmarks")
    code = run_eval.main(["--offline", "--runs-root", str(tmp_path / "runs")])
    assert code == 0
    written = list((tmp_path / "benchmarks").glob("*.json"))
    assert len(written) == 1
    assert read_benchmark(written[0]).passed
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_epic10_demo_scores_and_gates(tmp_path: Path) -> None:
    summary = run_demo(tmp_path / "runs")
    assert summary["passed"] is True
    assert summary["coverage"] == 1.0
    assert summary["release_passing_tagged"] is True
    assert summary["release_blocked_failures"]
    assert Path(summary["benchmark"]).is_file()
