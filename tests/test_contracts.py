"""Validation at pipeline hand-offs, including strict malformed input rejection."""

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from schemas.requests import ResearchRequest
from schemas.responses import FetchedPage, RunReport, SearchResult, Source


@pytest.mark.parametrize("topic", ["", "  ", "ab", " ab ", "x" * 251, 42, None])
def test_rejects_invalid_topic_with_named_field(topic: object) -> None:
    with pytest.raises(ValidationError) as error:
        ResearchRequest.model_validate({"topic": topic})
    assert error.value.errors()[0]["loc"] == ("topic",)


@pytest.mark.parametrize("topic", ["abc", "x" * 250, "  2026 agentic AI frameworks  "])
def test_accepts_trimmed_topic_and_default_budgets(topic: str) -> None:
    request = ResearchRequest(topic=topic)
    assert request.topic == topic.strip()
    assert (request.pages, request.per_page, request.max_urls) == (3, 10, 30)


@pytest.mark.parametrize("field", ["pages", "per_page", "max_urls"])
@pytest.mark.parametrize("value", [0, -1, True, "three", 1.5])
def test_rejects_malformed_budget(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as error:
        ResearchRequest.model_validate({"topic": "Valid topic", field: value})
    assert (field,) in [entry["loc"] for entry in error.value.errors()]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ResearchRequest.model_validate({"topic": "Valid topic", "surprise": 1})


@pytest.mark.parametrize(
    "model,fields",
    [
        (ResearchRequest, {"topic", "pages", "per_page", "max_urls"}),
        (SearchResult, {"url", "title", "snippet", "rank", "query"}),
        (FetchedPage, {"html", "status", "final_url"}),
        (
            Source,
            {
                "source_id",
                "url",
                "title",
                "author",
                "published",
                "body_markdown",
                "word_count",
                "fetched_at",
            },
        ),
        (
            RunReport,
            {
                "run_id",
                "topic",
                "model",
                "status",
                "status_reasons",
                "phase_timings_seconds",
                "urls_found",
                "urls_clean",
                "urls_fetched",
                "urls_extracted",
                "urls_thin",
                "urls_failed",
                "extraction_failures",
                "url_outcomes",
                "blog_path",
                "citation_count",
                "tokens_used",
                "cost_usd",
                "duration_seconds",
                "retries",
            },
        ),
    ],
)
def test_contracts_include_prd_fields(model: type[BaseModel], fields: set[str]) -> None:
    assert issubclass(model, BaseModel)
    assert set(model.model_fields) == fields


def source_payload() -> dict[str, object]:
    return {
        "source_id": "S-07",
        "url": "https://example.com/article",
        "title": "Article",
        "author": None,
        "published": None,
        "body_markdown": "Clean content",
        "word_count": 2,
        "fetched_at": datetime(2026, 10, 1, tzinfo=UTC),
    }


def test_source_json_round_trip_preserves_url_and_timestamp() -> None:
    source = Source.model_validate(source_payload())
    assert Source.model_validate_json(source.model_dump_json()) == source
    assert source.model_dump()["url"] == "https://example.com/article"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "invalid"),
        ("url", "ftp://example.com/article"),
        ("word_count", -1),
        ("fetched_at", datetime(2026, 10, 1)),
    ],
)
def test_source_rejects_malformed_metadata(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as error:
        Source.model_validate({**source_payload(), field: value})
    assert (field,) in [entry["loc"] for entry in error.value.errors()]


def test_fetched_page_preserves_non_success_status_for_failure_handling() -> None:
    page = FetchedPage.model_validate(
        {"html": "", "status": 404, "final_url": "https://example.com/"}
    )
    assert page.status == 404
    with pytest.raises(ValidationError, match="status"):
        FetchedPage.model_validate({"html": "", "status": 600, "final_url": "https://example.com/"})


def test_report_validates_counts_status_and_json() -> None:
    payload = {
        "run_id": "demo",
        "topic": "Valid topic",
        "model": "openrouter:test",
        "status": "succeeded",
        "urls_found": 30,
        "urls_extracted": 24,
        "extraction_failures": 6,
        "blog_path": "output/blog.md",
        "citation_count": 20,
        "tokens_used": 1000,
        "cost_usd": 0.5,
        "duration_seconds": 4.5,
    }
    report = RunReport.model_validate(payload)
    assert RunReport.model_validate_json(report.model_dump_json()) == report
    for field, value in (
        ("status", "ready"),
        ("urls_found", -1),
        ("duration_seconds", float("inf")),
    ):
        with pytest.raises(ValidationError, match=field):
            RunReport.model_validate({**payload, field: value})
