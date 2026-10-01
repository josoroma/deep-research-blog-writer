# EPIC-3 acceptance evidence

Verification date: 2026-10-01. See [the runbook](../../SPECS-LOGS/EPIC-3-RUNBOOK.md) for setup, successful commands, the PM demo, and story acceptance.

Each transcript contains the actual command, combined stdout/stderr, and exit code. [commands.jsonl](commands.jsonl) adds UTC completion time, working directory, duration, and expected exit status.

| Evidence | Result |
| --- | --- |
| [01 setup](01-setup.txt) | Locked environment and Git hooks |
| [02 formatting](02-format.txt) | Ruff formatting |
| [03 quality gates](03-quality-gates.txt) | Ruff/strict mypy pass; offline tests pass; coverage above 80% |
| [04 hooks](04-hooks.txt) | Ruff, formatting, strict mypy, and offline pytest hooks pass |
| [05 offline demo](05-demo-epic-3.txt) | Real CLI path: four sub-agents, orchestrator tools, todos, files on disk, containment, marker absent |
| [06 build](06-build.txt) | Source distribution and wheel |
| [07 installed wheel](07-installed-wheel.txt) | Console script and skeleton outside the checkout; invalid topic exits 2 |
| [08 uv version](08-uv-version.txt) | uv version |
| [09 invalid topic](09-invalid-topic.txt) | `deep-research-blog ""` exits 2 and creates no workspace |
| [10 fresh checkout](10-fresh-checkout.txt) | Committed revision passes setup/checks/hooks/demos/build/wheel from a clean clone |
| [Coverage XML](coverage.xml) | Line and branch coverage |
| [Source hashes](source-sha256.txt) | SHA-256 snapshot of runtime, tests, build/configuration, and verifier scripts |

Only the offline demo and the unit suite run here; neither calls a provider. The recordings contain no real API keys; local `.env` remains ignored. Existing EPIC-1 and EPIC-2 evidence remains unchanged.
