"""`make eval`: run the pipeline on the golden dataset and score every topic (US-10.3).

Live by default: it uses the production models and SerpApi. `--offline` runs the
same scoring path against the fixture pipeline so the logic is testable without
credentials. Results are written to `evaluations/benchmarks/<date>-<commit>.json`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from evaluations.judge import AlwaysSupportedJudge, ModelJudge
from evaluations.scoring import Benchmark, Judge, TopicScore, benchmark_name, score_topic
from schemas.common import Contract
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import RunReport
from services.reporting import RunLedger
from workflows.authoring_run import load_corpus_run, run_authoring
from workflows.corpus_run import run_corpus
from workflows.reporting_run import run_report
from workflows.search_run import run_search

BENCHMARKS_DIR = Path("evaluations/benchmarks")
GOLDEN_DATASET = Path("evaluations/golden_dataset.json")


class GoldenTopic(Contract):
    id: str = Field(min_length=1)
    topic: str = Field(min_length=3)
    pages: int = Field(default=3, ge=1)
    per_page: int = Field(default=10, ge=1)
    max_urls: int = Field(default=30, ge=1)


class GoldenDataset(Contract):
    version: int = Field(ge=1)
    source: str
    topics: list[GoldenTopic] = Field(min_length=1)


def load_dataset(path: Path = GOLDEN_DATASET) -> GoldenDataset:
    return GoldenDataset.model_validate_json(path.read_text(encoding="utf-8"))


def current_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_topic_live(topic: GoldenTopic, settings: RunSettings, runs_root: Path) -> Path:
    """Run search → corpus → authoring → report with the production services."""
    request = ResearchRequest(
        topic=topic.topic, pages=topic.pages, per_page=topic.per_page, max_urls=topic.max_urls
    )
    search = run_search(request, settings, runs_root=runs_root)
    if search.status != "completed":
        raise RuntimeError(f"Search failed for {topic.id}: {search.error}")
    workspace = Path(search.workspace)
    corpus = run_corpus(workspace, settings)
    if corpus.status != "completed":
        raise RuntimeError(f"Corpus failed for {topic.id}: {corpus.error}")
    run_authoring(workspace, settings)
    ledger = RunLedger(settings.models.orchestrator)
    run_report(
        workspace,
        load_corpus_run(workspace),
        settings,
        ledger,
        blog_path="output/blog.md",
        duration_seconds=0.0,
    )
    return workspace


def score_workspace(workspace: Path, topic: GoldenTopic, judge: Judge | None) -> TopicScore:
    report = RunReport.model_validate_json((workspace / "output/run.json").read_text())
    return score_topic(workspace, report, topic_id=topic.id, judge=judge)


def write_benchmark(benchmark: Benchmark, directory: Path | None = None) -> Path:
    directory = directory if directory is not None else BENCHMARKS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / benchmark_name(benchmark.date, benchmark.commit)
    payload = json.dumps(benchmark.model_dump(mode="json"), indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def build_benchmark(
    scores: list[TopicScore], *, commit: str, model: str, judge_model: str, date: str
) -> Benchmark:
    failures = [
        f"{score.topic_id}: {', '.join(score.failures)}" for score in scores if not score.passed
    ]
    return Benchmark(
        date=date,
        commit=commit,
        model=model,
        judge_model=judge_model,
        topics=scores,
        passed=not failures,
        failures=failures,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Score the fixture pipeline")
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument("--dataset", type=Path, default=GOLDEN_DATASET)
    args = parser.parse_args(argv)
    dataset = load_dataset(args.dataset)
    settings = RunSettings()
    judge: Judge = AlwaysSupportedJudge() if args.offline else ModelJudge(settings)
    scores: list[TopicScore] = []
    if args.offline:
        from evaluations.offline_eval import run_offline_topic

        for topic in dataset.topics:
            # The fixture provider answers one topic, so each golden topic gets its
            # own runs root; otherwise identical run ids collide within a second.
            workspace = run_offline_topic(topic, args.runs_root / topic.id)
            scores.append(score_workspace(workspace, topic, judge))
    else:
        for topic in dataset.topics:
            workspace = run_topic_live(topic, settings, args.runs_root)
            scores.append(score_workspace(workspace, topic, judge))
    benchmark = build_benchmark(
        scores,
        commit=current_commit(),
        model=settings.models.orchestrator,
        judge_model=settings.models.orchestrator,
        date=datetime.now(UTC).strftime("%Y-%m-%d"),
    )
    path = write_benchmark(benchmark)
    print(json.dumps(benchmark.model_dump(mode="json"), indent=2))
    print(f"benchmark: {path}", file=sys.stderr)
    return 0 if benchmark.passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
