"""US-5.3: real parsers and branch probes against original packaged HTML."""

import json
from collections.abc import Sequence

import pytest
from pydantic import HttpUrl, ValidationError
from trafilatura.settings import Document

from evaluations.fetch_fixtures import fixture_html
from schemas.config import RunSettings
from schemas.content import ExtractionResult, FetchResult, ParsedArticle, ParserAttempt, utc_now
from schemas.responses import FetchedPage
from schemas.tool_io import ExtractMarkdownInput
from services.extraction_service import (
    BeautifulSoupExtractor,
    ExtractionService,
    Extractor,
    ReadabilityExtractor,
    TrafilaturaExtractor,
    create_extraction_service,
    word_count,
)
from tools.registry import create_tool_registry


def request(name: str = "article") -> ExtractMarkdownInput:
    return ExtractMarkdownInput(
        page=FetchedPage(
            html=fixture_html(name), status=200, final_url=HttpUrl("https://fixture.test/fetched")
        ),
        source_id="S-01",
    )


@pytest.mark.parametrize(
    "parser", [TrafilaturaExtractor(), ReadabilityExtractor(), BeautifulSoupExtractor()]
)
@pytest.mark.parametrize("fixture", ["article", "missing-metadata", "boilerplate-heavy"])
def test_real_parsers_extract_main_body_and_optional_metadata(
    parser: Extractor, fixture: str
) -> None:
    result = ExtractionService([parser]).extract(request(fixture))
    assert result.outcome == "extracted" and result.source is not None
    source = result.source
    assert source.title == "Polite Evidence Collection"
    assert source.word_count >= 200
    assert "Public research depends" in source.body_markdown
    for chrome in ("NAV_SENTINEL", "FOOTER_SENTINEL", "SIDEBAR_SENTINEL", "author:"):
        assert chrome not in source.body_markdown
    assert not source.body_markdown.startswith("---")
    if fixture == "missing-metadata":
        assert source.author is None and source.published is None
        assert str(source.url) == "https://fixture.test/fetched"
    else:
        assert source.author == "Alex Researcher" and source.published == "2026-09-01"
        assert str(source.url) == "https://fixture.test/canonical?id=7"


class CandidateExtractor:
    def __init__(self, name: str, words: int | None, *, fail: bool = False) -> None:
        self.name, self.words, self.fail = name, words, fail
        self.called = 0

    def extract(self, page: FetchedPage) -> ParsedArticle | None:
        self.called += 1
        if self.fail:
            raise RuntimeError("Secret fixture error must not enter artifacts")
        if self.words is None:
            return None
        return ParsedArticle(title="Injected parser", body_markdown="evidence " * self.words)


@pytest.mark.parametrize("first", [None, 0, 199])
@pytest.mark.parametrize("second", [None, 0, 199])
def test_empty_and_thin_parsers_fall_back_in_order(first: int | None, second: int | None) -> None:
    parsers = [
        CandidateExtractor("trafilatura", first),
        CandidateExtractor("readability-lxml", second),
        CandidateExtractor("beautifulsoup4", 200),
        CandidateExtractor("unused", 300),
    ]
    result = ExtractionService(parsers).extract(request())
    assert result.outcome == "extracted" and result.source is not None
    assert [attempt.parser for attempt in result.attempts] == [
        parser.name for parser in parsers[:3]
    ]
    assert result.source.word_count == 200 and parsers[3].called == 0


def test_errors_fall_back_and_all_errors_have_safe_reason() -> None:
    bad = CandidateExtractor("broken", None, fail=True)
    result = ExtractionService([bad, BeautifulSoupExtractor()]).extract(request())
    assert result.outcome == "extracted" and result.attempts[0].error == "RuntimeError"
    failed = ExtractionService([bad]).extract(request())
    assert failed.outcome == "extraction_failed" and failed.source is None
    assert "Secret" not in failed.model_dump_json()


@pytest.mark.parametrize("words,outcome", [(199, "too_thin"), (200, "extracted")])
def test_exact_body_word_threshold(words: int, outcome: str) -> None:
    result = ExtractionService([CandidateExtractor("custom", words)]).extract(request())
    assert result.outcome == outcome


def test_real_chain_records_thin_page_without_source() -> None:
    result = ExtractionService().extract(request("thin"))
    assert result.outcome == "too_thin" and result.source is None
    assert [attempt.parser for attempt in result.attempts] == [
        "trafilatura",
        "readability-lxml",
        "beautifulsoup4",
    ]
    assert all(attempt.word_count < 200 for attempt in result.attempts)


@pytest.mark.parametrize(
    "strategy,parser_name",
    [
        ("fallback", "trafilatura"),
        ("trafilatura", "trafilatura"),
        ("readability", "readability-lxml"),
        ("beautifulsoup", "beautifulsoup4"),
    ],
)
def test_config_selects_real_extractor_through_registered_tool(
    strategy: str, parser_name: str
) -> None:
    settings = RunSettings(_env_file=None, extractor_strategy=strategy)
    registry = create_tool_registry(extractor=create_extraction_service(settings))
    result = registry["extract_markdown"].invoke(request())
    assert isinstance(result, ExtractionResult) and result.source is not None
    assert result.attempts[0].parser == parser_name


def test_injected_alternative_and_visible_word_count() -> None:
    custom: Sequence[Extractor] = [CandidateExtractor("alternative", 222)]
    result = create_tool_registry(extractor=ExtractionService(custom))["extract_markdown"].invoke(
        request()
    )
    assert isinstance(result, ExtractionResult) and result.source is not None
    assert result.source.title == "Injected parser"
    assert (
        word_count("# Heading\n[visible words](https://a.test/many/hidden/path/words) ![image](x)")
        == 3
    )


def test_reject_invalid_page_and_empty_parser_configuration() -> None:
    with pytest.raises(ValueError, match="At least"):
        ExtractionService([])
    invalid = request().model_dump()
    invalid["page"]["status"] = 404
    with pytest.raises(ValueError, match="successfully fetched"):
        ExtractionService().extract(ExtractMarkdownInput.model_validate(invalid))


def test_canonical_relative_and_bad_scheme_fallback() -> None:
    original = fixture_html().replace(
        "https://fixture.test/canonical?utm_source=demo&amp;id=7", "/relative#section"
    )
    page = FetchedPage(html=original, status=200, final_url=HttpUrl("https://fixture.test/fetched"))
    candidate = BeautifulSoupExtractor().extract(page)
    assert candidate is not None and str(candidate.canonical_url) == "https://fixture.test/relative"
    page.html = original.replace("/relative#section", "javascript:bad")
    candidate = BeautifulSoupExtractor().extract(page)
    assert candidate is not None and candidate.canonical_url is None


def test_result_invariants_prevent_empty_success() -> None:
    with pytest.raises(ValidationError):
        FetchResult(
            url=HttpUrl("https://fixture.test/a"),
            final_url=HttpUrl("https://fixture.test/a"),
            outcome="fetched",
            attempts=1,
            fetched_at=utc_now(),
        )
    with pytest.raises(ValidationError):
        ExtractionResult(outcome="extracted", attempts=[ParserAttempt(parser="x", outcome="empty")])


def test_missing_publication_metadata_does_not_use_parser_date_guess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = Document(text="evidence " * 250, title="Publication unknown", date="2015-12-03")
    monkeypatch.setattr("services.extraction_service.extract_with_metadata", lambda *a, **kw: doc)
    result = ExtractionService([TrafilaturaExtractor()]).extract(request("missing-metadata"))
    assert result.source is not None and result.source.published is None


@pytest.mark.parametrize("shape", ["object", "list", "graph"])
def test_explicit_structured_article_metadata(shape: str) -> None:
    entry = {
        "@type": "NewsArticle",
        "author": {"name": "Casey Writer"},
        "datePublished": "2026-08-15",
    }
    payload: object
    if shape == "object":
        payload = entry
    elif shape == "list":
        payload = [entry]
    else:
        payload = {"@graph": [entry]}
    html = fixture_html("missing-metadata").replace(
        "</head>",
        (
            '<script type="application/ld+json">malformed</script>'
            f'<script type="application/ld+json">{json.dumps(payload)}</script></head>'
        ),
    )
    page = FetchedPage(html=html, status=200, final_url=HttpUrl("https://fixture.test/a"))
    result = ExtractionService().extract(ExtractMarkdownInput(page=page, source_id="S-01"))
    assert result.source is not None
    assert result.source.author == "Casey Writer" and result.source.published == "2026-08-15"
