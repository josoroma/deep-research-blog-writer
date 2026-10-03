"""US-8.1 to US-8.4: run report, outcome, one retry, and resume."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import HttpUrl

from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import RunReport, SearchResult, Source
from schemas.state import RunState, UrlOutcome
from services.checkpoints import make_sqlite_checkpointer
from services.corpus import CorpusSource, write_source
from services.reliability import run_phase
from services.reporting import RunLedger, UsageRecord, build_run_report, classify_outcome
from services.workspace import create_run_workspace
from workflows.cli import main
from workflows.reporting_run import run_report
from workflows.resume import checkpoint_path, next_phase

FETCHED_AT = datetime(2026, 10, 1, tzinfo=UTC)


def settings() -> RunSettings:
    return RunSettings(_env_file=None, crawler_contact="https://example.org/contact")


def run_with(tmp_path: Path, extracted: int, clean: int = 30) -> tuple[Path, RunState]:
    request = ResearchRequest(topic="Reporting fixtures")
    workspace = create_run_workspace(request, tmp_path)
    results = []
    outcomes = {}
    for rank in range(1, clean + 1):
        url = HttpUrl(f"https://example.com/post/{rank}")
        results.append(
            SearchResult(url=url, title="Kept", snippet="Fixture", rank=rank, query=request.topic)
        )
        kept = rank <= extracted
        if kept:
            write_source(
                workspace.root,
                CorpusSource(
                    source=Source(
                        source_id=f"S-{rank:02d}",
                        url=url,
                        title="Kept",
                        author=None,
                        published=None,
                        body_markdown="Evidence.",
                        word_count=1,
                        fetched_at=FETCHED_AT,
                    ),
                    path=f"research/{rank:03d}_kept.md",
                    rank=rank,
                ),
            )
        outcomes[str(url)] = UrlOutcome(
            rank=rank,
            url=url,
            outcome="extracted" if kept else "too_thin",
            source_id=f"S-{rank:02d}" if kept else None,
        )
    run = RunState(
        run_id=workspace.run_id,
        topic=request.topic,
        completed_phases=["search"],
        clean_results=results,
        url_outcomes=outcomes,
    )
    return workspace.root, run


def test_report_carries_the_required_fields(tmp_path: Path) -> None:
    root, run = run_with(tmp_path, extracted=28)
    ledger = RunLedger("openrouter:test", price_per_token=0.0)
    ledger.phase_timings = {"search": 1.5}
    ledger.usage = [UsageRecord(100, 0.25), UsageRecord(50, 0.10)]
    report = build_run_report(
        run,
        ledger,
        workspace=root,
        blog_path="output/blog.md",
        citation_count=4,
        duration_seconds=3.0,
        status="succeeded",
        status_reasons=[],
    )
    assert report.urls_extracted == 28
    assert report.urls_extracted == len(list((root / "research").glob("*.md")))
    assert report.urls_clean == 30
    assert report.cost_usd == pytest.approx(0.35)
    assert len(report.url_outcomes) == 30
    assert report.phase_timings_seconds == {"search": 1.5}


def test_missing_cost_is_priced_from_tokens() -> None:
    ledger = RunLedger("openrouter:test", price_per_token=0.002)
    ledger.usage = [UsageRecord(1000, None)]
    tokens, cost = ledger.cost()
    assert tokens == 1000
    assert cost == pytest.approx(2.0)


def test_classify_succeeded_degraded_and_failed(tmp_path: Path) -> None:
    _, enough = run_with(tmp_path / "ok", extracted=26)
    assert classify_outcome(enough, max_urls=30, recorded_reasons=[])[0] == "succeeded"
    _, few = run_with(tmp_path / "few", extracted=21)
    status, reasons = classify_outcome(few, max_urls=30, recorded_reasons=[])
    assert status == "degraded" and "too_few_sources" in reasons
    status, reasons = classify_outcome(enough, max_urls=30, recorded_reasons=["blog_length"])
    assert status == "degraded" and reasons == ["blog_length"]
    for reason in ("no_results", "no_sources", "phase_failed", "dangling_citations"):
        status, reasons = classify_outcome(enough, max_urls=30, recorded_reasons=[reason])
        assert status == "failed" and reason in reasons


def test_phase_retries_once_then_fails(tmp_path: Path) -> None:
    calls = {"count": 0}

    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return "ok"

    result, retries = run_phase("search", flaky, tmp_path / "logs" / "execution.log")
    assert result == "ok" and retries == 1
    logged = json.loads((tmp_path / "logs" / "execution.log").read_text().splitlines()[0])
    assert {key: logged[key] for key in ("phase", "retry", "error")} == {
        "phase": "search",
        "retry": 1,
        "error": "RuntimeError",
    }
    assert logged["run_id"] == tmp_path.name and logged["event"] == "retry"
    assert logged["level"] == "WARNING" and logged["timestamp"]

    def always() -> str:
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError):
        run_phase("search", always, tmp_path / "logs" / "execution.log")


def test_resume_skips_completed_phases(tmp_path: Path) -> None:
    assert next_phase(["plan", "search"]) == "normalize"
    assert next_phase(["plan", "search", "normalize", "fetch", "index"]) == "synthesize"
    root, run = run_with(tmp_path, extracted=12)
    (root / "corpus_state.json").write_text(run.model_dump_json())
    saver = make_sqlite_checkpointer(checkpoint_path(root))
    assert checkpoint_path(root).exists()
    del saver
    resumed = settings().model_copy(update={"runs_dir": str(tmp_path)})
    code = main(["--resume", root.name], settings=resumed)
    assert code == 0


def test_written_report_validates(tmp_path: Path) -> None:
    root, run = run_with(tmp_path, extracted=26)

    report = run_report(
        root,
        run,
        settings(),
        RunLedger("openrouter:test"),
        blog_path="output/blog.md",
        duration_seconds=1.0,
    )
    reloaded = RunReport.model_validate_json((root / "output" / "run.json").read_text())
    assert reloaded == report
    assert reloaded.status == "succeeded"
