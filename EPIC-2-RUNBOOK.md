# EPIC-2 implementation and PM demonstration runbook

Verified: 2026-10-01. US-2.1–US-2.6 are implemented, including a successful live production-model tool call. The plan was written in [EPIC-2.md](EPIC-2.md) before implementation. [Raw evidence](docs/evidence/epic-2/README.md) records the commands, output, exit codes, UTC timestamps, coverage, and source hashes.

Delivered: strict Pydantic hand-off contracts and environment settings; explicit RunState within DeepAgentState; a nonempty typed tool registry with a real LangChain adapter; five packaged prompt files; a central, configurable OpenRouter model service with fake injection; and a separate live smoke command. The deterministic `record_phase_completion` tool executes through a real LangGraph ToolNode and restores typed checkpoint state.

This milestone uses an in-memory checkpointer. Agent assembly, run workspaces, search/extraction, the blog CLI, and durable SQLite resume remain in their specified later epics. The offline demo records a fixture URL's outcome as `pending`; it demonstrates the building blocks rather than producing a researched article.

## Install, configure, and run

Prerequisites: Git, Make, and uv. The verified uv version is 0.11.14. If uv is missing, follow its [installation instructions](https://docs.astral.sh/uv/getting-started/installation/). From the repository root, these successful commands reproduce the local setup and offline demonstration:

```sh
uv python install 3.12
make setup
make check
make demo-epic-2
```

Observed setup output:

```text
Python 3.12 is already installed
Resolved 82 packages
Checked 80 packages
pre-commit installed at .git/hooks/pre-commit
```

uv uses `.python-version` and `.venv`; activating the virtual environment is optional. Locked versions were Python 3.12.9, DeepAgents 0.7.21, LangChain 1.4.3, LangGraph 1.2.12, langchain-openrouter 0.2.9, Pydantic 2.12.5, and pydantic-settings 2.15.0. See the [environment transcript](docs/evidence/epic-2/11-environment.txt).

The offline checks and demo require no credentials. For the live check, create a local `.env` from `.env.example` if it does not already exist, then enter `OPENROUTER_API_KEY` in that file locally. Existing configuration can be kept. `.env` is Git-ignored and credentials are not included in this evidence. `SERPER_API_KEY` is unnecessary for EPIC-2.

The settings read environment variables before `.env`. Budgets default to `PAGES=3`, `PER_PAGE=10`, and `MAX_URLS=30`; invalid integer values name the field in their validation error. All five `MODELS__<AGENT>` settings default to `openrouter:deepseek/deepseek-v4.1-flash`. Production smoke acceptance requires that default for every agent.

```sh
make smoke-epic-2
```

This successful command sent one live request with forced typed tool choice, a 30-second timeout, SDK retries disabled, and a 128-token output cap. It validated exactly one `FoundationPing` call, its call ID, and its arguments. The actual response was:

```json
{
  "status": "passed",
  "model": "openrouter:deepseek/deepseek-v4.1-flash",
  "tool": "FoundationPing",
  "arguments": {"value": "EPIC-2-ready"},
  "provider_preferences": {"require_parameters": true, "data_collection": "deny"},
  "usage": {"input_tokens": 326, "output_tokens": 65, "total_tokens": 391}
}
```

Exit code was 0. The [full transcript](docs/evidence/epic-2/02-live-smoke.txt) also includes cache/reasoning token detail. Future runs require provider availability and credit. Missing credentials produce a pending result with CLI exit 2; an invalid response/provider failure produces CLI exit 1. Make may report exit 2 for a failed recipe. A live result is separate from offline test success.

## Successful commands and results

All commands in this table were run successfully; links preserve their actual outputs. The dependency-add command records implementation history; subsequent installations use the lockfile through `make setup`.

| Command | Observed result | Transcript |
| --- | --- | --- |
| `uv add 'pydantic-settings>=2,<3'` | Added settings 2.15.0 and python-dotenv 1.2.4; updated lockfile | [01](docs/evidence/epic-2/01-settings-dependency.txt) |
| `uv python install 3.12` | Python 3.12 already installed | [10](docs/evidence/epic-2/10-python-install.txt) |
| `make setup` | Locked dependencies and Git hook installed | [03](docs/evidence/epic-2/03-setup.txt) |
| `make format` | 33 Python files already formatted | [04](docs/evidence/epic-2/04-format.txt) |
| `make check` | Lock/Ruff/format checks pass; strict mypy passes 33 files; 179 tests pass, one live test deselected; 99.31% coverage | [05](docs/evidence/epic-2/05-quality-gates.txt) |
| `make demo-epic-2` | Typed tool execution, checkpoint restoration, five prompts/models, four contract rejections, three architecture rejections | [06](docs/evidence/epic-2/06-offline-demo.txt) |
| `make hooks` | Ruff, formatting, strict mypy, and offline pytest hooks pass | [12](docs/evidence/epic-2/12-hooks-verified.txt) |
| `make build` | Wheel and source distribution built | [08](docs/evidence/epic-2/08-build.txt) |
| `sh scripts/verify-epic-2-package.sh` | Installed wheel plus 60 locked runtime dependencies in a temporary environment; five prompts and real graph/checkpoint demo pass outside checkout | [09](docs/evidence/epic-2/09-installed-wheel.txt) |
| `make smoke-epic-2` | One valid live production-model tool call; 391 total tokens | [02](docs/evidence/epic-2/02-live-smoke.txt) |
| `uv --version` | uv 0.11.14 | [13](docs/evidence/epic-2/13-uv-version.txt) |
| `shasum -a 256 -c docs/evidence/epic-2/source-sha256.txt` | All 47 tested source/configuration/test/script hashes match | [14](docs/evidence/epic-2/14-source-verification.txt) |
| `git commit -m 'feat: implement EPIC-2 contracts and agent building blocks'` | Created implementation commit `f13077a` with all hooks passing | [15](docs/evidence/epic-2/15-implementation-commit.txt) |
| `sh scripts/verify-epic-2-checkout.sh` | Fresh committed clone passes setup, checks, hooks, offline demo, build, and installed-wheel verification | [16](docs/evidence/epic-2/16-fresh-checkout.txt) |

The original hook attempt reported files changing while mypy ran: the evidence recorder was updating the tracked command manifest during that check. Mypy itself reported no type errors. The check was rerun with evidence writes serialized and all hooks passed. Both [original output](docs/evidence/epic-2/07-hooks.txt) and [successful rerun](docs/evidence/epic-2/12-hooks-verified.txt) are retained.

The combined line/branch coverage is 99.31%, above the retained 80% floor. [Coverage XML](docs/evidence/epic-2/coverage.xml) records 456/458 lines and 116/118 branches covered. Live-smoke logic is unit-tested with scripted responses; the real provider acceptance is the separate recorded live command. Offline tests deny socket connections and clear credential/configuration environment overrides for isolation.

## PM demo, about 10 minutes

1. Open [the plan](EPIC-2.md), [ADR 0002](docs/adr/0002-openrouter-deepseek-v4-1-flash.md), and the acceptance table below to establish the delivered scope.
2. Run `make demo-epic-2`. Show the trimmed topic, budgets `[3, 10, 30]`, the registered tool, all five prompt lengths, and five production model IDs. Point to `fake_injection_verified: true`, `checkpoint_restored: true`, and `completed_phases: ["search"]`. These values come from actual ToolNode execution and checkpoint restoration.
3. In that same output, show rejection of short/long topics, malformed state replacement, and raw-dictionary tool output. The static probes also reject an HTTP import, direct provider construction, and an inline system prompt without executing the invalid code.
4. Run `make check` and `make hooks`. Show 179 passing offline tests, strict typing, and coverage above 80%. Architecture fixture tests also cover nested agent files and inline sub-agent dictionary prompts.
5. Run `make build` then `sh scripts/verify-epic-2-package.sh`. Show all five prompt resources and the typed graph/checkpoint working from the installed wheel outside the checkout.
6. Open [the recorded live result](docs/evidence/epic-2/02-live-smoke.txt), or run `make smoke-epic-2` for a new live demonstration. Show the validated tool call and required provider preferences. Replaying this command sends another provider request.
7. Use the acceptance table to walk through all six stories. The commit and fresh-checkout transcript in the delivery section establish reproducibility from committed files.

The offline demo creates and removes temporary architecture probes. It does not require editing production files or provisioning external services.

## Acceptance matrix

| Story | Delivered acceptance | Evidence of done |
| --- | --- | --- |
| US-2.1 | Topic trims before 3–250 validation; 3/10/30 defaults; five PRD contracts; validated environment/.env settings | [Contract tests](tests/test_contracts.py), [settings tests](tests/test_settings.py), [quality output](docs/evidence/epic-2/05-quality-gates.txt) |
| US-2.2 | RunState under DeepAgentState `run`; every clean URL has a typed outcome; malformed replacements fail; nested models survive a real checkpoint | [State/tool integration tests](tests/test_state_and_tools.py), [offline demo](docs/evidence/epic-2/06-offline-demo.txt) |
| US-2.3 | Nonempty TOOLS; Pydantic input/output declarations; registration/call validation; raw dict and corrupted model outputs rejected; runtime hidden from model-facing tool schema | [Registry](tools/registry.py), [state/tool tests](tests/test_state_and_tools.py), [offline demo](docs/evidence/epic-2/06-offline-demo.txt) |
| US-2.4 | Exact file-content prompt loader; all five packaged prompts; orchestrator carries operating rules/workflow and governing decisions; inline prompts rejected | [Catalog/architecture tests](tests/test_prompts_and_architecture.py), [orchestrator prompt](prompts/orchestrator.md), [wheel evidence](docs/evidence/epic-2/09-installed-wheel.txt) |
| US-2.5 | Per-agent configured ChatOpenRouter models; actual SDK request captures include both required preferences; fake injection needs no key; provider construction blocked in agents | [LLM service tests](tests/test_llm_service.py), [architecture tests](tests/test_prompts_and_architecture.py), [quality output](docs/evidence/epic-2/05-quality-gates.txt) |
| US-2.6 | All five production defaults match the specified model; ADR recorded; valid live typed tool call | [ADR 0002](docs/adr/0002-openrouter-deepseek-v4-1-flash.md), [settings tests](tests/test_settings.py), [live result](docs/evidence/epic-2/02-live-smoke.txt) |

## Delivery and reproducibility

Implementation commit: `f13077a9a5287b1ce7079f225096870dc8e176da`. The [commit transcript](docs/evidence/epic-2/15-implementation-commit.txt) records successful hooks and the committed files. A [fresh temporary clone of that exact revision](docs/evidence/epic-2/16-fresh-checkout.txt) passed setup, all quality gates/hooks, the offline demo, build, and installed-wheel verification with no local `.env`. It reported no tracked-file changes. Final documentation and evidence updates are committed separately; application, configuration, and test hashes remain the same.

Reproduce the committed checkout without local `.env` files using:

```sh
sh scripts/verify-epic-2-checkout.sh
```

This script clones committed HEAD into a temporary directory, runs setup, quality gates, hooks, the offline demo, build, and installed-wheel verification, then checks for tracked-file changes. It removes the temporary clone when finished.

Verify the tested application/configuration/test files against the recorded snapshot:

```sh
shasum -a 256 -c docs/evidence/epic-2/source-sha256.txt
```

The local quality, hook, wheel, and live checks are observed evidence. Hosted GitHub Actions execution requires a configured remote and push; this delivery does not claim a hosted CI run.
