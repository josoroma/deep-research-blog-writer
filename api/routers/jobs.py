"""Job submission, polling, and resume endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse

from api.dependencies import JobServiceDep, require_token
from api.errors import ERROR_RESPONSES, conflict, not_found
from application.job_service import validate_idempotency_key
from schemas.api import JobAccepted, JobLinks, JobStatus, ResumeRequest, SubmissionRequest
from schemas.jobs import JobRecord

router = APIRouter(
    prefix="/v1",
    tags=["jobs"],
    dependencies=[Depends(require_token)],
    responses=ERROR_RESPONSES,
)

IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]


def _links(job_id: str) -> JobLinks:
    return JobLinks(status=f"/v1/jobs/{job_id}")


def _status(record: JobRecord) -> JobStatus:
    return JobStatus(
        job_id=record.job_id,
        status=record.state,
        operation=record.operation,
        run_id=record.run_id,
        phase=record.phase,
        attempt=record.attempt,
        status_reasons=record.status_reasons,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
        links=_links(record.job_id),
    )


@router.post("/runs", status_code=202, response_model=JobAccepted)
def submit_run(
    payload: SubmissionRequest,
    response: Response,
    service: JobServiceDep,
    idempotency_key: IdempotencyKey = None,
) -> JobAccepted:
    """Admit a search or research job and return ``202`` with its status link.

    An exact replay of the same key and body returns ``200`` with the original job.
    """
    record, created = service.submit(payload, idempotency_key=idempotency_key)
    response.status_code = 202 if created else 200
    response.headers["Location"] = f"/v1/jobs/{record.job_id}"
    return JobAccepted(
        job_id=record.job_id,
        status=record.state,
        operation=record.operation,
        run_id=record.run_id,
        links=_links(record.job_id),
    )


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str, service: JobServiceDep) -> JobStatus:
    """Return a job's state, phase, attempt, and safe reasons."""
    record = service.status(job_id)
    if record is None:
        raise not_found("job")
    return _status(record)


@router.post("/runs/{run_id}/resume", status_code=202)
def resume_run(
    run_id: str,
    service: JobServiceDep,
    payload: ResumeRequest | None = None,
    idempotency_key: IdempotencyKey = None,
) -> JSONResponse:
    """Re-queue an interrupted run as a new attempt on the same workspace.

    The key is validated before state checks so a malformed request is reported
    as such, regardless of the run's state. Store failures surface as ``503``
    through the shared handler.
    """
    del payload
    validate_idempotency_key(idempotency_key)
    record = service.latest_for_run(run_id)
    if record is None:
        raise not_found("run")
    if not service.eligible_for_resume(record):
        raise conflict("not_resumable", "Only an interrupted run with a workspace can resume")
    released = service.release_for_resume(record)
    return JSONResponse(
        status_code=202,
        content={
            "job_id": released.job_id,
            "status": released.state,
            "operation": released.operation,
            "run_id": released.run_id,
            "links": {"status": f"/v1/jobs/{released.job_id}"},
        },
        headers={"Location": f"/v1/jobs/{released.job_id}"},
    )
