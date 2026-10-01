# Deep Research Blog Writer

A Python project for an evidence-grounded research-to-blog pipeline using DeepAgents on LangGraph. EPIC-1 and EPIC-2 provide the foundation, quality gates, validated contracts, explicit state, typed tools, prompt catalog, and OpenRouter model service. Agent assembly and the research pipeline are scheduled in later epics.

## Install and run

Prerequisites: Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Make. uv uses `.python-version` to select Python 3.12 and can download it when needed.

```sh
uv python install 3.12
make setup
make check
make demo-epic-2
```

`make setup` installs dependencies from `uv.lock` and the pre-commit hook. `make check` runs lint, formatting, strict typing, and offline tests with an 80% coverage floor. `make demo-epic-2` validates a request, executes a typed tool through a real LangGraph ToolNode, restores typed checkpoint state, loads all five prompts, and demonstrates rejected contracts and agent patterns. It uses a fake model and needs no API keys. The server and blog-generation CLI belong to later epics. `make demo` remains the foundation dependency and quality-gate demonstration.

For the live model acceptance check, create `.env` from `.env.example` if it does not exist, then set `OPENROUTER_API_KEY` locally. `.env` and `runs/` are ignored by Git. Run `make smoke-epic-2` to request one typed tool call from `openrouter:deepseek/deepseek-v4.1-flash`. The command uses a 30-second timeout, disables SDK retries, and validates the returned arguments. `SERPER_API_KEY` is reserved for the later search integration.

All five agent models can be configured independently with `MODELS__ORCHESTRATOR`, `MODELS__SEARCH_AGENT`, `MODELS__RESEARCH_AGENT`, `MODELS__ANALYST_AGENT`, and `MODELS__WRITER_AGENT`. Each expects an `openrouter:<model-id>` value. The live production acceptance check requires all five to retain the specified production default. Environment variables override `.env`.

## Development checks

```sh
make check     # Lockfile, Ruff, formatting, mypy --strict, pytest with >=80% coverage
make hooks     # Pinned Ruff/mypy hooks and the complete test suite
make boundary  # Scan every Python module under agents/
make format    # Apply Ruff formatting
make build     # Build the wheel and source distribution
sh scripts/verify-epic-2-package.sh # Verify the built wheel outside this checkout
```

The Git hook runs Ruff, formatting, strict typing, and offline coverage tests, including the HTTP/provider/prompt architecture checks. Live tests are opt-in and excluded from these gates. GitHub Actions is configured to use the same checks on pushes and pull requests. Dependencies are installed with uv; virtual environment activation is optional because `uv run --locked` selects it automatically.

## Layout and rules

| Directory | Responsibility |
| --- | --- |
| `agents/` | Orchestration; no direct HTTP client imports |
| `tools/` | Typed, deterministic execution |
| `workflows/` | Workflow assembly and lifecycle |
| `prompts/` | Agent prompt catalog |
| `schemas/` | Pydantic contracts |
| `services/` | External provider integrations |
| `evaluations/` | Architecture checks and future quality evaluations |
| `tests/` | Offline regression tests |
| `docs/` | Architecture decisions and delivery evidence |

The boundary checker rejects imports of `requests`, `httpx`, `aiohttp`, `urllib3`, `urllib.request`, and `http.client` from agents, including submodules and parent-package `from` imports. It parses code without executing it. Computed dynamic imports and indirect network access are outside this static check.

Agent modules obtain models from `services.llm_service.LLMService` and prompts from `prompts.catalog.load_prompt`. Architecture tests reject provider imports/construction and inline system prompts, including sub-agent dictionaries. Registered application tools declare Pydantic input and output models; the LangChain adapter handles injected runtime context and validated state updates. The EPIC-2 checkpointer is in memory; durable per-run SQLite resume is scoped to US-8.4.

See [EPIC-2.md](EPIC-2.md) for the implemented plan and [EPIC-2-RUNBOOK.md](EPIC-2-RUNBOOK.md) for successful commands, PM demonstrations, and acceptance evidence. The earlier foundation delivery is documented in [EPIC-1.md](EPIC-1.md) and [EPIC-1-RUNBOOK.md](EPIC-1-RUNBOOK.md). See [docs/adr/](docs/adr/README.md) for decisions and [SPECS.md](SPECS.md) for subsequent stories.
