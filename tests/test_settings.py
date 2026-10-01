"""Configuration validation, precedence, model overrides, and secret masking."""

from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from schemas.config import AGENT_NAMES, PRODUCTION_MODEL, AgentModels, AgentName, RunSettings


def test_production_defaults_for_all_five_agents() -> None:
    settings = RunSettings(_env_file=None)
    assert {settings.models.for_agent(agent) for agent in AGENT_NAMES} == {PRODUCTION_MODEL}
    assert (settings.pages, settings.per_page, settings.max_urls) == (3, 10, 30)


def test_dotenv_and_environment_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "PAGES=2\nOPENROUTER_API_KEY=example-dotenv-key\nMODELS__WRITER_AGENT=openrouter:example/writer\nUNKNOWN_FUTURE_SETTING=allowed\n"
    )
    monkeypatch.setenv("PAGES", "4")
    settings = RunSettings(_env_file=env)
    assert settings.pages == 4
    assert settings.models.writer_agent == "openrouter:example/writer"
    assert settings.models.orchestrator == PRODUCTION_MODEL
    assert settings.openrouter_api_key is not None
    assert settings.openrouter_api_key.get_secret_value() == "example-dotenv-key"
    assert "example-dotenv-key" not in repr(settings)
    assert "example-dotenv-key" not in settings.model_dump_json()


def test_empty_example_keys_are_unset(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=\nSERPER_API_KEY=\n")
    settings = RunSettings(_env_file=env)
    assert settings.openrouter_api_key is settings.serper_api_key is None


@pytest.mark.parametrize(
    "field,value",
    [("PAGES", "three"), ("PER_PAGE", "0"), ("MAX_URLS", "-1"), ("MODEL_TIMEOUT_SECONDS", "0")],
)
def test_bad_environment_value_names_field(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    monkeypatch.setenv(field, value)
    with pytest.raises(ValidationError, match=field.lower()):
        RunSettings(_env_file=None)


@pytest.mark.parametrize(
    "model", ["", "deepseek/model", "openai:model", "openrouter:", "openrouter:bad model"]
)
def test_invalid_model_override_names_agent(model: str) -> None:
    with pytest.raises(ValidationError, match="writer_agent"):
        AgentModels(writer_agent=model)


def test_unknown_agent_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown agent"):
        AgentModels().for_agent(cast(AgentName, "unknown"))


@pytest.mark.parametrize("value", [True, 1.5, "3.0", "three"])
def test_settings_reject_wrong_integer_types(value: object) -> None:
    with pytest.raises(ValidationError, match="pages"):
        RunSettings(_env_file=None, pages=cast(int, value))
