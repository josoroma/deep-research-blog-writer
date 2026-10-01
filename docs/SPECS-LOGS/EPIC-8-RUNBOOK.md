# EPIC-8 Runbook: Reliability and Run Reporting

Status: verified offline on 2026-10-01. Every finished run writes `output/run.json`
that validates as a `RunReport`. The outcome follows PD-017 and maps to the
PD-008 exit status. A phase that raises is retried once, and an interrupted run
resumes from `runs/<run_id>/checkpoints.sqlite`.

## What a PM sees

- `output/run.json` with the topic, model, per-phase timings, URL counts, one
  outcome entry per clean URL, the citation count, and token and cost totals.
- A status of `succeeded`, `degraded`, or `failed`, with the reason, and an exit
  status of 0, 3, or 1.
- A phase that failed once, was logged, and recovered on its single retry.
- `checkpoints.sqlite` inside the run workspace, and a resume that starts at the
  first phase not yet recorded.

## Commands that passed

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy --strict
uv run --locked pytest -q -m 'not live' -p no:cacheprovider
make demo-epic-8
make hooks
make build
sh scripts/verify-epic-8-package.sh
```

Result: 438 offline tests passed, coverage 92.50%, strict typing clean, and the
installed wheel reproduced the report, the classification, the retry, and the
checkpoint outside the checkout.

## Demo

```sh
make setup
make demo-epic-8
uv run --locked python scripts/inspect-run-report.py runs/<run-id>
```

`make demo-epic-8` builds an offline corpus, writes the report, classifies the
outcome, recovers a phase that fails once, and writes the per-run checkpoint.
No model and no network are used.

## Evidence

| Check | Result |
| --- | --- |
| Report validates as `RunReport` with the FR-10 and PD-018 fields | passed |
| Extracted count equals the source files | passed |
| Cost sums reported usage and prices a missing cost from tokens | passed |
| 26 of 30 extracted classifies `succeeded` | passed |
| 21 of 30 extracted classifies `degraded` / `too_few_sources` | passed |
| `blog_length` classifies `degraded`; failure reasons classify `failed` | passed |
| A raised phase is logged and retried once | passed |
| Resume starts at the first unrecorded phase | passed |
| Checkpoint stored at `runs/<run_id>/checkpoints.sqlite` | passed |
| Installed wheel, exit 2 for an unknown run | passed |
