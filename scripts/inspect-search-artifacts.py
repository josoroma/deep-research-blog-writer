"""Validate saved Search milestone artifacts and print PM acceptance facts."""

import json
import sys
from pathlib import Path

from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.search import QueryVariants, SearchPlan
from services.search_session import normalize_results

workspace = Path(sys.argv[1])
request = ResearchRequest.model_validate_json((workspace / "request.json").read_text())
plan = SearchPlan.model_validate_json((workspace / "search_plan.json").read_text())
QueryVariants(variants=plan.variants)
raw = [
    SearchResult.model_validate(row)
    for row in json.loads((workspace / "search_results.json").read_text())
]
clean = [
    SearchResult.model_validate(row)
    for row in json.loads((workspace / "clean_results.json").read_text())
]
expected_calls = [(request.topic, 1), *((query, 1) for query in plan.variants)]
expected_calls.extend((request.topic, page) for page in range(2, request.pages + 1))
assert [(call.query, call.page) for call in plan.calls] == expected_calls
order = {key: index for index, key in enumerate(expected_calls)}
positions = []
for result in raw:
    page = (result.rank - 1) // request.per_page + 1
    positions.append((order[(result.query, page)], result.rank))
assert positions == sorted(positions)
assert len(positions) == len(set(positions))
assert sum(result.query == request.topic for result in raw) <= request.pages * request.per_page
expected = normalize_results(raw, request.max_urls)
assert clean == expected.clean_results
assert [result.rank for result in clean] == list(range(1, len(clean) + 1))
print(f"Workspace: {workspace}")
print(f"Provider: {plan.provider}; variants: {len(plan.variants)}; pages: {len(plan.calls)}")
print(f"Normalization counts: {expected.counts.model_dump()}")
print("Verified: query/rank/URL/title/snippet contracts; breadth-first merge; unique positions.")
print("Verified: canonicalization, denylist, earliest duplicate, cap, contiguous clean ranks.")
print("Artifacts: request.json, search_plan.json, search_results.json, clean_results.json")
