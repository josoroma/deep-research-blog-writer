"""`make release VERSION=x.y.z`: tag only when every golden topic passes (US-10.5).

The gate runs `make eval`, reads the benchmark it wrote, and creates the tag only
when every topic meets every PD-021 threshold. A failing topic is reported and no
tag is created. `--dry-run` reports the decision without tagging.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from pydantic import Field

from evaluations.run_eval import BENCHMARKS_DIR
from evaluations.scoring import Benchmark
from schemas.common import Contract


class ReleaseDecision(Contract):
    version: str
    tag: str
    benchmark: str
    passed: bool
    failures: list[str] = Field(default_factory=list)
    tagged: bool = False


def tag_name(version: str) -> str:
    return version if version.startswith("v") else f"v{version}"


def latest_benchmark(directory: Path = BENCHMARKS_DIR) -> Path:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No benchmark in {directory}; run `make eval` first")
    return files[-1]


def read_benchmark(path: Path) -> Benchmark:
    return Benchmark.model_validate_json(path.read_text(encoding="utf-8"))


def decide(version: str, benchmark: Benchmark, *, benchmark_path: Path) -> ReleaseDecision:
    return ReleaseDecision(
        version=version,
        tag=tag_name(version),
        benchmark=str(benchmark_path),
        passed=benchmark.passed,
        failures=benchmark.failures,
    )


def create_tag(tag: str) -> None:
    subprocess.run(["git", "tag", tag], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version, e.g. 1.0.0")
    parser.add_argument("--dry-run", action="store_true", help="Report without tagging")
    parser.add_argument("--benchmark", type=Path, help="Score an existing benchmark file")
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    args = parser.parse_args(argv)
    if args.benchmark is not None:
        benchmark_path = args.benchmark
        benchmark = read_benchmark(benchmark_path)
    else:
        from evaluations.run_eval import main as run_eval

        code = run_eval(["--runs-root", str(args.runs_root)])
        benchmark_path = latest_benchmark()
        benchmark = read_benchmark(benchmark_path)
        if code not in (0, 1):
            return code
    decision = decide(args.version, benchmark, benchmark_path=benchmark_path)
    if decision.passed and not args.dry_run:
        create_tag(decision.tag)
        decision = decision.model_copy(update={"tagged": True})
    print(json.dumps(decision.model_dump(mode="json"), indent=2))
    if not decision.passed:
        for failure in decision.failures:
            print(f"release blocked: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
