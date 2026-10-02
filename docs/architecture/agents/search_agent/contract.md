# search_agent — contract

## Input

- `GoogleSearchInput` — the `query` and the `page` to request. The query must be the topic or one of the planner variants, and the page must be inside the saved plan.

## Output

- `GoogleSearchOutput` — the `list[SearchResult]` for the requested page, each row carrying its `url`, `title`, `snippet`, `rank`, and `query`.

## Success criteria

| Criterion | Source |
| --- | --- |
| Run paged queries and collect candidate URLs | PRD.md §9 |
| Preserve query, rank, URL, title, and snippet metadata | SPECS.md US-4.1 |
| Respect the `pages`, `per_page`, and `max_urls` budgets | PRD.md NFR-4 |
| Merge results breadth-first: topic page 1, variant page 1s, then remaining topic pages | SPECS.md US-4.2 |
| Use the approved search API and never scrape result pages | PRD.md Non-Goals, SPECS.md PD-007 |

## Failure conditions

- The provider returns an HTTP error, times out, or returns invalid JSON: `SearchProviderError`, and the run fails with the plan preserved.
- The provider returns more results than `per_page`, duplicate ranks, or ranks outside the page window: `SearchProviderError`.
- The agent requests a query or page outside the saved plan: `ValueError`.
- A planned call is retried after it already failed: `SearchProviderError`; a new run is required.
