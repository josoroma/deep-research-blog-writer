"""Deterministic fake providers and tools for the server fixture profile.

Selecting ``API_RUN_PROFILE=fixture`` swaps in these fakes at the worker boundary
only. They make no model, search or website calls, so an integration check can
exercise the real database, API process and worker without a network or keys.
Clients cannot enable this profile in a request.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import HttpUrl

from evaluations.fakes import ScriptedChatModel
from schemas.content import ExtractionResult, FetchResult, ParserAttempt, utc_now
from schemas.responses import FetchedPage, SearchResult, Source
from schemas.search import QueryVariants
from schemas.tool_io import ExtractMarkdownInput
from services.authoring import REQUIRED_HEADINGS
from services.corpus import read_corpus
from services.extraction_service import ExtractionService
from services.search_provider import FakeSearchProvider

FIXTURE_WORDS = 320


def fixture_search_pages(
    topic: str, *, pages: int, per_page: int
) -> Mapping[tuple[str, int], list[SearchResult]]:
    """Ten results per primary topic page; variant queries legitimately return none."""
    results: dict[tuple[str, int], list[SearchResult]] = {}
    for page in range(1, pages + 1):
        offset = (page - 1) * per_page
        results[(topic, page)] = [
            SearchResult(
                url=HttpUrl(f"https://fixture.test/article-{offset + index}"),
                title=f"Fixture source {offset + index}",
                snippet="Server fixture result",
                rank=offset + index,
                query=topic,
            )
            for index in range(1, per_page + 1)
        ]
    return results


class FixtureExtractionService(ExtractionService):
    """Produce a valid, long-enough source without parsing anything.

    Subclassing the real service keeps the tool boundary's type honest while the
    deterministic body avoids any parser or network call.
    """

    def __init__(self) -> None:
        """Register a single no-op parser so the base class invariants hold."""
        super().__init__((_FixtureExtractor(),))

    def extract(self, request: ExtractMarkdownInput) -> ExtractionResult:
        """Return a fixed, valid source for ``request.source_id``."""
        body = " ".join(["fixture-evidence"] * FIXTURE_WORDS)
        source = Source(
            source_id=request.source_id,
            url=request.page.final_url,
            title=f"Fixture source {request.source_id}",
            author=None,
            published=None,
            body_markdown=f"# Fixture source {request.source_id}\n\n{body}\n",
            word_count=FIXTURE_WORDS,
            fetched_at=request.fetched_at,
        )
        return ExtractionResult(
            outcome="extracted",
            source=source,
            attempts=[
                ParserAttempt(parser="fixture", outcome="extracted", word_count=FIXTURE_WORDS)
            ],
        )


class _FixtureExtractor:
    """A no-op extractor so the base service has at least one parser."""

    name = "fixture"

    def extract(self, page: FetchedPage) -> None:
        """Decline every page; the fixture service never reaches this parser."""
        del page


class FixtureFetcher:
    """A synchronous fetcher returning a fixed HTML page for every URL."""

    def fetch(self, url: HttpUrl) -> FetchResult:
        """Return a successful fetch of a fixed page without any network call."""
        html = "<html><head><title>Fixture</title></head><body><p>fixture</p></body></html>"
        page = FetchedPage(html=html, status=200, final_url=url)
        return FetchResult(
            url=url,
            final_url=url,
            outcome="fetched",
            page=page,
            attempts=1,
            status=200,
            fetched_at=utc_now(),
        )


def fixture_model() -> ScriptedChatModel:
    """A scripted model for the fixture profile; prompts are ignored."""
    return ScriptedChatModel(script=[])


def fixture_search_provider(topic: str, *, pages: int, per_page: int) -> FakeSearchProvider:
    """Build an offline provider whose pages are derived from ``topic``."""
    return FakeSearchProvider(fixture_search_pages(topic, pages=pages, per_page=per_page))


def fixture_variants() -> QueryVariants:
    """Two deterministic variants that differ from any topic, for the fixture profile."""
    return QueryVariants(
        variants=["fixture framework architecture comparison", "fixture production evaluation"]
    )


def fixture_authoring(root: Path) -> None:
    """Write a valid summary and a cited draft without invoking a model.

    Deterministic and offline, matching the structure and citation rules the real
    authoring phase enforces, so the fixture profile exercises the same gates.
    """
    base = Path(root)
    records = read_corpus(base)
    if not records:
        raise RuntimeError("Fixture authoring needs at least one collected source")
    cited = records[0].source.source_id
    sections = "\n\n".join(
        [
            "## Recurring themes",
            f"### Theme: Frameworks\n\nThe corpus compares frameworks [{cited}].",
            "## Named frameworks",
            f"Named frameworks appear across sources [{cited}].",
            "## Points of agreement",
            f"Sources agree on production discipline [{cited}].",
            "## Points of disagreement",
            f"Sources differ on scope [{cited}].",
            "## Gaps",
            "Cost modelling is thin.",
            "## Suggested outline",
            "Introduction, landscape, analysis, outlook.",
        ]
    )
    summary_path = base / "research" / "summary.md"
    summary_path.write_text(sections + "\n", encoding="utf-8")

    body = " ".join(["fixture-evidence"] * 400)
    blocks = []
    for index, title in enumerate(REQUIRED_HEADINGS[:-1]):
        record = records[index % len(records)]
        blocks.append(f"## {title}\n\n{body} [{record.source.source_id}].")
    references = "\n".join(
        f"- [{record.source.source_id}] {record.source.title} {record.source.url}"
        for record in records
    )
    blog = (
        f"# {records[0].source.title}\n\n"
        + "\n\n".join(blocks)
        + f"\n\n## References\n\n{references}\n"
    )
    blog_path = base / "output" / "blog.md"
    blog_path.parent.mkdir(parents=True, exist_ok=True)
    blog_path.write_text(blog, encoding="utf-8")
