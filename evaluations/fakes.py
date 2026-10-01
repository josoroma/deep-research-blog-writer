"""Offline scripted chat model for the EPIC-3 skeleton demo and tests.

It binds tool names per call through `Runnable.bind`, so a test can assert exactly
which tools each agent was offered, and it records every model input across all
agents, so a test can prove raw HTML never reaches a model context.
"""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import PrivateAttr


class ScriptedChatModel(BaseChatModel):
    """Return one scripted AIMessage per model call; bind tools without a provider."""

    script: list[AIMessage]
    on_call: Callable[[list[str], list[BaseMessage]], None] | None = None
    _index: int = PrivateAttr(default=0)
    _bound: list[str] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "epic3-scripted"

    def bind_tools(
        self, tools: Sequence[Any], *, tool_choice: Any = None, **kwargs: Any
    ) -> Runnable[Any, Any]:
        self._bound = sorted(convert_to_openai_tool(tool)["function"]["name"] for tool in tools)
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.on_call is not None:
            self.on_call(list(self._bound), list(messages))
        message = self.script[self._index]
        self._index += 1
        return ChatResult(generations=[ChatGeneration(message=message)])
