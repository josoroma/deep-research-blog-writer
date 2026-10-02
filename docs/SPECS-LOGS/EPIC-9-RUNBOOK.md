# EPIC-9 Runbook: Observability

Date: 2026-10-02, America/Costa_Rica.

Status: implementation and local acceptance verified. Final committed-checkout verification is in progress. Hosted LangSmith readback has not run: `LANGSMITH_API_KEY` is absent locally. Native LangSmith SDK traces were verified with a recording client; the hosted smoke is implemented and available when credentials are configured.

## Delivered behavior

[EPIC-9.md](../../EPIC-9.md) was written before implementation. The existing research, search, fetch, corpus, authoring, reporting, and resume-inspection entry points now own their observability lifecycle. Each run appends JSON objects to `logs/execution.log` and saves totals to `logs/telemetry.json`. No global execution log is used.

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

The hosted smoke checks root/descendant metadata, finished spans, model/sub-agent/internal-tool descendants, and saves `logs/hosted_trace_evidence.json` including a LangSmith URL. It uses no live model or search request. This command is credential-dependent and is not listed as passed in this delivery.

## Successful commands and exact outputs

All listed commands completed with exit 0. Full stdout/stderr and exit statuses are saved in [docs/evidence/epic-9](../evidence/epic-9/); [commands.jsonl](../evidence/epic-9/commands.jsonl) records their start times and durations.

| Command | Verified result | Transcript |
| --- | --- | --- |
| `make setup` | Locked install; pre-commit installed | [01-setup.txt](../evidence/epic-9/01-setup.txt) |
| `make check` | Lock, lint, format, strict typing; 450 passed, 3 live tests excluded; coverage 88.82% | [02-check.txt](../evidence/epic-9/02-check.txt) |
| `docker compose -f ops/observability/compose.yaml config --quiet` | Compose configuration valid | [03-compose-config.txt](../evidence/epic-9/03-compose-config.txt) |
| `make observability-up` | All three services running | [04-stack-up.txt](../evidence/epic-9/04-stack-up.txt) |
| `make demo-epic-9` | 97 SDK spans, 77 JSON log records, real OTLP protobuf delivery | [05-offline-demo.txt](../evidence/epic-9/05-offline-demo.txt) |
| `make smoke-epic-9` | All metric values queryable; eight provisioned panels have data; Grafana proxy works | [06-stack-smoke.txt](../evidence/epic-9/06-stack-smoke.txt) |
| `make demo-epic-2 demo-epic-3 demo-epic-4 demo-epic-5 demo-epic-6 demo-epic-7 demo-epic-8` | Existing milestone demonstrations passed | [07-existing-demos.txt](../evidence/epic-9/07-existing-demos.txt) |
| `make build` | Wheel and source distribution built | [08-build.txt](../evidence/epic-9/08-build.txt) |
| `docker compose -f ops/observability/compose.yaml ps` | Collector :4318, Prometheus :9090, Grafana :3001 bound to 127.0.0.1 | [09-stack-status.txt](../evidence/epic-9/09-stack-status.txt) |
| `sh scripts/verify-epic-9-package.sh` | Installed wheel outside checkout reproduces traces/logs/usage/retries/citations; console rejects missing resume with exit 2 | [10-installed-package.txt](../evidence/epic-9/10-installed-package.txt) |
| `uv run --locked python scripts/inspect-observability.py runs/epic-9-observability-evidence-20261002T141145Z` | Logs and finished trace spans validate; URL failures include reasons | [11-inspect-demo.txt](../evidence/epic-9/11-inspect-demo.txt) |

Selected output from the quality gate:

```text
All checks passed!
Success: no issues found in 98 source files
450 passed, 3 deselected
Required test coverage of 80% reached. Total coverage: 88.82%
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
5. Show the [saved dashboard screenshot](../evidence/epic-9/grafana-dashboard.png) and committed snapshots when a live stack is unavailable. Hosted LangSmith navigation is a separate demo after the key is configured; run `make smoke-langsmith` and open its returned URL.

## Acceptance evidence and limits

| Story | Evidence |
| --- | --- |
| US-9.1 | 97 native SDK spans, one root, completed descendants, root ancestry and run_id/topic metadata on every span; hosted smoke implemented but not executed |
| US-9.2 | Every log line is JSON with timestamp/level/run_id/phase/event; all five required failure categories carry URL/reason; concurrent isolated logs and credential redaction tested |
| US-9.3 | Actual OTLP/HTTP protobuf received/decoded; token/cost/retry/citation values checked; disabled export constructs no provider; failing metrics and trace exporters preserve workflow results |
| US-9.4 | Real Compose services and Prometheus queries; all eight provisioned Grafana panels return data; Grafana datasource proxy verified; ADR committed |

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
