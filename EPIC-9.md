# EPIC-9: Observability

Date: 2026-10-02

Status: Planned before implementation; implementation and local acceptance verified. Final committed-checkout verification is in progress. Hosted LangSmith readback requires a locally configured key and has not been run. Verification and the final runbook are recorded under `docs/SPECS-LOGS/` with supporting evidence under `docs/evidence/epic-9/`.

## Objective

Implement US-9.1–US-9.4 and PD-020 in [SPECS.md](SPECS.md#epic-9-observability): identifiable LangSmith traces, per-run JSON Lines logs, optional OTLP metrics, and a runnable local Collector → Prometheus → Grafana stack. Instrument the existing CLI/workflows, registered tools, model calls, retries, URL outcomes, and reporting rather than relying on manufactured counters.

## Implementation sequence

1. Add validated tracing/metrics settings and locked OpenTelemetry dependencies. Tracing is explicitly configured; metrics export stays disabled unless `OTEL_EXPORTER_OTLP_ENDPOINT` is supplied. Keep clients, keys, and exporter state outside agent/checkpoint state.
2. Implement a run-owned observability service. Append timestamped, thread-safe JSON records to `logs/execution.log` with level, run_id, phase, and event. Log source failures with sanitized URL and reason; redact credentials and avoid recording raw HTML or entire model messages. Start/finish events and failure events must also cover exceptional exits.
3. Bind registered internal tools to the active run observer; collect tool counts, phase timings, source outcomes, and fetch/phase retry events. Add model callback accounting for token usage and reported cost. Preserve application results and existing report contracts, and keep report totals consistent with the collected ledger.
4. Configure LangSmith root traces with run_id/topic metadata, propagate that metadata and context into native model/sub-agent/tool spans, and flush tracing before CLI exit. Verify the hierarchy offline against a local recording endpoint; when credentials are configured, execute one hosted smoke and inspect its saved trace metadata/children.
5. Record OpenTelemetry counters/histograms for runs by status, tokens, cost, run/phase latency, tool calls, retries, URL outcomes, and dangling citations. Use a run-owned SDK provider and OTLP/HTTP exporter only when configured; flush short-lived CLI runs, handle unavailable telemetry without changing the research result, and verify real protobuf delivery with an offline local receiver.
6. Add pinned Docker Compose services under `ops/observability/`, Collector OTLP receivers and Prometheus exporter, Prometheus scrape configuration, and a provisioned Grafana datasource/dashboard covering all eight PD-020 panels. Bind ports locally, persist Prometheus/Grafana state in named volumes, and document start/stop commands without deleting data. Record an ADR.
7. Add a repeatable offline PM demo using actual tools and the agent hierarchy, a local OTLP receiver, and inspectable logs/trace/metric snapshots. Add a stack smoke that checks readiness, sends real OTLP metrics, queries Prometheus, and verifies Grafana provisioning. Keep hosted tracing and Docker checks separate from network-free quality gates.
8. Run locked setup, lint/format/strict typing/tests and coverage, hooks, existing demos, new demo, package/build checks, and committed fresh-checkout verification. Save exact successful command outputs, actual integration results, artifact snapshots, coverage, and source hashes. Update only verified EPIC-9 story/task statuses and finalize `docs/SPECS-LOGS/EPIC-9-RUNBOOK.md`.

## Acceptance evidence

| Story | Required evidence |
| --- | --- |
| US-9.1 | Root run metadata; sub-agent, model and tool descendants; configured hosted trace inspection when credentials are available |
| US-9.2 | Every log line validates as one JSON object with timestamp/level/run_id/phase/event; every failure category includes URL/reason; concurrent runs remain isolated |
| US-9.3 | Real OTLP protobuf received with token/latency/cost/tool/retry/citation metrics; unset endpoint creates no exporter/network calls; telemetry outage preserves application behavior |
| US-9.4 | Compose validates and starts; emitted metrics are queryable in Prometheus; provisioned Grafana datasource/dashboard includes runs/status, tokens, cost, phase latency, tools, retries, URL outcomes and dangling citations |

## Completion checklist

- [x] Configuration, dependencies, architecture decision and setup documentation.
- [x] LangSmith trace configuration and hierarchy verified.
- [x] Per-run structured logs and source-failure records verified.
- [x] Optional OTLP metrics, flushing and disabled behavior verified.
- [x] Docker stack and all dashboard panels verified.
- [ ] Offline demo, meaningful tests, coverage and hooks pass.
- [ ] Build, installed package, existing demos and fresh checkout pass.
- [ ] Runbook, exact command transcripts, snapshots and hashes saved.
- [ ] Implementation and final evidence committed.
