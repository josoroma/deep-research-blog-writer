"""Validate output/run.json against the RunReport model and print the outcome."""

import json
import sys
from pathlib import Path

from schemas.responses import RunReport
from services.reporting import EXIT_STATUS


def main() -> int:
    workspace = Path(sys.argv[1])
    report = RunReport.model_validate_json((workspace / "output" / "run.json").read_text())
    print(
        json.dumps(
            {
                "status": report.status,
                "exit_status": EXIT_STATUS[report.status],
                "reasons": report.status_reasons,
                "urls_extracted": report.urls_extracted,
                "urls_clean": report.urls_clean,
                "cost_usd": report.cost_usd,
                "outcomes": len(report.url_outcomes),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
