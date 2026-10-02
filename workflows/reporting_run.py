"""Write the run report and classify the outcome (US-8.1, US-8.2)."""

from pathlib import Path

from schemas.config import RunSettings
from schemas.responses import RunReport
from schemas.state import RunState
from services.authoring import validate_citations
from services.observability import (
    bind_workspace,
    current_observer,
    observed_workflow,
)
from services.reliability import run_phase
from services.reporting import (
    RunLedger,
    build_run_report,
    classify_outcome,
    write_run_report,
)

LOG_PATH = "logs/execution.log"


@observed_workflow("report")
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
    bind_workspace(workspace, run.topic)
    finding = validate_citations(workspace)
    observer = current_observer()
    if observer is not None:
        observer.record_citations(len(finding.dangling_source_ids))
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
        if observer is None:
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
    if observer is None:
        ledger.retries += retries
    if report.retries != ledger.retries:
        report = report.model_copy(update={"retries": ledger.retries})
        write_run_report(workspace, report)
    return report
