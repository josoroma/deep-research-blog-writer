"""Summary, blog, and citation checks for the authoring milestone.

The analyst and writer produce the files. These checks only read them, so a
draft is never regenerated to satisfy a length rule (NFR-4, PD-015) and a
citation finding never rewrites the draft it reports on.
"""

import re
from pathlib import Path

from pydantic import Field

from schemas.common import Contract, SourceID
from services.corpus import read_corpus

SUMMARY_PATH = "research/summary.md"
BLOG_PATH = "output/blog.md"
MIN_WORDS = 2000
MAX_WORDS = 5000
REQUIRED_SUMMARY = (
    "recurring themes",
    "named frameworks",
    "points of agreement",
    "points of disagreement",
    "gaps",
    "suggested outline",
)
REQUIRED_HEADINGS = (
    "Introduction",
    "Landscape",
    "Key Frameworks",
    "Analysis and Trade-offs",
    "Outlook",
    "Conclusion",
    "References",
)
CITATION = re.compile(r"\[(S-\d{2,})\]")
REFERENCE_LINE = re.compile(r"^[-*]?\s*\[?(S-\d{2,})\]?\s*(.*)$")


class SummaryCheck(Contract):
    """Whether the summary covers the FR-7 contents and cites real sources."""

    present: bool
    missing_sections: list[str]
    themes_without_sources: list[str]
    unknown_source_ids: list[SourceID]
    referenced_source_ids: list[SourceID]

    @property
    def passed(self) -> bool:
        return (
            self.present
            and not self.missing_sections
            and not self.themes_without_sources
            and not self.unknown_source_ids
        )


class BlogCheck(Contract):
    """Structure and length of the draft. An out-of-range draft is kept."""

    present: bool
    word_count: int = Field(ge=0)
    headings_valid: bool
    within_length: bool
    reason: str | None = None


class CitationFinding(Contract):
    """Every `[S-NN]` resolved against the corpus and the References section."""

    citations_checked: int = Field(ge=0)
    dangling_source_ids: list[SourceID]
    mismatched_source_ids: list[SourceID]

    @property
    def passed(self) -> bool:
        return not self.dangling_source_ids and not self.mismatched_source_ids


def _words(text: str) -> int:
    return len(text.split())


def _sections(text: str) -> list[tuple[int, str, str]]:
    """Headings as (level, title, body that follows until the next heading)."""
    matches = list(re.finditer(r"^(#{1,6}) (.+)$", text, re.MULTILINE))
    sections: list[tuple[int, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((len(match.group(1)), match.group(2).strip(), text[match.end() : end]))
    return sections


def check_summary(root: Path) -> SummaryCheck:
    """FR-7: required contents, and every theme cites a source that exists."""
    path = root / SUMMARY_PATH
    if not path.is_file():
        return SummaryCheck(
            present=False,
            missing_sections=list(REQUIRED_SUMMARY),
            themes_without_sources=[],
            unknown_source_ids=[],
            referenced_source_ids=[],
        )
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    missing = [section for section in REQUIRED_SUMMARY if section not in lowered]
    known = {record.source.source_id for record in read_corpus(root)}
    themes_without = [
        title
        for _, title, body in _sections(text)
        if title.lower().startswith("theme") and not CITATION.findall(body)
    ]
    referenced = CITATION.findall(text)
    unknown = sorted({source_id for source_id in referenced if source_id not in known})
    return SummaryCheck(
        present=True,
        missing_sections=missing,
        themes_without_sources=themes_without,
        unknown_source_ids=unknown,
        referenced_source_ids=sorted(set(referenced)),
    )


def check_blog(root: Path) -> BlogCheck:
    """PD-015: one title, the seven sections in order, and the length range."""
    path = root / BLOG_PATH
    if not path.is_file():
        return BlogCheck(present=False, word_count=0, headings_valid=False, within_length=False)
    text = path.read_text(encoding="utf-8")
    headings = [(level, title) for level, title, _ in _sections(text)]
    expected = [(2, title) for title in REQUIRED_HEADINGS]
    headings_valid = (
        bool(headings)
        and headings[0][0] == 1
        and headings[1:] == expected
        and sum(1 for level, _ in headings if level == 1) == 1
    )
    count = _words(text)
    within = MIN_WORDS <= count <= MAX_WORDS
    return BlogCheck(
        present=True,
        word_count=count,
        headings_valid=headings_valid,
        within_length=within,
        reason=None if within else "blog_length",
    )


def _references(text: str) -> dict[str, str]:
    """Source id to the remainder of its References line, URL included."""
    sections = _sections(text)
    body = next((body for level, title, body in sections if title == "References"), "")
    found: dict[str, str] = {}
    for line in body.splitlines():
        match = REFERENCE_LINE.match(line.strip())
        if match:
            found[match.group(1)] = match.group(2)
    return found


def validate_citations(root: Path) -> CitationFinding:
    """FR-9: every `[S-NN]` resolves, and References repeats its title and URL."""
    blog = root / BLOG_PATH
    if not blog.is_file():
        return CitationFinding(
            citations_checked=0, dangling_source_ids=[], mismatched_source_ids=[]
        )
    text = blog.read_text(encoding="utf-8")
    cited = list(dict.fromkeys(CITATION.findall(text)))
    corpus = {record.source.source_id: record for record in read_corpus(root)}
    dangling = [source_id for source_id in cited if source_id not in corpus]
    references = _references(text)
    mismatched: list[str] = []
    for source_id in cited:
        record = corpus.get(source_id)
        if record is None:
            continue
        line = references.get(source_id)
        url = str(record.source.url)
        if line is None or url not in line or record.source.title not in line:
            mismatched.append(source_id)
    return CitationFinding(
        citations_checked=len(cited),
        dangling_source_ids=dangling,
        mismatched_source_ids=mismatched,
    )
