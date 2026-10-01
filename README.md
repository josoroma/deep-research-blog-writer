# Deep Research Blog Writer

A Python research-to-blog pipeline using DeepAgents on LangGraph. EPIC-1–EPIC-4 provide locked setup, quality gates, typed contracts/state/tools, central OpenRouter models and packaged prompts, the four-agent skeleton, and real API search with ranked normalization. Fetching, extraction, corpus/article generation, citation checks, and durable resume belong to later epics.

## Install and run

Prerequisites: Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Make. uv selects Python 3.12 through `.python-version` and can install it when needed. No server is required.

```sh
make setup
make check
make demo-epic-4
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

## Development checks

```sh
make check
make hooks
make boundary
make format
make build
sh scripts/verify-epic-4-package.sh
sh scripts/verify-epic-4-checkout.sh
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
| `docs/` | ADRs and recorded delivery evidence |

Agents never import HTTP clients or construct provider clients. Per-run registry closures bind search tools to a workspace and provider; credentials and clients stay outside agent/checkpoint state. Search tools validate both input and output. The static boundary checker parses imports and prompt/model construction; computed indirect network access is outside its scope. SQLite resume is a later story.

See [EPIC-4.md](EPIC-4.md) and [EPIC-4-RUNBOOK.md](EPIC-4-RUNBOOK.md) for the plan, successful command outputs, and PM evidence. Earlier deliveries: [EPIC-1](EPIC-1-RUNBOOK.md), [EPIC-2](EPIC-2-RUNBOOK.md), and [EPIC-3](EPIC-3-RUNBOOK.md). Product decisions live in [SPECS.md](SPECS.md); architectural decisions in [docs/adr/](docs/adr/README.md).
