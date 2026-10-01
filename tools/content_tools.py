"""Internal typed fetch/extract tools; agents receive metadata via EPIC-6 collection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from schemas.content import ExtractionResult, FetchResult
from schemas.tool_io import ExtractMarkdownInput, FetchUrlInput
from services.extraction_service import ExtractionService

if TYPE_CHECKING:
    from services.fetch_service import Fetcher
    from tools.registry import Runtime, ToolRegistry


def register_content_tools(
    registry: ToolRegistry,
    fetcher: Fetcher | None,
    extractor: ExtractionService | None,
) -> None:
    from tools.registry import TypedTool

    extraction = extractor if extractor is not None else ExtractionService()

    def fetch(request: FetchUrlInput, runtime: Runtime | None = None) -> FetchResult:
        if fetcher is None:
            raise RuntimeError("fetch_url requires a run-owned FetchService binding")
        return fetcher.fetch(request.url)

    def extract(request: ExtractMarkdownInput, runtime: Runtime | None = None) -> ExtractionResult:
        return extraction.extract(request)

    registry.register(
        TypedTool[FetchUrlInput, FetchResult](
            name="fetch_url",
            input_model=FetchUrlInput,
            output_model=FetchResult,
            handler=fetch,
            description="Internal: fetch permitted HTML with retries and shared politeness limits.",
        )
    )
    registry.register(
        TypedTool[ExtractMarkdownInput, ExtractionResult](
            name="extract_markdown",
            input_model=ExtractMarkdownInput,
            output_model=ExtractionResult,
            handler=extract,
            description="Internal: extract clean Markdown with ordered parser fallback.",
        )
    )
