"""The production `write_run_report` tool.

A run's final report is deterministic: counts come from the corpus, the outcome
comes from PD-017 classification, and accounting comes from the run ledger. This
tool binds those to one run so the orchestrator writes the same report the CLI
would, and no stub can stand in for it during production execution (M4).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from schemas.config import RunSettings
from schemas.responses import RunReport
from schemas.state import RunState
from schemas.tool_io import WriteRunReportInput, WriteRunReportOutput
from services.authoring import BLOG_PATH, validate_citations
from services.observability import current_observer
from services.reporting import RunLedger, build_run_report, classify_outcome, write_run_report
from tools.base import TypedTool

if TYPE_CHECKING:
    from tools.base import ToolRegistry


class ReportSession:
    """One run's report inputs. Never shared across runs."""

    def __init__(
        self,
        root: Path,
        run: RunState,
        settings: RunSettings,
        ledger: RunLedger,
        *,
        started_at: float | None = None,
        recorded_reasons: list[str] | None = None,
    ) -> None:
        self.root = root
        self.run = run
        self.settings = settings
        self.ledger = ledger
        self.started_at = started_at if started_at is not None else time.monotonic()
        self.recorded_reasons = list(recorded_reasons or [])
        self.written: RunReport | None = None


def register_report_tools(registry: ToolRegistry, session: ReportSession | None) -> None:
    def write_report_tool(
        request: WriteRunReportInput, runtime: object | None = None
    ) -> WriteRunReportOutput:
        del request, runtime
        if session is None:
            raise ValueError("The production report tool requires a ReportSession")
        finding = validate_citations(session.root)
        observer = current_observer()
        if observer is not None:
            observer.record_citations(len(finding.dangling_source_ids))
        reasons = list(session.recorded_reasons)
        if finding.dangling_source_ids and "dangling_citations" not in reasons:
            reasons.append("dangling_citations")
        status, status_reasons = classify_outcome(
            session.run, max_urls=session.settings.max_urls, recorded_reasons=reasons
        )
        report = build_run_report(
            session.run,
            session.ledger,
            workspace=session.root,
            blog_path=BLOG_PATH,
            citation_count=finding.citations_checked,
            duration_seconds=time.monotonic() - session.started_at,
            status=status,
            status_reasons=status_reasons,
        )
        write_run_report(session.root, report)
        session.written = report
        return WriteRunReportOutput(report_path="output/run.json")

    registry.register(
        TypedTool[WriteRunReportInput, WriteRunReportOutput](
            name="write_run_report",
            input_model=WriteRunReportInput,
            output_model=WriteRunReportOutput,
            handler=write_report_tool,
            description=(
                "Classify the run against PD-017 and write the validated final "
                "RunReport to output/run.json. Called once, after the citation gate."
            ),
        )
    )
