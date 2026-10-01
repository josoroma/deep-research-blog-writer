"""Central ChatOpenRouter construction and offline fake injection."""

from langchain_core.language_models import BaseChatModel
from langchain_openrouter import ChatOpenRouter

from schemas.config import AGENT_NAMES, AgentName, RunSettings


class MissingOpenRouterKey(ValueError):
    """A live model was requested without locally configured credentials."""


class LLMService:
    def __init__(self, settings: RunSettings, *, fake_model: BaseChatModel | None = None) -> None:
        self.settings = settings
        self.fake_model = fake_model

    def for_agent(self, agent: AgentName) -> BaseChatModel:
        if agent not in AGENT_NAMES:
            raise ValueError(f"Unknown agent: {agent}")
        if self.fake_model is not None:
            return self.fake_model
        key = self.settings.openrouter_api_key
        if key is None or not key.get_secret_value().strip():
            raise MissingOpenRouterKey("Set OPENROUTER_API_KEY in the environment or local .env")
        return ChatOpenRouter(
            model_name=self.settings.models.for_agent(agent).removeprefix("openrouter:"),
            openrouter_api_key=key,
            openrouter_provider={"require_parameters": True, "data_collection": "deny"},
            temperature=0,
            max_retries=self.settings.model_max_retries,
            # The locked integration forwards request_timeout as SDK timeout_ms.
            request_timeout=self.settings.model_timeout_seconds * 1000,
        )
