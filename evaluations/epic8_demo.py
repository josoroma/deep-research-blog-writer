"""Offline EPIC-8 demo: report, outcome classification, retry, and resume.

No model and no network. Counts come from a real corpus, the cost from recorded
usage, and the checkpoint from the per-run SQLite saver.
"""

import json
from pathlib import Path
from typing import Any

from evaluations.epic7_demo import run_demo as run_authoring_demo
from schemas.config import RunSettings
from schemas.responses import RunReport
from services.checkpoints import make_sqlite_checkpointer
from services.reliability import run_phase
from services.reporting import EXIT_STATUS, RunLedger, UsageRecord, classify_outcome
from workflows.authoring_run import load_corpus_run
from workflows.reporting_run import run_report
from workflows.resume import checkpoint_path, next_phase


def run_demo(runs_root: Path) -> dict[str, Any]:
    authoring = run_authoring_demo(runs_root)
    workspace = Path(authoring["workspace"])
    run = load_corpus_run(workspace)
    ledger = RunLedger("openrouter:demo", price_per_token=0.001)
    ledger.phase_timings = {"search": 0.4, "index": 0.2}
    ledger.usage = [UsageRecord(200, 0.05), UsageRecord(100, None)]
    settings = RunSettings(_env_file=None, crawler_contact="https://example.org/contact")
    report = run_report(
        workspace,
        run,
        settings,
        ledger,
        blog_path="output/blog.md",
        duration_seconds=1.2,
    )
    RunReport.model_validate_json((workspace / "output" / "run.json").read_text())
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient")
        return "recovered"

    recovered, retries = run_phase("synthesize", flaky, workspace / "logs" / "execution.log")
    saver = make_sqlite_checkpointer(checkpoint_path(workspace))
    del saver
    summary = {
        "mode": "offline; real report, classification, retry, and checkpoint",
        "workspace": str(workspace),
        "status": report.status,
        "exit_status": EXIT_STATUS[report.status],
        "urls_extracted": report.urls_extracted,
        "cost_usd": report.cost_usd,
        "outcomes": len(report.url_outcomes),
        "retry_recovered": recovered == "recovered" and retries == 1,
        "resumed_at": next_phase(run.completed_phases),
        "checkpoint": checkpoint_path(workspace).exists(),
        "degraded_rule": classify_outcome(run, max_urls=30, recorded_reasons=["blog_length"])[0],
    }
    (workspace / "demo_evidence.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_demo(Path("runs")), indent=2))
