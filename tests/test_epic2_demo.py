"""The offline demonstration reports real validated state and expected rejections."""

import json

import pytest

from evaluations.epic2_demo import main
from schemas.config import AGENT_NAMES, PRODUCTION_MODEL


def test_demo_runs_offline_and_demonstrates_building_blocks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "offline; no provider request"
    assert result["topic"] == "2026 agentic AI frameworks"
    assert result["budgets"] == [3, 10, 30]
    assert result["checkpoint_restored"] is True
    assert result["fake_injection_verified"] is True
    assert result["run"]["completed_phases"] == ["search"]
    assert len(result["expected_rejections"]) == 4
    assert len(result["rejected_agent_patterns"]) == 3
    assert set(result["prompts_loaded"]) == set(AGENT_NAMES)
    assert set(result["configured_models"].values()) == {PRODUCTION_MODEL}
