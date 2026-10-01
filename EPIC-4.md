# EPIC-4: Search

Date: 2026-10-01

Status: Implemented. Functional tests, live integration, CLI, and installed-wheel checks pass; final fresh-checkout and evidence commits are being recorded in `EPIC-4-RUNBOOK.md`.

## Objective and scope

Implement US-4.1–US-4.4 from [SPECS.md](SPECS.md#epic-4-search), building on the committed EPIC-3 skeleton. Produce real, typed Google search results through an approved API, two or three orchestrator-derived query variants, persisted raw results, and a ranked, deduplicated, filtered list capped at the requested maximum.

The user supplied a SerpApi account screenshot and then added `SERPAPI_API_KEY` locally after the initial Serper request returned HTTP 403. SerpApi is the selected default; update PD-009 and US-4.2 to match this decision. Preserve Serper as an explicitly selectable alternate behind the same interface. The two services use separate credentials. A screenshot or configured key alone is not live acceptance evidence.

Fetching, extraction, corpus construction, article generation, citation validation, durable SQLite resume, and run-report classification remain in their owning later epics.

## Implementation sequence

1. **Provider interface and contracts (US-4.1).** Define a `SearchProvider` protocol and deterministic fake provider. Validate query, positive page/per-page values, and returned `SearchResult` contracts. Introduce HTTPX as a direct locked dependency. Providers issue bounded API requests and return organic results only; no Google result-page requests or HTML parsing. Convert page-relative positions into query-relative ranks, so default page 2 returns ranks 11–20. Malformed responses and HTTP/network errors become credential-safe domain errors.
2. **Production integration (US-4.2).** Implement Serper (`POST https://google.serper.dev/search`, `X-API-KEY`, JSON query/page/num) and SerpApi (`GET https://serpapi.com/search.json`, engine/query/start/key). Select through `SEARCH_PROVIDER`; store separate `SERPER_API_KEY` and `SERPAPI_API_KEY` secrets. Fail before searching or creating a run workspace when the selected key is missing. Record ADR 0005 and a separate opt-in live page-2 smoke test. SerpApi's documented Google interface uses offset pagination rather than a configurable `num` parameter; enforce its supported page size clearly instead of silently accepting an unsupported budget.
3. **Planning and request budget (US-4.3).** Add a typed `plan_search` tool so the orchestrator records two or three distinct variants. Persist `search_plan.json`. Use the required schedule: topic page 1, each variant page 1 in derivation order, then remaining topic pages. Bound requests to the planned query/page pairs. Cache repeated calls within the run to prevent duplicate provider spend, reject unplanned calls, and persist collected results in planned order even if tool execution arrives out of order.
4. **Per-run tool integration (US-4.1/US-4.3).** Replace the search and normalization stubs with typed implementations bound to a per-run search session and workspace. Create per-run registries without mutating shared globals. Pass them to the existing four-agent assembly so provider changes require no agent edits. Initialize `RunState` for real calls; state-changing tools read `runtime.state` and return validated replacements. Mark planning complete after saving the plan. Page tools return stateless results so batched model tool calls do not compete on LangGraph’s run-state channel. Normalization confirms every page/artifact and records search and normalization completion in one validated update. Preserve metadata-only model inputs and the agent HTTP/provider/prompt architecture gates.
5. **Normalization (US-4.4).** Strip `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_cid`, and `mc_eid` query parameters, fragments, and trailing slashes; retain meaningful query parameters. Match all PD-011 denied hosts and their subdomains without rejecting look-alike domains. Keep the first occurrence in breadth-first order, apply `max_urls`, and assign contiguous clean ranks starting at 1. Persist `clean_results.json`; initialize a pending typed outcome for every clean URL. Reject normalization before all planned pages are present.
6. **Runnable Search milestone.** Add `--search-only` to the existing console script. By default the orchestrator model derives validated variants, with one bounded validation-repair attempt before rejecting an invalid plan; explicit repeated `--query-variant` arguments allow reproducible provider demonstrations without a model call. Execute the registered tools and stop after normalization, reporting raw/clean counts and artifact paths. Keep the full skeleton route available and explicitly label the remaining stubs. Add `make demo-epic-4` using a fake model/provider through the real DeepAgents tool path, with saved artifacts for the PM to inspect.
7. **Verification and delivery.** Test pagination, transport payloads, provider swapping, missing keys, credential-safe failures, request budgets/replay, planner validation, breadth-first ordering, every normalization rule, typed state updates, and actual search sub-agent/orchestrator integration. Retain strict typing, Ruff, offline socket guards, and ≥80% coverage. Run locked setup, quality gates, hooks, prior demos, Search demo, build, installed-wheel verification, and a committed fresh checkout. Record successful command transcripts, exit codes, coverage, source hashes, live evidence, and story acceptance in `docs/evidence/epic-4/` and `EPIC-4-RUNBOOK.md`. Commit with hooks active and update only verified EPIC-4 statuses.

## Acceptance matrix

| Story | Evidence required |
| --- | --- |
| US-4.1 | Topic pages 1–3 collect ≤30 topic results; every persisted result retains query/rank/url/title/snippet; provider injection/configuration changes results without agent edits |
| US-4.2 | Correct selected provider endpoint, pagination, authentication, organic-result mapping; missing selected key fails before search; ADR and isolated live integration test; actual live result recorded separately |
| US-4.3 | Two or three distinct variants recorded by the orchestrator; every variant page 1 searched; raw results merge in PD-010 order regardless of arrival order |
| US-4.4 | Exact canonical URL example; first duplicate retained; all denied hosts/subdomains filtered; meaningful parameters retained; cap applied; contiguous ranks and ordered clean file |

## Completion checklist

- [x] Provider choice and configuration documented consistently.
- [x] US-4.1 implemented and verified.
- [x] US-4.2 implemented and verified; actual live acceptance outcome recorded.
- [x] US-4.3 implemented and verified.
- [x] US-4.4 implemented and verified.
- [ ] CLI/Search demo, strict checks/hooks, wheel, and fresh-checkout verification pass.
- [ ] Runbook, raw command outputs, coverage, and source hashes saved.
- [ ] Implementation and final evidence committed with hooks active.

## Technical references

Provider integration is checked against the [Serper API](https://serper.dev/) and [SerpApi Google API documentation](https://serpapi.com/search-api). Framework details are checked against the installed locked DeepAgents/LangChain packages. The existing product decisions govern tool ownership, merge order, normalization, and remaining scope.
