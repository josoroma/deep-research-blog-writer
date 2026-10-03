"""A private SDK provider per CLI invocation; no global meter or implicit export."""

from collections.abc import Mapping
from typing import Any

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

METRICS = {
    "runs": "research_runs",
    "tokens": "research_tokens",
    "cost": "research_cost_usd",
    "tools": "research_tool_calls",
    "retries": "research_retries",
    "urls": "research_url_outcomes",
    "dangling": "research_dangling_citations",
}


class DeliveryExporter(MetricExporter):
    """SDK flush success means completion, so also track actual delivery results."""

    def __init__(self, delegate: MetricExporter) -> None:
        super().__init__(delegate._preferred_temporality, delegate._preferred_aggregation)
        self.delegate = delegate
        self.failed = False

    def export(
        self, metrics_data: MetricsData, timeout_millis: float = 10_000, **kwargs: Any
    ) -> MetricExportResult:
        try:
            result = self.delegate.export(metrics_data, timeout_millis, **kwargs)
        except Exception:  # noqa: BLE001 - an exporter error is a failed export
            result = MetricExportResult.FAILURE
        self.failed |= result is not MetricExportResult.SUCCESS
        return result

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        return self.delegate.force_flush(timeout_millis)

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: Any) -> None:
        self.delegate.shutdown(timeout_millis, **kwargs)


class RunMetrics:
    def __init__(
        self, endpoint: str | None, timeout: float, *, exporter: MetricExporter | None = None
    ) -> None:
        self.provider: MeterProvider | None = None
        self.counters: dict[str, Counter] = {}
        self.histograms: dict[str, Histogram] = {}
        self.exporter: DeliveryExporter | None = None
        if endpoint is None:
            return
        address = endpoint if endpoint.endswith("/v1/metrics") else f"{endpoint}/v1/metrics"
        self.exporter = DeliveryExporter(
            exporter or OTLPMetricExporter(endpoint=address, timeout=timeout)
        )
        reader = PeriodicExportingMetricReader(
            self.exporter,
            export_interval_millis=3_600_000,
            export_timeout_millis=timeout * 1000,
        )
        self.provider = MeterProvider(
            metric_readers=[reader],
            shutdown_on_exit=False,
            resource=Resource.create({"service.name": "deep-research-blog-writer"}),
        )
        meter = self.provider.get_meter("deep_research_blog_writer", "0.1.0")
        self.counters = {key: meter.create_counter(name, unit="1") for key, name in METRICS.items()}
        self.histograms = {
            key: meter.create_histogram(f"research_{key}_duration", unit="s")
            for key in ("run", "phase", "tool")
        }

    def add(self, name: str, value: int | float, attributes: Mapping[str, str]) -> None:
        if self.provider is not None:
            self.counters[name].add(value, attributes=dict(attributes))

    def duration(self, name: str, value: float, attributes: Mapping[str, str]) -> None:
        if self.provider is not None:
            self.histograms[name].record(value, attributes=dict(attributes))

    def close(self, timeout: float) -> bool:
        if self.provider is None:
            return True
        try:
            flushed = self.provider.force_flush(timeout_millis=timeout * 1000)
            self.provider.shutdown(timeout_millis=timeout * 1000)
            return bool(flushed) and self.exporter is not None and not self.exporter.failed
        except Exception:  # noqa: BLE001 - shutdown reports success as a bool
            return False
