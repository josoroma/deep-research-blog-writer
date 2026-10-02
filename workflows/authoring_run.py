"""EPIC-7 milestone: synthesize the corpus and write the cited draft.

The analyst and writer run through the configured model, which writes the files
through the workspace backend. The citation gate is deterministic: it validates,
and on failure re-invokes the writer at most twice (PD-016). The draft is never
regenerated for length (PD-015).
"""

import json
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage

from agents.deep_research import build_deep_agent
from schemas.common import Contract, SourceID
from schemas.config import RunSettings
from schemas.state import RunState
from schemas.tool_io import ValidateCitationsOutput
from schemas.workspace import RunWorkspace
from services.artifacts import write_json
from services.authoring import BLOG_PATH, SUMMARY_PATH, check_blog, validate_citations
from services.llm_service import LLMService
from services.observability import (
    bind_workspace,
    current_observer,
    observed_config,
    observed_workflow,
)
from tools.authoring_tools import AuthoringSession
from tools.registry import create_tool_registry
from workflows.search_run import tool_runtime

MAX_REPAIR_PASSES = 2
GATE_REPORT = "output/run.json"


class AuthoringSummary(Contract):
    run_id: str
    workspace: str
    status: Literal["completed", "failed"]
    summary_path: str | None = None
    blog_path: str | None = None
    word_count: int = 0
    citations_checked: int = 0
    repair_passes: int = 0
    dangling_source_ids: list[SourceID] = []
    mismatched_source_ids: list[SourceID] = []
    reason: str | None = None
    error: str | None = None


def _record(workspace: Path, summary: AuthoringSummary) -> None:
    """The citation-gate record. The full run report stays in US-8.1."""
    write_json(workspace / GATE_REPORT, summary.model_dump(mode="json"))


def load_corpus_run(workspace: Path) -> RunState:
    """The corpus state written by the EPIC-6 milestone."""
    return RunState.model_validate(json.loads((workspace / "corpus_state.json").read_text()))


def validate_now(workspace: Path) -> ValidateCitationsOutput:
    """Validate the current draft without recording a phase."""
    finding = validate_citations(workspace)
    return ValidateCitationsOutput(
        citations_checked=finding.citations_checked,
        dangling_source_ids=finding.dangling_source_ids,
        mismatched_source_ids=finding.mismatched_source_ids,
        run=load_corpus_run(workspace),
    )


def _finish(workspace: Path, run: RunState, summary: AuthoringSummary) -> AuthoringSummary:
    blog = check_blog(workspace)
    summary.blog_path = BLOG_PATH if blog.present else None
    summary.word_count = blog.word_count
    summary.summary_path = SUMMARY_PATH if (workspace / SUMMARY_PATH).is_file() else None
    if not blog.present or not blog.headings_valid:
        summary.status = "failed"
        summary.reason = "blog_structure"
        summary.error = "output/blog.md is missing or its headings are out of order"
        _record(workspace, summary)
        return summary
    if not blog.within_length:
        summary.reason = "blog_length"
    session = AuthoringSession(workspace, run)
    registry = create_tool_registry(authoring_session=session)
    finding = registry["validate_citations"].invoke({}, tool_runtime(run))
    assert isinstance(finding, ValidateCitationsOutput)
    summary.citations_checked = finding.citations_checked
    summary.dangling_source_ids = list(finding.dangling_source_ids)
    summary.mismatched_source_ids = list(finding.mismatched_source_ids)
    if not finding.passed:
        summary.status = "failed"
        summary.reason = "dangling_citations"
    _record(workspace, summary)
    return summary


@observed_workflow("authoring")
def run_authoring(
    workspace: Path, settings: RunSettings, *, llm: LLMService | None = None
) -> AuthoringSummary:
    """Run the analyst, the writer, and at most two citation repair passes."""
    run = load_corpus_run(workspace)
    bind_workspace(workspace, run.topic)
    summary = AuthoringSummary(run_id=run.run_id, workspace=str(workspace), status="completed")
    service = llm or LLMService(settings)
    agent = build_deep_agent(
        service,
        RunWorkspace(root=workspace, run_id=run.run_id),
        tool_registry=create_tool_registry(),
    )
    prompts = [
        "Read every source file and write research/summary.md.",
        "Write output/blog.md once from the corpus and the summary.",
    ]
    try:
        for prompt in prompts:
            agent.invoke(
                {"messages": [HumanMessage(content=prompt)], "run": run},
                config=observed_config(settings.recursion_limit),
            )
        for _ in range(MAX_REPAIR_PASSES):
            finding = validate_now(workspace)
            if finding.passed:
                break
            outstanding = finding.dangling_source_ids + finding.mismatched_source_ids
            summary.repair_passes += 1
            observer = current_observer()
            if observer is not None:
                observer.retry("citations", "citation_repair")
            agent.invoke(
                {
                    "messages": [
                        HumanMessage(
                            content="Fix or remove these dangling citations: "
                            + ", ".join(outstanding)
                        )
                    ],
                    "run": run,
                },
                config=observed_config(settings.recursion_limit),
            )
    except Exception as error:  # noqa: BLE001 - the CLI reports any invocation failure
        summary.status = "failed"
        summary.error = type(error).__name__
        _record(workspace, summary)
        return summary
    return _finish(workspace, run, summary)
