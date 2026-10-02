"""US-10.1: the unit suite is offline, and a provider-reaching test fails loudly.

The autouse fixture in `tests/conftest.py` strips provider credentials and replaces
`socket.socket.connect` with a failing stub. These tests prove both halves of the
contract: the suite runs with no keys and no network, and a test that tries to reach
a provider fails and names the attempted call.
"""

import os
import socket

import pytest
from langchain_core.messages import AIMessage
from langchain_openrouter import ChatOpenRouter
from pydantic import SecretStr

from evaluations.fakes import ScriptedChatModel
from schemas.config import RunSettings
from services.llm_service import LLMService, MissingOpenRouterKey

PROVIDER_KEYS = ("OPENROUTER_API_KEY", "SERPER_API_KEY", "SERPAPI_API_KEY")


def test_provider_credentials_are_unset_in_the_offline_suite() -> None:
    """Scenario: the unit suite passes offline. The fixture removes every key."""
    assert all(os.environ.get(name) is None for name in PROVIDER_KEYS)


def test_outbound_network_is_blocked_in_the_offline_suite() -> None:
    """Scenario: the unit suite passes offline. A real connection cannot be opened."""
    with pytest.raises(pytest.fail.Exception, match="Network access is forbidden"):
        socket.create_connection(("api.openrouter.ai", 443), timeout=0.1)


def test_fake_chat_model_answers_without_a_provider() -> None:
    """The scripted fixture is the offline substitute for a provider call."""
    model = ScriptedChatModel(script=[AIMessage(content="offline answer")])
    assert model.invoke("hello").content == "offline answer"


def test_provider_reaching_call_fails_and_names_the_attempt() -> None:
    """Scenario: a unit test that reaches a provider fails and reports the call.

    With no key configured, the service refuses before any client is built, and the
    error names the provider credential the test would have needed.
    """
    service = LLMService(RunSettings(_env_file=None))
    with pytest.raises(MissingOpenRouterKey, match="OPENROUTER_API_KEY"):
        service.for_agent("orchestrator")


def test_configured_provider_client_cannot_open_a_socket() -> None:
    """A constructed provider client still cannot reach the network in the suite."""
    settings = RunSettings(_env_file=None, openrouter_api_key=SecretStr("offline-example-key"))
    model = LLMService(settings).for_agent("orchestrator")
    assert isinstance(model, ChatOpenRouter)
    with pytest.raises(pytest.fail.Exception, match="Network access is forbidden"):
        socket.socket().connect(("api.openrouter.ai", 443))
