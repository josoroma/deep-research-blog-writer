"""Deterministic PM acceptance demo for the FastAPI migration (M3-M5).

Runs an isolated fixture profile: it starts the app in-process with an in-memory
store, submits a research job, drives the worker, and then reads the job, run
status, final report, and an artifact download. It makes no model, search, or
website call and uses temporary storage separate from real research runs.

The demo prints the exact commands it represents so an operator can reproduce the
same flow over real HTTP with ``make demo-api``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app
from schemas.config import ApiSettings
from services.job_store import MemoryJobStore
from workers.research_worker import ResearchWorker

TOPIC = "Research telemetry quality"
MAX_URLS = 3


def run_demo() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="api-fixture-demo-") as root:
        runs_dir = Path(root) / "runs"
        api = ApiSettings(
            _env_file=None,
            run_profile="fixture",
            runs_dir=str(runs_dir),
            queue_limit=5,
        )
        store = MemoryJobStore()
        app = create_app(api, store=store)
        evidence: dict[str, object] = {"commands": DEMO_COMMANDS}
        with TestClient(app) as client:
            live = client.get("/health/live")
            ready = client.get("/health/ready")
            evidence["health"] = {"live": live.status_code, "ready": ready.status_code}

            accepted = client.post(
                "/v1/runs",
                json={
                    "mode": "research",
                    "topic": TOPIC,
                    "pages": 1,
                    "per_page": 10,
                    "max_urls": MAX_URLS,
                },
                headers={"Idempotency-Key": "pm-fastapi-demo-1"},
            )
            evidence["submit"] = {
                "status": accepted.status_code,
                "location": accepted.headers.get("location"),
                "body": accepted.json(),
            }
            job_id = accepted.json()["job_id"]

            duplicate = client.post(
                "/v1/runs",
                json={
                    "mode": "research",
                    "topic": TOPIC,
                    "pages": 1,
                    "per_page": 10,
                    "max_urls": MAX_URLS,
                },
                headers={"Idempotency-Key": "pm-fastapi-demo-1"},
            )
            evidence["idempotent_replay"] = {
                "status": duplicate.status_code,
                "same_job": duplicate.json()["job_id"] == job_id,
            }

            worker = ResearchWorker(store, api, identity="pm-demo-worker", once=True)
            outcome = worker.run_once()
            evidence["worker"] = None if outcome is None else outcome.__dict__

            status = client.get(f"/v1/jobs/{job_id}").json()
            run_id = status["run_id"]
            evidence["job"] = status

            report = client.get(f"/v1/runs/{run_id}/report")
            evidence["report"] = {
                "status": report.status_code,
                "body": report.json()["report"] if report.status_code == 200 else report.json(),
            }
            run_status = client.get(f"/v1/runs/{run_id}").json()
            evidence["run"] = run_status

            artifacts = client.get(f"/v1/runs/{run_id}/artifacts").json()["artifacts"]
            evidence["artifacts"] = [entry["artifact_id"] for entry in artifacts]
            download = client.get(f"/v1/runs/{run_id}/artifacts/output/blog.md")
            evidence["blog_download"] = {
                "status": download.status_code,
                "bytes": len(download.content),
            }
            logs = client.get(f"/v1/runs/{run_id}/logs", params={"limit": 5}).json()
            evidence["log_records"] = len(logs["records"])
        return evidence


DEMO_COMMANDS: list[str] = [
    "curl --fail --silent --show-error http://127.0.0.1:8000/health/ready",
    "curl --include -H 'Content-Type: application/json' "
    "-H 'Idempotency-Key: pm-fastapi-demo-1' "
    '-d \'{"mode":"research","topic":"Research telemetry quality",'
    '"pages":1,"per_page":10,"max_urls":3}\' http://127.0.0.1:8000/v1/runs',
    "curl http://127.0.0.1:8000/v1/jobs/<job_id>",
    "curl http://127.0.0.1:8000/v1/runs/<run_id>/report",
    "curl -o blog.md http://127.0.0.1:8000/v1/runs/<run_id>/artifacts/output/blog.md",
]


def main() -> int:  # pragma: no cover - demo entry point
    evidence = run_demo()
    print(json.dumps(evidence, indent=2, default=str))
    report = evidence.get("report", {})
    assert isinstance(report, dict)
    body = report.get("body")
    status = body.get("status") if isinstance(body, dict) else None
    print(f"\nPM acceptance: report status = {status}")
    return 0 if report.get("status") == 200 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
