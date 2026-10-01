"""Write the run report and classify the outcome (US-8.1, US-8.2)."""

from pathlib import Path

from schemas.config import RunSettings
from schemas.responses import RunReport
from schemas.state import RunState
from services.authoring import validate_citations
from services.reliability import run_phase
from services.reporting import (
    RunLedger,
    build_run_report,
    classify_outcome,
    write_run_report,
)

LOG_PATH = "logs/execution.log"


def run_report(
    workspace: Path,
    run: RunState,
    settings: RunSettings,
    ledger: RunLedger,
    *,
    blog_path: str,
    duration_seconds: float,
    recorded_reasons: list[str] | None = None,
) -> RunReport:
    """Classify, then always write the report, including after a failed phase."""
    finding = validate_citations(workspace)
    reasons = list(recorded_reasons or [])
    if finding.dangling_source_ids and "dangling_citations" not in reasons:
        reasons.append("dangling_citations")
    status, status_reasons = classify_outcome(
        run, max_urls=settings.max_urls, recorded_reasons=reasons
    )

    def write() -> RunReport:
        report = build_run_report(
            run,
            ledger,
            workspace=workspace,
            blog_path=blog_path,
            citation_count=finding.citations_checked,
            duration_seconds=duration_seconds,
            status=status,
            status_reasons=status_reasons,
        )
        write_run_report(workspace, report)
        return report

    try:
        report, retries = run_phase("report", write, workspace / LOG_PATH)
    except Exception:
        ledger.retries += 1
        failed, failed_reasons = classify_outcome(
            run, max_urls=settings.max_urls, recorded_reasons=[*reasons, "phase_failed"]
        )
        report = build_run_report(
            run,
            ledger,
            workspace=workspace,
            blog_path=blog_path,
            citation_count=finding.citations_checked,
            duration_seconds=duration_seconds,
            status=failed,
            status_reasons=failed_reasons,
        )
        write_run_report(workspace, report)
        return report
    ledger.retries += retries
    return report
