"""Validate a corpus workspace and print concise acceptance evidence."""

import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from schemas.state import RunState
from services.corpus import INDEX_COLUMNS, parse_source, read_corpus
from workflows.fetch_run import load_search_workspace

workspace = Path(sys.argv[1])
pending = load_search_workspace(workspace)
state = RunState.model_validate_json((workspace / "corpus_state.json").read_text())
assert state.clean_results == pending.clean_results
assert state.completed_phases[-1] == "index"
assert all(outcome.outcome != "pending" for outcome in state.url_outcomes.values())
records = read_corpus(workspace)
extracted = {
    outcome.source_id for outcome in state.url_outcomes.values() if outcome.outcome == "extracted"
}
assert {record.source.source_id for record in records} == extracted
for record in records:
    parsed = parse_source(workspace / record.path, (workspace / record.path).read_text())
    assert parsed == record
    assert record.source.word_count >= 200
    assert record.source.source_id == f"S-{record.rank:02d}"
index = (workspace / "research/index.md").read_text(encoding="utf-8")
header = "| " + " | ".join(INDEX_COLUMNS) + " |"
assert header in index
for record in records:
    host = urlsplit(str(record.source.url)).hostname or ""
    assert f"| {record.source.source_id} |" in index
    assert host in index
print(f"Workspace: {workspace}")
print(f"Sources: {len(records)} written, {len(state.url_outcomes)} clean URLs")
print(f"Outcomes: {dict(Counter(item.outcome for item in state.url_outcomes.values()))}")
print("Verified: front-matter round-trips, source ids match ranks, index has one row per file.")
print("Verified: failed ranks leave gaps; every clean URL has a terminal outcome.")
