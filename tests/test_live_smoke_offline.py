"""Exercise smoke validation using scripted responses; these tests never call OpenRouter."""

import json
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from evaluations import live_smoke
from schemas.config import RunSettings


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    def settings(*, model_max_retries: int = 0, model_timeout_seconds: int = 30) -> RunSettings:
        return RunSettings(
            _env_file=None,
            model_max_retries=model_max_retries,
            model_timeout_seconds=model_timeout_seconds,
        )

    monkeypatch.setattr(live_smoke, "RunSettings", settings)


def stub_model(monkeypatch: pytest.MonkeyPatch, response: AIMessage) -> Mock:
    model = Mock()
    model.bind_tools.return_value.invoke.return_value = response
    service = Mock()
    service.for_agent.return_value = model
    monkeypatch.setattr(live_smoke, "LLMService", Mock(return_value=service))
    return model


def test_missing_credentials_are_pending_and_not_a_pass(capsys: pytest.CaptureFixture[str]) -> None:
    assert live_smoke.main() == 2
    assert "Live acceptance pending" in capsys.readouterr().err


def test_valid_scripted_tool_call_is_validated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    model = stub_model(
        monkeypatch,
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "FoundationPing",
                    "args": {"value": "EPIC-2-ready"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
    )
    assert live_smoke.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "passed"
    assert output["arguments"] == {"value": "EPIC-2-ready"}
    assert model.bind_tools.return_value.invoke.call_args.kwargs["max_tokens"] == 128
    assert model.bind_tools.return_value.invoke.call_args.kwargs["retries"] is None


@pytest.mark.parametrize(
    "calls",
    [
        [],
        [{"name": "WrongTool", "args": {"value": "EPIC-2-ready"}, "id": "1", "type": "tool_call"}],
        [{"name": "FoundationPing", "args": {"value": "wrong"}, "id": "1", "type": "tool_call"}],
        [
            {
                "name": "FoundationPing",
                "args": {"value": "EPIC-2-ready"},
                "id": "",
                "type": "tool_call",
            }
        ],
    ],
)
def test_invalid_scripted_calls_fail(
    monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, object]]
) -> None:
    stub_model(monkeypatch, AIMessage(content="", tool_calls=calls))
    assert live_smoke.main() == 1


def test_provider_exception_does_not_expose_sensitive_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    model = stub_model(monkeypatch, AIMessage(content=""))
    model.bind_tools.return_value.invoke.side_effect = RuntimeError("sensitive-provider-body")
    assert live_smoke.main() == 1
    output = capsys.readouterr().err
    assert "RuntimeError" in output
    assert "sensitive-provider-body" not in output


def test_live_smoke_rejects_nonproduction_model_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODELS__WRITER_AGENT", "openrouter:example/other")
    assert live_smoke.main() == 1
