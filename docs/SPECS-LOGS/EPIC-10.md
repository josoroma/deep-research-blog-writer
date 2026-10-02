# EPIC-10: Testing and Evaluation

Date: 2026-10-02

Status: DONE. Planned before implementation; implementation and offline acceptance verified. Successful commands and PM evidence are recorded in [EPIC-10-RUNBOOK.md](EPIC-10-RUNBOOK.md) and `docs/evidence/epic-10/`.

## Objective

Implement US-10.1–US-10.5 and PD-021 in [SPECS.md](../../SPECS.md#epic-10-testing-and-evaluation): keep the unit suite offline and deterministic, add an end-to-end workflow test that runs the whole pipeline on fixtures, and evaluate real runs against a golden dataset before every release (PRD.md milestone M5).

## Current baseline

- The offline suite already blocks sockets and strips provider credentials in `tests/conftest.py`, and `evaluations/fakes.py` provides `ScriptedChatModel`. US-10.1 is therefore mostly a matter of proving the two scenarios and closing the gaps, not building the fixture from scratch.
- Every phase is a separate command. `run_search`, `run_fetch`, `run_corpus`, `run_authoring`, and `run_report` are the real entry points; `workflows/cli.py` exposes them as `--search-only`, `--fetch-only`, `--corpus-only`, and `--author-only`. There is no single command that runs the whole pipeline, so the US-10.2 workflow test must drive the phases in order.
- `evaluations/epic9_demo.py` already runs search, corpus, authoring, and reporting with a scripted model, mock HTTP, and a fake provider. It is the closest existing end-to-end harness and the natural base for the US-10.2 test.
- `services/authoring.py` provides `check_blog`, `check_summary`, and `validate_citations`. `services/reporting.py` provides `RunReport`, `classify_outcome`, and `EXIT_STATUS`. `services/corpus.py` provides `read_corpus`.
- `evaluations/fixtures/epic5/` holds packaged HTML fixtures. `evaluations/fetch_fixtures.py` serves them over a mock transport.
- There is no `evaluations/golden_dataset.json`, no `evaluations/scoring.py`, no `evaluations/benchmarks/`, and no `make eval` or `make release` target.
- `pyproject.toml` builds the wheel from `agents`, `tools`, `workflows`, `prompts`, `schemas`, `services`, and `evaluations`, so new evaluation modules ship with the package.

## Implementation sequence

1. **US-10.1 — offline unit suite.** Confirm the two acceptance scenarios against the existing `tests/conftest.py` and `evaluations/fakes.py`. Add a test that proves a provider-reaching call fails and names the attempted call, and a test that proves the suite passes with the three provider keys unset. Extend the fake model only if a scenario needs it.
2. **US-10.2 — full workflow on fixtures.** Add a fixture corpus of 30 URLs and a fake search provider, then a test that drives search → corpus → authoring → report and asserts the workspace contents, zero dangling citations, and the partial-failure case (28 extracted).
3. **US-10.3 — golden dataset and scoring.** Add `evaluations/golden_dataset.json` with the three PD-021 topics, `evaluations/scoring.py` with citation-validity, length, and Definition of Done checks, and a `make eval` target that runs the pipeline per topic and writes `evaluations/benchmarks/<date>-<commit>.json`.
4. **US-10.4 — coverage, groundedness, hallucination rate.** Add the coverage scorer and a claim-level judge that defaults to DeepSeek V4.1 Flash on OpenRouter, with an offline fake judge for tests.
5. **US-10.5 — release gate.** Add `make release VERSION=x.y.z`, which runs `make eval` and tags `vX.Y.Z` only when every golden topic passes every PD-021 threshold.
6. **Verification.** Run locked setup, lint/format/strict typing/tests and coverage, hooks, existing demos, the new offline demo, build, installed-wheel, and committed fresh-checkout verification. Save exact command outputs, coverage, and source hashes. Update only verified EPIC-10 story/task statuses and finalize `docs/SPECS-LOGS/EPIC-10-RUNBOOK.md`.

## Acceptance matrix

| Story | Scenario | Evidence |
| --- | --- | --- |
| US-10.1 | The unit suite passes offline | `make check` with provider keys unset; a test asserting the suite runs with sockets blocked |
| US-10.1 | A unit test that reaches a provider fails | A test that attempts a provider call and asserts the failure names the attempted call |
| US-10.2 | Run the pipeline on fixtures | Workflow test asserting 30 source files, `index.md`, `summary.md`, `blog.md`, `run.json`, zero dangling citations |
| US-10.2 | Survive failed fixtures | Workflow test with one unreachable and one thin fixture asserting `run.json` reports 28 extracted |
| US-10.3 | Score the golden topics | `make eval` runs every PD-021 topic and scores citation validity and length |
| US-10.3 | Check the Definition of Done | Score reports each PRD.md §13 item |
| US-10.3 | Keep benchmark history | `evaluations/benchmarks/<date>-<commit>.json` holds every topic's scores |
| US-10.4 | Score coverage | 18 cited of 27 corpus sources scores 0.67 |
| US-10.4 | Score groundedness and hallucination rate | Judge returns supported share and unsupported/uncited share |
| US-10.5 | A failing evaluation stops the release | `make release` reports the failing topic and creates no tag |
| US-10.5 | A passing evaluation tags the release | `make release` creates `vX.Y.Z` |

## Completion checklist

- [x] Offline unit-suite scenarios verified.
- [x] Full-workflow fixture test and partial-failure test pass.
- [x] Golden dataset, scoring module, and `make eval` implemented.
- [x] Coverage, groundedness, and hallucination-rate scorers implemented.
- [x] `make release` gate implemented and tested.
- [x] Offline demo, meaningful tests, coverage, and hooks pass.
- [x] Build, installed package, existing demos, and fresh checkout pass.
- [x] Runbook, exact command transcripts, snapshots, and hashes saved.
- [x] Implementation and evidence committed.

## Scope boundary

- Live `make eval` runs call the production models and SerpApi. They are opt-in and are not part of the offline gate; the offline tests exercise the scoring and gate logic with fakes.
- The judge model is a real OpenRouter call in production and a fake in tests. No new provider integration is added.
- EPIC-11 (agent documentation) is out of scope.
