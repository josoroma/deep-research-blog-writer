"""PM demo: real corpus tools and parsers, mocked HTTP, explicit virtual timing.

Proves the EPIC-6 acceptance facts offline: rank-numbered immutable source files
with front-matter, title and URL slugs, an index row per file, and a run that
keeps going when individual sources fail.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import HttpUrl

from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.state import RunState
from services.artifacts import write_json
from services.corpus import parse_source, read_corpus
from services.fetch_service import FetchService
from services.source_backend import ImmutableSourceBackend
from services.workspace import create_run_workspace
from workflows.corpus_run import run_corpus

TITLES = {
    "/non-ascii": "标题",
}
PATHS = [
    "/article",
    "/redirect",
    "/missing",
    "/blocked",
    "/pdf",
    "/thin",
    "/missing-metadata",
    "/boilerplate-heavy",
    "/exhaust",
    "/non-ascii",
]


def run_demo(runs_root: Path) -> dict[str, Any]:
    settings = RunSettings(
        _env_file=None, crawler_contact="https://example.org/offline-demo-contact"
    )
    request = ResearchRequest(topic="EPIC-6 research corpus")
    workspace = create_run_workspace(request, runs_root)
    clean = [
        SearchResult(
            url=HttpUrl(f"https://fixture.test{path}"),
            title=TITLES.get(path, f"Fixture {path.strip('/')}"),
            snippet="Original offline fixture",
            rank=rank,
            query=request.topic,
        )
        for rank, path in enumerate(PATHS, 1)
    ]
    write_json(
        workspace.root / "clean_results.json", [row.model_dump(mode="json") for row in clean]
    )
    transport, clock = FixtureHTTP(delay=0.001), VirtualClock()
    with FetchService(
        settings, client=transport.client(), clock=clock, sleep=clock.sleep, jitter=lambda: 0.0
    ) as fetcher:
        summary = run_corpus(workspace.root, settings, fetcher=fetcher)
    assert summary.status == "completed", summary.error
    state = RunState.model_validate_json((workspace.root / "corpus_state.json").read_text())
    records = read_corpus(workspace.root)
    files = {record.rank: record for record in records}
    assert summary.outcomes == {
        "extracted": 5,
        "unreachable": 2,
        "robots_disallowed": 1,
        "unsupported_content": 1,
        "too_thin": 1,
    }
    assert set(files) == {1, 2, 7, 8, 10}
    assert 3 not in files and 6 not in files
    article = files[1]
    assert article.path == "research/001_polite-evidence-collection.md"
    assert article.source.source_id == "S-01"
    assert article.source.author == "Alex Researcher"
    fallback = files[10]
    assert fallback.path == "research/010_fixture-test-non-ascii.md"
    assert fallback.source.source_id == "S-10"
    index = (workspace.root / "research/index.md").read_text(encoding="utf-8")
    assert index.count("\n| S-") == len(records)
    assert "| S-01 | Polite Evidence Collection | fixture.test |" in index
    for record in records:
        text = (workspace.root / record.path).read_text(encoding="utf-8")
        parsed = parse_source(workspace.root / record.path, text)
        assert parsed.source.word_count >= 200
        assert parsed.source.body_markdown == record.source.body_markdown
    backend = ImmutableSourceBackend(root_dir=workspace.root, virtual_mode=True)
    target = f"/{article.path}"
    before = (workspace.root / article.path).read_bytes()
    write = backend.write(target, "overwrite")
    edit = backend.edit(target, article.source.title, "changed")
    delete = backend.delete(target)
    assert write.error and edit.error and delete.error
    assert (workspace.root / article.path).read_bytes() == before
    assert state.completed_phases[-1] == "index"
    assert all(outcome.outcome != "pending" for outcome in state.url_outcomes.values())
    report = {
        "mode": "offline; mock HTTP, real registered corpus tools and extraction libraries",
        "timing": "virtual monotonic seconds",
        "workspace": str(workspace.root),
        "summary": summary.model_dump(mode="json"),
        "source_files": sorted(record.path for record in records),
        "rank_gaps": sorted(set(range(1, len(clean) + 1)) - set(files)),
        "title_slug": article.path,
        "url_slug_fallback": fallback.path,
        "index_rows": len(records),
        "immutable_source_refused": True,
        "metadata_only": all("body_markdown" not in source for source in summary.files),
    }
    write_json(workspace.root / "demo_evidence.json", report)
    return report


def main() -> int:
    print(json.dumps(run_demo(Path("runs")), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
