"""US-11.1: every agent has a PD-022 skill file and a traceable contract."""

import re
from pathlib import Path

import pytest

from schemas.config import AGENT_NAMES, AgentName

DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs" / "architecture" / "agents"

SKILL_SECTIONS = (
    "Purpose",
    "Capabilities",
    "Non-Capabilities",
    "Inputs",
    "Outputs",
    "Available Tools",
    "Security",
    "Observability",
    "Evaluation Criteria",
    "Failure Modes",
    "Example",
)

CONTRACT_SECTIONS = ("Input", "Output", "Success criteria", "Failure conditions")

# Every Pydantic contract the agents consume or produce, by class name.
CONTRACT_TYPES = frozenset(
    {
        "ResearchRequest",
        "QueryVariants",
        "SearchPlan",
        "SearchPlanOutput",
        "RunState",
        "RunStateUpdate",
        "GoogleSearchInput",
        "GoogleSearchOutput",
        "SearchResult",
        "NormalizeResultsInput",
        "NormalizeResultsOutput",
        "CollectSourceInput",
        "CollectSourceOutput",
        "SourceMetadata",
        "BuildIndexInput",
        "BuildIndexOutput",
        "ValidateCitationsInput",
        "ValidateCitationsOutput",
        "WriteRunReportInput",
        "WriteRunReportOutput",
        "Source",
        "RunReport",
        "UrlOutcome",
    }
)

SOURCE_REFERENCE = re.compile(r"\b(?:PRD\.md|SPECS\.md)\b")


def _agent_dir(agent: AgentName) -> Path:
    return DOCS_ROOT / agent


def _section(text: str, heading: str) -> str:
    """Return the body of a level-2 section, up to the next level-2 heading."""
    match = re.search(
        rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing section: {heading}"
    return match.group(1)


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_every_agent_has_a_skill_file(agent: AgentName) -> None:
    skill = _agent_dir(agent) / "skill.md"
    assert skill.is_file(), f"{agent} is missing skill.md"
    assert skill.read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_every_agent_has_a_contract(agent: AgentName) -> None:
    contract = _agent_dir(agent) / "contract.md"
    assert contract.is_file(), f"{agent} is missing contract.md"
    assert contract.read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_skill_file_carries_every_pd022_section(agent: AgentName) -> None:
    text = (_agent_dir(agent) / "skill.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
    assert headings == list(SKILL_SECTIONS), f"{agent} sections are out of order"


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_skill_inputs_and_outputs_name_contract_types(agent: AgentName) -> None:
    text = (_agent_dir(agent) / "skill.md").read_text(encoding="utf-8")
    for heading in ("Inputs", "Outputs"):
        body = _section(text, heading)
        named = {name for name in CONTRACT_TYPES if f"`{name}`" in body}
        assert named, f"{agent} {heading} names no Pydantic contract type"


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_contract_states_input_output_success_and_failure(agent: AgentName) -> None:
    text = (_agent_dir(agent) / "contract.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
    assert headings == list(CONTRACT_SECTIONS), f"{agent} contract sections are wrong"
    for heading in CONTRACT_SECTIONS:
        assert _section(text, heading).strip(), f"{agent} {heading} is empty"


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_contract_success_criteria_are_traceable(agent: AgentName) -> None:
    text = (_agent_dir(agent) / "contract.md").read_text(encoding="utf-8")
    body = _section(text, "Success criteria")
    rows = [line for line in body.splitlines() if line.strip().startswith("|")]
    # Drop the header and separator rows.
    data_rows = rows[2:]
    assert len(data_rows) >= 2, f"{agent} has too few success criteria"
    for row in data_rows:
        assert SOURCE_REFERENCE.search(row), f"{agent} criterion is not traceable: {row}"


def test_docs_index_links_every_agent() -> None:
    index = (DOCS_ROOT.parent / "README.md").read_text(encoding="utf-8")
    for agent in AGENT_NAMES:
        assert f"agents/{agent}/skill.md" in index
        assert f"agents/{agent}/contract.md" in index
