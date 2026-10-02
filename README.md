# Deep Research Blog Writer

A Python research-to-blog pipeline using DeepAgents on LangGraph. A topic goes in. Ranked search results, an immutable source corpus, a research summary, and a cited blog draft come out. EPIC-1 to EPIC-11 are delivered: locked setup and quality gates, typed contracts and tools, the four-agent skeleton, API search with ranked normalization, polite fetching with parser fallback, the research corpus, synthesis and blog authoring behind a citation gate, the run-report, retry, and resume building blocks, run-owned observability with a local metrics dashboard, an offline test suite plus a golden-dataset evaluation and release gate, and a skill file and contract for every agent under [docs/architecture](docs/architecture/README.md).

**Documentation site:** [https://josoroma.github.io/deep-research-blog-writer](https://josoroma.github.io/deep-research-blog-writer). It explains setup, the run loop, and the committed example run with diagrams. The same page is at [docs/pages/running-a-run.html](docs/pages/running-a-run.html).

## Contents

- [Install and run](#install-and-run)
- [Fetch and extraction](#fetch-and-extraction)
- [Live run](#live-run)
- [Evaluation and release gate](#evaluation-and-release-gate)
- [Development checks](#development-checks)
- [Layout and rules](#layout-and-rules)
- [Working one epic per session](#working-one-epic-per-session)

## Install and run

Prerequisites: Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Make. uv selects Python 3.12 through `.python-version` and can install it when needed. No server is required.

```sh
make setup
make check
make demo-epic-4
make demo-epic-5
```

`make setup` installs `uv.lock` and the Git hook. `make check` verifies the lock, Ruff, formatting, strict typing, and offline tests with an 80% coverage floor. The Search demo uses a scripted model and fake provider through the actual DeepAgents orchestrator/search sub-agent; it needs no API keys. It saves a plan, 50 raw results, and 30 clean URLs in the printed `runs/<run_id>/` workspace. The fixture deliberately includes tracking links, duplicates, and denied hosts; it also verifies reversed arrival order and cached replay.

Create `.env` only if it does not exist (`cp -n .env.example .env`), then set credentials locally:

```dotenv
SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=<your SerpApi key>
OPENROUTER_API_KEY=<your OpenRouter key>
```

`.env` and `runs/` are Git-ignored. SerpApi and Serper are separate services: Serper requires `SEARCH_PROVIDER=serper` and `SERPER_API_KEY`. There is no fallback between their keys. SerpApi Google search requires `--per-page 10`; unsupported sizes and missing selected credentials fail before workspace creation. The HTTP timeout defaults to 15 seconds; use a larger bound for slow uncached provider requests:

```sh
make smoke-epic-4
SEARCH_TIMEOUT_SECONDS=60 uv run --locked deep-research-blog "2026 agentic AI frameworks" --search-only
```

The smoke makes one page-2 API request, validates ranks 11–20, and makes no model request. The search-only command uses the production orchestrator to derive 2–3 variants, searches topic pages 1–3 plus each variant's first page, and saves `request.json`, `search_plan.json`, `search_results.json`, and `clean_results.json`. It prints counts, status, and paths, and exits 0 for completion, 1 for execution failure, or 2 for rejected input/configuration. Inspect the workspace printed by that command:

```sh
uv run --locked python scripts/inspect-search-artifacts.py runs/<run_id>
```

For a reproducible provider-only run, provide two or three repeated `--query-variant` arguments with `--search-only`; this avoids a model call. `--pages`, `--per-page`, and `--max-urls` override the configured budgets. Results merge as topic page 1, variant page 1s in derivation order, then remaining topic pages. Normalization strips tracking/fragments/trailing slashes, filters the specified hosts and subdomains, retains the earliest duplicate, caps at `max_urls`, and assigns contiguous clean ranks.

The command without `--search-only` invokes the full agent skeleton; downstream pipeline tools still contain explicitly named stubs. Its completion status describes that invocation, not a finished production blog. `make demo-epic-3` demonstrates the skeleton offline. `make demo-epic-2` demonstrates contracts, state/checkpoints, prompts, and tools. `make smoke-epic-2` validates one live OpenRouter tool call with a 30-second timeout and no SDK retries.

All five model IDs are independently configurable using `MODELS__ORCHESTRATOR`, `MODELS__SEARCH_AGENT`, `MODELS__RESEARCH_AGENT`, `MODELS__ANALYST_AGENT`, and `MODELS__WRITER_AGENT`, each an `openrouter:<model-id>`. The default remains `openrouter:deepseek/deepseek-v4.1-flash`. Environment variables override `.env`.

## Fetch and extraction

Set `CRAWLER_CONTACT` in your Git-ignored `.env` to a public URL or email. Then fetch and extract the clean URLs from a completed Search workspace:

```sh
uv run --locked deep-research-blog --fetch-only --workspace runs/<search_run_id>
uv run --locked python scripts/inspect-fetch-artifacts.py runs/<search_run_id>
make smoke-epic-5
```

Fetch-only needs no LLM or search key. It saves `fetch_outcomes.json` (HTTP metadata without HTML), `extraction_results.json` (clean Source previews and parser attempts), and `fetch_state.json` (one outcome per URL). Individual failures are recorded while processing continues. Exit 0 means this milestone processed every URL; it does not classify a completed research/blog run. Re-running replaces these JSON previews and fetches again. Immutable source files and production collection belong to EPIC-6.

Every request identifies the crawler. Page attempts share a 15-second network/body budget across redirects, with up to three transient retries, at most five active fetches, and at least one second between starts on a hostname. Longer robots Crawl-delay takes precedence. Redirect destinations are robots-checked. Non-HTML and blocked pages never reach extraction. The default parser chain is trafilatura → readability-lxml → beautifulsoup4 with a minimum of 200 visible body words. `EXTRACTOR_STRATEGY=trafilatura|readability|beautifulsoup` selects one parser; `fallback` restores the chain.

`make demo-epic-5` uses original packaged HTML, mocked HTTP and explicitly labelled virtual timing. It demonstrates redirects, retries, permanent failure, robots blocking, PDF skipping, thin-page rejection, optional metadata, ordered fallback and the 30-host concurrency probe. The live smoke separately retrieves one public Python documentation page with your configured contact.

## Live run

A live run is three commands. Search writes the workspace, corpus collection reads it, and authoring reads the corpus. The first uncached SerpApi query for a fresh topic can exceed the 15-second default, so raise the timeout:

```sh
SEARCH_TIMEOUT_SECONDS=60 uv run deep-research-blog "Python LangChain Deep Agents Startup Ideas" --search-only --pages 3 --per-page 10 --max-urls 30
```

```json
{
  "run_id": "python-langchain-deep-agents-startup-ideas-20261001T195605Z",
  "workspace": "runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z",
  "status": "completed",
  "provider": "serpapi",
  "search_plan_path": "runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z/search_plan.json",
  "raw_results_path": "runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z/search_results.json",
  "clean_results_path": "runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z/clean_results.json",
  "counts": {
    "raw": 52,
    "denied": 9,
    "duplicates": 2,
    "capped": 11,
    "kept": 30
  },
  "error": null
}
```

`runs/` is git-ignored, so the workspace shows up as untracked and should stay that way. The committed `runs.example/` folder is the saved output of the three commands below, kept for reference because a fresh run lands in `runs/` and is never committed. Collect the corpus, then write the draft, both against the printed workspace:

```sh
RUN=runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z
uv run deep-research-blog --corpus-only --workspace "$RUN"
uv run deep-research-blog --author-only --workspace "$RUN"
```

Corpus collection fetched all 30 URLs and kept going past individual failures. 21 sources were written and indexed; 6 were unreachable, 1 was blocked by robots, and 2 were too thin to extract:

```json
{
  "run_id": "python-langchain-deep-agents-startup-ideas-20261001T195605Z",
  "workspace": "runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z",
  "status": "completed",
  "urls_processed": 30,
  "sources_written": 21,
  "sources_indexed": 21,
  "outcomes": {
    "extracted": 21,
    "unreachable": 6,
    "robots_disallowed": 1,
    "too_thin": 2
  },
  "index_path": "research/index.md",
  "error": null
}
```

Authoring wrote `research/summary.md` and a 3193-word `output/blog.md`, then ran the citation gate. All 17 citations resolved to a source file, but two cited sources were listed in `## References` with a title or URL that did not match the source file. Two repair passes did not fix them, so the run ended `failed` with reason `dangling_citations`. The last draft is kept:

```json
{
  "run_id": "python-langchain-deep-agents-startup-ideas-20261001T195605Z",
  "workspace": "runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z",
  "status": "failed",
  "summary_path": "research/summary.md",
  "blog_path": "output/blog.md",
  "word_count": 3193,
  "citations_checked": 17,
  "repair_passes": 2,
  "dangling_source_ids": [],
  "mismatched_source_ids": ["S-14", "S-24"],
  "reason": "dangling_citations",
  "error": null
}
```

## Evaluation and release gate

The unit suite is offline: it strips provider credentials and blocks sockets, so it needs no keys and no network. The whole pipeline also runs on fixtures, and releases are scored against the PD-021 golden dataset before a tag is created.

```sh
make demo-epic-10
make eval-offline
```

`make demo-epic-10` scores one fixture topic and shows both a passing and a blocked release decision. `make eval-offline` runs the fixture pipeline for every golden topic and writes `evaluations/benchmarks/<date>-<commit>.json`. Neither needs credentials.

A live evaluation uses the production models and SerpApi, and the release gate tags only when every golden topic passes every PD-021 threshold:

```sh
make eval
make release VERSION=1.0.0
```

Each topic is scored for citation validity, length, coverage, groundedness, hallucination rate, and every PRD.md §13 Definition of Done item. The judge defaults to DeepSeek V4.1 Flash on OpenRouter. See [EPIC-10.md](docs/SPECS-LOGS/EPIC-10.md) and [the runbook](docs/SPECS-LOGS/EPIC-10-RUNBOOK.md).

## Development checks

```sh
make check
make hooks
make boundary
make format
make build
sh scripts/verify-epic-5-package.sh
sh scripts/verify-epic-5-checkout.sh
uv run --locked pytest -m live tests/test_search_workflow.py --no-cov
```

The package verifier runs the installed wheel outside the checkout. The checkout verifier clones committed files into a temporary directory, installs locked dependencies, runs all offline gates/demos, builds, and verifies the wheel without `.env`. The final pytest command is an explicit real provider request; live tests are excluded from offline gates. Search failures preserve completed artifacts and do not retry automatically. Start a new run to retry a failed search; cross-process resume is scoped to EPIC-8.

Git hooks and GitHub Actions use the same offline quality gates, including agent HTTP/provider/prompt architecture checks. uv handles virtual environment selection; activation is optional. Hosted CI execution is separate from local verification.

## Layout and rules

| Directory | Responsibility |
| --- | --- |
| `agents/` | Orchestration; models from `LLMService`, system prompts from the catalog |
| `tools/` | Typed execution and validated state updates |
| `workflows/` | CLI, assembly, and run lifecycle |
| `prompts/` | Packaged agent prompts |
| `schemas/` | Pydantic contracts |
| `services/` | Provider integration, per-run search session, and workspace services |
| `evaluations/` | Architecture checks and runnable demonstrations |
| `tests/` | Offline regression and opt-in live tests |
| `docs/` | ADRs, agent documentation, recorded delivery evidence, and explainer pages |
| `docs/architecture/` | A `skill.md` and `contract.md` for every agent |
| `docs/SPECS-LOGS/` | Per-epic plans (`EPIC-N.md`) and runbooks (`EPIC-N-RUNBOOK.md`) |

Agents never import HTTP clients or construct provider clients. Per-run registry closures bind search tools to a workspace and provider; credentials and clients stay outside agent/checkpoint state. Search tools validate both input and output. The static boundary checker parses imports and prompt/model construction; computed indirect network access is outside its scope.

Each epic's plan and runbook live in [docs/SPECS-LOGS/](docs/SPECS-LOGS/): for example [EPIC-8.md](docs/SPECS-LOGS/EPIC-8.md) and [EPIC-8-RUNBOOK.md](docs/SPECS-LOGS/EPIC-8-RUNBOOK.md). Product decisions live in [SPECS.md](SPECS.md); architectural decisions in [docs/adr/](docs/adr/README.md); each agent's skill file and contract in [docs/architecture/](docs/architecture/README.md). [docs/pages/running-a-run.html](docs/pages/running-a-run.html) explains a live run visually; open it from disk.

## Working one epic per session

Each epic is one session: plan it, implement that plan, then review and test it. Do not start the next epic in the same session. The three prompts below are the ones that produced EPIC-6, EPIC-7, and EPIC-8. Replace `N` with the epic number.

### 1. Plan

```text
Plan EPIC-N: <epic title from SPECS.md> in docs/SPECS-LOGS/EPIC-N.md.

Read the EPIC-N section of SPECS.md first: the objective, every user story and its acceptance scenarios, the tasks, and the product decisions the stories cite. Read the previous epic's plan and the code it left behind, and write the plan against that baseline rather than against the specification alone.

EPIC-N.md must contain: the objective, the current baseline, a numbered implementation sequence, an acceptance matrix mapping each scenario to evidence, a completion checklist, and an explicit scope boundary naming what belongs to later epics. Status is Planned. Do not implement anything, and do not mark any story done.
```

### 2. Implement

```text
docs/SPECS-LOGS/EPIC-N.md exists. Implement EPIC-N from it, in the order its sequence gives, and stop at its scope boundary.

Follow the repository conventions: Pydantic v2 strict contracts, tools registered through the tool registry with stubs left in place for anything this epic does not replace, and the offline suite kept network-blocked. Add tests for every row of the acceptance matrix, plus an offline demo at evaluations/epicN_demo.py and a Makefile demo-epic-N target that needs no API key.

When the tests pass, run the gates and record only the commands that actually passed: uv run --locked ruff check, ruff format --check, mypy --strict, pytest -m 'not live', make demo-epic-N, make hooks, make build, and the installed-wheel check. Fix failures rather than skipping a gate.
```

### 3. Review and test

```text
Review and test the EPIC-N implementation against its own plan. Do not add features.

Check each acceptance scenario against the code and the tests, and report any scenario that has no evidence. Run the full offline gate, the new demo, and the demos of every earlier epic. Then verify the built wheel outside the checkout and do a fresh-checkout run of setup, gates, hooks, and demos.

Write docs/SPECS-LOGS/EPIC-N-RUNBOOK.md with the commands that passed, the PM demo steps, and an evidence table. Save coverage, the command list, and a source manifest pinned to the implementation commit under docs/evidence/epic-N/. Mark a story or task DONE in SPECS.md only when its scenario passed. Commit the implementation and the evidence separately, with hooks active, and exclude .env and runs/.
```


## Observability (EPIC-9)

Run commands now write JSON Lines to `runs/<run-id>/logs/execution.log` and an inspectable `logs/telemetry.json` snapshot. Registered tools, native agent model calls, fetch/phase retries, source outcomes and citation checks populate actual counts. Model usage/cost is read from response metadata; missing provider cost is marked unavailable. The existing report retains its ledger fallback. No metric exporter is constructed when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset.

```sh
make setup
make demo-epic-9
make observability-up
make smoke-epic-9
```

The offline demo runs the native agent hierarchy with scripted model usage and mock web responses, receives real OTLP protobuf on loopback, and deliberately fails two citations to make the dashboard's failure and citation panels demonstrable. Open [Grafana's research dashboard](http://127.0.0.1:3001/d/research-runs) and select the printed run ID. [Prometheus](http://127.0.0.1:9090) exposes the corresponding run metrics. Grafana provides anonymous Viewer access locally.

To export normal CLI workflow metrics to the stack, set `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` in the ignored `.env`. For hosted traces, set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and optionally `LANGSMITH_PROJECT`, then run `make smoke-langsmith`. This smoke uses fixture research work with real hosted trace upload/readback. Stop the local stack with `make observability-down`; named volumes are retained.

See [EPIC-9.md](docs/SPECS-LOGS/EPIC-9.md), [the runbook](docs/SPECS-LOGS/EPIC-9-RUNBOOK.md), and [ADR 0008](docs/adr/0008-run-observability.md) for acceptance evidence, configuration, commands, and limitations.
