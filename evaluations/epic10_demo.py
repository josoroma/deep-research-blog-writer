"""Offline EPIC-10 demo: score a fixture run and exercise the release gate.

No model and no network. It runs the fixture pipeline for one golden topic, scores
it with the deterministic checks and the offline judge, writes a benchmark, and
shows both a passing and a blocked release decision.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluations.judge import AlwaysSupportedJudge
from evaluations.offline_eval import fixture_topic, run_offline_topic
from evaluations.release import decide
from evaluations.run_eval import build_benchmark, score_workspace, write_benchmark
from evaluations.scoring import (
    MAX_HALLUCINATION_RATE,
    MIN_COVERAGE,
    MIN_GROUNDEDNESS,
    coverage,
    factual_claims,
    groundedness_and_hallucination,
)
from schemas.responses import RunReport


def run_demo(runs_root: Path) -> dict[str, Any]:
    topic = fixture_topic()
    workspace = run_offline_topic(topic, runs_root)
    judge = AlwaysSupportedJudge()
    score = score_workspace(workspace, topic, judge)
    report = RunReport.model_validate_json((workspace / "output/run.json").read_text())
    claims = factual_claims(workspace)
    judged = judge.judge(claims)
    grounded, hallucination = groundedness_and_hallucination(claims, judged)
    benchmark = build_benchmark(
        [score], commit="offline-demo", model=report.model, judge_model=report.model, date="demo"
    )
    path = write_benchmark(benchmark, runs_root / "benchmarks")
    passing = decide("1.0.0", benchmark, benchmark_path=path)
    blocked = decide(
        "1.0.0",
        benchmark.model_copy(
            update={
                "passed": False,
                "failures": ["agentic-ai-frameworks: coverage_min_0.5"],
            }
        ),
        benchmark_path=path,
    )
    summary = {
        "mode": "offline; fixture pipeline, deterministic scoring, offline judge",
        "workspace": str(workspace),
        "topic_id": score.topic_id,
        "status": score.status,
        "citation_validity": score.citation_validity,
        "word_count": score.word_count,
        "coverage": score.coverage,
        "groundedness": score.groundedness,
        "hallucination_rate": score.hallucination_rate,
        "definition_of_done": score.definition_of_done.model_dump(),
        "thresholds": score.thresholds,
        "passed": score.passed,
        "factual_claims": len(claims),
        "benchmark": str(path),
        "release_passing_tagged": passing.passed,
        "release_blocked_failures": blocked.failures,
        "thresholds_pd_021": {
            "coverage_min": MIN_COVERAGE,
            "groundedness_min": MIN_GROUNDEDNESS,
            "hallucination_max": MAX_HALLUCINATION_RATE,
        },
        "coverage_recomputed": coverage(workspace),
    }
    (workspace / "demo_evidence.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    print(json.dumps(run_demo(Path("runs")), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
