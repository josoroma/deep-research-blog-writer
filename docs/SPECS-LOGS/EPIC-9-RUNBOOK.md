# EPIC-9 Runbook: Observability

Date: 2026-10-02, America/Costa_Rica.

Status: DONE. Final verification ran on committed revision `a162c6d117d0f061de7e6a3ca38bd668844e4eca` with no source changes in the working tree: gates, demo, live stack with all eight panels, hosted LangSmith readback, build, installed wheel, hooks, fresh checkout, and source hashes all passed. See [Final verification](#final-verification). The hosted smoke returns a succeeded report and 83 completed spans with run_id/topic metadata, including model, sub-agent, and internal-tool descendants; every hosted span is error-free.

## Delivered behavior

[EPIC-9.md](EPIC-9.md) was written before implementation. The existing research, search, fetch, corpus, authoring, reporting, and resume-inspection entry points now own their observability lifecycle. Each run appends JSON objects to `logs/execution.log` and saves totals to `logs/telemetry.json`. No global execution log is used.

Registered tools retain the run observer across worker threads. Native model callbacks collect usage and reported cost. Fetch backoffs, phase retries, citation repairs, source outcomes, and dangling citation checks populate the ledger. Full `RunReport` totals are kept consistent with that ledger. LangSmith roots and descendants carry run_id/topic metadata. Trace inputs/outputs are hidden at the SDK boundary; logs omit raw HTML and messages, redact credential query parameters, and reject log-path symlinks.

A configured OTLP endpoint creates a private OpenTelemetry provider. CLI completion flushes counters/histograms and shuts it down. An unset endpoint creates no exporter/provider; export failures are recorded without replacing the application result. [ADR 0008](../adr/0008-run-observability.md) explains these choices and the local stack.

## Install and configure

Prerequisites: Python 3.12+, `uv`, Git, and a running Docker engine with Compose for dashboard verification. This delivery used Python 3.12.9, uv 0.11.14, Docker 29.3.1, Compose 5.1.1, LangSmith 0.14.2, and OpenTelemetry SDK/exporter 1.45.0 on macOS ARM64. Docker images are pinned to Collector 0.143.0, Prometheus 3.5.0, and Grafana 12.2.0.

```sh
make setup
make check
make demo-epic-9
make observability-up
make smoke-epic-9
```

`make setup` installs locked dependencies and Git hooks. The first three commands require no provider credentials. The demo uses a loopback OTLP receiver; it makes no hosted model/search/trace requests. `make smoke-epic-9` requires the running local stack and verifies its real HTTP APIs.

For normal CLI runs, add these settings to the Git-ignored `.env` as needed:

```dotenv
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your local key>
LANGSMITH_PROJECT=deep-research-blog-writer
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
TELEMETRY_TIMEOUT_SECONDS=3
```

A blank OTLP endpoint disables metrics export. Tracing defaults to false and requires a key when enabled. Endpoints must be HTTP(S), without embedded credentials, query strings, or fragments. Existing OpenRouter/search/crawler settings still govern their corresponding live workflows. Do not put keys in command arguments or committed evidence.

For hosted trace upload/readback with deterministic fixture work:

```sh
make smoke-langsmith
```

The hosted smoke checks root/descendant metadata, finished spans, model/sub-agent/internal-tool descendants, and saves `logs/hosted_trace_evidence.json` including a LangSmith URL. It uses no live model or search request. This command passed after credentials were configured locally; the key remains outside committed evidence.

The verified successful hosted run is `epic-9-observability-evidence-20261002T162219Z` in project `deep-research-blog-writer`. Open [its LangSmith trace](https://smith.langchain.com/o/b621eff1-7373-525b-af60-627dc06dfb60/projects/p/fb415e04-9ac6-4413-87fa-86b73a256ad2/r/01a0fd6c-7949-7cd3-8ebd-72b982c19c83?poll=true) using an account with access to that workspace. Readback verified one root and 82 descendants: 59 chain spans, six model spans, and 18 tool spans, all completed and carrying the expected run_id/topic. The report status is `succeeded`, dangling citations are zero, and root/descendant errors are all null. The SDK emitted deprecation warnings for `read_run` and `get_run_url`; they did not prevent upload or readback.

The earlier hosted run at `20261002T161127Z` used the default failure fixture, which deliberately cites nonexistent `[S-98]` and `[S-99]`. Its upload/readback succeeded, but its research report failed and its root correctly displayed `run_failed`. The smoke originally checked transport and completion without checking trace errors. It now selects a success scenario with two extracted sources, builds citations and References from the actual saved corpus, requires a succeeded report, and rejects errors on the hosted root or descendants. Readback waits for the observed tool-call counts and all six model calls instead of requiring the failure fixture's span count. Offline regression checks cover both scenarios.

## Final verification

Every command below ran on 2026-10-02 against committed revision `a162c6d`, the first commit that contains the hosted-smoke correction. The working tree had no in-scope source changes. Each exited 0, and each transcript records the exact command, its full output, and its exit status. [commands.jsonl](../evidence/epic-9/commands.jsonl) indexes them with start times and durations.

| Command | Verified result | Transcript |
| --- | --- | --- |
| `make check` | Lock, lint, format, strict typing; 452 passed, 3 live tests excluded; coverage 88.72% | [37-final-check.txt](../evidence/epic-9/37-final-check.txt), [coverage](../evidence/epic-9/coverage-final.xml) |
| `make demo-epic-9` | 97 SDK spans, 77 JSON log records, 90 tokens, 5 retries, 2 dangling citations, real OTLP protobuf received, intended `failed` report | [38-final-demo.txt](../evidence/epic-9/38-final-demo.txt) |
| `make observability-up` | Collector, Prometheus, and Grafana running | [39-final-stack-up.txt](../evidence/epic-9/39-final-stack-up.txt) |
| `make smoke-epic-9` | OTLP delivered; all eight provisioned panels return data: 1 failed run, 90 tokens, $0.06, phase latency, tool calls, 5 retries, URL outcomes, 2 dangling citations; Grafana datasource proxy works | [40-final-stack-smoke.txt](../evidence/epic-9/40-final-stack-smoke.txt) |
| `make smoke-langsmith` | Success scenario; report `succeeded`; 83 spans (59 chain, 6 model, 18 tool), all ended, zero errors, one run_id and topic on every span; zero dangling citations | [41-final-hosted-smoke.txt](../evidence/epic-9/41-final-hosted-smoke.txt), [saved readback](../evidence/epic-9/hosted_trace_evidence_final.json) |
| `make build` | Wheel and source distribution built | [42-final-build.txt](../evidence/epic-9/42-final-build.txt) |
| `sh scripts/verify-epic-9-package.sh` | Installed wheel outside the checkout reproduces traces, logs, usage, retries, and citations; unknown resume exits 2 | [43-final-installed-package.txt](../evidence/epic-9/43-final-installed-package.txt) |
| `make hooks` | All four hooks passed | [44-final-hooks.txt](../evidence/epic-9/44-final-hooks.txt) |
| `sh scripts/verify-epic-9-checkout.sh` | Clean clone of `a162c6d` without `.env`: setup, gates, hooks, demos EPIC-2 to EPIC-9, build, installed wheel | [45-final-fresh-checkout.txt](../evidence/epic-9/45-final-fresh-checkout.txt) |
| `uv run --locked python scripts/verify-source-manifest.py docs/evidence/epic-9/final-source-manifest.json` | 197 source/configuration/fixture hashes match `a162c6d` | [46-final-source-hashes.txt](../evidence/epic-9/46-final-source-hashes.txt) |

The final hosted run is `epic-9-observability-evidence-20261002T164436Z` in project `deep-research-blog-writer`. Open [its LangSmith trace](https://smith.langchain.com/o/b621eff1-7373-525b-af60-627dc06dfb60/projects/p/fb415e04-9ac6-4413-87fa-86b73a256ad2/r/01a0fd80-deac-7ac1-80a8-b5d888464521?poll=true) with an account that can access that workspace. [verification.json](../evidence/epic-9/verification.json) records these results under `final_verification`, with the distribution hashes.

## Earlier verification records

The tables below are kept as history. They cover the initial delivery at `2a587e0` and the hosted-smoke correction before it was committed.

### Successful commands and exact outputs

All listed commands completed with exit 0. Full stdout/stderr and exit statuses are saved in [docs/evidence/epic-9](../evidence/epic-9/); [commands.jsonl](../evidence/epic-9/commands.jsonl) records their start times and durations. The original hosted run's [transport-only summary](../evidence/epic-9/32-hosted-smoke.txt) is preserved separately; the corrected successful hosted smoke has a full transcript.

| Command | Verified result | Transcript |
| --- | --- | --- |
| `make setup` | Locked install; pre-commit installed | [01-setup.txt](../evidence/epic-9/01-setup.txt) |
| `make check` | Lock, lint, format, strict typing; 451 passed, 3 live tests excluded; coverage 88.82% | [22-final-check.txt](../evidence/epic-9/22-final-check.txt) |
| `make check` after hosted-smoke correction | Lock, lint, format, strict typing; 452 passed, 3 live tests excluded; coverage 88.72% | [35-hosted-fix-check.txt](../evidence/epic-9/35-hosted-fix-check.txt) |
| `docker compose -f ops/observability/compose.yaml config --quiet` | Compose configuration valid | [03-compose-config.txt](../evidence/epic-9/03-compose-config.txt) |
| `make observability-up` | All three services running | [04-stack-up.txt](../evidence/epic-9/04-stack-up.txt) |
| `make demo-epic-9` | 97 SDK spans, 77 JSON log records, real OTLP protobuf delivery | [27-final-demo.txt](../evidence/epic-9/27-final-demo.txt) |
| `make smoke-epic-9` | All metric values queryable; eight provisioned panels have data; Grafana proxy works | [28-final-stack-smoke.txt](../evidence/epic-9/28-final-stack-smoke.txt) |
| `make smoke-langsmith` after correction | Hosted upload/readback passed; succeeded report; 83 completed spans with metadata, one root, no errors, zero dangling citations | [33-hosted-success.txt](../evidence/epic-9/33-hosted-success.txt), [saved JSON output](../evidence/epic-9/hosted_trace_evidence.json) |
| `make demo-epic-2 demo-epic-3 demo-epic-4 demo-epic-5 demo-epic-6 demo-epic-7 demo-epic-8` | Existing milestone demonstrations passed | [07-existing-demos.txt](../evidence/epic-9/07-existing-demos.txt) |
| `make build` | Wheel and source distribution built | [25-final-build.txt](../evidence/epic-9/25-final-build.txt) |
| `docker compose -f ops/observability/compose.yaml ps` | Collector :4318, Prometheus :9090, Grafana :3001 bound to 127.0.0.1 | [09-stack-status.txt](../evidence/epic-9/09-stack-status.txt) |
| `sh scripts/verify-epic-9-package.sh` | Installed wheel outside checkout reproduces traces/logs/usage/retries/citations; console rejects missing resume with exit 2 | [26-final-installed-package.txt](../evidence/epic-9/26-final-installed-package.txt) |
| `uv run --locked python scripts/inspect-observability.py runs/epic-9-observability-evidence-20261002T144106Z` | Logs and finished trace spans validate; URL failures include reasons | [31-final-inspect.txt](../evidence/epic-9/31-final-inspect.txt) |
| `make hooks` | All four hooks passed; commit hooks also passed after the source-recovery fix | [12-hooks.txt](../evidence/epic-9/12-hooks.txt), [23-recovery-fix-commit.txt](../evidence/epic-9/23-recovery-fix-commit.txt) |
| `sh scripts/verify-epic-9-checkout.sh` | Committed revision `2a587e0`: clean clone without .env; locked install, all gates/hooks/demos, build, installed wheel | [24-final-fresh-checkout.txt](../evidence/epic-9/24-final-fresh-checkout.txt) |
| `make observability-down` then `make observability-up` | Services stop/restart and retain named volumes | [16-stack-stop.txt](../evidence/epic-9/16-stack-stop.txt), [17-stack-restart.txt](../evidence/epic-9/17-stack-restart.txt) |
| `curl --fail --silent --show-error '<recorded Prometheus query_range URL>'` | Pre-restart token history still returns 90; exact URL/parameters in transcript | [29-history-after-restart.txt](../evidence/epic-9/29-history-after-restart.txt) |
| `uv run --locked python scripts/verify-source-manifest.py docs/evidence/epic-9/source-manifest.json` | 197 source/configuration/fixture hashes match final implementation | [30-final-source-hashes.txt](../evidence/epic-9/30-final-source-hashes.txt) |
| `uv run --locked python scripts/verify-source-manifest.py docs/evidence/epic-9/hosted-fix-source-manifest.json` | 197 current file hashes match the hosted-smoke correction worktree | [36-hosted-fix-source-hashes.txt](../evidence/epic-9/36-hosted-fix-source-hashes.txt) |

Selected output from the quality gate after the hosted-smoke correction:

```text
All checks passed!
Success: no issues found in 98 source files
452 passed, 3 deselected
Required test coverage of 80% reached. Total coverage: 88.72%
```

Selected demo results (timings vary on each run):

```text
trace_spans: 97
log_records: 77
tokens_used: 90
cost_usd: 0.060000000000000005
retries: 5
dangling_citations: 2
metrics_flushed: true
otlp_protobuf_received: true
report_status: failed
```

The failed report is intentional: the demo inserts `[S-98]` and `[S-99]`, which do not exist in the corpus. The demo command exits 0 because it verifies that failure correctly. Tokens and cost are scripted response metadata for six actual fixture model calls; $0.06 is a fixture total, not a real provider charge. Retry count comprises one recovered page timeout, three exhausted 503 backoffs, and one recovered phase retry.

## Five-minute PM demo

1. Run `make demo-epic-9` and copy the printed workspace. Run `uv run --locked python scripts/inspect-observability.py <workspace>`. Show 97 finished SDK trace spans rooted under one run, including `search_agent`, `task`, model calls, and internal corpus tools. Show required log fields and source failure URL/reason records.
2. Run `make observability-up`, then `make smoke-epic-9`. Open its printed dashboard URL at [Grafana](http://127.0.0.1:3001/d/research-runs), using the printed run ID in the Run selector. Viewer access needs no login.
3. Show all eight panels: one failed run, 90 tokens, $0.06 fixture cost, measured phase latency, 27 tool calls by name, five retries, eight URL outcomes, and two dangling citations. Source outcomes are two extracted, two unreachable, and one each robots_disallowed/unsupported_content/too_thin/failed.
4. Open [Prometheus](http://127.0.0.1:9090) and query `research_tokens_total{run_id="<printed-run-id>"}`. Show the value 90. The stack smoke also checked Grafana's datasource proxy and every panel's actual query.
5. Open the [successful hosted LangSmith trace](https://smith.langchain.com/o/b621eff1-7373-525b-af60-627dc06dfb60/projects/p/fb415e04-9ac6-4413-87fa-86b73a256ad2/r/01a0fd6c-7949-7cd3-8ebd-72b982c19c83?poll=true). Expand `task` and `search_agent`, then a model call and `collect_source`. Show that all 83 spans completed without errors and carry the run_id/topic. Show `report_status: succeeded`, `root_error: null`, and `dangling_citations: 0` in the saved evidence. To produce a new hosted run, execute `make smoke-langsmith` and open its returned URL. Use the [saved trace JSON](../evidence/epic-9/hosted_trace_evidence.json) and [dashboard screenshot](../evidence/epic-9/grafana-dashboard.png) when live access is unavailable.

## Acceptance evidence and limits

| Story | Evidence |
| --- | --- |
| US-9.1 | Offline failure scenario: 97 native SDK spans and a failed root; hosted success scenario: 83 spans and no errors. Both verify one root, completed descendants, root ancestry and run_id/topic metadata on every span |
| US-9.2 | Every log line is JSON with timestamp/level/run_id/phase/event; all five required failure categories carry URL/reason; concurrent isolated logs and credential redaction tested |
| US-9.3 | Actual OTLP/HTTP protobuf received/decoded; token/cost/retry/citation values checked; disabled export constructs no provider; failing metrics and trace exporters preserve workflow results |
| US-9.4 | Real Compose services and Prometheus queries; all eight provisioned Grafana panels return data; Grafana datasource proxy verified; ADR committed |

Runs counters count observed CLI/workflow invocations. Milestone stages and resume inspections sharing a workspace carry distinct `mode` labels. Final URL outcome totals update when a previously failed source recovers; failure history remains in the log.

The existing full research CLI is still the agent skeleton, and resume currently inspects the next saved phase. EPIC-9 instruments that existing behavior and the implemented milestone workflows. It does not complete missing pipeline orchestration. Report schema fields remain unchanged. Provider cost unavailable in a response is flagged unavailable; the existing ledger fallback still applies. Hallucination rate belongs to evaluation and is not estimated here.

Run IDs are metric labels for the local low-volume v1 stack. Completed series remain in Collector memory for 24 hours; Collector restarts discard that memory. Prometheus retains samples in its named volume for seven days. The dashboard shows observed cumulative totals; it is not a billing reconciliation. No alert rules were provisioned.

## Stop and restart

```sh
make observability-down
make observability-up
make smoke-epic-9
```

Compose `down` retains named volumes. Avoid `--volumes` when keeping PM evidence. A restart requires a new run to emit current Collector series; older Prometheus samples remain queryable over their recorded time range.

Docker Desktop was started with `docker desktop start` after its daemon stopped. The first pull then stalled in the Desktop credential helper. Public images were pulled using a temporary, task-owned Docker configuration with no credential helper; the user's Docker configuration was unchanged. Normal `make observability-up` subsequently succeeded with cached images. If this occurs locally, start/unlock Docker Desktop and retry the public image pull. No reset or prune was used.


## Delivery evidence

The initial delivery implementation source is `2a587e01e9fdb1b46447d6cb1079a066b7d3fedf` (initial implementation: `670f75b`), with its original hashes in [source-manifest.json](../evidence/epic-9/source-manifest.json). The hosted-smoke correction is verified in the worktree based on `e590c69`; [hosted-fix-source-manifest.json](../evidence/epic-9/hosted-fix-source-manifest.json) records 197 current file hashes. Epic plans, runbooks, and delivery evidence are excluded from both manifests. [verification.json](../evidence/epic-9/verification.json) retains the initial delivery's build/fresh-checkout results and separately records the correction's quality gate and successful, error-free hosted readback.

- [Final demo summary](../evidence/epic-9/demo_evidence.json), [execution log](../evidence/epic-9/execution.log), and [telemetry totals](../evidence/epic-9/telemetry.json).
- [97 finished SDK trace spans](../evidence/epic-9/trace_evidence.json), [decoded OTLP protobuf](../evidence/epic-9/otlp_evidence.json), and [validated full run report](../evidence/epic-9/run.json).
- [83 error-free hosted trace spans read back from LangSmith](../evidence/epic-9/hosted_trace_evidence.json), [succeeded hosted run report](../evidence/epic-9/hosted_success_run.json), [successful hosted command transcript](../evidence/epic-9/33-hosted-success.txt), and [correction quality-gate transcript](../evidence/epic-9/35-hosted-fix-check.txt).
- [Earlier failure-fixture hosted trace](../evidence/epic-9/hosted_failure_trace_evidence.json), preserved to explain the original `run_failed` screenshot.
- [Actual Prometheus/Grafana results](../evidence/epic-9/stack_evidence.json), [rendered dashboard screenshot](../evidence/epic-9/grafana-dashboard.png), and [coverage XML](../evidence/epic-9/coverage.xml).

Run demo commands sequentially. One parallel verification attempt was correctly rejected by the existing second-resolution workspace collision guard; [that failed attempt is preserved](../evidence/epic-9/27-parallel-collision.txt) in the command index. The subsequent sequential replay passed and is the final demo transcript above.
