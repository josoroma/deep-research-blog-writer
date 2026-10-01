"""Typed application tools with LangChain adapters at the framework boundary."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Protocol

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolArg, StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field, create_model

from schemas.requests import CompletePhaseInput
from schemas.state import ResearchAgentState, RunStateUpdate
from tools.search_tools import register_search_tools
from tools.state_tools import record_phase_completion
from tools.stubs import register_stub_tools

if TYPE_CHECKING:
    from services.search_session import SearchSession

Runtime = ToolRuntime[None, ResearchAgentState]


class ToolOutputError(TypeError):
    """An implementation returned something outside its declared output contract."""


class ToolDefinition(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def input_model(self) -> type[BaseModel]: ...
    @property
    def output_model(self) -> type[BaseModel]: ...
    def invoke(self, payload: object, runtime: Runtime | None = None) -> BaseModel: ...
    def as_langchain_tool(self) -> StructuredTool: ...


def validate_definition(definition: ToolDefinition) -> None:
    for field in ("input_model", "output_model"):
        model = getattr(definition, field, None)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise TypeError(f"Tool {definition.name!r} must declare a Pydantic {field}")
    if not definition.name or not definition.name.isidentifier():
        raise ValueError("Tool names must be nonempty identifiers")
    if "runtime" in definition.input_model.model_fields:
        raise ValueError("runtime is injected by the framework, not a model-facing field")


@dataclass(frozen=True)
class TypedTool[InputT: BaseModel, OutputT: BaseModel]:
    name: str
    input_model: type[InputT]
    output_model: type[OutputT]
    handler: Callable[[InputT, Runtime | None], OutputT]
    description: str
    updates_state: bool = False

    def __post_init__(self) -> None:
        validate_definition(self)
        if self.updates_state and not issubclass(self.output_model, RunStateUpdate):
            raise TypeError("A state-changing tool must declare RunStateUpdate output")

    def invoke(self, payload: object, runtime: Runtime | None = None) -> OutputT:
        request = self.input_model.model_validate(payload)
        result = self.handler(request, runtime)
        if not isinstance(result, self.output_model):
            raise ToolOutputError(
                f"Tool {self.name!r} must return {self.output_model.__name__}, "
                f"received {type(result).__name__}"
            )
        return self.output_model.model_validate(result.model_dump())

    def as_langchain_tool(self) -> StructuredTool:
        def execute(runtime: ToolRuntime[None, ResearchAgentState], **payload: object) -> object:
            result = self.invoke(payload, runtime)
            if not self.updates_state:
                return result.model_dump_json()
            if not isinstance(result, RunStateUpdate) or runtime.tool_call_id is None:
                raise ToolOutputError("A state update requires RunStateUpdate and a tool call id")
            return Command(
                update={
                    "run": result.run,
                    "messages": [
                        ToolMessage(
                            content=result.model_dump_json(),
                            tool_call_id=runtime.tool_call_id,
                            name=self.name,
                        )
                    ],
                }
            )

        # LangChain validates injected arguments before stripping them. Keep the original
        # contract strict and add a transport-only field hidden from tool_call_schema.
        adapter_input = create_model(
            f"{self.input_model.__name__}WithRuntime",
            __base__=self.input_model,
            runtime=(Annotated[object, InjectedToolArg()], Field(exclude=True)),
        )
        return StructuredTool.from_function(
            execute, name=self.name, description=self.description, args_schema=adapter_input
        )


class ToolRegistry(Mapping[str, ToolDefinition]):
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        validate_definition(definition)
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")
        self._tools[definition.name] = definition

    def __getitem__(self, name: str) -> ToolDefinition:
        return self._tools[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._tools)

    def __len__(self) -> int:
        return len(self._tools)


def create_tool_registry(search_session: SearchSession | None = None) -> ToolRegistry:
    """Build independent tool bindings; credentials and provider clients stay off state."""
    registry = ToolRegistry()
    registry.register(
        TypedTool[CompletePhaseInput, RunStateUpdate](
            name="record_phase_completion",
            input_model=CompletePhaseInput,
            output_model=RunStateUpdate,
            handler=record_phase_completion,
            description="Record a completed phase in validated run state; calls are idempotent.",
            updates_state=True,
        )
    )
    register_stub_tools(registry)
    register_search_tools(registry, search_session)
    return registry


TOOLS = create_tool_registry()
