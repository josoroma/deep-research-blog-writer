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
    crawler_contact: str | None = None
    extractor_strategy: Literal["fallback", "trafilatura", "readability", "beautifulsoup"] = (
        "fallback"
    )
    pages: int = Field(default=3, ge=1, strict=True)
    per_page: int = Field(default=10, ge=1, strict=True)
    max_urls: int = Field(default=30, ge=1, strict=True)
    models: AgentModels = Field(default_factory=AgentModels)
    model_timeout_seconds: int = Field(default=30, ge=1, strict=True)
    model_max_retries: int = Field(default=2, ge=0, strict=True)
    runs_dir: str = Field(default="runs", min_length=1)
    recursion_limit: int = Field(default=50, ge=1, strict=True)
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str = Field(default="deep-research-blog-writer", min_length=1)
    otel_exporter_otlp_endpoint: str | None = None
    telemetry_timeout_seconds: float = Field(default=3.0, gt=0, le=30, allow_inf_nan=False)

    @field_validator("langsmith_endpoint", "otel_exporter_otlp_endpoint")
    @classmethod
    def validate_telemetry_endpoint(cls, value: str | None) -> str | None:
        from urllib.parse import urlsplit

        if value is None:
            return None
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise ValueError("Telemetry endpoint must be an HTTP(S) URL without credentials")
        if parts.query or parts.fragment:
            raise ValueError("Telemetry endpoint must not contain a query or fragment")
        return value.rstrip("/")

    @field_validator("crawler_contact")
    @classmethod
    def validate_crawler_contact(cls, value: str | None) -> str | None:
        from urllib.parse import urlsplit

        if value is None:
            return None
        if any(char.isspace() or char in "()<>" for char in value):
            raise ValueError("Crawler contact must be a URL or email without whitespace")
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
            return value
        email = value.removeprefix("mailto:")
        if ":" not in email and email.count("@") == 1:
            local, domain = email.split("@")
            if local and "." in domain and not domain.startswith("."):
                return f"mailto:{email}"
        raise ValueError("Crawler contact must be a public HTTP(S) URL or email")

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


RunProfile = Literal["production", "fixture"]


class ApiSettings(BaseSettings):
    """Server-only configuration; never read by local CLI execution.

    Every field is optional so a misconfigured server still boots and reports a
    truthful readiness failure instead of crashing at import. Secrets are only read
    to open connections; they never reach a response body or a run artifact.
    """

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    database: SecretStr | None = None
    token: SecretStr | None = None
    runs_dir: str = Field(default="runs-api", min_length=1)
    queue_limit: int = Field(default=100, ge=1, strict=True)
    worker_lease_seconds: int = Field(default=60, ge=5, strict=True)
    worker_poll_seconds: float = Field(default=1.0, gt=0, le=30, allow_inf_nan=False)
    worker_heartbeat_seconds: float = Field(default=10.0, gt=0, le=60, allow_inf_nan=False)
    worker_identity: str | None = None
    allowed_origins: str = ""
    run_profile: RunProfile = "production"
    max_pages: int = Field(default=3, ge=1, strict=True)
    max_per_page: int = Field(default=10, ge=1, strict=True)
    max_max_urls: int = Field(default=30, ge=1, strict=True)
    artifact_max_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, strict=True)
    log_page_limit: int = Field(default=200, ge=1, strict=True)
    log_page_max_limit: int = Field(default=1000, ge=1, strict=True)
    migrations_dir: str | None = None

    @property
    def origins(self) -> list[str]:
        """Explicit CORS origins, split on commas and trimmed."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    def database_dsn(self) -> str | None:
        if self.database is None:
            return None
        value = self.database.get_secret_value().strip()
        return value or None

    def bearer_token(self) -> str | None:
        if self.token is None:
            return None
        value = self.token.get_secret_value().strip()
        return value or None


def run_settings_for_api(api: ApiSettings) -> RunSettings:
    """Reuse process provider/model settings; only the workspace root differs.

    The server's run root is separate from the local CLI default so worker-mutated
    workspaces never collide with developer runs. Fixture execution is selected by
    `API_RUN_PROFILE`, not by a client, and injects fakes at the worker boundary.
    """
    return RunSettings(runs_dir=api.runs_dir)
