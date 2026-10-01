"""The `deep-research-blog` console script (PD-008, M1 subset).

Exit status: 0 when the skeleton invocation completes, 1 when it fails, and 2 for
invalid input or a missing model key. PD-017 statuses and exit 3 arrive with US-8.2.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from services.llm_service import MissingOpenRouterKey
from workflows.research_run import RunSummary, run_research

EXIT_COMPLETED = 0
EXIT_FAILED = 1
EXIT_INVALID_INPUT = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deep-research-blog",
        description="Run the deep research blog writer skeleton for one topic.",
    )
    parser.add_argument("topic", help="Research topic, 3 to 250 characters after trimming.")
    parser.add_argument("--pages", type=int, default=None, help="Search result pages (default 3).")
    parser.add_argument("--per-page", type=int, default=None, help="Results per page (default 10).")
    parser.add_argument(
        "--max-urls", type=int, default=None, help="Maximum clean URLs (default 30)."
    )
    return parser


def _request_from_args(args: argparse.Namespace, settings: RunSettings) -> ResearchRequest:
    return ResearchRequest(
        topic=args.topic,
        pages=args.pages if args.pages is not None else settings.pages,
        per_page=args.per_page if args.per_page is not None else settings.per_page,
        max_urls=args.max_urls if args.max_urls is not None else settings.max_urls,
    )


def _print_summary(summary: RunSummary) -> None:
    print(f"run_id: {summary.run_id}")
    print(f"workspace: {summary.workspace}")
    print(f"status: {summary.status}")
    print(f"blog_path: {summary.blog_path}")
    print(f"blog_exists: {summary.blog_exists}")
    if summary.error is not None:
        print(f"error: {summary.error}")


def main(argv: Sequence[str] | None = None, settings: RunSettings | None = None) -> int:
    args = build_parser().parse_args(argv)
    resolved = settings if settings is not None else RunSettings()
    try:
        request = _request_from_args(args, resolved)
    except ValidationError as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    try:
        summary = run_research(request, resolved, runs_root=Path(resolved.runs_dir))
    except MissingOpenRouterKey as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    _print_summary(summary)
    return EXIT_COMPLETED if summary.status == "completed" else EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
