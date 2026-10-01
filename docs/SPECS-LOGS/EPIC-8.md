# EPIC-8: Reliability and Run Reporting

Date: 2026-10-01

Status: Planned. This plan is written before implementation. Successful commands and PM evidence will be recorded in `EPIC-8-RUNBOOK.md` and `docs/evidence/epic-8/` after verification.

## Objective

Implement US-8.1–US-8.4 from [SPECS.md](../../SPECS.md#epic-8-reliability-and-run-reporting). Every finished run writes `output/run.json` that validates as a `RunReport`: topic, model, per-phase timings, URL counts, citation count, token and cost totals, status, and one outcome entry per clean URL. The outcome is classified by PD-017 and mapped to the PD-008 exit status. A phase that raises is retried once; a second failure ends the run `failed` with `phase_failed` and still writes the report. An interrupted run resumes from `runs/<run_id>/checkpoints.sqlite` without repeating completed work.

Observability (traces, logs, metrics) stays in EPIC-9. This milestone logs the retry to the run's own JSON Lines file so the acceptance scenario is provable without that stack.

## Current baseline

- `RunReport` in `schemas/responses.py` carries the PRD §8 fields only. It has no `model`, no phase timings, no `urls_fetched`/`urls_thin`/`urls_failed`, no `urls_clean`, no `status_reasons`, no per-URL outcomes, and no cost.
- `output/run.json` is written by `workflows/authoring_run.py` as an `AuthoringSummary`. That file is the citation-gate record. US-8.1 replaces it with a validated `RunReport` at the end of every run.
- `write_run_report` is a labelled stub in `tools/stubs.py`.
- `services/checkpoints.py` returns an `InMemorySaver` and says the SQLite lifecycle belongs to US-8.4. `langgraph-checkpoint-sqlite` is not a dependency.
- `collect_source` already returns the existing source when a file for that rank exists (`tools/corpus_tools.py`). The skip is implemented; this milestone proves it and records the decision.
- The CLI has no `--resume`. Exit status is 0 or 1; exit 3 is named in the module docstring as arriving with US-8.2.
- `RunState.completed_phases` already exists and tools append to it. Nothing reads it to skip a phase.

## Implementation sequence

1. **Contracts.**
   - Extend `RunReport` with the FR-10 and PD-018 fields: `model`, `phase_timings_seconds`, `urls_fetched`, `urls_thin`, `urls_failed`, `urls_clean`, `status_reasons`, `url_outcomes` (rank, url, outcome, reason, source_id), and `cost_usd`. Keep every existing field.
   - Add `UsageRecord` (tokens, reported cost or `None`) and `PhaseTiming` contracts in `schemas/responses.py`.
   - Add `RunLedger` in `services/reporting.py`: phase timings, usage records, and the model price used when a response omits `usage.cost`.

2. **US-8.1: The report.**
   - `build_run_report(run, ledger, *, blog_path, citation_count, duration_seconds, status, status_reasons)` counts outcomes from `RunState.url_outcomes`: extracted, fetched (anything past pending), thin, and failed. The extracted count equals the number of source files.
   - Cost is the sum of reported `usage.cost`. A record with no cost contributes `tokens * price_per_token`.
   - Register `write_run_report` through `create_tool_registry` when a reporting session is bound, replacing the stub. It writes `output/run.json` and returns the validated report. It runs at the end of every run, including a failed one.

3. **US-8.2: Classification.**
   - `classify_outcome(run, *, max_urls, recorded_reasons)` implements PD-017. `no_results`, `no_sources`, `phase_failed`, and `dangling_citations` yield `failed`. Otherwise `too_few_sources` (extracted below 80% of `max_urls`) or `blog_length` yields `degraded`. Everything else is `succeeded`. Every matching reason is recorded.
   - The run command exits 0, 3, or 1 for succeeded, degraded, and failed (PD-008), and 2 for invalid input.

4. **US-8.3: One retry.**
   - `run_phase(name, call, log)` invokes `call`, and on exception appends one JSON Lines record to `runs/<run_id>/logs/execution.log` and invokes `call` once more. A second exception ends the run `failed` with `phase_failed` after `write_run_report` has run.
   - A retry that succeeds continues to the next phase. The retry count is recorded in the report.

5. **US-8.4: Resume.**
   - Record the decision as `docs/adr/0007-per-run-sqlite-checkpointer.md`: per-run SQLite through `langgraph-checkpoint-sqlite`, thread id equal to the run id, PostgreSQL as the upgrade path (PD-019).
   - Add the dependency and `make_sqlite_checkpointer(path)` beside the existing in-memory saver. The file is `runs/<run_id>/checkpoints.sqlite`.
   - `collect_source` keeps skipping a URL whose source file exists; a test interrupts a run after 12 of 30 files and asserts those 12 are not fetched again.
   - Add `--resume <run_id>`. It loads the saved workspace, reads `completed_phases`, and starts at the next phase. A run resumed after search does not search again; a run resumed after the index continues at synthesis.

6. **Demo and verification.**
   - `evaluations/epic8_demo.py` builds an offline corpus, writes the report, classifies succeeded, degraded, and failed cases, retries a phase once, and resumes a run whose search phase is already complete. No model and no network.
   - `scripts/inspect-run-report.py` validates `output/run.json` against `RunReport` and prints the status, reasons, counts, and cost.
   - Run the locked gates, hooks, the EPIC-2 through EPIC-7 demos, the wheel, and a fresh-checkout verification. Record evidence under `docs/evidence/epic-8/` and write `EPIC-8-RUNBOOK.md`.

## Acceptance matrix

| Story | Evidence |
| --- | --- |
| US-8.1 | `output/run.json` validates as `RunReport` and carries topic, run_id, model, phase timings, URL counts, citation count, tokens, cost, status, blog path, and duration |
| US-8.1 | `urls_clean`, `status_reasons`, and one outcome entry per clean URL are present |
| US-8.1 | 28 source files from 30 clean URLs report extracted = 28, equal to the file count |
| US-8.1 | Cost equals the sum of reported `usage.cost`; a response without it is priced from its tokens |
| US-8.2 | 26 of 30 extracted, length and citations clean → `succeeded` |
| US-8.2 | 21 of 30 extracted → `degraded`, reason `too_few_sources` |
| US-8.2 | Enough sources plus `blog_length` → `degraded` |
| US-8.2 | `no_results`, `no_sources`, `phase_failed`, or `dangling_citations` → `failed` with that reason |
| US-8.2 | Exit status is 0, 3, or 1 |
| US-8.3 | A raised exception is logged and the phase runs once more |
| US-8.3 | A successful retry continues; a second failure ends `failed` with `phase_failed` and still writes the report |
| US-8.4 | `--resume` after search does not search again and continues with the saved results |
| US-8.4 | 12 existing source files are not fetched again on resume |
| US-8.4 | Checkpoints are stored in `runs/<run_id>/checkpoints.sqlite` |

## Completion checklist

- [ ] `RunReport` extended with the FR-10 and PD-018 fields.
- [ ] `write_run_report` implemented and registered.
- [ ] Outcome classification and exit-status mapping implemented.
- [ ] Phase retry capped at one, with the report still written on failure.
- [ ] ADR recorded and the per-run SQLite checkpointer configured.
- [ ] `--resume` added and the source-file skip proven.
- [ ] Offline demo, inspect script, strict gates, hooks, prior demos, wheel, and fresh checkout pass.
- [ ] Runbook and evidence committed.

## Scope boundaries

- LangSmith traces, OTLP metrics, and the Grafana dashboard are EPIC-9. The retry log is a plain JSON Lines file in the run workspace.
- Scoring whether every non-obvious claim carries a citation stays in US-10.4.
- The in-memory checkpointer used by the unit tests stays. Only the run command uses the SQLite saver.

## Technical references

- [SPECS.md](../../SPECS.md#epic-8-reliability-and-run-reporting) US-8.1 to US-8.4.
- [PRD.md](../../PRD.md) FR-10, §8, §10, and NFR-1.
- PD-008, PD-017, PD-018, and PD-019 in [SPECS.md](../../SPECS.md).
