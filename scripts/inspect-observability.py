"""Print and validate the PM-facing observability evidence in one run workspace."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("workspace", type=Path)
args = parser.parse_args()
workspace = args.workspace
snapshot = json.loads((workspace / "logs/telemetry.json").read_text())
records = [json.loads(line) for line in (workspace / "logs/execution.log").read_text().splitlines()]
assert records
assert all({"timestamp", "level", "run_id", "phase", "event"} <= row.keys() for row in records)
assert all(row["run_id"] == workspace.name for row in records)
failures = [row for row in records if row["event"] == "source_failed"]
assert all(row.get("url") and row.get("reason") for row in failures)
trace_path = workspace / "logs/trace_evidence.json"
traces = json.loads(trace_path.read_text()) if trace_path.exists() else []
assert all(row["metadata"]["run_id"] == workspace.name and row["ended"] for row in traces)
print(
    json.dumps(
        {
            "workspace": str(workspace),
            "telemetry": snapshot,
            "valid_json_log_records": len(records),
            "ended_trace_spans": len(traces),
            "source_failures": failures,
        },
        indent=2,
    )
)
