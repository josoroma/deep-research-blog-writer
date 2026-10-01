"""Typed M1 stub tools so the skeleton runs end to end without real I/O.

Every stub is deterministic, offline, and writes nothing. `collect_source` calls
`fetch_url` and `extract_markdown` through the registry, so both sides of those
calls are validated exactly as they will be once the real implementations land.
The story that replaces a stub owns its final contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime

from schemas.responses import FetchedPage, Source
from schemas.state import ResearchAgentState
from schemas.tool_io import (
    BuildIndexInput,
    BuildIndexOutput,
    CollectSourceInput,
    ExtractMarkdownInput,
    FetchUrlInput,
    SourceMetadata,
    ValidateCitationsInput,
    ValidateCitationsOutput,
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


def _stub_build_index(request: BuildIndexInput, runtime: Runtime | None = None) -> BuildIndexOutput:
    return BuildIndexOutput(index_path="research/index.md", sources_indexed=0)


def _stub_validate_citations(
    request: ValidateCitationsInput, runtime: Runtime | None = None
) -> ValidateCitationsOutput:
    return ValidateCitationsOutput(citations_checked=0, dangling_source_ids=[])


def _stub_write_run_report(
    request: WriteRunReportInput, runtime: Runtime | None = None
) -> WriteRunReportOutput:
    return WriteRunReportOutput(report_path="output/run.json")


def register_stub_tools(registry: ToolRegistry) -> None:
    """Register the M1 stubs; `collect_source` composes fetch and extract."""
    from tools.registry import TypedTool  # local import avoids a registry/stubs cycle

    def collect_source(
        request: CollectSourceInput, runtime: Runtime | None = None
    ) -> SourceMetadata:
        source_id = f"S-{request.rank:02d}"
        page = registry["fetch_url"].invoke({"url": request.url})
        source = registry["extract_markdown"].invoke(
            {"page": page.model_dump(), "source_id": source_id}
        )
        assert isinstance(source, Source)
        return SourceMetadata(
            source_id=source_id,
            path=f"research/{request.rank:03d}_stub-source-{request.rank}.md",
            title=source.title,
            word_count=source.word_count,
        )

    registry.register(
        TypedTool[FetchUrlInput, FetchedPage](
            name="fetch_url",
            input_model=FetchUrlInput,
            output_model=FetchedPage,
            handler=_stub_fetch,
            description="M1 stub: return fixed HTML; called only inside collect_source.",
        )
    )
    registry.register(
        TypedTool[ExtractMarkdownInput, Source](
            name="extract_markdown",
            input_model=ExtractMarkdownInput,
            output_model=Source,
            handler=_stub_extract,
            description="M1 stub: return a fixed clean source; called only inside collect_source.",
        )
    )
    registry.register(
        TypedTool[CollectSourceInput, SourceMetadata](
            name="collect_source",
            input_model=CollectSourceInput,
            output_model=SourceMetadata,
            handler=collect_source,
            description="M1 stub: fetch and extract one URL, returning metadata only.",
        )
    )
    registry.register(
        TypedTool[BuildIndexInput, BuildIndexOutput](
            name="build_index",
            input_model=BuildIndexInput,
            output_model=BuildIndexOutput,
            handler=_stub_build_index,
            description="M1 stub: report the corpus index path; no index is written yet.",
        )
    )
    registry.register(
        TypedTool[ValidateCitationsInput, ValidateCitationsOutput](
            name="validate_citations",
            input_model=ValidateCitationsInput,
            output_model=ValidateCitationsOutput,
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
