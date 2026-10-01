# EPIC-5: Fetch and Extraction — Runbook and PM Evidence

Date: 2026-10-01

US-5.1–US-5.3 are implemented. The plan was created in [EPIC-5.md](EPIC-5.md) before implementation. Decisions are documented in [ADR 0006](docs/adr/0006-polite-fetch-and-extraction.md); their story/task statuses are DONE in [SPECS.md](SPECS.md#epic-5-fetch-and-extraction).

## Install, configure, and start

Prerequisites: Git, Make, and [uv](https://docs.astral.sh/uv/getting-started/installation/). Run from the repository root. uv selects Python 3.12 and manages `.venv`; shell activation is optional. There is no server or additional service to start.

```sh
make setup
make check
make demo-epic-5
```

Setup installs the committed lock and pre-commit hook. The offline demo needs no credentials. It uses mock HTTP, original packaged HTML, actual registered tools, and the three extraction libraries; delays are simulated with an explicitly labelled virtual clock. It prints a new `runs/<run_id>/` workspace and saves the files described below.

For live fetching, create `.env` only if absent (`cp -n .env.example .env`). Set your public crawler contact locally:

```dotenv
CRAWLER_CONTACT=https://github.com/josoroma/deep-research-blog-writer
EXTRACTOR_STRATEGY=fallback
```

The contact above is the value used for this delivery. HTTP(S) URLs, mailto addresses and bare email addresses are accepted. Live fetch-only runs require no OpenRouter, Serper, or SerpApi key. `.env` and `runs/` are Git-ignored.

Use the workspace printed by an EPIC-4 search-only run:

```sh
uv run --locked deep-research-blog --fetch-only --workspace runs/<search_run_id>
uv run --locked python scripts/inspect-fetch-artifacts.py runs/<search_run_id>
```

Fetch-only uses the saved topic and search budget. Exit 0 means every clean URL was processed, including recorded failures; exit 1 means a fatal milestone error; exit 2 rejects invalid configuration/input. The full blog status classification belongs to EPIC-8. Re-running fetch-only makes new requests and replaces the JSON previews. Durable resume is a later epic.

Run the small live demo independently:

```sh
make smoke-epic-5
uv run --locked pytest -m live tests/test_fetch_smoke.py --no-cov
```

To demonstrate the actual CLI without paying for a new search, seed one known public URL and use the printed workspace:

```sh
uv run --locked python scripts/create-live-fetch-workspace.py
uv run --locked deep-research-blog --fetch-only --workspace runs/<printed_run_id>
uv run --locked python scripts/inspect-fetch-artifacts.py runs/<printed_run_id>
```

That helper creates a manually seeded, typed Search input containing the public Python asyncio URL. It does not call a search provider. The normal production hand-off is an EPIC-4 workspace.

## Successful commands actually run

Full transcripts preserve the real outputs and exit status; [commands.jsonl](docs/evidence/epic-5/commands.jsonl) records UTC times, durations, and exact command arguments. The table omits the temporary recording wrapper because it only captures stdout/stderr.

| Command | Recorded result | Full output |
| --- | --- | --- |
| `uv add 'trafilatura>=2,<3' 'readability-lxml>=0.8,<1' 'beautifulsoup4>=4.13,<5' 'markdownify>=1,<2' 'protego>=0.5,<1'` | Locked trafilatura 2.2.0, readability-lxml 0.9, beautifulsoup4 4.15.0, markdownify 1.2.3, Protego 0.7.0; 104 packages resolved | [01-dependencies](docs/evidence/epic-5/01-dependencies.txt) |
| `make setup` | `Checked 101 packages`; `pre-commit installed at .git/hooks/pre-commit` | [05-setup](docs/evidence/epic-5/05-setup.txt) |
| `make check` | Ruff and formatting pass; strict mypy passes; `401 passed, 3 deselected`; `97.50%` coverage | [29-check](docs/evidence/epic-5/29-check.txt) |
| `make demo-epic-5` | 11 URLs processed; six extracted; five correctly recorded failures/skips; 30-host probe max active = 5 | [06-demo](docs/evidence/epic-5/06-demo.txt) |
| `make demo-epic-2 demo-epic-3 demo-epic-4` | Contract/checkpoint, agent skeleton, and real Search tool demos pass | [08-prior-demos](docs/evidence/epic-5/08-prior-demos.txt) |
| `uv run --locked python -m evaluations.fetch_live_smoke --output docs/evidence/epic-5/live-smoke.json` | Public page HTTP 200; trafilatura extracts 228 words; `passed: true` | [26-metadata-live-smoke](docs/evidence/epic-5/26-metadata-live-smoke.txt) |
| `uv run --locked pytest -m live tests/test_fetch_smoke.py --no-cov` | `1 passed, 7 deselected` | [09-live-test](docs/evidence/epic-5/09-live-test.txt) |
| `make build` | Wheel and source distribution built successfully | [10-build](docs/evidence/epic-5/10-build.txt) |
| `sh scripts/verify-epic-5-package.sh` | Installed-wheel tools, real parsers, fixtures, limits, fallback/artifacts pass outside checkout; console rejects missing workspace with exit 2 | [12-wheel](docs/evidence/epic-5/12-wheel.txt) |
| `uv run --locked python scripts/create-live-fetch-workspace.py` | Created `runs/epic-5-live-python-asyncio-fetch-20261001T152525Z` | [13-seed-live-workspace](docs/evidence/epic-5/13-seed-live-workspace.txt) |
| `uv run --locked deep-research-blog --fetch-only --workspace runs/epic-5-live-python-asyncio-fetch-20261001T152525Z` | `status: completed`, `urls_processed: 1`, `extracted: 1`; three artifacts saved | [27-live-cli](docs/evidence/epic-5/27-live-cli.txt) |
| `uv run --locked python scripts/inspect-fetch-artifacts.py runs/epic-5-polite-evidence-collection-20261001T152315Z` | Validates all 11 ranked outcomes, minimum word counts, matching IDs, no raw HTML, and failure/source separation | [15-inspect-offline](docs/evidence/epic-5/15-inspect-offline.txt) |
| `uv run --locked python scripts/inspect-fetch-artifacts.py runs/epic-5-live-python-asyncio-fetch-20261001T152525Z` | Validates actual CLI output and the extracted live source | [17-inspect-live](docs/evidence/epic-5/17-inspect-live.txt) |

An intermediate recorded check, [07-check](docs/evidence/epic-5/07-check.txt), failed because the artifact-inspection script needed formatting. `uv run --locked ruff format scripts/inspect-fetch-artifacts.py` corrected it; the subsequent [11-check](docs/evidence/epic-5/11-check.txt) passes. Earlier successful checkpoints remain in the evidence folder. No failed command is counted as successful.

## PM demonstration and evidence of done

1. Run `make demo-epic-5`. Explain that HTTP is mocked, extraction is real, and timing is virtual. The 30-host probe overlaps real asyncio tasks and records a shared maximum of five fetches.
2. Open the printed workspace, then run the artifact inspector against it. Show the six successful Sources and the five expected outcomes. Redirect and retry successes retain their original clean rank and source ID.
3. Show a successful Source: title `Polite Evidence Collection`, author `Alex Researcher`, publication `2026-09-01`, canonical URL `https://fixture.test/canonical?id=7`, and 288 clean body words. Navigation/sidebar/footer markers are absent. The missing-metadata fixture succeeds with null author/publication.
4. Show the thin-page entry: `too_thin`, `source: null`, and attempts for all three parsers. Show the PDF and robots-blocked URLs: neither is sent to extraction, and the blocked page has no HTTP page request. The 404 gets one attempt; the persistent 503 gets four, with 1/2/4-second virtual backoff.
5. Show `demo_evidence.json`: one robots request per origin; all identifying User-Agent headers verified; same-host starts spaced at least one second; the slow host's recorded starts `10, 15, 20` are five seconds apart. Show the explicitly forced empty/thin branch probe reaching the real beautifulsoup4 parser. Tests independently exercise each actual parser against all substantial fixtures.
6. Run the live smoke or live CLI helper sequence. Show HTTP 200 and successful extraction with the configured public contact. The saved live smoke's robots and page starts are over one real second apart. Public page content/word counts can change between runs.
7. Show `make check`, `make hooks`, and the wheel/fresh-checkout verification transcripts. These demonstrate local completion; hosted CI execution is separate.

Committed snapshots make the review independent of ignored local workspaces:

| Artifact | What it demonstrates |
| --- | --- |
| [offline/fetch_state.json](docs/evidence/epic-5/offline/fetch_state.json) | One typed terminal outcome for each of 11 clean URLs; fetch phase completion |
| [offline/fetch_outcomes.json](docs/evidence/epic-5/offline/fetch_outcomes.json) | Status, final URLs, attempt bounds and failure reasons; no raw HTML |
| [offline/extraction_results.json](docs/evidence/epic-5/offline/extraction_results.json) | Clean Source previews, metadata, optional fields, and parser attempts |
| [offline/demo_evidence.json](docs/evidence/epic-5/offline/demo_evidence.json) | Request timeline, robots cache, retry delays, concurrency and forced fallback probe |
| [live-smoke.json](docs/evidence/epic-5/live-smoke.json) | Actual HTTP, contact header, canonical URL and successful real extraction; body intentionally omitted |
| [live-cli/](docs/evidence/epic-5/live-cli/) | Original persisted artifacts from the successful live CLI invocation |
| [coverage.xml](docs/evidence/epic-5/coverage.xml) | 97.50% offline branch-aware coverage; live tests excluded |

## Scope and operation

The registered `fetch_url` and `extract_markdown` are real internal tools. Agents keep their specified assignments and do not receive raw page HTML. Fetch-only composes those tools outside model context. Fetch service limits/cache are shared within a run; independent services/processes have independent limits. The 15-second network/body budget is shared across page redirects within each attempt; robots requests have separate 15-second bounds. Polite waits, retries and robots checks add to total URL processing time.

`EXTRACTOR_STRATEGY=readability` or `beautifulsoup` selects a single implementation without agent changes; `fallback` restores all three. Empty/thin candidates fall through in order, parser exceptions are recorded safely, and all-thin/all-error results have no Source. Non-HTML/PDF, JavaScript rendering, and immutable corpus writing are outside this milestone.

Production `collect_source`, front-matter source files and `research/index.md` remain EPIC-6; the full agent command still has a clearly labelled collection stub. This runbook demonstrates completed fetching/extraction, not a completed production blog.

Publication dates require explicit meta tags, Article JSON-LD, or marked publication time elements. Parser date guesses are discarded. The passing [29-check](docs/evidence/epic-5/29-check.txt) includes redirect-budget and metadata regressions: 401 offline tests, 97.50% coverage. The corrected [live smoke](docs/evidence/epic-5/26-metadata-live-smoke.txt) extracts 228 words with null publication date, and the [live CLI](docs/evidence/epic-5/27-live-cli.txt) also passes. Earlier live transcripts retain the parser guesses as historical evidence, not accepted publication metadata.

[25-metadata-check](docs/evidence/epic-5/25-metadata-check.txt) caught a type inference error in the new structured-metadata test. Explicitly typed branches corrected it; [29-check](docs/evidence/epic-5/29-check.txt) passes.
