# EPIC-3 implementation and PM demonstration runbook

Verified: 2026-10-01. US-3.1–US-3.4 are implemented. The plan was written in [EPIC-3.md](EPIC-3.md) before implementation. [Raw evidence](../../docs/evidence/epic-3/README.md) records the commands, output, exit codes, coverage, and source hashes.

Delivered: a validated, collision-safe run workspace; one `create_deep_agent` orchestrator with exactly four sub-agents and the PD-005 tool assignment; typed offline stub tools; real-disk persistence through `FilesystemBackend(virtual_mode=True)`; and the `deep-research-blog` console script.

This milestone is the M1 skeleton. Search, normalization, fetching, extraction, source-file writing, indexing, synthesis, citation validation, the run report, retries, the SQLite checkpointer, and `--resume` remain in their specified later epics. The stub tools return fixed typed output and write nothing, so the demo proves the wiring, not a researched article.

## Install, configure, and run

Prerequisites: Git, Make, and uv. From the repository root, these successful commands reproduce the local setup and offline demonstration:

```sh
uv python install 3.12
make setup
make check
make demo-epic-3
```

The offline checks and demo require no credentials. The demo runs the real CLI path with a scripted fake model into a temporary `runs/` root, so it never calls a provider.

## Successful commands and results

All commands in this table were run successfully; links preserve their actual outputs.

| Command | Observed result | Transcript |
| --- | --- | --- |
| `make setup` | Locked dependencies and Git hook installed | [01](../../docs/evidence/epic-3/01-setup.txt) |
| `make format` | Ruff formatting applied | [02](../../docs/evidence/epic-3/02-format.txt) |
| `make check` | Lock/Ruff/format checks pass; strict mypy passes 47 files; 205 tests pass, one live test deselected; 98.02% coverage | [03](../../docs/evidence/epic-3/03-quality-gates.txt) |
| `make hooks` | Ruff, formatting, strict mypy, and offline pytest hooks pass | [04](../../docs/evidence/epic-3/04-hooks.txt) |
| `make demo-epic-3` | Four sub-agents, orchestrator tools, nine todos, files on disk, containment, marker absent | [05](../../docs/evidence/epic-3/05-demo-epic-3.txt) |
| `make build` | Wheel and source distribution built | [06](../../docs/evidence/epic-3/06-build.txt) |
| `sh scripts/verify-epic-3-package.sh` | Installed wheel: skeleton, four sub-agents, containment, and console script outside the checkout | [07](../../docs/evidence/epic-3/07-installed-wheel.txt) |
| `uv --version` | uv version | [08](../../docs/evidence/epic-3/08-uv-version.txt) |
| `uv run --locked deep-research-blog ""` | Exit 2 with the topic rule; no workspace created | [09](../../docs/evidence/epic-3/09-invalid-topic.txt) |
| `sh scripts/verify-epic-3-checkout.sh` | Fresh committed clone passes setup, checks, hooks, both demos, build, and installed-wheel verification | [10](../../docs/evidence/epic-3/10-fresh-checkout.txt) |

The combined line/branch coverage is 98.02%, above the retained 80% floor. [Coverage XML](../../docs/evidence/epic-3/coverage.xml) records the totals. Offline tests deny socket connections and clear credential/configuration environment overrides for isolation.

## PM demo, about 10 minutes

1. Open [the plan](EPIC-3.md), [ADR 0003](../../docs/adr/0003-filesystem-backend-for-run-workspace.md), [ADR 0004](../../docs/adr/0004-disable-general-purpose-subagent.md), and the acceptance table below to establish the delivered scope.
2. Run `make demo-epic-3`. Show:
   - `subagents`: `search_agent` → `google_search`, `research_agent` → `collect_source`, and `analyst_agent`/`writer_agent` with no extra tools;
   - `orchestrator_tools`: `normalize_results`, `build_index`, `validate_citations`, `write_run_report`;
   - `bound_tools`: the tools each agent was actually offered at its model call, including `write_todos` for the orchestrator and no `task` for any sub-agent;
   - `todos`: the nine pipeline phases;
   - `files_on_disk`: `request.json`, `research/summary.md`, and `output/blog.md` written by the real filesystem tools;
   - `marker_in_model_contexts: false`: the stub fetch HTML marker never reached a model;
   - `general_purpose_rejected: true` and `containment_refused: true`.
3. Run `uv run --locked deep-research-blog ""` to show exit 2 and that no `runs/` directory is created.
4. Run `make check` and `make hooks`. Show 205 passing offline tests, strict typing, and coverage above 80%.
5. Run `make build` then `sh scripts/verify-epic-3-package.sh`. Show the console script and the skeleton working from the installed wheel outside the checkout.
6. Use the acceptance table to walk through all four stories. The fresh-checkout transcript in the delivery section establishes reproducibility from committed files.

## Acceptance matrix

| Story | Delivered acceptance | Evidence of done |
| --- | --- | --- |
| US-3.1 | Run id is the topic slug, a hyphen, and a UTC timestamp; `runs/<run_id>/` is created; the validated request is stored; an invalid topic creates nothing | [Workspace tests](../../tests/test_workspace.py), [demo](../../docs/evidence/epic-3/05-demo-epic-3.txt) |
| US-3.2 | Four sub-agents with the PD-005 tools and catalog prompts; the orchestrator holds the deterministic tools and never fetch/extract/collect; raw HTML stays out of every model context; phases are todos; the skeleton runs end to end | [Agent tests](../../tests/test_deep_agent.py), [demo](../../docs/evidence/epic-3/05-demo-epic-3.txt), [SKILL.md](../../skills/deep-research-blog-writer/SKILL.md) |
| US-3.3 | Files reach disk before the next model step; traversal and symlink escapes are refused; ADR 0003 recorded | [Backend tests](../../tests/test_workspace_backend.py), [ADR 0003](../../docs/adr/0003-filesystem-backend-for-run-workspace.md) |
| US-3.4 | The console script starts a run, prints run_id/workspace/status/blog_path, honors budget overrides, and rejects an invalid topic with exit 2 | [CLI tests](../../tests/test_cli.py), [invalid-topic transcript](../../docs/evidence/epic-3/09-invalid-topic.txt) |

## Delivery and reproducibility

Implementation commit: `b13ca0a6ff6cd5c6361297ccd5c290269bb07ccd`. A fresh temporary clone of that revision passed setup, all quality gates/hooks, both offline demos, build, and installed-wheel verification with no local `.env`, and reported no tracked-file changes. Final documentation and evidence updates are committed separately; application, configuration, and test hashes remain the same.

Reproduce the committed checkout without local `.env` files using:

```sh
sh scripts/verify-epic-3-checkout.sh
```

This script clones committed HEAD into a temporary directory, runs setup, quality gates, hooks, both offline demos, build, and installed-wheel verification, then checks for tracked-file changes. It removes the temporary clone when finished.

Verify the tested application/configuration/test files against the recorded snapshot:

```sh
shasum -a 256 -c docs/evidence/epic-3/source-sha256.txt
```

The local quality, hook, demo, and wheel checks are observed evidence. Hosted GitHub Actions execution requires a configured remote and push; this delivery does not claim a hosted CI run.
