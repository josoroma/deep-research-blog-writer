# ADR 0008: Run-owned observability and a local metrics stack

Date: 2026-10-02

Status: Accepted

## Context

PD-020 requires run-identifiable LangSmith traces, JSON Lines logs, optional OTLP export, and eight Grafana panels. CLI processes are short-lived, and source tools run concurrently. Global loggers/providers and environment-driven implicit clients make attribution and disabled behavior unreliable.

## Decision

Each workflow owns a `RunObservability` scope. It binds to one workspace, logs only scalar event data, and captures registered tools explicitly so worker threads retain the same run owner. Model callbacks read response usage and reported cost; they never infer a provider price. Missing reported costs are marked unavailable in telemetry; the existing report keeps its configured ledger fallback.

When enabled, a LangSmith root carries run_id/topic metadata. The native DeepAgents/LangGraph callbacks and internal typed tool spans descend from that root. Hide trace inputs/outputs at the SDK boundary; flush the client on exit. Credentials and clients remain outside checkpoint state.

Only a configured OTLP/HTTP endpoint constructs a private OpenTelemetry meter provider. Counters and histograms accumulate actual execution data; CLI completion flushes and shuts down the provider. Export failure is logged and does not replace the application result. Run IDs are labels for local, low-volume v1 debugging; this cardinality must be reconsidered before a high-volume deployment.

Pinned Compose services receive OTLP/HTTP on localhost:4318, expose Collector metrics internally, scrape them with Prometheus on localhost:9090, and provision Grafana on localhost:3001. Named volumes preserve Prometheus/Grafana data. Anonymous Viewer access supports the local PM demo. Stop with Compose `down` without `--volumes`. The Collector retains completed-run series for 24 hours; Prometheus retains samples for seven days. Collector memory is not durable across restarts. No alert rules or hallucination-rate estimates are provisioned; hallucination rate belongs to evaluation.

## Consequences

Offline tests and demos use a recording LangSmith client and a real OTLP protobuf receiver without hosted credentials. Stack smoke tests additionally inspect Prometheus values and Grafana provisioning. Hosted verification is a separate opt-in smoke with locally configured credentials. Logs exclude raw pages/model messages and redact URL credentials and credential query parameters. The dashboard shows cumulative observed run totals, not a provider billing reconciliation.

## References

- [SPECS PD-020](../../SPECS.md#pd-020--observability-defaults)
- [LangSmith tracing context](https://reference.langchain.com/python/langsmith/run_helpers/tracing_context)
- [OpenTelemetry Python exporters](https://opentelemetry.io/docs/languages/python/exporters/)
- [OTLP HTTP metric exporter](https://opentelemetry-python.readthedocs.io/en/latest/exporter/otlp/otlp.html)
- [Collector Prometheus exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/prometheusexporter)
- [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
