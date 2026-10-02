# search_agent — skill

The search sub-agent runs the paged queries the orchestrator planned and returns typed results. It is assembled in `agents/deep_research.py` and prompted by `prompts/search_agent.md`.

## Purpose

Collect paged Google results through the registered `google_search` tool, preserving query, rank, URL, title, and snippet metadata, so the orchestrator can normalize them into clean URLs.

## Capabilities

- Calls `google_search` for the topic pages and for page 1 of each planner variant.
- Respects the `pages`, `per_page`, and `max_urls` budgets.
- Returns typed `SearchResult` rows with their query and rank intact.

## Non-Capabilities

- Never scrapes a result page or constructs a provider client.
- Never normalizes, deduplicates, or caps results; that belongs to `normalize_results`.
- Never fetches a URL or writes a file.
- Never invents a result, a rank, or a URL.

## Inputs

- `GoogleSearchInput` — the `query` and the `page` to request.
- The topic and the planner variants, supplied by the orchestrator.

## Outputs

- `GoogleSearchOutput` — the `list[SearchResult]` for the requested page.

## Available Tools

| Tool | Input | Output |
| --- | --- | --- |
| `google_search` | `GoogleSearchInput` | `GoogleSearchOutput` |

This is the only registered tool the sub-agent receives (`SUBAGENT_TOOLS["search_agent"]`). It does not receive `task`, `write_todos`, or any filesystem tool.

## Security

- The provider client and its key live in `services/search_provider.py`; the agent never sees them.
- The per-run `SearchSession` rejects a query or page outside the saved plan, so the agent cannot exceed the budget.
- The static boundary check forbids HTTP imports in agent modules.

## Observability

- Each `google_search` call is a tool span in the LangSmith trace and a `tool_started` and `tool_finished` pair in `logs/execution.log`.
- The tool call count is exported as an OTLP metric.

## Evaluation Criteria

- The saved `search_results.json` holds one row per planned call, with contiguous ranks per page.
- The merge order is topic page 1, variant page 1s in derivation order, then the remaining topic pages.
- The offline search demo (`make demo-epic-4`) asserts the merge order and the cached replay.

## Failure Modes

| Failure | Behavior |
| --- | --- |
| The provider returns an HTTP error or times out | `SearchProviderError`; the run fails and the plan is preserved |
| The provider returns malformed or out-of-range results | `SearchProviderError`; the results are rejected |
| The agent requests a query or page outside the plan | `ValueError`; the call is refused |
| A planned call is retried after it already failed | `SearchProviderError`; start a new run to retry |

## Example

For the topic "2026 agentic AI frameworks" with three variants, the orchestrator plans six calls: topic page 1, the three variant page 1s, then topic pages 2 and 3. The sub-agent calls `google_search` for each and returns 10 results per page, which the orchestrator merges and normalizes.
