"""One opt-in live corpus collection; no LLM or search credentials needed."""

import argparse
import json
from pathlib import Path

from pydantic import HttpUrl, ValidationError

from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from services.artifacts import write_json
from services.corpus import read_corpus
from services.workspace import create_run_workspace
from workflows.corpus_run import run_corpus

DEFAULT_URL = "https://docs.python.org/3.12/library/asyncio.html"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path, help="Optional JSON evidence path.")
    args = parser.parse_args()
    try:
        request = ResearchRequest(topic="EPIC-6 live research corpus", max_urls=1)
        workspace = create_run_workspace(request, Path("runs"))
        result = SearchResult(
            url=HttpUrl(args.url),
            title="Live corpus source",
            snippet="Opt-in live corpus smoke; no search provider called",
            rank=1,
            query=request.topic,
        )
        write_json(workspace.root / "clean_results.json", [result.model_dump(mode="json")])
        summary = run_corpus(workspace.root, RunSettings())
    except (ValueError, ValidationError) as error:
        print(f"Invalid input: {error}")
        return 2
    records = read_corpus(workspace.root)
    evidence = {
        "mode": "live HTTP, real corpus tools and extraction libraries",
        "workspace": str(workspace.root),
        "summary": summary.model_dump(mode="json"),
        "source_files": [record.path for record in records],
        "passed": summary.status == "completed" and summary.sources_written == 1,
    }
    if args.output:
        write_json(args.output, evidence)
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
