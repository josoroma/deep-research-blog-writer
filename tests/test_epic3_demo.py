"""The offline EPIC-3 demonstration reports real skeleton acceptance facts."""

import json

import pytest

from evaluations.epic3_demo import main
from schemas.config import AGENT_NAMES


def test_demo_runs_offline_and_reports_acceptance_facts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "offline; no provider request"
    assert result["subagents"] == {
        "search_agent": ["google_search"],
        "research_agent": ["collect_source"],
        "analyst_agent": [],
        "writer_agent": [],
    }
    assert result["orchestrator_tools"] == [
        "normalize_results",
        "build_index",
        "validate_citations",
        "write_run_report",
    ]
    assert set(result["prompts_loaded"]) == set(AGENT_NAMES)
    assert result["todos"] == [
        "plan",
        "search",
        "normalize",
        "fetch",
        "index",
        "synthesize",
        "write",
        "citations",
        "report",
    ]
    assert result["marker_in_model_contexts"] is False
    assert result["general_purpose_rejected"] is True
    assert result["containment_refused"] is True
    assert result["blog_exists"] is True
    assert "output/blog.md" in result["files_on_disk"]
    assert "research/summary.md" in result["files_on_disk"]
