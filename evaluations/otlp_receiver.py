"""Loopback OTLP/HTTP receiver for a reproducible CLI demo without a cloud service."""

from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)


def decode_metrics(payload: bytes) -> dict[str, Any]:
    request = ExportMetricsServiceRequest()
    request.ParseFromString(payload)
    return MessageToDict(request, preserving_proto_field_name=True)


def metric_points(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    metrics: dict[str, list[dict[str, Any]]] = {}
    for resource in payload.get("resource_metrics", []):
        for scope in resource.get("scope_metrics", []):
            for metric in scope.get("metrics", []):
                data = metric.get("sum", metric.get("histogram", {}))
                metrics.setdefault(metric["name"], []).extend(data.get("data_points", []))
    return metrics


@contextmanager
def local_receiver() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    received: list[dict[str, Any]] = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if (
                self.path != "/v1/metrics"
                or self.headers.get("Content-Type") != "application/x-protobuf"
            ):
                self.send_error(400)
                return
            received.append(decode_metrics(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
