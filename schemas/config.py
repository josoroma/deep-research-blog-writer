"""Environment-backed run configuration and independently selectable agent models."""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from schemas.common import Contract

AgentName = Literal[
    "orchestrator", "search_agent", "research_agent", "analyst_agent", "writer_agent"
]
AGENT_NAMES: tuple[AgentName, ...] = (
    "orchestrator",
    "search_agent",
    "research_agent",
    "analyst_agent",
    "writer_agent",
)
PRODUCTION_MODEL = "openrouter:deepseek/deepseek-v4.1-flash"


def validate_model_id(value: str) -> str:
    provider, separator, model = value.partition(":")
    if provider != "openrouter" or not separator or not model or any(c.isspace() for c in value):
        raise ValueError("Model must be a nonempty openrouter:<model-id> without whitespace")
    return value


ModelID = Annotated[str, AfterValidator(validate_model_id)]


class AgentModels(Contract):
    orchestrator: ModelID = PRODUCTION_MODEL
    search_agent: ModelID = PRODUCTION_MODEL
    research_agent: ModelID = PRODUCTION_MODEL
    analyst_agent: ModelID = PRODUCTION_MODEL
    writer_agent: ModelID = PRODUCTION_MODEL

    def for_agent(self, agent: AgentName) -> str:
        if agent not in AGENT_NAMES:
            raise ValueError(f"Unknown agent: {agent}")
        models = {
            "orchestrator": self.orchestrator,
            "search_agent": self.search_agent,
            "research_agent": self.research_agent,
            "analyst_agent": self.analyst_agent,
            "writer_agent": self.writer_agent,
        }
        return models[agent]


class RunSettings(BaseSettings):
    """Environment overrides .env; empty example credentials count as unset.

    Settings coerce environment strings (e.g. PAGES=3); malformed values still fail.
    Extra .env keys are ignored so later integration settings can share the file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    openrouter_api_key: SecretStr | None = None
    serper_api_key: SecretStr | None = None
    serpapi_api_key: SecretStr | None = None
    search_provider: Literal["serper", "serpapi"] = "serpapi"
    search_timeout_seconds: int = Field(default=15, ge=1, strict=True)
    pages: int = Field(default=3, ge=1, strict=True)
    per_page: int = Field(default=10, ge=1, strict=True)
    max_urls: int = Field(default=30, ge=1, strict=True)
    models: AgentModels = Field(default_factory=AgentModels)
    model_timeout_seconds: int = Field(default=30, ge=1, strict=True)
    model_max_retries: int = Field(default=2, ge=0, strict=True)
    runs_dir: str = Field(default="runs", min_length=1)
    recursion_limit: int = Field(default=50, ge=1, strict=True)

    @field_validator(
        "pages",
        "per_page",
        "max_urls",
        "model_timeout_seconds",
        "model_max_retries",
        "recursion_limit",
        "search_timeout_seconds",
        mode="before",
    )
    @classmethod
    def parse_integer_environment(cls, value: object) -> object:
        return int(value) if isinstance(value, str) else value
