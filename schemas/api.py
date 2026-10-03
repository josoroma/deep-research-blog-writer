"""HTTP request, response and error contracts for the server API (M2).

These models are the only shapes that cross the transport boundary. Domain
contracts (``ResearchRequest``, ``RunReport``) are reused inside them so the CLI
and the API validate identical business rules.
"""

from typing import Any, Literal

from pydantic import AwareDatetime, Field

from schemas.common import Contract
from schemas.jobs import JobOperation, JobState
from schemas.requests import ResearchRequest
from schemas.responses import RunReport

ArtifactKind = Literal["markdown", "json", "log", "state", "other"]


class SubmissionRequest(Contract):
    """Admission payload. Budgets are re-checked against server-side caps."""

    mode: JobOperation = "research"
    topic: str = Field(min_length=3, max_length=250)
    pages: int = Field(default=3, ge=1)
    per_page: int = Field(default=10, ge=1)
    max_urls: int = Field(default=30, ge=1)

    def to_research_request(self) -> ResearchRequest:
        return ResearchRequest(
            topic=self.topic, pages=self.pages, per_page=self.per_page, max_urls=self.max_urls
        )


class JobLinks(Contract):
    status: str = Field(min_length=1)


class JobAccepted(Contract):
    job_id: str = Field(min_length=1)
    status: JobState
    operation: JobOperation
    run_id: str | None = None
    links: JobLinks


class JobStatus(Contract):
    job_id: str = Field(min_length=1)
    status: JobState
    operation: JobOperation
    run_id: str | None = None
    phase: str | None = None
    attempt: int = Field(ge=0)
    status_reasons: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    links: JobLinks


class ResumeRequest(Contract):
    """Resume carries no body fields today; the contract exists for evolution."""

    reason: str | None = Field(default=None, max_length=200)


class RunListItem(Contract):
    run_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    status: str | None = None
    created_at: AwareDatetime | None = None


class RunList(Contract):
    runs: list[RunListItem]
    next_cursor: str | None = None


class RunStatus(Contract):
    run_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    completed_phases: list[str] = Field(default_factory=list)
    execution_status: str | None = None
    report_available: bool = False
    artifacts_available: bool = False


class ArtifactEntry(Contract):
    artifact_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    kind: ArtifactKind
    media_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    download_url: str = Field(min_length=1)


class ArtifactList(Contract):
    artifacts: list[ArtifactEntry]


class LogRecord(Contract):
    """Projected, already-redacted records from the run's JSON Lines log."""

    timestamp: str | None = None
    level: str | None = None
    phase: str | None = None
    event: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class LogPage(Contract):
    records: list[LogRecord]
    next_cursor: str | None = None


class RunReportEnvelope(Contract):
    run_id: str = Field(min_length=1)
    report: RunReport


class ErrorBody(Contract):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)


class ErrorResponse(Contract):
    error: ErrorBody
