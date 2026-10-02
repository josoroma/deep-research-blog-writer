# EPIC-11 Runbook: Agent Documentation

Date: 2026-10-02, America/Costa_Rica.

Status: DONE. Implementation and offline acceptance verified on committed revision `40b676ad8d0b06d5b7dc2d9bd88e5700e91c9e59` with no in-scope working-tree changes. The documentation check, the offline suite, the demo, the offline eval, the build, the installed wheel, the hooks, and a fresh checkout all passed.

## Delivered behavior

[EPIC-11.md](EPIC-11.md) was written before implementation. Every agent now has human documentation under `docs/architecture/agents/`, in the PD-022 format, and a test keeps it complete.

- **US-11.1 — skill files.** `docs/architecture/agents/<agent>/skill.md` exists for the orchestrator and each of its four sub-agents. Each file carries the eleven PD-022 sections in order — Purpose, Capabilities, Non-Capabilities, Inputs, Outputs, Available Tools, Security, Observability, Evaluation Criteria, Failure Modes, and Example — and its Inputs and Outputs name the Pydantic contract types the agent consumes and produces.
- **US-11.1 — contracts.** `docs/architecture/agents/<agent>/contract.md` states the agent's input, output, success criteria, and failure conditions. Every success criterion cites the `PRD.md` or `SPECS.md` item it comes from.
- **Index.** `docs/architecture/README.md` lists the five agents with their roles, tools, and links, and explains how the pieces fit: agents orchestrate, prompts come from the catalog, HTTP stays in services, state is typed, and sources are immutable.
- **Documentation check.** `tests/test_agent_docs.py` reads `docs/architecture/agents/` and asserts every agent has both files, that `skill.md` carries every PD-022 section in order and names contract types, that `contract.md` states input, output, success criteria, and failure conditions, and that each success criterion is traceable to `PRD.md` or `SPECS.md`.

The documents describe the agents as they exist today. They add no tools, change no prompts, and alter no runtime behavior. The `skill.md` files are human documentation, not runtime skills.

## Install and configure

Prerequisites: Python 3.12+, `uv`, and Git. The documentation check needs no credentials and no network.

```sh
make setup
make check
uv run --locked pytest tests/test_agent_docs.py -q --no-cov
```

## Successful commands and exact outputs

All listed commands completed with exit 0. Full stdout/stderr and exit statuses are saved in [docs/evidence/epic-11](../evidence/epic-11/); [commands.jsonl](../evidence/epic-11/commands.jsonl) records their start times and durations.

| Command | Verified result | Transcript |
| --- | --- | --- |
| `uv sync --locked` | Locked install | [01-setup.txt](../evidence/epic-11/01-setup.txt) |
| `make check` | Lock, lint, format, strict typing; 522 passed, 3 live tests excluded; coverage 88.69% | [02-check.txt](../evidence/epic-11/02-check.txt), [coverage](../evidence/epic-11/coverage.xml) |
| `uv run pytest tests/test_agent_docs.py -q --no-cov` | 31 documentation checks passed | [03-agent-docs.txt](../evidence/epic-11/03-agent-docs.txt) |
| `make demo-epic-10` | Fixture topic scored; coverage 1.0, groundedness 1.0, hallucination 0.0; release gate shown passing and blocked | [04-demo.txt](../evidence/epic-11/04-demo.txt) |
| `make eval-offline` | Every golden topic scored and a benchmark written | [05-eval-offline.txt](../evidence/epic-11/05-eval-offline.txt) |
| `make build` | Wheel and source distribution built | [06-build.txt](../evidence/epic-11/06-build.txt) |
| `sh scripts/verify-epic-10-package.sh` | Installed wheel outside the checkout scores a fixture run and exercises the release gate | [07-installed-package.txt](../evidence/epic-11/07-installed-package.txt) |
| `make hooks` | All four hooks passed | [08-hooks.txt](../evidence/epic-11/08-hooks.txt) |
| `make demo-epic-2 … demo-epic-9` | Existing milestone demonstrations passed | [09-existing-demos.txt](../evidence/epic-11/09-existing-demos.txt) |
| `sh scripts/verify-epic-11-checkout.sh` | Clean clone of `40b676a` without `.env`: setup, gates, hooks, the agent-docs check, demos EPIC-2 to EPIC-10, `make eval-offline`, build, installed wheel | [10-fresh-checkout.txt](../evidence/epic-11/10-fresh-checkout.txt) |
| `uv run python scripts/verify-source-manifest.py docs/evidence/epic-11/source-manifest.json` | 225 source/configuration/fixture hashes match `40b676a` | [11-source-hashes.txt](../evidence/epic-11/11-source-hashes.txt) |

Selected output from the quality gate:

```text
All checks passed!
Success: no issues found in 108 source files
522 passed, 3 deselected
Required test coverage of 80% reached. Total coverage: 88.69%
```

Selected output from the documentation check:

```text
31 passed in 0.03s
```

## Five-minute PM demo

1. Open `docs/architecture/README.md` and show the five agents with their roles, tools, and links to each `skill.md` and `contract.md`.
2. Open `docs/architecture/agents/orchestrator/skill.md` and show the eleven PD-022 sections in order, with Inputs and Outputs naming the Pydantic contract types.
3. Open `docs/architecture/agents/writer_agent/contract.md` and show the input, output, success criteria table with its `PRD.md` and `SPECS.md` sources, and the failure conditions.
4. Run `uv run --locked pytest tests/test_agent_docs.py -q --no-cov` and show all 31 checks pass.
5. Break the documentation on purpose — delete a section heading from one `skill.md` — rerun the check, and show it fails and names the missing section. Restore the file.

## Acceptance evidence and limits

| Story | Evidence |
| --- | --- |
| US-11.1 — every agent has a skill file | `tests/test_agent_docs.py` asserts each of the five agents has `skill.md` with all eleven PD-022 sections in order, and that Inputs and Outputs name contract types |
| US-11.1 — every agent has a contract | `tests/test_agent_docs.py` asserts each agent's `contract.md` states input, output, success criteria, and failure conditions, and that each success criterion cites `PRD.md` or `SPECS.md` |

Limits:

- The documents are prose. The check verifies structure, section order, contract-type names, and traceable sources; it does not verify that the prose is accurate. Accuracy is maintained by review and by the runtime tests that exercise the same behavior.
- The `skill.md` files are not loaded at run time. The agents load their prompts from `prompts/` through the catalog; nothing under `docs/architecture/` is imported.
- The check reads the repository layout directly. It is part of the offline suite and runs in `make check` and in the pre-commit hooks.

## Delivery evidence

The implementation source is `40b676ad8d0b06d5b7dc2d9bd88e5700e91c9e59`, with its hashes in [source-manifest.json](../evidence/epic-11/source-manifest.json). Epic plans, runbooks, and delivery evidence are excluded from the manifest. [verification.json](../evidence/epic-11/verification.json) records the test counts, coverage, distribution hashes, and the documented agents.

- [Documentation check transcript](../evidence/epic-11/03-agent-docs.txt) and [quality gate transcript](../evidence/epic-11/02-check.txt).
- [Fresh-checkout transcript](../evidence/epic-11/10-fresh-checkout.txt) and [installed-wheel transcript](../evidence/epic-11/07-installed-package.txt).
- [Coverage XML](../evidence/epic-11/coverage.xml) and [source hashes](../evidence/epic-11/11-source-hashes.txt).
