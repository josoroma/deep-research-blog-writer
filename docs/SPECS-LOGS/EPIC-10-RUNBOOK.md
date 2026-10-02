# EPIC-10 Runbook: Testing and Evaluation

Date: 2026-10-02, America/Costa_Rica.

Status: DONE. Implementation and offline acceptance verified on committed revision `20f486d7351d4ab12282c2251e6812c9c710c32e` with no in-scope working-tree changes. The offline suite, the fixture pipeline, the scoring module, the offline eval, the release gate, the build, the installed wheel, the hooks, and a fresh checkout all passed.

## Delivered behavior

[EPIC-10.md](EPIC-10.md) was written before implementation. The unit suite stays offline and deterministic, the whole pipeline runs on fixtures, and releases are scored against the PD-021 golden dataset before a tag is created.

- **US-10.1 — offline unit suite.** `tests/conftest.py` already stripped provider credentials and replaced `socket.socket.connect` with a failing stub. `tests/test_offline_suite.py` now proves both scenarios: the suite runs with `OPENROUTER_API_KEY`, `SERPER_API_KEY`, and `SERPAPI_API_KEY` unset and sockets blocked, and a provider-reaching call fails and names the attempted call.
- **US-10.2 — full workflow on fixtures.** `evaluations/workflow_fixtures.py` provides 30 fixture URLs, a fake search provider, a mock transport, and a scripted model. `tests/test_workflow_end_to_end.py` drives search → corpus → authoring → report and asserts the workspace contents, zero dangling citations, and the partial-failure case.
- **US-10.3 — golden dataset and scoring.** `evaluations/golden_dataset.json` lists the three PD-021 topics. `evaluations/scoring.py` scores citation validity, length, coverage, groundedness, hallucination rate, and each PRD.md §13 Definition of Done item. `make eval` runs the pipeline per topic and writes `evaluations/benchmarks/<date>-<commit>.json`.
- **US-10.4 — coverage, groundedness, hallucination rate.** `coverage` is the share of corpus sources cited. `evaluations/judge.py` is the claim-level judge, defaulting to DeepSeek V4.1 Flash on OpenRouter; tests inject `AlwaysSupportedJudge`.
- **US-10.5 — release gate.** `make release VERSION=x.y.z` runs `make eval` and creates `vX.Y.Z` only when every golden topic passes every PD-021 threshold. A failing topic is reported and no tag is created.

## Install and configure

Prerequisites: Python 3.12+, `uv`, and Git. The offline commands need no credentials. Live `make eval` and `make release` need `OPENROUTER_API_KEY` and `SERPAPI_API_KEY` in the Git-ignored `.env`.

```sh
make setup
make check
make demo-epic-10
make eval-offline
```

`make eval-offline` runs the fixture pipeline for every golden topic and writes a benchmark. It needs no keys and no network. `make demo-epic-10` scores one fixture topic and shows both a passing and a blocked release decision.

For a live evaluation and a gated release:

```sh
make eval
make release VERSION=1.0.0
```

`make eval` uses the production models and SerpApi and writes `evaluations/benchmarks/<date>-<commit>.json`. `make release` runs `make eval` and tags only when every topic passes. Use `--dry-run` to see the decision without tagging.

## Successful commands and exact outputs

All listed commands completed with exit 0 unless noted. Full stdout/stderr and exit statuses are saved in [docs/evidence/epic-10](../evidence/epic-10/); [commands.jsonl](../evidence/epic-10/commands.jsonl) records their start times and durations.

| Command | Verified result | Transcript |
| --- | --- | --- |
| `make setup` | Locked install; pre-commit installed | [01-setup.txt](../evidence/epic-10/01-setup.txt) |
| `make check` | Lock, lint, format, strict typing; 491 passed, 3 live tests excluded; coverage 88.69% | [02-check.txt](../evidence/epic-10/02-check.txt), [coverage](../evidence/epic-10/coverage.xml) |
| `uv run pytest tests/test_offline_suite.py tests/test_workflow_end_to_end.py tests/test_evaluation.py --no-cov` | 39 new tests passed | [03-offline-suite.txt](../evidence/epic-10/03-offline-suite.txt) |
| `make demo-epic-10` | Fixture topic scored; coverage 1.0, groundedness 1.0, hallucination 0.0, Definition of Done passed; release gate shown passing and blocked | [04-demo.txt](../evidence/epic-10/04-demo.txt) |
| `make eval-offline` | Every golden topic scored and a benchmark written | [05-eval-offline.txt](../evidence/epic-10/05-eval-offline.txt), [benchmark](../evidence/epic-10/benchmark-offline.json) |
| `python -m evaluations.release --version 1.0.0 --benchmark <failing> --dry-run` | Exit 1; reports `agentic-ai-frameworks: coverage_min_0.5`; no tag | [06-release-blocked.txt](../evidence/epic-10/06-release-blocked.txt) |
| `python -m evaluations.release --version 1.0.0 --benchmark <passing> --dry-run` | Exit 0; every threshold passed; tag `v1.0.0` | [07-release-passing.txt](../evidence/epic-10/07-release-passing.txt) |
| `make build` | Wheel and source distribution built | [08-build.txt](../evidence/epic-10/08-build.txt) |
| `sh scripts/verify-epic-10-package.sh` | Installed wheel outside the checkout scores a fixture run and exercises the release gate | [09-installed-package.txt](../evidence/epic-10/09-installed-package.txt) |
| `make hooks` | All four hooks passed | [10-hooks.txt](../evidence/epic-10/10-hooks.txt) |
| `make demo-epic-2 … demo-epic-9` | Existing milestone demonstrations passed | [11-existing-demos.txt](../evidence/epic-10/11-existing-demos.txt) |
| `sh scripts/verify-epic-10-checkout.sh` | Clean clone of `20f486d` without `.env`: setup, gates, hooks, demos EPIC-2 to EPIC-10, `make eval-offline`, build, installed wheel | [12-fresh-checkout.txt](../evidence/epic-10/12-fresh-checkout.txt) |
| `uv run python scripts/verify-source-manifest.py docs/evidence/epic-10/source-manifest.json` | 211 source/configuration/fixture hashes match `20f486d` | [13-source-hashes.txt](../evidence/epic-10/13-source-hashes.txt) |

Selected output from the quality gate:

```text
All checks passed!
Success: no issues found in 108 source files
491 passed, 3 deselected
Required test coverage of 80% reached. Total coverage: 88.69%
```

Selected demo results:

```text
coverage: 1.0
groundedness: 1.0
hallucination_rate: 0.0
definition_of_done: all true
passed: true
release_passing_tagged: true
release_blocked_failures: ["agentic-ai-frameworks: coverage_min_0.5"]
```

## Five-minute PM demo

1. Run `make demo-epic-10`. Show the fixture topic scored: citation validity true, 2,128 words, coverage 1.0, groundedness 1.0, hallucination rate 0.0, and every Definition of Done item true.
2. Show the two release decisions in the same output: a passing benchmark that would tag `v1.0.0`, and a blocked benchmark that reports `coverage_min_0.5` and creates no tag.
3. Run `make eval-offline` and open the printed benchmark under `evaluations/benchmarks/`. Show one entry per PD-021 topic with its thresholds and pass verdict.
4. Run `uv run --locked pytest tests/test_offline_suite.py -q` and show the two US-10.1 scenarios: the suite runs with no keys and blocked sockets, and a provider-reaching call fails and names the attempt.
5. Run `uv run --locked pytest tests/test_workflow_end_to_end.py -q` and show the two US-10.2 scenarios: the full pipeline writes every artifact with zero dangling citations, and the partial-failure run reports 28 extracted of 30.

## Acceptance evidence and limits

| Story | Evidence |
| --- | --- |
| US-10.1 | `tests/test_offline_suite.py`: keys unset, sockets blocked, provider call fails and names the attempt |
| US-10.2 | `tests/test_workflow_end_to_end.py`: 30 source files, `index.md`, `summary.md`, `blog.md`, `run.json`, zero dangling citations; partial failure reports 28 extracted |
| US-10.3 | `evaluations/golden_dataset.json`, `evaluations/scoring.py`, `make eval` writing `evaluations/benchmarks/<date>-<commit>.json` |
| US-10.4 | `coverage` returns 0.67 for 18 of 27; `groundedness_and_hallucination` returns the supported and unsupported shares; `evaluations/judge.py` defaults to DeepSeek V4.1 Flash |
| US-10.5 | `make release` blocks a failing benchmark with exit 1 and tags a passing one with `vX.Y.Z` |

Limits:

- Live `make eval` and `make release` call the production models and SerpApi. They are opt-in and are not part of the offline gate. The offline tests exercise the same scoring and gate logic with fakes.
- The judge is a real OpenRouter call in production. The offline suite and the demo use `AlwaysSupportedJudge`, so groundedness and hallucination rate are 1.0 and 0.0 there by construction; the live path is where the judge's own verdicts matter.
- Coverage counts distinct cited source ids against the corpus. A blog that cites one source many times still counts as one.
- The release gate reads the newest benchmark file. Run `make eval` immediately before `make release` so the benchmark matches the revision being tagged.

## Delivery evidence

The implementation source is `20f486d7351d4ab12282c2251e6812c9c710c32e`, with its hashes in [source-manifest.json](../evidence/epic-10/source-manifest.json). Epic plans, runbooks, and delivery evidence are excluded from the manifest. [verification.json](../evidence/epic-10/verification.json) records the test counts, coverage, distribution hashes, and the release-gate outcomes.

- [Offline demo summary](../evidence/epic-10/04-demo.txt) and [offline benchmark](../evidence/epic-10/benchmark-offline.json).
- [Blocked release decision](../evidence/epic-10/06-release-blocked.txt) and [passing release decision](../evidence/epic-10/07-release-passing.txt).
- [Fresh-checkout transcript](../evidence/epic-10/12-fresh-checkout.txt) and [installed-wheel transcript](../evidence/epic-10/09-installed-package.txt).
- [Coverage XML](../evidence/epic-10/coverage.xml) and [source hashes](../evidence/epic-10/13-source-hashes.txt).
