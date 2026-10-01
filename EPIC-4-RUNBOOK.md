# EPIC-4 Search runbook

Date: 2026-10-01. Status: DONE. Implementation revision `f350effee023b49c0bd12e896880259165b65f68` passed committed fresh-checkout verification. Final documentation and evidence are committed separately.

## Delivered behavior

US-4.1–US-4.4 implement API search, 2–3 orchestrator-derived query variants, deterministic breadth-first merge, raw-result persistence, URL canonicalization, ranked deduplication, all 12 denied hosts plus subdomains, and a capped clean list with contiguous ranks and pending typed URL outcomes. SerpApi is the selected default for the account/key supplied by the user; Serper remains explicitly configurable. [ADR 0005](docs/adr/0005-search-provider.md) records the decision and API formats.

Search tools use per-run provider/session bindings. Repeated successful page calls reuse cached results; unplanned calls and repeat attempts after provider failure are rejected. Plan/raw/clean files are written atomically. Batched model tool calls are tested through the actual DeepAgents orchestrator/search-agent graph; normalization records completed search/normalization in one validated state update.

Fetching, extraction, corpus/article generation, citation validation, reporting status rules, and durable resume remain in later epics. Use `--search-only` for this milestone; the full pipeline command still invokes the downstream skeleton.

## Install and configure

Run from the repository root. Prerequisites are Git, Make, and [uv](https://docs.astral.sh/uv/getting-started/installation/). `make setup` uses Python 3.12 and installs the locked dependencies plus Git hooks; uv handles virtual environment selection.

```sh
make setup
make check
make demo-epic-4
```

The offline demo requires no keys or server. For live search, keep the existing `.env` or create it only when missing with `cp -n .env.example .env`. Set values locally:

```dotenv
SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=<your SerpApi key>
OPENROUTER_API_KEY=<your OpenRouter key>
```

SerpApi Google search requires `per_page=10`. Serper instead uses `SEARCH_PROVIDER=serper` and `SERPER_API_KEY`. The providers do not share keys. Environment overrides `.env`; neither `.env` nor `runs/` is committed.

```sh
make smoke-epic-4
SEARCH_TIMEOUT_SECONDS=60 uv run --locked deep-research-blog "2026 agentic AI frameworks" --search-only
```

The smoke issues one page-2 search and no model request. The search-only command derives variants with the configured orchestrator model, permits one validation-repair attempt, then makes five or six planned API calls. The default HTTP timeout is 15 seconds; the successful full live run used the explicit 60-second bound above. An upstream timeout exits 1 and preserves completed artifacts. Start a new run to retry; process resume is a later story.

For provider-only demonstrations, add two or three repeated `--query-variant "..."` arguments. This skips the model request. Budgets are configurable through `--pages`, `--per-page`, and `--max-urls`. The command prints status/counts/artifact paths; exits are 0 completed, 1 execution failure, 2 invalid input/configuration.

## Successful commands and actual outputs

Full transcripts include commands and exit codes; [commands.jsonl](docs/evidence/epic-4/commands.jsonl) records UTC times and durations. Selected successful verification commands:

| Command | Actual result | Transcript |
| --- | --- | --- |
| `uv add 'httpx>=0.28,<1'` | HTTPX made a direct locked dependency; exit 0 | [01](docs/evidence/epic-4/01-http-dependency.txt) |
| `make setup` | 80 installed packages checked; Git hook installed; exit 0 | [06](docs/evidence/epic-4/06-setup.txt) |
| `make check` | Lock, Ruff, formatting, strict mypy pass; 294 tests pass, 2 live tests deselected; 97.73% coverage; exit 0 | [13](docs/evidence/epic-4/13-check.txt) |
| `make hooks` | Ruff, formatting, strict typing and offline coverage hooks all pass; exit 0 | [21](docs/evidence/epic-4/21-hooks.txt) |
| `make demo-epic-4` | Actual batched search-agent tools; 50 raw → 30 clean; replay/cache/budget/ranking assertions pass; exit 0 | [11](docs/evidence/epic-4/11-batch-demo.txt) |
| `make smoke-epic-4` | SerpApi page 2 returns 10 results ranked 11–20; exit 0 | [03](docs/evidence/epic-4/03-live-serpapi.txt) |
| `uv run --locked pytest -m live tests/test_search_workflow.py --no-cov` | 1 live integration test passes; exit 0 | [09](docs/evidence/epic-4/09-live-pytest.txt) |
| `SEARCH_TIMEOUT_SECONDS=60 uv run --locked deep-research-blog "2026 agentic AI frameworks" --search-only` | Production orchestrator derives 3 variants; 51 raw → 30 clean; exit 0 | [05](docs/evidence/epic-4/05-live-search-cli.txt) |
| Provider-only command shown below | Final implementation live run: 50 raw → 30 clean; exit 0 | [19](docs/evidence/epic-4/19-live-repeatable-cli.txt) |
| `make demo-epic-2 demo-epic-3` | Prior contracts/state and four-agent skeleton demonstrations pass; exit 0 | [15](docs/evidence/epic-4/15-prior-demos.txt) |
| `make build` | Wheel and source distribution built; exit 0 | [16](docs/evidence/epic-4/16-build.txt) |
| `sh scripts/verify-epic-4-checkout.sh` | Committed revision installs from scratch without `.env`; all gates, prior/Search demos, build and installed-wheel checks pass; exit 0 | [23](docs/evidence/epic-4/23-fresh-checkout.txt) |
| `sh scripts/verify-epic-4-package.sh` | Installed wheel outside checkout runs Search, packaged prompts, tool state and saved artifacts; installed CLI rejects invalid input with exit 2; verifier exits 0 | [18](docs/evidence/epic-4/18-wheel.txt) |
| `uv run --locked python scripts/inspect-search-artifacts.py runs/2026-agentic-ai-frameworks-20261001T141115Z` | Persisted offline contracts, order, normalization, cap, and ranks verified; exit 0 | [17](docs/evidence/epic-4/17-inspect-offline.txt) |

Observed production planner run:

```text
run_id: 2026-agentic-ai-frameworks-20261001T140224Z
status: completed
provider: serpapi
counts: raw=51, denied=11, duplicates=0, capped=10, kept=30
error: null
```

The production planner run above was executed during implementation. Final source quality, graph batching, and installed-wheel checks are recorded separately. Live Google results and model phrasings can change; fixed fixtures provide repeatable acceptance numbers.

The following provider-only command also completed on the final implementation (no model call):

```sh
SEARCH_TIMEOUT_SECONDS=60 uv run --locked deep-research-blog "2026 agentic AI frameworks" --search-only \
  --query-variant "agentic AI framework comparison" \
  --query-variant "best agentic AI frameworks 2026" \
  --query-variant "agentic AI framework benchmarks"
```

```text
run_id: 2026-agentic-ai-frameworks-20261001T141738Z
status: completed
counts: raw=50, denied=10, duplicates=0, capped=10, kept=30
error: null
```

Inspect the [saved final live artifacts](docs/evidence/epic-4/live-repeatable/search_plan.json). The earlier production planner live artifacts were also validated by [the inspector](docs/evidence/epic-4/20-inspect-live.txt).

## PM demonstration

1. Run `make demo-epic-4` and open the printed workspace. The real DeepAgents orchestrator records two variants, delegates a batch of five search calls, and normalizes the results. The model/provider are explicitly offline fixtures.
2. Show the four artifacts: `request.json` contains 3/10/30 budgets, `search_plan.json` contains query/page provenance, `search_results.json` retains every query/rank/URL/title/snippet, and `clean_results.json` contains the selected article URLs.
3. Point to `batched_search_tool_calls: true`, `topic_results: 30`, and counts `raw=50, denied=3, duplicates=1, capped=16, kept=30`. Show the first clean URL `https://example.com/post?id=7` and title `Fixture 0-1`; this proves tracking removal and retention of the earlier duplicate. Clean ranks are 1–30.
4. Show `completed_phases: [plan, search, normalize]`, 30 pending outcomes, cached replay, and rejection of an unplanned query. The fixtures arrive out of planned order; the persisted merge still follows topic page 1, variant page 1s, topic pages 2–3.
5. Validate the files with `uv run --locked python scripts/inspect-search-artifacts.py runs/<printed-run_id>`. Inspect the saved [offline snapshot](docs/evidence/epic-4/offline/search_plan.json) to demonstrate without generating a new workspace.
6. Show the successful [live page-2 transcript](docs/evidence/epic-4/03-live-serpapi.txt), [live pytest](docs/evidence/epic-4/09-live-pytest.txt), and [production planner/API run](docs/evidence/epic-4/05-live-search-cli.txt). The saved [live plan](docs/evidence/epic-4/live-planner/search_plan.json), [raw results](docs/evidence/epic-4/live-planner/search_results.json), and [clean results](docs/evidence/epic-4/live-planner/clean_results.json) are available after local run cleanup.
7. Present [quality-gate output](docs/evidence/epic-4/13-check.txt), [coverage XML](docs/evidence/epic-4/coverage.xml), and [installed-wheel](docs/evidence/epic-4/18-wheel.txt)/[fresh-checkout](docs/evidence/epic-4/23-fresh-checkout.txt) evidence. These are the engineering acceptance checks. [source-manifest.json](docs/evidence/epic-4/source-manifest.json) records SHA-256 hashes for 81 source/configuration/test files and both build artifacts, linked to the verified implementation revision. [The hash verification](docs/evidence/epic-4/26-source-hashes.txt) confirms they still match.

## Evidence of done by story

| Story | Proof |
| --- | --- |
| US-4.1 | Protocol/fake and both configured adapters; typed registered `google_search`; actual graph batch searches all three topic pages; saved raw metadata; transport/provider-swap tests |
| US-4.2 | Selected SerpApi endpoint/key/start payload; ranks 11–20 in real page-2 smoke and isolated live test; missing-key preflight before workspace; credential-safe errors; ADR 0005 |
| US-4.3 | Central orchestrator structured planner, validated 2–3 alternatives and one repair; actual agent plan/delegation; three variants in live plan; variant queries retained; merge order verified under reversed/batched arrivals |
| US-4.4 | Exact canonical example, earliest duplicate, every denied host/subdomain and look-alike boundary, meaningful/blank/repeated parameters, cap, clean ranks/file order, pending URL outcomes |

Tests also verify no repeated spend after failure, atomic-write recovery, symlink destination containment, malformed provider contracts, bounded timeout, no redirects/retries, explicit failures on bad responses, and the existing agent architecture rules.

## Observed failures and reproducibility

The ledger retains development failures rather than presenting them as successful commands. The initial Serper key returned HTTP 403 ([02](docs/evidence/epic-4/02-live-search.txt)); the user then configured SerpApi and its live check passed. An uncached API request exceeded 15 seconds ([04](docs/evidence/epic-4/04-live-search-cli.txt)); a new run with a 60-second bound completed ([05](docs/evidence/epic-4/05-live-search-cli.txt)). Another request later exceeded 60 seconds ([14](docs/evidence/epic-4/14-live-search-cli.txt)); the command correctly reported failure without claiming clean output. Live availability is an external dependency.

A model plan repeated the topic ([12](docs/evidence/epic-4/12-final-live-cli.txt)); the planner rejected it before search. The prompt/schema now explicitly require alternative phrasings, with one bounded validation-repair attempt tested. A deliberately malformed test fixture needed a typing correction ([10](docs/evidence/epic-4/10-final-check.txt)); the final strict check passes in [13](docs/evidence/epic-4/13-check.txt).

Hosted GitHub Actions was configured earlier; this run records local checks and a local fresh checkout, not a hosted CI execution. No production article or release evaluation is claimed.

## Inspect committed evidence without credentials

```sh
uv run --locked python scripts/inspect-search-artifacts.py docs/evidence/epic-4/offline
uv run --locked python scripts/inspect-search-artifacts.py docs/evidence/epic-4/live-repeatable
```

These commands validate the saved snapshots using the current contracts and normalizer. They make no model/provider requests. See [offline snapshot inspection](docs/evidence/epic-4/24-offline-snapshot.txt) and [live snapshot inspection](docs/evidence/epic-4/25-live-snapshot.txt).
