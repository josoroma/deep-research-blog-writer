# Deep Research Blog Writer

A Python project for an evidence-grounded research-to-blog pipeline using DeepAgents on LangGraph. EPIC-1 provides the project foundation, quality gates, agent import boundary, and ADR log. The research pipeline is scheduled in later epics.

## Install and start the foundation

Prerequisites: Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Make. uv uses `.python-version` to select Python 3.12 and can download it when needed.

```sh
uv python install 3.12
make setup
make demo
```

`make setup` installs the dependencies from `uv.lock` and the pre-commit hook. `make demo` prints installed versions, checks the agent boundary, and runs lint, formatting, strict typing, tests, and coverage. API keys are unnecessary for this foundation demo. There is no server or blog-generation CLI in EPIC-1.

`.env.example` lists keys for future pipeline integrations. When those integrations are implemented, create local configuration with `cp -n .env.example .env` and fill in your own keys. `.env` and `runs/` are ignored by Git.

## Development checks

```sh
make check     # Lockfile, Ruff, formatting, mypy --strict, pytest with >=80% coverage
make hooks     # Pinned Ruff/mypy hooks and the complete test suite
make boundary  # Scan every Python module under agents/
make format    # Apply Ruff formatting
make build     # Build the wheel and source distribution
```

The Git hook runs Ruff, formatting, strict typing, and coverage tests. GitHub Actions uses the same checks on pushes and pull requests. Dependencies are installed with uv; virtual environment activation is optional because `uv run --locked` selects it automatically.

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

See [EPIC-1.md](EPIC-1.md) for the implementation plan, [EPIC-1-RUNBOOK.md](EPIC-1-RUNBOOK.md) for verified commands and the PM demo, [docs/adr/](docs/adr/README.md) for decisions, and [SPECS.md](SPECS.md) for subsequent stories.
