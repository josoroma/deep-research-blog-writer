"""The citation gate, bound to one run's workspace.

Validation reads the draft and the corpus. It never rewrites either, so the
repair loop in the workflow decides what happens next (PD-016).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from schemas.state import RunState
from schemas.tool_io import ValidateCitationsInput, ValidateCitationsOutput
from services.authoring import validate_citations

if TYPE_CHECKING:
    from tools.registry import Runtime, ToolRegistry


class AuthoringSession:
    """One run's workspace. Never shared across runs."""

    def __init__(self, root: Path, run: RunState) -> None:
        self.root = root
        self.run = run


def register_authoring_tools(registry: ToolRegistry, session: AuthoringSession | None) -> None:
    from tools.registry import TypedTool

    def current(runtime: Runtime | None) -> tuple[AuthoringSession, RunState]:
        if session is None or runtime is None:
            raise ValueError("Citation tools require an AuthoringSession and ToolRuntime")
        run = RunState.model_validate(runtime.state["run"])
        if run.run_id != session.run.run_id:
            raise ValueError("AuthoringSession does not match the active run")
        return session, run

    def validate(
        request: ValidateCitationsInput, runtime: Runtime | None
    ) -> ValidateCitationsOutput:
        bound, run = current(runtime)
        finding = validate_citations(bound.root)
        phases = list(run.completed_phases)
        if finding.passed and "citations" not in phases:
            phases.append("citations")
        return ValidateCitationsOutput(
            citations_checked=finding.citations_checked,
            dangling_source_ids=finding.dangling_source_ids,
            mismatched_source_ids=finding.mismatched_source_ids,
            run=run.replaced(completed_phases=phases),
        )

    registry.register(
        TypedTool[ValidateCitationsInput, ValidateCitationsOutput](
            name="validate_citations",
            input_model=ValidateCitationsInput,
            output_model=ValidateCitationsOutput,
            handler=validate,
            updates_state=True,
            description=(
                "Check every [S-NN] in output/blog.md against the corpus and the "
                "References section. Reports dangling and mismatched source ids."
            ),
        )
    )
