# ADR 0005: SerpApi Google search behind a provider interface

- Status: Accepted
- Date: 2026-10-01
- Applies to: PD-009; US-4.1–US-4.4

## Context

The original spec recommended Serper.dev. During EPIC-4 the user supplied a SerpApi account screenshot and configured `SERPAPI_API_KEY` after the original Serper check returned HTTP 403. These are separate services: their keys and request formats are not interchangeable.

## Decision

Default `SEARCH_PROVIDER` to `serpapi`. Read the selected key through `RunSettings` as `SecretStr`. `SearchProvider` defines preflight and typed search; the factory also supports explicit `SEARCH_PROVIDER=serper` with `SERPER_API_KEY`. Agent code and tool contracts are independent of that selection. Fake provider injection is explicit in offline tests and demonstrations.

SerpApi uses `GET https://serpapi.com/search.json`, `engine=google`, `q`, `start=(page-1)*10`, `hl=en`, `gl=us`, and `api_key`. The [current Google API documentation](https://serpapi.com/search-api) documents offset pagination and has no supported `num` parameter. Require `per_page=10` for this provider; reject other page sizes before creating the workspace. This restriction is specific to SerpApi Google search, rather than silently sending an unsupported parameter. Serper uses `POST https://google.serper.dev/search`, `X-API-KEY`, and JSON `q`, `page`, and `num` through the alternate adapter ([Serper](https://serper.dev/)).

Map only structured organic results into `SearchResult`. Convert page-relative organic positions into query-relative ranks. Ignore ads, knowledge graphs, HTML links, and provider request metadata. The application never fetches or parses Google result pages.

The orchestrator validates query variants and allows one model repair if validation fails, before any search/workspace. Use a 15-second configurable HTTP timeout, disable redirects, and issue no automatic search retries. Missing keys fail before any search/workspace. HTTP, timeout, invalid JSON, and invalid provider fields produce domain errors without request URLs, provider bodies, or credentials. A per-run session enforces the exact topic/variant query/page budget; successful calls replay from memory and failed attempts cannot spend again. Disk-write recovery reuses cached results. Durable process restart/resume belongs to EPIC-8.

Persist the plan, raw results in PD-010 breadth-first order, and canonical, deduplicated, host-filtered, capped clean results. Page tools return stateless outputs, allowing multiple search calls in a single model turn without conflicting LangGraph state writes. Normalization verifies all planned pages, saves both raw/clean artifacts, and records completed search and normalization in one state update. Clean ranks are contiguous and initialize pending URL outcomes in typed run state. Bind session closures in a separate registry per run; never store credentials or provider clients in agent/checkpoint state.

## Consequences and validation

SerpApi is usable with the user's account, and Serper remains selectable without agent edits. Default runs make five or six API requests: three topic pages plus two or three variant page-1 searches. All calls retain typed URL/title/snippet/query/rank provenance. Empty organic pages are valid; provider errors do not become empty successes.

Offline tests use socket guards and HTTPX mock transport for both adapters, plus the real DeepAgents orchestrator/search-agent path. The live smoke and the `live` pytest marker each check one real page-2 request independently of the offline gates. Actual executed results, the production planner CLI, and PM evidence are recorded in [EPIC-4-RUNBOOK.md](../../EPIC-4-RUNBOOK.md).
