"""One opt-in public HTML fetch/extraction; no LLM or search credentials needed."""

import argparse
import json
from pathlib import Path

from pydantic import HttpUrl, ValidationError

from schemas.config import RunSettings
from schemas.content import ExtractionResult, FetchResult
from services.artifacts import write_json
from services.extraction_service import create_extraction_service
from services.fetch_service import FetchService
from tools.registry import create_tool_registry

DEFAULT_URL = "https://docs.python.org/3.12/library/asyncio.html"


def run_smoke(settings: RunSettings, url: HttpUrl) -> dict[str, object]:
    with FetchService(settings) as fetcher:
        registry = create_tool_registry(
            fetcher=fetcher, extractor=create_extraction_service(settings)
        )
        fetched = registry["fetch_url"].invoke({"url": url})
        assert isinstance(fetched, FetchResult)
        evidence: dict[str, object] = {
            "mode": "live HTTP and actual extraction libraries",
            "user_agent": fetcher.user_agent,
            "fetch": fetched.model_dump(mode="json", exclude={"page"}),
        }
        if fetched.page is not None:
            extracted = registry["extract_markdown"].invoke(
                {
                    "page": fetched.page.model_dump(),
                    "source_id": "S-01",
                    "fetched_at": fetched.fetched_at,
                }
            )
            assert isinstance(extracted, ExtractionResult)
            evidence["extraction"] = extracted.model_dump(
                mode="json",
                exclude={"source": {"body_markdown"}},
            )
            evidence["passed"] = extracted.outcome == "extracted"
        else:
            evidence["passed"] = False
        evidence["requests"] = [event.model_dump(mode="json") for event in fetcher.events]
        evidence["retries"] = [event.model_dump(mode="json") for event in fetcher.retries]
        return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--output", type=Path, help="Optional JSON evidence path (parent must exist)."
    )
    args = parser.parse_args()
    try:
        evidence = run_smoke(RunSettings(), HttpUrl(args.url))
    except (ValueError, ValidationError) as error:
        print(f"Invalid input: {error}")
        return 2
    if args.output:
        write_json(args.output, evidence)
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
