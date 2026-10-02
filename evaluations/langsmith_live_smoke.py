"""Opt-in hosted tracing of actual graph/tools with deterministic fixture work."""

import json
import time
from pathlib import Path
from typing import Any

from langsmith import Client
from langsmith.schemas import Run

from evaluations.epic9_demo import run_demo
from schemas.config import RunSettings
from services.artifacts import write_json
from services.observability import RunObservability


def main() -> int:
    settings = RunSettings()
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        raise SystemExit("Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY in .env")
    observer = RunObservability(settings, "hosted-smoke")
    demo = run_demo(Path("runs"), observer=observer)
    assert observer.root is not None
    client = Client(
        api_url=settings.langsmith_endpoint, api_key=settings.langsmith_api_key.get_secret_value()
    )

    def descendants(parent: Run) -> list[Run]:
        children: list[Run] = []
        for child in parent.child_runs or []:
            children.extend([child, *descendants(child)])
        return children

    deadline = time.monotonic() + 45
    while True:
        try:
            root = client.read_run(observer.root.id, load_child_runs=True)
            children = descendants(root)
            if len(children) >= 90 and all(child.end_time for child in children):
                break
        except Exception:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Hosted LangSmith trace is not readable; check credentials/project"
                ) from None
        if time.monotonic() >= deadline:
            raise RuntimeError("Hosted trace descendants did not finish ingesting")
        time.sleep(0.5)
    runs = [root, *children]
    assert all(
        run.extra.get("metadata", {}).get("run_id") == demo["telemetry"]["run_id"] for run in runs
    )
    assert all(
        run.extra.get("metadata", {}).get("topic") == demo["telemetry"]["topic"] for run in runs
    )
    assert any(run.run_type == "llm" for run in children)
    assert any(run.name == "task" for run in children)
    assert any(run.name == "collect_source" for run in children)
    evidence: dict[str, Any] = {
        "workspace": demo["workspace"],
        "trace_url": client.get_run_url(run=root),
        "trace_id": str(root.id),
        "project": settings.langsmith_project,
        "spans": [
            {
                "id": str(run.id),
                "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
                "name": run.name,
                "type": run.run_type,
                "ended": run.end_time is not None,
                "metadata": run.extra.get("metadata", {}),
            }
            for run in runs
        ],
    }
    write_json(Path(demo["workspace"]) / "logs/hosted_trace_evidence.json", evidence)
    client.close()
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
