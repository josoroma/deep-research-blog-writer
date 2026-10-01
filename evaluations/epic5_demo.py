"""PM demo: actual internal tools/parsers, mocked HTTP, explicit virtual timing."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pydantic import HttpUrl

from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock, fixture_html
from schemas.config import RunSettings
from schemas.content import ParsedArticle
from schemas.requests import ResearchRequest
from schemas.responses import FetchedPage, SearchResult
from schemas.tool_io import ExtractMarkdownInput
from services.artifacts import write_json
from services.extraction_service import BeautifulSoupExtractor, ExtractionService
from services.fetch_service import FetchService
from services.workspace import create_run_workspace
from tools.registry import create_tool_registry
from workflows.fetch_run import run_fetch

PATHS = [
    "/redirect",
    "/retry",
    "/missing",
    "/blocked",
    "/pdf",
    "/thin",
    "/missing-metadata",
    "/boilerplate-heavy",
    "/exhaust",
]


class ForcedCandidate:
    """Explicit branch probe: force the first two candidates to be empty/thin."""

    def __init__(self, name: str, thin: bool) -> None:
        self.name, self.thin = name, thin

    def extract(self, page: FetchedPage) -> ParsedArticle | None:
        return ParsedArticle(title="Thin probe", body_markdown="short probe") if self.thin else None


def run_demo(runs_root: Path) -> dict[str, Any]:
    settings = RunSettings(
        _env_file=None, crawler_contact="https://example.org/offline-demo-contact"
    )
    request = ResearchRequest(topic="EPIC-5 polite evidence collection")
    workspace = create_run_workspace(request, runs_root)
    urls = [f"https://fixture.test{path}" for path in PATHS] + [
        "https://slow.fixture.test/first",
        "https://slow.fixture.test/second",
    ]
    clean = [
        SearchResult(
            url=HttpUrl(url),
            title=f"Fixture {rank}",
            snippet="Original offline fixture",
            rank=rank,
            query=request.topic,
        )
        for rank, url in enumerate(urls, 1)
    ]
    write_json(
        workspace.root / "clean_results.json", [row.model_dump(mode="json") for row in clean]
    )
    transport, clock = FixtureHTTP(delay=0.001), VirtualClock()
    with FetchService(
        settings, client=transport.client(), clock=clock, sleep=clock.sleep, jitter=lambda: 0.0
    ) as fetcher:
        summary = run_fetch(workspace.root, settings, fetcher=fetcher)
        assert summary.status == "completed"
        assert summary.outcomes == {
            "extracted": 6,
            "unreachable": 2,
            "robots_disallowed": 1,
            "unsupported_content": 1,
            "too_thin": 1,
        }
        timeline = [event.model_dump(mode="json") for event in fetcher.events]
        slow_starts = [
            event.started for event in fetcher.events if event.host == "slow.fixture.test"
        ]
        assert all(
            right - left >= 5 for left, right in zip(slow_starts, slow_starts[1:], strict=False)
        )
        assert transport.counts["https://fixture.test/robots.txt"] == 1
        assert all(req.headers["user-agent"] == fetcher.user_agent for req in transport.requests)
        user_agent = fetcher.user_agent
        retries = [event.model_dump(mode="json") for event in fetcher.retries]
    probe_transport, probe_clock = FixtureHTTP(delay=0.005), VirtualClock()
    with FetchService(
        settings, client=probe_transport.client(), clock=probe_clock, sleep=probe_clock.sleep
    ) as service:
        registry = create_tool_registry(fetcher=service)
        with ThreadPoolExecutor(max_workers=30) as pool:
            probe = list(
                pool.map(
                    lambda index: registry["fetch_url"].invoke(
                        {"url": f"https://h{index}.fixture.test/a"}
                    ),
                    range(30),
                )
            )
        assert len(probe) == 30 and service.max_active == 5
        max_active = service.max_active
    forced = ExtractionService(
        [
            ForcedCandidate("trafilatura:forced-empty", False),
            ForcedCandidate("readability-lxml:forced-thin", True),
            BeautifulSoupExtractor(),
        ]
    ).extract(
        ExtractMarkdownInput(
            page=FetchedPage(
                html=fixture_html(), status=200, final_url=HttpUrl("https://fixture.test/a")
            ),
            source_id="S-99",
        )
    )
    assert forced.outcome == "extracted" and len(forced.attempts) == 3
    state = json.loads((workspace.root / "fetch_state.json").read_text())
    extractions = json.loads((workspace.root / "extraction_results.json").read_text())
    assert len(state["url_outcomes"]) == len(clean)
    assert not (workspace.root / "research").exists()
    for extraction in extractions:
        source = extraction["source"]
        if source:
            assert all(
                marker not in source["body_markdown"]
                for marker in (
                    "NAV_SENTINEL",
                    "FOOTER_SENTINEL",
                    "SIDEBAR_SENTINEL",
                    "<html>",
                )
            )
    report = {
        "mode": "offline; mock HTTP, real registered tools and extraction libraries",
        "timing": "virtual monotonic seconds; HTTP concurrency overlaps in real asyncio tasks",
        "workspace": str(workspace.root),
        "summary": summary.model_dump(mode="json"),
        "completed_phases": state["completed_phases"],
        "user_agent": user_agent,
        "robots_requests_per_origin": {
            url: count for url, count in transport.counts.items() if url.endswith("/robots.txt")
        },
        "page_requests": {
            url: count for url, count in transport.counts.items() if not url.endswith("/robots.txt")
        },
        "retry_delays": retries,
        "requests": timeline,
        "slow_host_start_times": slow_starts,
        "thirty_host_probe": {"urls": 30, "max_active": max_active, "limit": 5},
        "fallback_probe": {
            "first_two_parsers": "forced candidates; third is real beautifulsoup4",
            "attempts": [attempt.model_dump() for attempt in forced.attempts],
        },
        "raw_html_absent_from_artifacts": all(
            "<html>" not in (workspace.root / name).read_text() for name in summary.files
        ),
        "no_corpus_files_written": True,
    }
    write_json(workspace.root / "demo_evidence.json", report)
    return report


def main() -> int:
    print(json.dumps(run_demo(Path("runs")), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
