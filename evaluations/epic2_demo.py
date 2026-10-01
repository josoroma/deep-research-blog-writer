"""Offline PM demonstration of validated contracts and actual tool/state integration."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import SecretStr, ValidationError

from evaluations.agent_architecture import find_agent_architecture_violations
from evaluations.agent_boundary import find_forbidden_imports
from prompts.catalog import load_prompt
from schemas.common import Contract
from schemas.config import AGENT_NAMES, AgentModels, AgentName, RunSettings
from schemas.requests import CompletePhaseInput, ResearchRequest
from schemas.responses import SearchResult
from schemas.state import ResearchAgentState, RunState, RunStateUpdate, UrlOutcome
from services.checkpoints import make_checkpointer
from services.llm_service import LLMService
from tools.registry import TOOLS, ToolOutputError, TypedTool


class DemoResult(Contract):
    mode: str = "offline; no provider request"
    topic: str
    budgets: tuple[int, int, int]
    registered_tools: list[str]
    prompts_loaded: dict[AgentName, int]
    configured_models: dict[AgentName, str]
    provider_preferences: dict[str, str | bool]
    fake_injection_verified: bool
    checkpoint_restored: bool
    run: RunState
    expected_rejections: list[str]
    rejected_agent_patterns: list[str]


def main() -> int:
    request = ResearchRequest(topic="  2026 agentic AI frameworks  ")
    source = SearchResult.model_validate(
        {
            "url": "https://example.com/article",
            "title": "Offline fixture",
            "snippet": "Fixture",
            "rank": 1,
            "query": request.topic,
        }
    )
    state = RunState(
        run_id="epic-2-demo",
        topic=request.topic,
        clean_results=[source],
        url_outcomes={str(source.url): UrlOutcome(rank=source.rank, url=source.url)},
    )
    fake = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "record_phase_completion",
                        "args": {"phase": "search"},
                        "id": "call-epic-2-demo",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    settings = RunSettings(_env_file=None, models=AgentModels())
    service = LLMService(settings, fake_model=fake)
    assert all(service.for_agent(agent) is fake for agent in AGENT_NAMES)
    message = service.for_agent("orchestrator").invoke(load_prompt("orchestrator"))
    graph: StateGraph[ResearchAgentState, None, ResearchAgentState, ResearchAgentState] = (
        StateGraph(ResearchAgentState)
    )
    graph.add_node(
        "tools",
        ToolNode([TOOLS["record_phase_completion"].as_langchain_tool()], handle_tool_errors=False),
    )
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile(checkpointer=make_checkpointer())
    config: RunnableConfig = {"configurable": {"thread_id": state.run_id}}
    initial: ResearchAgentState = {"messages": [message], "run": state}
    result = compiled.invoke(initial, config)
    restored = compiled.get_state(config).values["run"]
    assert isinstance(restored, RunState) and restored == result["run"]
    assert restored.completed_phases == ["search"]

    rejected: list[str] = []
    for topic in ("ab", "x" * 251):
        try:
            ResearchRequest(topic=topic)
        except ValidationError:
            rejected.append("topic outside 3–250 characters")
    try:
        state.replaced(completed_phases="invalid")
    except ValidationError:
        rejected.append("malformed state replacement")
    broken = TypedTool(
        "bad_output_probe",
        CompletePhaseInput,
        RunStateUpdate,
        lambda request, runtime: cast(RunStateUpdate, {}),
        "Demonstrate raw-dict rejection",
    )
    try:
        broken.invoke({"phase": "search"})
    except ToolOutputError:
        rejected.append("raw dictionary tool output")
    assert len(rejected) == 4

    with TemporaryDirectory(prefix="epic2-agent-check-") as directory:
        probe = Path(directory) / "agent.py"
        probe.write_text(
            'import httpx\nChatOpenRouter(model="example")\n'
            'create_deep_agent(system_prompt="inline")\n',
            encoding="utf-8",
        )
        patterns = [str(violation) for violation in find_forbidden_imports(Path(directory))]
        patterns.extend(
            violation.rule for violation in find_agent_architecture_violations(Path(directory))
        )
        assert len(patterns) == 3

    # Construction is offline; SDK stubs in tests check actual outgoing parameters.
    configured = LLMService(
        RunSettings(
            _env_file=None,
            models=AgentModels(),
            openrouter_api_key=SecretStr("offline-placeholder"),
        )
    ).for_agent("orchestrator")
    assert isinstance(configured, ChatOpenRouter) and configured.openrouter_provider is not None
    output = DemoResult(
        topic=request.topic,
        budgets=(request.pages, request.per_page, request.max_urls),
        registered_tools=list(TOOLS),
        prompts_loaded={agent: len(load_prompt(agent)) for agent in AGENT_NAMES},
        configured_models={agent: settings.models.for_agent(agent) for agent in AGENT_NAMES},
        provider_preferences=configured.openrouter_provider,
        fake_injection_verified=True,
        checkpoint_restored=True,
        run=restored,
        expected_rejections=rejected,
        rejected_agent_patterns=patterns,
    )
    print(output.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
