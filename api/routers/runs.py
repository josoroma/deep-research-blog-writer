"""Read APIs for registered runs: status, report, artifacts, and bounded logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from api.dependencies import ReaderDep, require_token
from api.errors import ApiError, not_found
from schemas.api import (
    ArtifactEntry,
    ArtifactList,
    LogPage,
    LogRecord,
    RunList,
    RunListItem,
    RunReportEnvelope,
    RunStatus,
)
from services.artifact_reader import ArtifactNotFound, ArtifactReader, ArtifactTooLarge, UnsafePath

router = APIRouter(prefix="/v1", tags=["runs"], dependencies=[Depends(require_token)])


def _guard(run_id: str, artifact_reader: ArtifactReader) -> None:
    try:
        artifact_reader.run_root(run_id)
    except (ArtifactNotFound, UnsafePath):
        raise not_found("run") from None


def _report_status(run_id: str, artifact_reader: ArtifactReader) -> str | None:
    report = artifact_reader.read_report(run_id)
    return report.status if report is not None else None


@router.get("/runs", response_model=RunList)
def list_runs(
    artifact_reader: ReaderDep,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> RunList:
    root = artifact_reader.runs_root
    if not root.is_dir():
        return RunList(runs=[], next_cursor=None)
    start = int(cursor) if cursor and cursor.isdigit() else 0
    names = sorted(
        entry.name for entry in root.iterdir() if entry.is_dir() and not entry.is_symlink()
    )
    page = names[start : start + limit]
    items = [
        RunListItem(
            run_id=name,
            topic=artifact_reader.run_topic(name),
            status=_report_status(name, artifact_reader),
        )
        for name in page
    ]
    nxt = str(start + limit) if start + limit < len(names) else None
    return RunList(runs=items, next_cursor=nxt)


@router.get("/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str, artifact_reader: ReaderDep) -> RunStatus:
    _guard(run_id, artifact_reader)
    state = artifact_reader.read_run_state(run_id)
    completed = state.get("completed_phases")
    report = artifact_reader.read_report(run_id)
    return RunStatus(
        run_id=run_id,
        topic=artifact_reader.run_topic(run_id),
        completed_phases=[str(phase) for phase in completed] if isinstance(completed, list) else [],
        execution_status=report.status if report is not None else None,
        report_available=report is not None,
        artifacts_available=bool(artifact_reader.list_artifacts(run_id)),
    )


@router.get("/runs/{run_id}/report", response_model=RunReportEnvelope)
def get_report(run_id: str, artifact_reader: ReaderDep) -> RunReportEnvelope:
    _guard(run_id, artifact_reader)
    report = artifact_reader.read_report(run_id)
    if report is None:
        raise ApiError(409, "report_not_ready", "The final report is not available yet")
    return RunReportEnvelope(run_id=run_id, report=report)


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactList)
def get_artifacts(run_id: str, artifact_reader: ReaderDep) -> ArtifactList:
    _guard(run_id, artifact_reader)
    return ArtifactList(
        artifacts=[
            ArtifactEntry.model_validate(entry) for entry in artifact_reader.list_artifacts(run_id)
        ]
    )


@router.get("/runs/{run_id}/artifacts/{artifact_path:path}")
def download_artifact(run_id: str, artifact_path: str, artifact_reader: ReaderDep) -> Response:
    _guard(run_id, artifact_reader)
    try:
        filename, media_type, payload = artifact_reader.read_bytes(run_id, artifact_path)
    except (ArtifactNotFound, ArtifactTooLarge, UnsafePath):
        raise not_found("artifact") from None
    disposition = "attachment" if media_type.startswith("text/") else "inline"
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/logs", response_model=LogPage)
def get_logs(
    run_id: str,
    artifact_reader: ReaderDep,
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1),
) -> LogPage:
    _guard(run_id, artifact_reader)
    bounded = min(limit, artifact_reader.log_page_limit)
    records, next_cursor = artifact_reader.read_log_page(run_id, cursor=cursor, limit=bounded)
    return LogPage(
        records=[LogRecord.model_validate(record) for record in records],
        next_cursor=str(next_cursor) if next_cursor is not None else None,
    )
