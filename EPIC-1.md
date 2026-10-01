# EPIC-1: Project Foundation and Quality Gates

Date: 2026-09-30  
Status: Planned; implementation and verification follow this plan.

## Objective and scope

Implement all four stories in [SPECS.md](SPECS.md#epic-1-project-foundation-and-quality-gates), following PD-001, PD-002, NFR-007, and [PRD.md §4–5](PRD.md#4-why-deepagents). Deliver a reproducible Python foundation that later epics can extend.

The starting directory contains specifications and the research-writing skill, but no application code, Python project, or Git repository. Use root-level packages as required by US-1.1. Pin the development interpreter to Python 3.12 and declare support for Python >=3.12. Keep the foundation demo offline and free of API credentials.

The research CLI, model configuration, typed pipeline contracts, agent assembly, search, extraction, observability stack, and release evaluations belong to later epics. EPIC-1 starts the development environment and quality checks; it does not start a server or produce a blog.

## Implementation sequence

1. **US-1.1 — Scaffold the project.** Initialize Git on `main` and a uv-managed project. Add LangChain, LangGraph, DeepAgents, `langchain-openrouter`, and Pydantic >=2,<3; resolve and commit `uv.lock`. Create importable `agents/`, `tools/`, `workflows/`, `prompts/`, `schemas/`, `services/`, `evaluations/`, `tests/`, and `docs/`. Configure packaging explicitly for the root-level application packages. Add `.env.example` with blank `OPENROUTER_API_KEY` and `SERPER_API_KEY`; ignore secrets, virtual environments, run artifacts, caches, and generated reports.
2. **US-1.2 — Enforce quality.** Configure Ruff linting/import ordering/formatting, strict mypy, and pytest-cov with an 80% coverage floor in `pyproject.toml`. Pin Ruff 0.13.0 and mypy 1.18.1 locally to match the specified hooks. Add `ruff-check`/`ruff-format` from ruff-pre-commit `v0.13.0`, mypy from mirrors-mypy `v1.18.1`, and an always-running local pytest coverage hook. Check whole packages for typing and tests on every commit, including documentation-only commits. Add Make targets for setup, lint, format, typing, tests, checks, and demo. Add a CI workflow using the same locked dependencies and checks; record local execution separately from hosted CI execution.
3. **US-1.3 — Enforce the agent boundary.** Implement a typed AST-based checker in `evaluations/` and a test that recursively scans every Python module under `agents/`. Forbid `requests`, `httpx`, `aiohttp`, `urllib3`, `urllib.request`, and `http.client`, including aliases, submodules, and `from` imports of these modules. Preserve file and line diagnostics. Test allowed imports and intentional violations using temporary fixtures. Any syntax error must fail rather than silently skip a module. This enforces the specified import boundary, not arbitrary runtime behavior.
4. **US-1.4 — Establish ADRs.** Create `docs/adr/README.md`, a reusable template, and `0001-deepagents-on-langgraph.md`. Each numbered ADR includes Context, Decision, and Consequences with pros and cons. ADR 0001 explains planning, filesystem/context offloading, sub-agents, and LangGraph orchestration/checkpointing from PRD §4. Keep the template distinct from accepted numbered decisions.
5. **Verify and capture evidence.** Install the environment and Git hook, run each gate and all hooks, verify distribution build/install and importable dependencies/packages, and demonstrate failures for untyped code, forbidden HTTP imports, lint/format issues, and insufficient coverage. Use disposable copies or temporary files and restore the passing checkout. Test a fresh checkout with `uv sync --locked`. Record exact commands, real outputs, exit codes, versions, coverage, and provenance in committed evidence. Create a runbook mapping the evidence to every acceptance criterion, with installation, setup, start/demo, and troubleshooting instructions.
6. **Close the epic.** Mark only EPIC-1 and its stories/tasks complete in the specification and this plan after checks pass. Commit the lockfile and implementation with the actual pre-commit hook active. Finish with a clean working tree and links to the plan, runbook, and evidence.

## Acceptance and evidence matrix

| Story | Required result | Verification |
| --- | --- | --- |
| US-1.1 | Git repository; Python >=3.12; locked required dependencies; nine package directories; secret-safe example | `git status`, `uv sync --locked`, version/import checks, wheel build/install, fresh checkout, `git check-ignore` |
| US-1.2 | Ruff and formatting pass; strict typing enforced; tests fail below 80%; hooks reject failures | `make check`, `uv run pre-commit run --all-files`, disposable failing fixtures and commit attempts |
| US-1.3 | Every agent module scanned; all six forbidden imports rejected; file named; clean agents pass | Boundary suite and temporary nested agent module demo |
| US-1.4 | Numbered ADR 0001 and template with Context, Decision, pros and cons | Inspect ADR files during PM walkthrough |

## Quality and implementation decisions

- Use empty, documented packages rather than speculative implementations of later stories.
- Keep the AST checker reusable so the PM can see a direct boundary failure as well as a pytest failure.
- Measure coverage over all application packages, including `evaluations/`; do not count tests as application coverage or lower the required threshold.
- Use locked uv commands in automation so checks cannot silently update dependencies. A developer can still use the acceptance command `uv sync`.
- Install pre-commit after uv sync. Hook environments for Ruff and mypy are pinned; mypy must see the project virtual environment for installed type information.
- Use real local outputs as evidence. A configured GitHub Actions workflow is not evidence that hosted CI ran.
- Package installation must work beyond the repository working directory, without accidentally including `tests/` or documentation as application packages.

## PM demonstration

1. Show the package layout, `.env.example`, lockfile, and ADR 0001.
2. Run the offline foundation demo and show installed versions, all quality gates, and coverage >=80%.
3. Show intentional import, typing, and coverage failures in a disposable checkout; explain the named module and nonzero exit status.
4. Show pre-commit rejecting a bad commit and accepting the verified implementation.
5. Open the acceptance matrix and recorded command transcripts in `EPIC-1-RUNBOOK.md` and `docs/evidence/epic-1/`.

## Completion checklist

- [ ] US-1.1 implemented and verified.
- [ ] US-1.2 implemented and verified, including failure cases.
- [ ] US-1.3 implemented and verified across the complete forbidden list.
- [ ] US-1.4 implemented and inspected.
- [ ] Fresh-checkout install and wheel installation verified.
- [ ] Runbook and actual command evidence written.
- [ ] Lockfile and implementation committed with hooks passing; working tree clean.

## Tool references

Implementation follows the official documentation for [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/), [Ruff pre-commit integration](https://docs.astral.sh/ruff/integrations/), [pre-commit](https://pre-commit.com/), [mypy configuration](https://mypy.readthedocs.io/en/stable/config_file.html), and [pytest-cov configuration](https://pytest-cov.readthedocs.io/en/latest/config.html). The exact Ruff and mypy revisions come from US-1.2, rather than newer defaults.
