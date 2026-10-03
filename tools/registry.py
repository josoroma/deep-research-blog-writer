"""Assemble the per-run tool registry from the typed tool modules.

The primitives (``TypedTool``, ``ToolRegistry``, ``Runtime``) live in
``tools.base`` and are re-exported here for existing callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from schemas.requests import CompletePhaseInput
from schemas.state import RunStateUpdate
from services.observability import current_observer
from tools.authoring_tools import AuthoringSession, register_authoring_tools
from tools.base import (
    Runtime,
    ToolDefinition,
    ToolOutputError,
    ToolRegistry,
    TypedTool,
    validate_definition,
)
from tools.content_tools import register_content_tools
from tools.corpus_tools import CorpusSession, register_corpus_tools
from tools.report_tools import ReportSession, register_report_tools
from tools.search_tools import register_search_tools
from tools.state_tools import record_phase_completion
from tools.stubs import register_stub_tools

if TYPE_CHECKING:
    from services.extraction_service import ExtractionService
    from services.fetch_service import Fetcher
    from services.search_session import SearchSession

__all__ = [
    "TOOLS",
    "Runtime",
    "ToolDefinition",
    "ToolOutputError",
    "ToolRegistry",
    "TypedTool",
    "create_tool_registry",
    "validate_definition",
]


def create_tool_registry(
    search_session: SearchSession | None = None,
    *,
    fetcher: Fetcher | None = None,
    extractor: ExtractionService | None = None,
    corpus_session: CorpusSession | None = None,
    authoring_session: AuthoringSession | None = None,
    report_session: ReportSession | None = None,
    production: bool = False,
) -> ToolRegistry:
    """Build independent tool bindings; credentials and provider clients stay off state.

    ``production`` forbids the M1 stub collection: full execution must bind real
    sessions, so an unbound production registry fails loudly instead of silently
    reporting fake success.
    """
    registry = ToolRegistry(current_observer())
    registry.register(
        TypedTool[CompletePhaseInput, RunStateUpdate](
            name="record_phase_completion",
            input_model=CompletePhaseInput,
            output_model=RunStateUpdate,
            handler=record_phase_completion,
            description="Record a completed phase in validated run state; calls are idempotent.",
            updates_state=True,
        )
    )
    if report_session is not None:
        register_report_tools(registry, report_session)
    elif not production:
        register_stub_tools(
            registry,
            corpus=corpus_session is not None,
            authoring=authoring_session is not None,
            report=True,
        )
    register_search_tools(registry, search_session)
    register_content_tools(registry, fetcher, extractor)
    if corpus_session is not None:
        register_corpus_tools(registry, corpus_session)
    if authoring_session is not None:
        register_authoring_tools(registry, authoring_session)
    return registry


TOOLS = create_tool_registry()
