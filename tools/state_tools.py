"""Deterministic, idempotent progress update; no model or provider calls."""

from langchain.tools import ToolRuntime

from schemas.requests import CompletePhaseInput
from schemas.state import ResearchAgentState, RunState, RunStateUpdate


def record_phase_completion(
    request: CompletePhaseInput, runtime: ToolRuntime[None, ResearchAgentState] | None
) -> RunStateUpdate:
    if runtime is None:
        raise ValueError("record_phase_completion requires ToolRuntime with run state")
    current = RunState.model_validate(runtime.state["run"])
    phases = list(current.completed_phases)
    if request.phase not in phases:
        phases.append(request.phase)
    return RunStateUpdate(run=current.replaced(completed_phases=phases))
