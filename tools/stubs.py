"""Typed M1 stub tools so the skeleton runs end to end without real I/O.

Every stub is deterministic, offline, and writes nothing. Production fetch and
extraction are registered separately in EPIC-5. This private fake collection
keeps the M1 skeleton runnable until EPIC-6 implements immutable corpus files.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime

from schemas.responses import FetchedPage, Source
from schemas.state import ResearchAgentState
from schemas.tool_io import (
    BuildIndexInput,
    BuildIndexStubOutput,
    CollectSourceInput,
    ExtractMarkdownInput,
    FetchUrlInput,
    SourceMetadata,
    ValidateCitationsInput,
    ValidateCitationsStubOutput,
    WriteRunReportInput,
    WriteRunReportOutput,
)

if TYPE_CHECKING:
    from tools.registry import ToolRegistry

Runtime = ToolRuntime[None, ResearchAgentState]

RAW_HTML_MARKER = "EPIC3-RAW-HTML-MARKER"
STUB_FETCHED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _stub_fetch(request: FetchUrlInput, runtime: Runtime | None = None) -> FetchedPage:
    html = f"<html><body><p>{RAW_HTML_MARKER}</p></body></html>"
    return FetchedPage(html=html, status=200, final_url=request.url)


def _stub_extract(request: ExtractMarkdownInput, runtime: Runtime | None = None) -> Source:
    title = f"Stub source {request.source_id}"
    body = f"# {title}\n\nClean stub body; raw HTML never reaches an agent."
    return Source(
        source_id=request.source_id,
        url=request.page.final_url,
        title=title,
        author=None,
        published=None,
        body_markdown=body,
        word_count=len(body.split()),
        fetched_at=STUB_FETCHED_AT,
    )


def _stub_build_index(
    request: BuildIndexInput, runtime: Runtime | None = None
) -> BuildIndexStubOutput:
    return BuildIndexStubOutput(index_path="research/index.md", sources_indexed=0)


def _stub_validate_citations(
    request: ValidateCitationsInput, runtime: Runtime | None = None
) -> ValidateCitationsStubOutput:
    return ValidateCitationsStubOutput(citations_checked=0, dangling_source_ids=[])


def _stub_write_run_report(
    request: WriteRunReportInput, runtime: Runtime | None = None
) -> WriteRunReportOutput:
    return WriteRunReportOutput(report_path="output/run.json")


def register_stub_tools(
    registry: ToolRegistry, *, corpus: bool = False, authoring: bool = False
) -> None:
    """Register the remaining future-epic stubs.

    A corpus-bound registry replaces `collect_source` and `build_index`, and an
    authoring-bound registry replaces `validate_citations`. The report stub stays
    until EPIC-8.
    """
    from tools.registry import TypedTool  # local import avoids a registry/stubs cycle

    def collect_source(
        request: CollectSourceInput, runtime: Runtime | None = None
    ) -> SourceMetadata:
        source_id = f"S-{request.rank:02d}"
        page = _stub_fetch(FetchUrlInput(url=request.url))
        source = _stub_extract(ExtractMarkdownInput(page=page, source_id=source_id))
        assert isinstance(source, Source)
        return SourceMetadata(
            source_id=source_id,
            path=f"research/{request.rank:03d}_stub-source-{request.rank}.md",
            title=source.title,
            word_count=source.word_count,
        )

    if not corpus:
        registry.register(
            TypedTool[CollectSourceInput, SourceMetadata](
                name="collect_source",
                input_model=CollectSourceInput,
                output_model=SourceMetadata,
                handler=collect_source,
                description="M1 stub pending EPIC-6: fake metadata; no corpus file is written.",
            )
        )
        registry.register(
            TypedTool[BuildIndexInput, BuildIndexStubOutput](
                name="build_index",
                input_model=BuildIndexInput,
                output_model=BuildIndexStubOutput,
                handler=_stub_build_index,
                description="M1 stub: report the corpus index path; no index is written yet.",
            )
        )
    if not authoring:
        registry.register(
            TypedTool[ValidateCitationsInput, ValidateCitationsStubOutput](
                name="validate_citations",
                input_model=ValidateCitationsInput,
                output_model=ValidateCitationsStubOutput,
                handler=_stub_validate_citations,
                description="M1 stub: report no citations checked; no validation yet.",
            )
        )
    registry.register(
        TypedTool[WriteRunReportInput, WriteRunReportOutput](
            name="write_run_report",
            input_model=WriteRunReportInput,
            output_model=WriteRunReportOutput,
            handler=_stub_write_run_report,
            description="M1 stub: report the run report path; no report is written yet.",
        )
    )
