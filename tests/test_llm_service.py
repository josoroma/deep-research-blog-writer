"""Capture actual ChatOpenRouter SDK parameters without provider/network calls."""

from types import SimpleNamespace
from typing import cast

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_openrouter import ChatOpenRouter
from pydantic import SecretStr

from schemas.config import AGENT_NAMES, AgentModels, AgentName, RunSettings
from services.llm_service import LLMService, MissingOpenRouterKey


class StubChatAPI:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def send(self, **kwargs: object) -> dict[str, object]:
        self.requests.append(kwargs)
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "stubbed response"},
                    "finish_reason": "stop",
                }
            ]
        }


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_configured_agent_model_and_provider_preferences_reach_sdk(agent: AgentName) -> None:
    settings = RunSettings(
        _env_file=None,
        openrouter_api_key=SecretStr("example-offline-key"),
        models=AgentModels.model_validate({agent: f"openrouter:example/{agent}"}),
    )
    model = LLMService(settings).for_agent(agent)
    assert isinstance(model, ChatOpenRouter)
    assert model.model_name == f"example/{agent}"
    assert model.request_timeout == 30_000
    stub = StubChatAPI()
    model.client = SimpleNamespace(chat=stub)
    assert model.invoke("hello").content == "stubbed response"
    assert stub.requests[0]["model"] == f"example/{agent}"
    assert stub.requests[0]["provider"] == {"require_parameters": True, "data_collection": "deny"}


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_fake_injection_returns_same_model_without_credentials(agent: AgentName) -> None:
    fake = FakeMessagesListChatModel(responses=[AIMessage(content="offline")])
    service = LLMService(RunSettings(_env_file=None), fake_model=fake)
    assert service.for_agent(agent) is fake
    assert service.for_agent(agent).invoke("hello").content == "offline"


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_or_empty_key_fails_before_client_construction(key: str | None) -> None:
    settings = RunSettings(
        _env_file=None, openrouter_api_key=SecretStr(key) if key is not None else None
    )
    with pytest.raises(MissingOpenRouterKey, match="OPENROUTER_API_KEY"):
        LLMService(settings).for_agent("orchestrator")


def test_unknown_agent_fails_even_when_a_fake_is_supplied() -> None:
    fake = FakeMessagesListChatModel(responses=[AIMessage(content="offline")])
    with pytest.raises(ValueError, match="Unknown agent"):
        LLMService(RunSettings(_env_file=None), fake_model=fake).for_agent(
            cast(AgentName, "unknown")
        )
