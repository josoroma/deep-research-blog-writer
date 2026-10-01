# EPIC-2 acceptance evidence

Verification date: 2026-10-01. See [the runbook](../../../EPIC-2-RUNBOOK.md) for setup, successful commands, the PM demo, and story acceptance.

Each transcript contains the actual command, combined stdout/stderr, and exit code. [commands.jsonl](commands.jsonl) adds UTC completion time, working directory, duration, and expected exit status. Entries are written on completion, so their order may differ from the numbered file names.

| Evidence | Result |
| --- | --- |
| [01 settings dependency](01-settings-dependency.txt) | Direct dependency and lockfile update |
| [02 live smoke](02-live-smoke.txt) | Valid production-model tool call, exit 0; 391 tokens |
| [03 setup](03-setup.txt) | Locked environment and Git hooks |
| [04 formatting](04-format.txt) | 33 files already formatted |
| [05 quality gates](05-quality-gates.txt) | Ruff/strict mypy pass; 179 passing offline tests; 99.31% coverage |
| [06 offline demo](06-offline-demo.txt) | Actual ToolNode/checkpoint, prompt catalog, configured models, and expected rejection cases |
| [07 initial hook attempt](07-hooks.txt) | Evidence manifest changed during the hook; type checks themselves passed; retained for transparency |
| [08 build](08-build.txt) | Source distribution and wheel |
| [09 installed wheel](09-installed-wheel.txt) | Contracts, five prompts, and real graph/checkpoint outside checkout |
| [10 Python setup](10-python-install.txt) | Python 3.12 already installed |
| [11 environment](11-environment.txt) | Actual locked dependency/tool versions |
| [12 verified hooks](12-hooks-verified.txt) | All hooks pass with serialized evidence writes |
| [Coverage XML](coverage.xml) | 456/458 lines and 116/118 branches covered |
| [Source hashes](source-sha256.txt) | SHA-256 snapshot of runtime, tests, build/configuration, and verifier scripts |

Only the explicit live command invokes the provider. Offline smoke unit tests use scripted responses. The recordings contain no real API keys; local `.env` remains ignored. Existing EPIC-1 evidence remains unchanged.
