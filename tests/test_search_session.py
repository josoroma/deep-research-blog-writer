"""Stable merge, budget, artifact, and normalization acceptance tests."""

import json
import os
from pathlib import Path

import pytest
from pydantic import BaseModel, HttpUrl, ValidationError

from evaluations.epic4_demo import TOPIC, VARIANTS, demo_provider, run_demo
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.search import QueryVariants
from schemas.state import RunState
from services.search_provider import FakeSearchProvider, SearchProviderError
from services.search_session import DENIED_HOSTS, SearchSession, canonicalize_url, normalize_results
from services.workspace import create_run_workspace
from tools.registry import TOOLS, create_tool_registry
from workflows.search_run import tool_runtime


def row(url: str, rank: int = 1, query: str = TOPIC, title: str = "First") -> SearchResult:
    return SearchResult.model_validate(
        {"url": url, "rank": rank, "query": query, "title": title, "snippet": "Snippet"}
    )


def session_at(root: Path, provider: FakeSearchProvider | None = None) -> SearchSession:
    request = ResearchRequest(topic=TOPIC)
    return SearchSession(request, create_run_workspace(request, root), provider or demo_provider())


def test_default_pages_merge_even_when_arriving_in_reverse_and_replay_is_free(
    tmp_path: Path,
) -> None:
    session = session_at(tmp_path)
    assert session.results == [] and not session.complete
    plan = session.plan(QueryVariants(variants=VARIANTS))
    for call in reversed(plan.calls):
        session.search(call.query, call.page)
    assert session.complete
    raw = json.loads((session.workspace.root / "search_results.json").read_text())
    assert len(raw) == 50
    assert sum(result["query"] == TOPIC for result in raw) == 30
    assert [result["rank"] for result in raw if result["query"] == TOPIC] == list(range(1, 31))
    assert [raw[offset]["query"] for offset in (0, 10, 20, 30, 40)] == [
        TOPIC,
        *VARIANTS,
        TOPIC,
        TOPIC,
    ]
    assert all(set(result) == {"query", "rank", "url", "title", "snippet"} for result in raw)
    assert isinstance(session.provider, FakeSearchProvider)
    session.search(TOPIC, 1)
    assert len(session.provider.calls) == 5
    session.plan(QueryVariants(variants=VARIANTS))
    with pytest.raises(ValueError, match="Cannot change"):
        session.plan(QueryVariants(variants=["new variant", "another variant"]))
    normalized = session.normalize(30)
    clean = json.loads((session.workspace.root / "clean_results.json").read_text())
    assert normalized.counts.model_dump() == {
        "raw": 50,
        "denied": 3,
        "duplicates": 1,
        "capped": 16,
        "kept": 30,
    }
    assert clean[0]["url"] == "https://example.com/post?id=7"
    assert clean[0]["title"] == "Fixture 0-1"
    assert [result["rank"] for result in clean] == list(range(1, 31))


def test_budget_rejects_unplanned_calls_and_premature_normalization(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    with pytest.raises(ValueError, match="plan_search"):
        session.search(TOPIC, 1)
    with pytest.raises(ValueError, match="differ"):
        session.plan(QueryVariants(variants=[TOPIC.upper(), "other query"]))
    session.plan(QueryVariants(variants=VARIANTS))
    for query, page in ((TOPIC, 4), (VARIANTS[0], 2), ("unplanned", 1)):
        with pytest.raises(ValueError, match="budget"):
            session.search(query, page)
    with pytest.raises(ValueError, match="All planned"):
        session.normalize(30)
    assert isinstance(session.provider, FakeSearchProvider) and session.provider.calls == []


@pytest.mark.parametrize(
    "rows",
    [
        [row("https://example.com", rank=11)],
        [row("https://example.com", query="wrong query")],
        [row("https://example.com"), row("https://example.com/other")],
        [row(f"https://example.com/{index}", rank=index) for index in range(1, 12)],
    ],
)
def test_provider_contract_violations_do_not_persist_bad_artifacts(
    tmp_path: Path, rows: list[SearchResult]
) -> None:
    session = session_at(tmp_path, FakeSearchProvider({(TOPIC, 1): rows}))
    session.plan(QueryVariants(variants=VARIANTS))
    with pytest.raises(SearchProviderError, match="contract"):
        session.search(TOPIC, 1)
    assert not (session.workspace.root / "search_results.json").exists()


def test_three_variants_empty_pages_and_configured_budget(tmp_path: Path) -> None:
    request = ResearchRequest(topic=TOPIC, pages=1, per_page=5, max_urls=2)
    session = SearchSession(request, create_run_workspace(request, tmp_path), FakeSearchProvider())
    plan = session.plan(QueryVariants(variants=[*VARIANTS, "framework design patterns"]))
    assert len(plan.calls) == 4
    for call in plan.calls:
        session.search(call.query, call.page)
    with pytest.raises(ValueError, match="budget"):
        session.normalize(3)
    assert session.normalize(2).clean_results == []


@pytest.mark.parametrize("host", DENIED_HOSTS)
@pytest.mark.parametrize("prefix", ["", "www.", "news.deep."])
def test_all_denied_hosts_and_subdomains_are_filtered(host: str, prefix: str) -> None:
    normalized = normalize_results([row(f"https://{prefix}{host}/article")], 30)
    assert normalized.clean_results == []
    assert normalized.counts.denied == 1


def test_lookalike_hosts_keep_meaningful_params_blank_values_and_order() -> None:
    url = HttpUrl(
        "https://example.com/post///?UTM_Source=x&gclid=y&fbclid=x&msclkid=x&mc_cid=x&mc_eid=x&id=7&tag=a&tag=b&blank=#intro"
    )
    assert canonicalize_url(url) == "https://example.com/post?id=7&tag=a&tag=b&blank="
    hosts = ["notyoutube.com", "youtube.com.example.org", "facebook.example.com"]
    clean = normalize_results(
        [row(f"https://{host}/article", rank=index) for index, host in enumerate(hosts, 1)], 2
    )
    assert [result.url.host for result in clean.clean_results] == hosts[:2]
    assert [result.rank for result in clean.clean_results] == [1, 2]
    assert clean.counts.capped == 1
    with pytest.raises(ValueError, match="positive"):
        normalize_results([], 0)


def test_typed_tools_hide_runtime_and_reject_cross_run_binding(tmp_path: Path) -> None:
    session = session_at(tmp_path)
    registry = create_tool_registry(session)
    run = RunState(run_id=session.workspace.run_id, topic=TOPIC)
    exposed = registry["google_search"].as_langchain_tool().tool_call_schema
    assert isinstance(exposed, type) and issubclass(exposed, BaseModel)
    assert "runtime" not in exposed.model_fields
    with pytest.raises(ValueError, match="SearchSession"):
        TOOLS["plan_search"].invoke({"variants": VARIANTS}, tool_runtime(run))
    with pytest.raises(ValueError, match="does not match"):
        registry["plan_search"].invoke(
            {"variants": VARIANTS}, tool_runtime(run.replaced(run_id="other"))
        )
    assert not (session.workspace.root / "search_plan.json").exists()


@pytest.mark.parametrize("parallel", [False, True])
def test_real_deepagents_tool_state_returns_from_search_subagent(
    tmp_path: Path, parallel: bool
) -> None:
    demo = run_demo(tmp_path, parallel=parallel)
    assert demo["completed_phases"] == ["plan", "search", "normalize"]
    assert demo["pending_url_outcomes"] == 30
    assert demo["repeated_call_cached"] and demo["unplanned_call_rejected"]
    assert demo["merge_order_verified"]
    workspace = Path(demo["workspace"])
    assert sorted(path.name for path in workspace.iterdir()) == [
        "clean_results.json",
        "request.json",
        "search_plan.json",
        "search_results.json",
    ]


@pytest.mark.parametrize(
    "variants", [["one"], ["a", "b", "c", "d"], ["one", "ONE"], [" ", "other"]]
)
def test_query_variant_contract_rejects_invalid_plan(variants: list[str]) -> None:
    with pytest.raises(ValidationError):
        QueryVariants(variants=variants)


def test_failed_search_cannot_spend_again_or_change_plan(tmp_path: Path) -> None:
    provider = FakeSearchProvider({(TOPIC, 1): [row("https://example.com", rank=11)]})
    session = session_at(tmp_path, provider)
    session.plan(QueryVariants(variants=VARIANTS))
    with pytest.raises(SearchProviderError, match="contract"):
        session.search(TOPIC, 1)
    with pytest.raises(SearchProviderError, match="previously failed"):
        session.search(TOPIC, 1)
    with pytest.raises(ValueError, match="Cannot change"):
        session.plan(QueryVariants(variants=["new phrasing", "another phrasing"]))
    assert len(provider.calls) == 1


def test_failed_artifact_write_can_be_repaired_without_second_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = session_at(tmp_path)
    session.plan(QueryVariants(variants=VARIANTS))
    original = os.replace

    def fail_write(source: object, destination: object) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(os, "replace", fail_write)
    with pytest.raises(OSError):
        session.search(TOPIC, 1)
    assert not list(session.workspace.root.glob(".search_results.json-*"))
    monkeypatch.setattr(os, "replace", original)
    session.search(TOPIC, 1)
    assert isinstance(session.provider, FakeSearchProvider)
    assert len(session.provider.calls) == 1
    assert len(json.loads((session.workspace.root / "search_results.json").read_text())) == 10


def test_artifacts_replace_destination_symlink_without_writing_outside_run(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("unchanged")
    session = session_at(tmp_path / "runs")
    destination = session.workspace.root / "search_plan.json"
    destination.symlink_to(outside)
    session.plan(QueryVariants(variants=VARIANTS))
    assert outside.read_text() == "unchanged"
    assert not destination.is_symlink()


def test_invalid_provider_model_instances_are_redacted_at_boundary(tmp_path: Path) -> None:
    invalid = SearchResult.model_construct(
        url=HttpUrl("https://example.com"),
        rank=-1,
        query=TOPIC,
        title="unsafe-provider-field",
        snippet="",
    )
    session = session_at(tmp_path, FakeSearchProvider({(TOPIC, 1): [invalid]}))
    session.plan(QueryVariants(variants=VARIANTS))
    with pytest.raises(SearchProviderError, match="contract") as caught:
        session.search(TOPIC, 1)
    assert "unsafe-provider-field" not in str(caught.value)
