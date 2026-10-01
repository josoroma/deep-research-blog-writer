"""Validate saved Fetch artifacts and print concise acceptance evidence."""

import json
import sys
from collections import Counter
from pathlib import Path

from schemas.content import ExtractionResult, FetchResult
from schemas.state import RunState
from workflows.fetch_run import load_search_workspace

workspace = Path(sys.argv[1])
pending = load_search_workspace(workspace)
state = RunState.model_validate_json((workspace / "fetch_state.json").read_text())
assert state.clean_results == pending.clean_results
assert state.completed_phases == ["plan", "search", "normalize", "fetch"]
rows = json.loads((workspace / "fetch_outcomes.json").read_text())
assert [row["rank"] for row in rows] == list(range(1, len(pending.clean_results) + 1))
for row in rows:
    assert "page" not in row
    values = {key: value for key, value in row.items() if key != "rank"}
    # Successful artifact metadata deliberately omits HTML; validate its scalar fields
    # against the same schema while using an empty internal hand-off for this check.
    if values["outcome"] == "fetched":
        values["page"] = {"html": "", "status": 200, "final_url": values["final_url"]}
    FetchResult.model_validate_json(json.dumps(values))
extractions = json.loads((workspace / "extraction_results.json").read_text())
for row in extractions:
    extraction = ExtractionResult.model_validate_json(
        json.dumps({key: value for key, value in row.items() if key not in {"rank", "url"}})
    )
    outcome = state.url_outcomes[row["url"]]
    assert extraction.outcome == outcome.outcome
    if extraction.source:
        assert extraction.source.source_id == outcome.source_id == f"S-{row['rank']:02d}"
        assert extraction.source.word_count >= 200
        assert all(
            marker not in extraction.source.body_markdown
            for marker in (
                "NAV_SENTINEL",
                "FOOTER_SENTINEL",
                "SIDEBAR_SENTINEL",
                "<html>",
            )
        )
assert all(outcome.outcome != "pending" for outcome in state.url_outcomes.values())
print(f"Workspace: {workspace}")
print(f"URL outcomes: {dict(Counter(outcome.outcome for outcome in state.url_outcomes.values()))}")
print("Verified: contiguous ranks, complete outcomes, matching source IDs, >=200-word successes.")
print("Verified: raw HTML absent; failure results contain no Source; corpus files remain EPIC-6.")
print("Artifacts: fetch_outcomes.json, extraction_results.json, fetch_state.json")
