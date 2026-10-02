"""Verify actual OTLP ingestion, Prometheus values, and Grafana provisioning."""

import json
import time
from pathlib import Path
from typing import Any

import httpx

from evaluations.epic9_demo import run_demo
from services.artifacts import write_json

PROMETHEUS = "http://127.0.0.1:9090"
GRAFANA = "http://127.0.0.1:3001"


def wait_json(
    client: httpx.Client, url: str, *, params: dict[str, str] | None = None
) -> dict[str, Any]:
    deadline = time.monotonic() + 45
    while True:
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except (httpx.HTTPError, ValueError):
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Local observability service not ready: {url}") from None
            time.sleep(0.5)


def verify_stack(runs_root: Path) -> dict[str, Any]:
    with httpx.Client(timeout=3, trust_env=False) as client:
        assert wait_json(client, f"{GRAFANA}/api/health")["database"] == "ok"
        wait_json(client, f"{PROMETHEUS}/api/v1/status/buildinfo")
        demo = run_demo(runs_root, endpoint="http://127.0.0.1:4318")
        run_id = demo["telemetry"]["run_id"]
        queries = {
            "runs": f'research_runs_total{{run_id="{run_id}"}}',
            "tokens": f'research_tokens_total{{run_id="{run_id}"}}',
            "cost": f'research_cost_usd_total{{run_id="{run_id}"}}',
            "phase_latency": f'research_phase_duration_seconds_count{{run_id="{run_id}"}}',
            "tool_calls": f'research_tool_calls_total{{run_id="{run_id}"}}',
            "retries": f'research_retries_total{{run_id="{run_id}"}}',
            "url_outcomes": f'research_url_outcomes_total{{run_id="{run_id}"}}',
            "dangling_citations": f'research_dangling_citations_total{{run_id="{run_id}"}}',
        }
        results: dict[str, Any] = {}
        deadline = time.monotonic() + 45
        while True:
            results = {
                name: wait_json(client, f"{PROMETHEUS}/api/v1/query", params={"query": query})[
                    "data"
                ]["result"]
                for name, query in queries.items()
            }
            if all(results.values()):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Prometheus did not ingest every required metric")
            time.sleep(0.5)
        assert float(results["tokens"][0]["value"][1]) == 90
        assert abs(float(results["cost"][0]["value"][1]) - 0.06) < 0.000001
        assert float(results["retries"][0]["value"][1]) == 5
        assert float(results["dangling_citations"][0]["value"][1]) == 2
        assert results["runs"][0]["metric"]["status"] == "failed"
        assert sum(float(row["value"][1]) for row in results["url_outcomes"]) == 8
        dashboard = wait_json(client, f"{GRAFANA}/api/dashboards/uid/research-runs")
        source = wait_json(client, f"{GRAFANA}/api/datasources/uid/research-prometheus")
        assert source["url"] == "http://prometheus:9090"
        panels = dashboard["dashboard"]["panels"]
        assert len(panels) == 8
        panel_results = {}
        for panel in panels:
            expression = panel["targets"][0]["expr"].replace("$run_id", run_id)
            data = wait_json(client, f"{PROMETHEUS}/api/v1/query", params={"query": expression})[
                "data"
            ]["result"]
            assert data, f"Dashboard panel has no data: {panel['title']}"
            panel_results[panel["title"]] = data
        # Exercise Grafana's datasource proxy, so provisioning is checked end to end.
        proxy = wait_json(
            client,
            f"{GRAFANA}/api/datasources/proxy/uid/research-prometheus/api/v1/query",
            params={"query": queries["tokens"]},
        )
        assert float(proxy["data"]["result"][0]["value"][1]) == 90
        evidence = {
            "workspace": demo["workspace"],
            "run_id": run_id,
            "otlp_delivered": demo["telemetry"]["metrics_flushed"],
            "prometheus": results,
            "dashboard_panels": panel_results,
            "grafana_datasource_proxy_verified": True,
            "dashboard_url": f"{GRAFANA}/d/research-runs?var-run_id={run_id}",
        }
        write_json(Path(demo["workspace"]) / "logs/stack_evidence.json", evidence)
        print(json.dumps(evidence, indent=2))
        return evidence


def main() -> int:
    verify_stack(Path("runs"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
