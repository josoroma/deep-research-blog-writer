"""Reviewed prompt resources and recursive enforcement of the agent boundary."""

from importlib.resources import files
from pathlib import Path
from typing import cast

import pytest

from evaluations.agent_architecture import find_agent_architecture_violations
from prompts.catalog import load_prompt
from schemas.config import AGENT_NAMES, AgentName


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_catalog_returns_exact_resource_content(agent: AgentName) -> None:
    assert load_prompt(agent) == files("prompts").joinpath(f"{agent}.md").read_text(
        encoding="utf-8"
    )
    assert load_prompt(agent).strip()


def test_orchestrator_carries_rules_workflow_and_governing_product_decisions() -> None:
    prompt = load_prompt("orchestrator")
    for rule in (
        "Agents orchestrate",
        "Every source is a file",
        "Cite only the corpus",
        "Never abort",
        "Respect the budget",
        "No paywalled/gated content",
    ):
        assert rule in prompt
    for phase in (
        "Plan",
        "Search",
        "Normalize",
        "Fetch + extract",
        "Index",
        "Synthesize",
        "Write",
        "Citation gate",
        "Report",
    ):
        assert phase in prompt
    for required in (
        "collect_source",
        "normalize_results",
        "validate_citations",
        "write_run_report",
        "at most 2",
        "must not be loaded as a runtime skill",
        "immutable",
    ):
        assert required in prompt


@pytest.mark.parametrize("name", ["unknown", "../writer_agent", "/tmp/secrets"])
def test_prompt_name_is_allowlisted(name: str) -> None:
    with pytest.raises(ValueError, match="Unknown agent"):
        load_prompt(cast(AgentName, name))


def test_repository_agent_modules_respect_prompt_and_model_boundary() -> None:
    violations = find_agent_architecture_violations(Path(__file__).resolve().parents[1] / "agents")
    assert not violations, "\n".join(map(str, violations))


@pytest.mark.parametrize(
    "source",
    [
        'create_deep_agent(system_prompt="inline")',
        'create_deep_agent(instructions="inline")',
        'create_deep_agent(system_prompt=f"inline {name}")',
        'PROMPT = "inline"\ncreate_deep_agent(system_prompt=PROMPT)',
        'PROMPT: str = "inline"\ncreate_deep_agent(system_prompt=PROMPT)',
        'A = "one"\nB = A\ncreate_deep_agent(system_prompt=B)',
        'create_deep_agent(system_prompt="one" + "two")',
        'SUBAGENTS = [{"name": "writer_agent", "system_prompt": "inline"}]',
        'PROMPT = "inline"\nSUBAGENTS = [{"system_prompt": PROMPT}]',
    ],
)
def test_inline_prompt_in_nested_agent_is_rejected(tmp_path: Path, source: str) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    path = nested / "writer.py"
    path.write_text(source + "\n")
    violations = find_agent_architecture_violations(tmp_path)
    assert any("inline system prompt" in violation.rule for violation in violations)
    assert all(violation.path == path for violation in violations)


@pytest.mark.parametrize(
    "source",
    [
        'from langchain_openrouter import ChatOpenRouter as Client\nClient(model="example")',
        'from langchain_openai import ChatOpenAI\nChatOpenAI(model="example")',
        "import openrouter\nopenrouter.OpenRouter()",
        'from langchain.chat_models import init_chat_model as client\nclient(model="example")',
        'ChatAnthropic(model="example")',
    ],
)
def test_provider_construction_and_imports_are_rejected(tmp_path: Path, source: str) -> None:
    (tmp_path / "agent.py").write_text(source + "\n")
    violations = find_agent_architecture_violations(tmp_path)
    assert any("provider" in violation.rule for violation in violations)


@pytest.mark.parametrize(
    "source",
    [
        "from prompts.catalog import load_prompt\n"
        'create_deep_agent(system_prompt=load_prompt("writer_agent"))',
        'PROMPT = load_prompt("orchestrator")\ncreate_deep_agent(system_prompt=PROMPT)',
        'SUBAGENTS = [{"system_prompt": load_prompt("writer_agent")}]',
        'from services.llm_service import LLMService\nservice.for_agent("writer_agent")',
        "from . import local_helper",
        "A = B\nB = A\ncreate_deep_agent(system_prompt=A)",
    ],
)
def test_catalog_loading_and_service_access_are_allowed(tmp_path: Path, source: str) -> None:
    (tmp_path / "agent.py").write_text(source + "\n")
    assert find_agent_architecture_violations(tmp_path) == []


def test_missing_directory_and_invalid_syntax_fail(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        find_agent_architecture_violations(tmp_path / "missing")
    (tmp_path / "broken.py").write_text("def broken(\n")
    with pytest.raises(SyntaxError):
        find_agent_architecture_violations(tmp_path)
