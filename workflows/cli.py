"""The `deep-research-blog` console script (PD-008, M1 subset).

Exit status: 0 when the run succeeds, 1 when it fails, 2 for invalid input or a
missing model key, and 3 when the run is degraded (PD-008, PD-017).
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.search import QueryVariants
from services.llm_service import MissingOpenRouterKey
from services.observability import RunObservability, observability_scope
from services.search_provider import SearchProviderError
from workflows.authoring_run import AuthoringSummary, run_authoring
from workflows.corpus_run import CorpusSummary, run_corpus
from workflows.fetch_run import FetchSummary, load_search_workspace, run_fetch
from workflows.research_run import RunSummary, run_research
from workflows.resume import load_saved_run, next_phase
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
    parser.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="Resume an interrupted run from its last completed phase.",
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


def _exit_for(status: str) -> int:
    return EXIT_COMPLETED if status == "completed" else EXIT_FAILED


def _workspace_flag(args: argparse.Namespace) -> str | None:
    """Return the selected workspace-phase flag, or ``None`` for a topic run."""
    for name, selected in (
        ("--author-only", args.author_only),
        ("--corpus-only", args.corpus_only),
        ("--fetch-only", args.fetch_only),
    ):
        if selected:
            return name
    return None


def _inspect_resume(args: argparse.Namespace, settings: RunSettings) -> int:
    """Print the phase an interrupted run would restart at; never continue it."""
    workspace = Path(settings.runs_dir) / args.resume
    if not workspace.is_dir():
        raise ValueError(f"No workspace for run {args.resume}")
    saved_run = load_saved_run(workspace)
    phase = next_phase(saved_run.completed_phases)
    observer = RunObservability(settings, "resume")
    with observability_scope(observer):
        observer.bind(workspace, saved_run.topic)
        observer.event("resume", "resume_inspected", resumed_at=phase)
        observer.finish()
    print(json.dumps({"run_id": args.resume, "resumed_at": phase}))
    return EXIT_COMPLETED


def _run_workspace_phase(args: argparse.Namespace, settings: RunSettings, flag: str) -> int:
    """Run fetch, corpus, or authoring against an existing search workspace.

    The saved request is the budget: overriding it here would make the phases
    disagree about how many URLs the run owns.
    """
    budget_overrides = (args.pages, args.per_page, args.max_urls)
    if args.workspace is None or args.query_variant or any(v is not None for v in budget_overrides):
        raise ValueError(f"{flag} requires --workspace and uses its saved search budget")
    saved = load_search_workspace(args.workspace)
    if args.topic is not None and args.topic.strip() != saved.topic:
        raise ValueError("Topic must match the saved workspace request")
    milestone: AuthoringSummary | CorpusSummary | FetchSummary
    if flag == "--author-only":
        milestone = run_authoring(args.workspace, settings)
    elif flag == "--corpus-only":
        milestone = run_corpus(args.workspace, settings)
    else:
        milestone = run_fetch(args.workspace, settings)
    print(milestone.model_dump_json(indent=2))
    return _exit_for(milestone.status)


def _topic_request(
    args: argparse.Namespace, settings: RunSettings
) -> tuple[ResearchRequest, QueryVariants | None]:
    """Validate a topic run's arguments into a request and optional variants."""
    if args.workspace is not None:
        raise ValueError("--workspace requires --fetch-only, --corpus-only, or --author-only")
    if args.topic is None:
        raise ValueError("A topic is required")
    request = _request_from_args(args, settings)
    if args.query_variant and not args.search_only:
        raise ValueError("--query-variant requires --search-only")
    variants = QueryVariants(variants=args.query_variant) if args.query_variant else None
    return request, variants


def _run_topic(
    args: argparse.Namespace,
    settings: RunSettings,
    request: ResearchRequest,
    variants: QueryVariants | None,
) -> int:
    """Run search only, or the full research skeleton, for a new topic."""
    runs_root = Path(settings.runs_dir)
    if args.search_only:
        search_summary = run_search(request, settings, runs_root=runs_root, variants=variants)
        print(search_summary.model_dump_json(indent=2))
        return _exit_for(search_summary.status)
    summary = run_research(request, settings, runs_root=runs_root)
    _print_summary(summary)
    return _exit_for(summary.status)


def _invalid(error: Exception) -> int:
    print(f"Invalid input: {error}", file=sys.stderr)
    return EXIT_INVALID_INPUT


def main(argv: Sequence[str] | None = None, settings: RunSettings | None = None) -> int:
    """Parse CLI arguments and dispatch to one mode.

    Validation and provider-setup errors exit 2 before any run work; a phase that
    ran and failed exits 1. Each mode lives in its own function so this one only
    routes.
    """
    args = build_parser().parse_args(argv)
    try:
        resolved = settings if settings is not None else RunSettings()
        if args.resume is not None:
            return _inspect_resume(args, resolved)
        flag = _workspace_flag(args)
        if flag is not None:
            return _run_workspace_phase(args, resolved, flag)
        request, variants = _topic_request(args, resolved)
    except (ValidationError, ValueError) as error:
        return _invalid(error)
    try:
        return _run_topic(args, resolved, request, variants)
    except (MissingOpenRouterKey, SearchProviderError, ValueError) as error:
        return _invalid(error)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
