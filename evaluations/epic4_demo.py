"""Offline Search demo through the real orchestrator and search sub-agent."""

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from agents.deep_research import build_deep_agent
from evaluations.fakes import ScriptedChatModel
from schemas.config import RunSettings
from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.state import RunState
from services.llm_service import LLMService
from services.search_provider import FakeSearchProvider
from services.search_session import SearchSession
from services.workspace import create_run_workspace
from tools.registry import create_tool_registry

TOPIC = "2026 agentic AI frameworks"
VARIANTS = ["agent framework architecture comparison", "production agent framework evaluation"]


def demo_provider() -> FakeSearchProvider:
    sequence = [(TOPIC, 1), *((query, 1) for query in VARIANTS), (TOPIC, 2), (TOPIC, 3)]
    pages = {}
    for batch, (query, page) in enumerate(sequence):
        pages[(query, page)] = [
            SearchResult.model_validate(
                {
                    "url": f"https://example.com/batch-{batch}/article-{index}",
                    "title": f"Fixture {batch}-{index}",
                    "snippet": "Offline search fixture",
                    "query": query,
                    "rank": (page - 1) * 10 + index,
                }
            )
            for index in range(1, 11)
        ]
    replacements = {
        (TOPIC, 1, 0): "https://example.com/post/?utm_source=x&gclid=y&id=7#intro",
        (TOPIC, 1, 1): "https://www.reddit.com/r/agents/",
        (VARIANTS[0], 1, 0): "https://example.com/post?id=7",
        (VARIANTS[1], 1, 1): "https://youtu.be/video",
        (TOPIC, 2, 0): "https://news.facebook.com/article",
    }
    for (query, page, index), url in replacements.items():
        previous = pages[(query, page)][index]
        pages[(query, page)][index] = SearchResult.model_validate(
            {**previous.model_dump(), "url": url}
        )
    return FakeSearchProvider(pages)


def call(name: str, args: dict[str, Any], index: int) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args,
                "id": f"epic4-{index}",
                "type": "tool_call",
            }
        ],
    )


def run_demo(runs_root: Path, *, parallel: bool = True) -> dict[str, Any]:
    request = ResearchRequest(topic=TOPIC)
    settings = RunSettings(_env_file=None)
    provider = demo_provider()
    workspace = create_run_workspace(request, runs_root)
    session = SearchSession(request, workspace, provider)
    sequence = [(TOPIC, 1), *((query, 1) for query in VARIANTS), (TOPIC, 2), (TOPIC, 3)]
    # Deliberately reverse arrival order to exercise the deterministic breadth-first merge.
    search_messages = [
        call("google_search", {"query": query, "page": page}, index)
        for index, (query, page) in enumerate(reversed(sequence), 2)
    ]
    if parallel:
        search_messages = [
            AIMessage(
                content="",
                tool_calls=[
                    tool_call for message in search_messages for tool_call in message.tool_calls
                ],
            )
        ]
    script = [
        call("plan_search", {"variants": VARIANTS}, 0),
        call(
            "task",
            {"subagent_type": "search_agent", "description": "Execute the saved search plan."},
            1,
        ),
        *search_messages,
        AIMessage(content="All planned searches completed."),
        call("normalize_results", {"max_urls": request.max_urls}, 8),
        AIMessage(content="Search milestone completed; artifacts saved."),
    ]
    model = ScriptedChatModel(script=script)
    agent = build_deep_agent(
        LLMService(settings, fake_model=model),
        workspace,
        tool_registry=create_tool_registry(session),
    )
    result = agent.invoke(
        {
            "messages": [{"role": "user", "content": request.model_dump_json()}],
            "run": RunState(run_id=workspace.run_id, topic=TOPIC),
        },
        config={"recursion_limit": settings.recursion_limit},
    )
    run = RunState.model_validate(result["run"])
    assert run.completed_phases == ["plan", "search", "normalize"]
    assert len(run.clean_results) == 30
    assert str(run.clean_results[0].url) == "https://example.com/post?id=7"
    assert run.clean_results[0].title == "Fixture 0-1"
    assert run.query_variants == VARIANTS
    normalized = session.normalize(request.max_urls)
    session.search(TOPIC, 1)
    assert len(provider.calls) == 5
    blocked = False
    try:
        session.search("unplanned query", 1)
    except ValueError:
        blocked = True
    assert blocked
    raw = json.loads((workspace.root / "search_results.json").read_text())
    clean = json.loads((workspace.root / "clean_results.json").read_text())
    assert [(row["query"], row["rank"]) for row in raw] == [
        (query, (page - 1) * 10 + index) for query, page in sequence for index in range(1, 11)
    ]
    assert [row["rank"] for row in clean] == list(range(1, 31))
    return {
        "mode": "offline; scripted model and fake provider; real DeepAgents tools",
        "run_id": workspace.run_id,
        "workspace": str(workspace.root),
        "completed_phases": run.completed_phases,
        "query_variants": VARIANTS,
        "provider_calls": [call.model_dump() for call in provider.calls],
        "topic_results": sum(row["query"] == TOPIC for row in raw),
        "counts": normalized.counts.model_dump(),
        "first_clean_result": clean[0],
        "batched_search_tool_calls": parallel,
        "merge_order_verified": True,
        "contiguous_clean_ranks": True,
        "repeated_call_cached": True,
        "unplanned_call_rejected": blocked,
        "pending_url_outcomes": len(run.url_outcomes),
        "files": sorted(path.name for path in workspace.root.iterdir() if path.is_file()),
    }


def main() -> int:
    output = run_demo(Path("runs"))
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
