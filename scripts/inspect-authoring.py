"""Inspect a finished authoring workspace and print the gate findings."""

import json
import sys
from pathlib import Path

from services.authoring import check_blog, check_summary, validate_citations


def main() -> int:
    workspace = Path(sys.argv[1])
    summary = check_summary(workspace)
    blog = check_blog(workspace)
    finding = validate_citations(workspace)
    report = {
        "summary_passed": summary.passed,
        "missing_sections": summary.missing_sections,
        "unknown_source_ids": summary.unknown_source_ids,
        "word_count": blog.word_count,
        "headings_valid": blog.headings_valid,
        "within_length": blog.within_length,
        "citations_checked": finding.citations_checked,
        "dangling": finding.dangling_source_ids,
        "mismatched": finding.mismatched_source_ids,
    }
    print(json.dumps(report, indent=2))
    return 0 if summary.passed and blog.headings_valid and finding.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
