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
from schemas.search import QueryVariants
from services.llm_service import MissingOpenRouterKey
from services.search_provider import SearchProviderError
from workflows.authoring_run import run_authoring
from workflows.corpus_run import run_corpus
from workflows.fetch_run import load_search_workspace, run_fetch
from workflows.research_run import RunSummary, run_research
from workflows.search_run import run_search

EXIT_COMPLETED = 0
EXIT_FAILED = 1
EXIT_INVALID_INPUT = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deep-research-blog",
        description="Run the deep research blog writer skeleton for one topic.",
    )
    parser.add_argument(
        "topic", nargs="?", help="Research topic, 3 to 250 characters after trimming."
    )
    parser.add_argument("--pages", type=int, default=None, help="Search result pages (default 3).")
    parser.add_argument("--per-page", type=int, default=None, help="Results per page (default 10).")
    parser.add_argument(
        "--max-urls", type=int, default=None, help="Maximum clean URLs (default 30)."
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--search-only", action="store_true", help="Stop after saving clean search results."
    )
    modes.add_argument(
        "--fetch-only", action="store_true", help="Fetch/extract an existing search workspace."
    )
    modes.add_argument(
        "--corpus-only",
        action="store_true",
        help="Collect immutable sources and index an existing search workspace.",
    )
    modes.add_argument(
        "--author-only",
        action="store_true",
        help="Write the summary and cited draft for an existing corpus workspace.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Existing workspace for --fetch-only, --corpus-only, or --author-only.",
    )
    parser.add_argument(
        "--query-variant",
        action="append",
        help="Provide 2 or 3 variants for a reproducible search-only run.",
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
    """Parse CLI arguments and run one skeleton, search, fetch, or corpus invocation."""
    args = build_parser().parse_args(argv)
    variants = None
    try:
        resolved = settings if settings is not None else RunSettings()
        if args.fetch_only or args.corpus_only or args.author_only:
            flag = next(
                name
                for name, selected in (
                    ("--author-only", args.author_only),
                    ("--corpus-only", args.corpus_only),
                    ("--fetch-only", args.fetch_only),
                )
                if selected
            )
            if (
                args.workspace is None
                or args.query_variant
                or any(value is not None for value in (args.pages, args.per_page, args.max_urls))
            ):
                raise ValueError(f"{flag} requires --workspace and uses its saved search budget")
            saved = load_search_workspace(args.workspace)
            if args.topic is not None and args.topic.strip() != saved.topic:
                raise ValueError("Topic must match the saved workspace request")
            milestone = (
                run_authoring(args.workspace, resolved)
                if args.author_only
                else run_corpus(args.workspace, resolved)
                if args.corpus_only
                else run_fetch(args.workspace, resolved)
            )
            print(milestone.model_dump_json(indent=2))
            return EXIT_COMPLETED if milestone.status == "completed" else EXIT_FAILED
        if args.workspace is not None:
            raise ValueError("--workspace requires --fetch-only, --corpus-only, or --author-only")
        if args.topic is None:
            raise ValueError("A topic is required")
        request = _request_from_args(args, resolved)
        if args.query_variant and not args.search_only:
            raise ValueError("--query-variant requires --search-only")
        variants = QueryVariants(variants=args.query_variant) if args.query_variant else None
    except (ValidationError, ValueError) as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    try:
        if args.search_only:
            search_summary = run_search(
                request, resolved, runs_root=Path(resolved.runs_dir), variants=variants
            )
            print(search_summary.model_dump_json(indent=2))
            return EXIT_COMPLETED if search_summary.status == "completed" else EXIT_FAILED
        summary = run_research(request, resolved, runs_root=Path(resolved.runs_dir))
    except (MissingOpenRouterKey, SearchProviderError, ValueError) as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    _print_summary(summary)
    return EXIT_COMPLETED if summary.status == "completed" else EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
