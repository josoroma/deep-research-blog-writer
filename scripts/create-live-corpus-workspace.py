"""Seed one public URL for the live corpus CLI demo; this does not call a search API."""

from pathlib import Path

from pydantic import HttpUrl

from evaluations.fetch_live_smoke import DEFAULT_URL
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from services.artifacts import write_json
from services.workspace import create_run_workspace

request = ResearchRequest(topic="EPIC-6 live research corpus", max_urls=1)
workspace = create_run_workspace(request, Path("runs"))
result = SearchResult(
    url=HttpUrl(DEFAULT_URL),
    title="Python asyncio documentation",
    snippet="Manually seeded public URL; no search provider called",
    rank=1,
    query=request.topic,
)
write_json(workspace.root / "clean_results.json", [result.model_dump(mode="json")])
print(workspace.root)
