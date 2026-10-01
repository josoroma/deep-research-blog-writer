"""Actual registry invocation, ToolRuntime updates, and LangGraph checkpoint restoration."""

from types import SimpleNamespace
from typing import cast, get_type_hints

import pytest
from deepagents import DeepAgentState
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, ValidationError

from schemas.common import Contract
from schemas.requests import CompletePhaseInput
from schemas.responses import SearchResult
from schemas.state import ResearchAgentState, RunState, RunStateUpdate, UrlOutcome
from services.checkpoints import make_checkpointer
from tools.registry import TOOLS, Runtime, ToolDefinition, ToolOutputError, ToolRegistry, TypedTool


def example_state() -> RunState:
    result = SearchResult.model_validate(
        {
            "url": "https://example.com/article",
            "title": "Article",
            "snippet": "Snippet",
            "rank": 1,
            "query": "Valid topic",
        }
    )
    return RunState(
        run_id="demo",
        topic="Valid topic",
        clean_results=[result],
        url_outcomes={str(result.url): UrlOutcome(rank=1, url=result.url)},
    )


def runtime_for(state: RunState, call_id: str | None = "call-demo") -> Runtime:
    return Runtime(
        state={"messages": [], "run": state},
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id=call_id,
        store=None,
    )


def test_deep_agent_state_extends_the_harness_and_declares_run() -> None:
    assert set(DeepAgentState.__annotations__).issubset(ResearchAgentState.__annotations__)
    assert get_type_hints(ResearchAgentState)["run"] is RunState


@pytest.mark.parametrize(
    "changes",
    [
        {"topic": 42},
        {"completed_phases": "search"},
        {"completed_phases": ["unknown"]},
        {"completed_phases": ["search", "search"]},
        {"url_outcomes": {}},
        {"clean_results": []},
    ],
)
def test_replacement_validates_wrong_types_and_progress_invariants(
    changes: dict[str, object],
) -> None:
    state = example_state()
    with pytest.raises(ValidationError):
        state.replaced(**changes)
    assert state.completed_phases == []


def test_outcomes_must_match_urls_and_ranks() -> None:
    state = example_state()
    key = next(iter(state.url_outcomes))
    for changes in ({"rank": 2}, {"url": "https://example.com/other"}):
        outcome = UrlOutcome.model_validate({**state.url_outcomes[key].model_dump(), **changes})
        with pytest.raises(ValidationError, match="mismatch"):
            state.replaced(url_outcomes={key: outcome})
    with pytest.raises(ValidationError, match="unique URLs"):
        state.replaced(clean_results=state.clean_results * 2)


def test_registered_tool_returns_a_validated_replacement_without_mutating_input() -> None:
    state = example_state()
    output = TOOLS["record_phase_completion"].invoke({"phase": "search"}, runtime_for(state))
    assert isinstance(output, RunStateUpdate)
    assert output.run.completed_phases == ["search"]
    assert state.completed_phases == []
    repeated = TOOLS["record_phase_completion"].invoke({"phase": "search"}, runtime_for(output.run))
    assert repeated == output


def test_state_tool_requires_runtime_and_rejects_corrupted_state() -> None:
    with pytest.raises(ValueError, match="requires ToolRuntime"):
        TOOLS["record_phase_completion"].invoke({"phase": "search"})
    state = RunState.model_construct(run_id="demo", topic=cast(str, 123))
    with pytest.raises(ValidationError, match="topic"):
        TOOLS["record_phase_completion"].invoke({"phase": "search"}, runtime_for(state))


def test_every_registered_tool_has_explicit_pydantic_contracts() -> None:
    assert TOOLS, "The registry must not pass by being empty"
    for name, definition in TOOLS.items():
        assert name == definition.name
        assert issubclass(definition.input_model, BaseModel)
        assert issubclass(definition.output_model, BaseModel)


@pytest.mark.parametrize("field", ["input_model", "output_model"])
def test_registration_rejects_missing_contract(field: str) -> None:
    attributes: dict[str, object] = {
        "name": "untyped",
        "input_model": CompletePhaseInput,
        "output_model": RunStateUpdate,
    }
    attributes[field] = None
    with pytest.raises(TypeError, match=field):
        ToolRegistry().register(cast(ToolDefinition, SimpleNamespace(**attributes)))


def test_duplicate_registration_and_invalid_names_are_rejected() -> None:
    registry = ToolRegistry()
    definition = TOOLS["record_phase_completion"]
    registry.register(definition)
    assert len(registry) == 1
    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition)
    with pytest.raises(ValueError, match="identifiers"):
        registry.register(
            cast(
                ToolDefinition,
                SimpleNamespace(
                    name="",
                    input_model=CompletePhaseInput,
                    output_model=RunStateUpdate,
                ),
            )
        )


class EchoInput(Contract):
    message: str


class EchoOutput(Contract):
    message: str


def echo(request: EchoInput, runtime: Runtime | None) -> EchoOutput:
    return EchoOutput(message=request.message)


def test_invocation_rejects_bad_input_before_handler_runs() -> None:
    definition = TypedTool("echo", EchoInput, EchoOutput, echo, "Echo a validated message")
    with pytest.raises(ValidationError, match="message"):
        definition.invoke({"message": 123})
    assert definition.invoke({"message": "hello"}) == EchoOutput(message="hello")


def test_raw_dictionary_and_corrupted_model_outputs_are_rejected() -> None:
    def raw(request: EchoInput, runtime: Runtime | None) -> EchoOutput:
        return cast(EchoOutput, {"message": request.message})

    definition = TypedTool("raw", EchoInput, EchoOutput, raw, "Deliberately broken output")
    with pytest.raises(ToolOutputError, match="received dict"):
        definition.invoke({"message": "hello"})

    def corrupt(request: EchoInput, runtime: Runtime | None) -> EchoOutput:
        return EchoOutput.model_construct(message=cast(str, 123))

    broken = TypedTool("corrupt", EchoInput, EchoOutput, corrupt, "Corrupted model")
    with pytest.warns(UserWarning), pytest.raises(ValidationError, match="message"):
        broken.invoke({"message": "hello"})


def test_wrong_model_output_is_rejected() -> None:
    def wrong(request: EchoInput, runtime: Runtime | None) -> EchoOutput:
        return cast(EchoOutput, CompletePhaseInput(phase="search"))

    definition = TypedTool("wrong", EchoInput, EchoOutput, wrong, "Wrong model")
    with pytest.raises(ToolOutputError, match="received CompletePhaseInput"):
        definition.invoke({"message": "hello"})


def test_runtime_cannot_be_a_model_facing_field() -> None:
    class SpoofInput(Contract):
        runtime: str

    with pytest.raises(ValueError, match="injected"):
        ToolRegistry().register(
            cast(
                ToolDefinition,
                SimpleNamespace(
                    name="spoof",
                    input_model=SpoofInput,
                    output_model=EchoOutput,
                ),
            )
        )


def test_state_tools_must_declare_state_output() -> None:
    with pytest.raises(TypeError, match="RunStateUpdate"):
        TypedTool(
            "wrong_state", EchoInput, EchoOutput, echo, "Wrong state contract", updates_state=True
        )


def test_runtime_is_hidden_and_missing_call_id_fails_adapter() -> None:
    tool = TOOLS["record_phase_completion"].as_langchain_tool()
    schema = tool.tool_call_schema
    assert isinstance(schema, type) and issubclass(schema, BaseModel)
    assert "runtime" not in schema.model_json_schema()["properties"]
    with pytest.raises(ToolOutputError, match="tool call id"):
        tool.invoke({"phase": "search", "runtime": runtime_for(example_state(), None)})


def test_stateless_tool_adapter_returns_validated_json() -> None:
    definition = TypedTool("echo", EchoInput, EchoOutput, echo, "Echo")
    tool = definition.as_langchain_tool()
    assert (
        tool.invoke({"message": "hello", "runtime": runtime_for(example_state())})
        == '{"message":"hello"}'
    )


def test_real_tool_node_updates_state_and_checkpointer_round_trips_nested_models() -> None:
    state = example_state()
    tool = TOOLS["record_phase_completion"].as_langchain_tool()
    graph: StateGraph[ResearchAgentState, None, ResearchAgentState, ResearchAgentState] = (
        StateGraph(ResearchAgentState)
    )
    graph.add_node("tools", ToolNode([tool], handle_tool_errors=False))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    saver = make_checkpointer()
    compiled = graph.compile(checkpointer=saver)
    config: RunnableConfig = {"configurable": {"thread_id": "epic-2-round-trip"}}
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "record_phase_completion",
                "args": {"phase": "search"},
                "id": "call-demo",
                "type": "tool_call",
            }
        ],
    )
    initial: ResearchAgentState = {"messages": [message], "run": state}
    result = compiled.invoke(initial, config)
    assert isinstance(result["run"], RunState)
    assert result["run"].completed_phases == ["search"]
    restored = compiled.get_state(config).values["run"]
    assert isinstance(restored, RunState)
    assert restored == result["run"]
    assert all(isinstance(outcome, UrlOutcome) for outcome in restored.url_outcomes.values())
    assert isinstance(result["messages"][-1], ToolMessage)
    assert result["messages"][-1].tool_call_id == "call-demo"
    checkpoint = saver.get_tuple(config)
    assert checkpoint is not None
    assert checkpoint.checkpoint["channel_values"]["run"] == restored
