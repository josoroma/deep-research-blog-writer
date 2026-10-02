"""Recording SDK boundaries for network-free observability verification."""

from threading import RLock
from typing import Any

from langsmith import Client
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult, MetricsData


class RecordingTraceClient(Client):
    def __init__(self) -> None:
        super().__init__(
            api_url="https://trace.fixture.test",
            api_key="offline",
            auto_batch_tracing=False,
            hide_inputs=True,
            hide_outputs=True,
        )
        self.records: dict[str, dict[str, Any]] = {}
        self.lock = RLock()

    def create_run(self, name: str, inputs: dict[str, Any], run_type: Any, **kwargs: Any) -> None:
        del inputs
        with self.lock:
            self.records[str(kwargs["id"])] = {
                "id": str(kwargs["id"]),
                "name": name,
                "run_type": run_type,
                "parent_run_id": str(kwargs["parent_run_id"])
                if kwargs.get("parent_run_id")
                else None,
                "metadata": kwargs.get("extra", {}).get("metadata", {}),
                "ended": False,
            }

    def update_run(self, run_id: Any, **kwargs: Any) -> None:
        with self.lock:
            if str(run_id) in self.records:
                self.records[str(run_id)]["ended"] = kwargs.get("end_time") is not None


class RecordingMetricExporter(MetricExporter):
    def __init__(self, *, fails: bool = False) -> None:
        super().__init__()
        self.batches: list[MetricsData] = []
        self.fails = fails
        self.closed = False

    def export(
        self, metrics_data: MetricsData, timeout_millis: float = 10_000, **kwargs: Any
    ) -> MetricExportResult:
        del timeout_millis, kwargs
        self.batches.append(metrics_data)
        return MetricExportResult.FAILURE if self.fails else MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        del timeout_millis
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: Any) -> None:
        del timeout_millis, kwargs
        self.closed = True
