"""Replaceable extractors, ordered fallback, and a validated clean Source boundary."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify
from pydantic import HttpUrl, ValidationError
from readability import Document
from trafilatura import extract_with_metadata

from schemas.config import RunSettings
from schemas.content import ExtractionResult, ParsedArticle, ParserAttempt
from schemas.responses import FetchedPage, Source
from schemas.tool_io import ExtractMarkdownInput
from services.search_session import canonicalize_url

MIN_WORDS = 200
CHROME = (
    "nav,footer,header,aside,script,style,noscript,form,iframe,svg,"
    "[role=navigation],[role=banner],[role=contentinfo],[role=complementary],"
    ".sidebar,.navigation,.menu,.cookie-banner,.comments,.advertisement"
)


class Extractor(Protocol):
    @property
    def name(self) -> str: ...
    def extract(self, page: FetchedPage) -> ParsedArticle | None: ...


def word_count(markdown: str) -> int:
    # Count visible text, excluding link destinations, images and markup.
    visible = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", markdown)
    visible = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", visible)
    visible = re.sub(r"<[^>]*>", " ", visible)
    return len(re.findall(r"\b\w+(?:['’’-]\w+)*\b", visible, re.UNICODE))


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _metadata(page: FetchedPage) -> dict[str, str | HttpUrl | None]:
    soup = BeautifulSoup(page.html, "lxml")

    def meta(*names: str) -> str | None:
        for name in names:
            tag = (
                soup.find("meta", attrs={"name": name})
                or soup.find("meta", attrs={"property": name})
                or soup.find("meta", attrs={"itemprop": name})
            )
            if isinstance(tag, Tag):
                value = _string(tag.get("content"))
                if value:
                    return value
        return None

    title = meta("og:title", "twitter:title")
    if not title:
        heading = soup.find("h1") or soup.find("title")
        title = heading.get_text(" ", strip=True) if isinstance(heading, Tag) else ""
    author = meta("author", "article:author", "citation_author", "dc.creator")
    published = meta(
        "article:published_time", "date", "datePublished", "pubdate", "citation_publication_date"
    )
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            structured: object = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        entries: list[object] = structured if isinstance(structured, list) else [structured]
        if isinstance(structured, dict) and isinstance(structured.get("@graph"), list):
            entries = structured["@graph"]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if not any(value in ("Article", "NewsArticle", "BlogPosting") for value in kinds):
                continue
            credited = entry.get("author")
            if isinstance(credited, dict):
                credited = credited.get("name")
            author = author or _string(credited)
            published = published or _string(entry.get("datePublished"))
    time_tag = soup.find("time", attrs={"pubdate": True}) or soup.find(
        "time", attrs={"itemprop": "datePublished"}
    )
    if isinstance(time_tag, Tag):
        published = published or _string(time_tag.get("datetime"))
    canonical: HttpUrl | None = None
    tag = soup.find("link", rel="canonical")
    href = _string(tag.get("href")) if isinstance(tag, Tag) else None
    if href:
        try:
            canonical = HttpUrl(canonicalize_url(HttpUrl(urljoin(str(page.final_url), href))))
        except (ValueError, ValidationError):
            pass
    return {"title": title, "author": author, "published": published, "canonical_url": canonical}


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for node in soup.select(CHROME):
        node.decompose()
    return str(soup)


def _markdown(html: str) -> str:
    result: str = markdownify(_clean_html(html), heading_style="ATX", bullets="-", strip=["img"])
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def _article(page: FetchedPage, body: str, **overrides: object) -> ParsedArticle:
    metadata: dict[str, object] = {**_metadata(page), **overrides, "body_markdown": body}
    # Removing a duplicate title heading also keeps the 200-word threshold about body text.
    title = metadata.get("title")
    if isinstance(title, str) and body.startswith(f"# {title}\n"):
        metadata["body_markdown"] = body[len(f"# {title}\n") :].lstrip()
    return ParsedArticle.model_validate(metadata)


class TrafilaturaExtractor:
    name = "trafilatura"

    def extract(self, page: FetchedPage) -> ParsedArticle | None:
        doc = extract_with_metadata(
            _clean_html(page.html),
            url=str(page.final_url),
            output_format="markdown",
            fast=True,
            favor_precision=True,
            include_comments=False,
            include_links=True,
            include_tables=True,
        )
        if doc is None:
            return None
        body = _string(doc.text)
        if body is None:
            return None
        # trafilatura's Markdown includes generated metadata front-matter. Metadata
        # belongs in Source fields and must not inflate the article word count.
        body = re.sub(r"\A---\n.*?\n---\n", "", body, count=1, flags=re.DOTALL).lstrip()
        original = _metadata(page)
        return _article(
            page,
            body,
            title=original["title"] or _string(doc.title) or "",
            author=original["author"] or _string(doc.author),
            # Date heuristics can mistake linked dates, copyright or modification
            # dates for publication. Preserve explicit metadata, otherwise null.
            published=original["published"],
        )


class ReadabilityExtractor:
    name = "readability-lxml"

    def extract(self, page: FetchedPage) -> ParsedArticle | None:
        document = Document(_clean_html(page.html))
        summary: str = document.summary()
        return _article(page, _markdown(summary))


class BeautifulSoupExtractor:
    name = "beautifulsoup4"

    def extract(self, page: FetchedPage) -> ParsedArticle | None:
        soup = BeautifulSoup(_clean_html(page.html), "lxml")
        main = soup.find("article") or soup.find("main") or soup.find("body")
        return _article(page, _markdown(str(main))) if isinstance(main, Tag) else None


class ExtractionService:
    def __init__(self, extractors: Sequence[Extractor] | None = None) -> None:
        self.extractors = (
            tuple(extractors)
            if extractors is not None
            else (
                TrafilaturaExtractor(),
                ReadabilityExtractor(),
                BeautifulSoupExtractor(),
            )
        )
        if not self.extractors:
            raise ValueError("At least one extractor is required")

    def extract(self, request: ExtractMarkdownInput) -> ExtractionResult:
        if request.page.status != 200:
            raise ValueError("Only successfully fetched HTML can be extracted")
        attempts: list[ParserAttempt] = []
        for parser in self.extractors:
            try:
                raw = parser.extract(request.page)
                candidate = ParsedArticle.model_validate(raw.model_dump()) if raw else None
                count = word_count(candidate.body_markdown) if candidate else 0
                if candidate is None or count == 0:
                    attempts.append(ParserAttempt(parser=parser.name, outcome="empty"))
                    continue
                if count < MIN_WORDS:
                    attempts.append(
                        ParserAttempt(
                            parser=parser.name,
                            outcome="too_thin",
                            word_count=count,
                        )
                    )
                    continue
                source = Source(
                    source_id=request.source_id,
                    url=candidate.canonical_url or request.page.final_url,
                    title=candidate.title or str(request.page.final_url),
                    author=candidate.author,
                    published=candidate.published,
                    body_markdown=candidate.body_markdown,
                    word_count=count,
                    fetched_at=request.fetched_at,
                )
                attempts.append(
                    ParserAttempt(
                        parser=parser.name,
                        outcome="extracted",
                        word_count=count,
                    )
                )
                return ExtractionResult(outcome="extracted", source=source, attempts=attempts)
            except Exception as error:
                attempts.append(
                    ParserAttempt(
                        parser=parser.name,
                        outcome="error",
                        error=type(error).__name__,
                    )
                )
        all_errors = all(attempt.outcome == "error" for attempt in attempts)
        return ExtractionResult(
            outcome="extraction_failed" if all_errors else "too_thin",
            attempts=attempts,
            reason="all_parsers_failed" if all_errors else "no_parser_reached_200_words",
        )


def create_extraction_service(settings: RunSettings) -> ExtractionService:
    parsers: dict[str, Extractor] = {
        "trafilatura": TrafilaturaExtractor(),
        "readability": ReadabilityExtractor(),
        "beautifulsoup": BeautifulSoupExtractor(),
    }
    return ExtractionService(
        None
        if settings.extractor_strategy == "fallback"
        else [parsers[settings.extractor_strategy]]
    )
