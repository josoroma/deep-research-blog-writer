"""Offline fixtures for the US-10.2 full-workflow test.

A fake search provider returns 30 URLs, a mock transport serves one fixture page per
URL, and a scripted model writes the summary and the cited draft. Nothing here opens
a socket or reads a credential.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import httpx
from langchain_core.messages import AIMessage
from pydantic import HttpUrl

from evaluations.fetch_fixtures import fixture_html
from schemas.responses import SearchResult
from services.authoring import REQUIRED_HEADINGS
from services.corpus import read_corpus

TOPIC = "2026 agentic AI frameworks"
VARIANTS = ["agent framework architecture comparison", "production agent framework evaluation"]
URL_COUNT = 30
# One URL is unreachable and one page is too thin, so 28 of 30 extract.
UNREACHABLE_PATH = "/missing"
THIN_PATH = "/thin"
EXTRACTED_COUNT = URL_COUNT - 2


def fixture_urls(count: int = URL_COUNT) -> list[str]:
    """Distinct fixture URLs, one per clean rank.

    Rank 1 is the unreachable page and rank 2 is the thin page, so a full run
    extracts `EXTRACTED_COUNT` of `count` URLs.
    """
    urls = [f"https://fixture.test/article-{rank}" for rank in range(1, count + 1)]
    if count >= 2:
        urls[0] = f"https://fixture.test{UNREACHABLE_PATH}"
        urls[1] = f"https://fixture.test{THIN_PATH}"
    return urls


def clean_results(count: int = URL_COUNT) -> list[SearchResult]:
    return [
        SearchResult(
            url=HttpUrl(url),
            title=f"Fixture article {rank}",
            snippet="Offline workflow fixture",
            rank=rank,
            query=TOPIC,
        )
        for rank, url in enumerate(fixture_urls(count), 1)
    ]


class WorkflowHTTP:
    """Serve one fixture page per URL; two paths fail on purpose."""

    def __init__(self, *, unreachable: bool = True, thin: bool = True) -> None:
        self.unreachable = unreachable
        self.thin = thin
        self.requests: list[str] = []

    async def respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if self.unreachable and request.url.path == UNREACHABLE_PATH:
            return httpx.Response(404)
        if self.thin and request.url.path == THIN_PATH:
            return httpx.Response(
                200, headers={"content-type": "text/html"}, text=fixture_html("thin")
            )
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text=fixture_html("article")
        )

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.respond), trust_env=False)


def _body(words: int) -> str:
    return " ".join(["evidence"] * words)


def render_summary(workspace: Path) -> str:
    """A summary that satisfies `check_summary` and cites real sources."""
    records = read_corpus(workspace)
    cited = records[0].source.source_id if records else "S-01"
    return "\n\n".join(
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


def render_blog(workspace: Path) -> str:
    """A 2000–5000 word draft with the required headings and resolvable citations."""
    records = read_corpus(workspace)
    if not records:
        raise ValueError("The workflow fixture needs at least one source to cite")
    sections = []
    for index, title in enumerate(REQUIRED_HEADINGS[:-1]):
        record = records[index % len(records)]
        sections.append(f"## {title}\n\n{_body(320)} [{record.source.source_id}].")
    references = "\n".join(
        f"- [{record.source.source_id}] {record.source.title} {record.source.url}"
        for record in records
    )
    return f"# {TOPIC}\n\n" + "\n\n".join(sections) + f"\n\n## References\n\n{references}\n"


def authoring_script(workspace: Path) -> list[AIMessage]:
    """Two write_file calls: the summary, then the cited draft."""
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {
                        "file_path": "/research/summary.md",
                        "content": render_summary(workspace),
                    },
                    "id": "write-summary",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="summary written"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"file_path": "/output/blog.md", "content": render_blog(workspace)},
                    "id": "write-blog",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="blog written"),
    ]


def planner_script() -> list[AIMessage]:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "QueryVariants",
                    "args": {"variants": VARIANTS},
                    "id": "planner",
                    "type": "tool_call",
                }
            ],
        )
    ]


def search_pages() -> Mapping[tuple[str, int], list[SearchResult]]:
    """Three pages of ten topic results; the planner variants return nothing extra.

    Ranks follow the provider contract: page N carries ranks (N-1)*10+1 .. N*10.
    """
    pages: dict[tuple[str, int], list[SearchResult]] = {}
    for page in range(1, 4):
        lower = (page - 1) * 10
        pages[(TOPIC, page)] = [
            SearchResult(
                url=HttpUrl(url),
                title=f"Fixture article {rank}",
                snippet="Offline workflow fixture",
                rank=rank,
                query=TOPIC,
            )
            for rank, url in enumerate(fixture_urls()[lower : lower + 10], lower + 1)
        ]
    return pages
