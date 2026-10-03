"""Immutable, rank-numbered Markdown sources and the corpus index.

Rendering and indexing are deterministic. Models decide which tool to call; they
never produce a source file or the index (BR-010). A source file is written once
and never overwritten (BR-003, PD-014).
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import Field, HttpUrl

from schemas.common import Contract, SourceID
from schemas.errors import ConflictError
from schemas.responses import SearchResult, Source
from schemas.state import RunState, UrlOutcome
from services.workspace import slugify

RESEARCH_DIR = "research"
INDEX_PATH = "research/index.md"
SOURCE_FILE = re.compile(r"^(?P<rank>\d{3})_(?P<slug>[a-z0-9-]+)\.md$")
INDEX_COLUMNS = ("source_id", "title", "host", "word_count", "url")


class CorpusSource(Contract):
    """A written source file: its validated content plus where it lives."""

    source: Source
    path: str
    rank: int = Field(ge=1)


class SourceExistsError(ConflictError, FileExistsError):
    """A source file already exists and must not be rewritten."""

    code = "source_exists"


def source_id_for(rank: int) -> SourceID:
    return f"S-{rank:02d}"


def source_slug(title: str, url: HttpUrl) -> str:
    """PD-014: slug the title, falling back to the URL host and path."""
    slug = slugify(title)
    if slug != "topic":
        return slug
    parts = urlsplit(str(url))
    fallback = slugify(f"{parts.hostname or ''} {parts.path}")
    return fallback if fallback != "topic" else "source"


def source_path(rank: int, slug: str) -> str:
    return f"{RESEARCH_DIR}/{rank:03d}_{slug}.md"


def render_source(record: CorpusSource) -> str:
    """Front-matter, then the title heading, then the extracted body unchanged."""
    source = record.source
    front_matter = {
        "source_id": source.source_id,
        "url": str(source.url),
        "title": source.title,
        "author": source.author,
        "published": source.published,
        "fetched": source.fetched_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "word_count": source.word_count,
    }
    header = yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True).strip()
    body = source.body_markdown
    if body.startswith(f"# {source.title}\n"):
        # The heading is added exactly once; an extractor that already emitted it
        # must not produce a duplicated title.
        body = body[len(f"# {source.title}\n") :].lstrip("\n")
    return f"---\n{header}\n---\n# {source.title}\n\n{body.rstrip()}\n"


def parse_source(path: Path, text: str) -> CorpusSource:
    """Read one source file back into the contract the index is built from."""
    match = SOURCE_FILE.match(path.name)
    if match is None or path.parent.name != RESEARCH_DIR:
        raise ValueError(f"Source file name is not rank-numbered: {path.name}")
    if not text.startswith("---\n"):
        raise ValueError(f"Source file has no front-matter: {path.name}")
    _, header, rest = text.split("---\n", 2)
    loaded = yaml.safe_load(header)
    if not isinstance(loaded, dict):
        raise ValueError(f"Source front-matter is not a mapping: {path.name}")
    fetched = loaded.get("fetched")
    if isinstance(fetched, str):
        loaded["fetched_at"] = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
    loaded.pop("fetched", None)
    body = rest.lstrip("\n")
    title = loaded.get("title")
    heading = f"# {title}\n"
    if not isinstance(title, str) or not body.startswith(heading):
        raise ValueError(f"Source body does not start with its title heading: {path.name}")
    source = Source.model_validate({**loaded, "body_markdown": body[len(heading) :].lstrip("\n")})
    rank = int(match.group("rank"))
    if source.source_id != source_id_for(rank):
        raise ValueError(f"Source id does not match its file rank: {path.name}")
    relative = f"{RESEARCH_DIR}/{path.name}"
    return CorpusSource(source=source, path=relative, rank=rank)


def write_source(root: Path, record: CorpusSource) -> None:
    """Write one source file exactly once, refusing symlinks and existing files."""
    destination = root / record.path
    if destination.is_symlink():
        raise ValueError(f"Source destination is a symlink: {record.path}")
    if destination.exists():
        raise SourceExistsError(f"Source file already exists: {record.path}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(render_source(record))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_corpus(root: Path) -> list[CorpusSource]:
    """Every written source, in rank order, validated against its file name."""
    directory = root / RESEARCH_DIR
    if not directory.is_dir():
        return []
    records = [
        parse_source(path, path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("[0-9][0-9][0-9]_*.md"))
    ]
    ranks = [record.rank for record in records]
    if len(set(ranks)) != len(ranks):
        raise ValueError("Corpus contains two source files for one rank")
    return records


def render_index(records: list[CorpusSource]) -> str:
    """One table row per source file, in rank order, with the host of its URL."""

    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    rows = [
        "| " + " | ".join(INDEX_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in INDEX_COLUMNS) + " |",
    ]
    for record in sorted(records, key=lambda item: item.rank):
        source = record.source
        rows.append(
            "| "
            + " | ".join(
                cell(value)
                for value in (
                    source.source_id,
                    source.title,
                    urlsplit(str(source.url)).hostname or "",
                    source.word_count,
                    source.url,
                )
            )
            + " |"
        )
    return "# Research corpus\n\n" + "\n".join(rows) + "\n"


def write_index(root: Path, records: list[CorpusSource]) -> str:
    destination = root / INDEX_PATH
    if destination.is_symlink():
        raise ValueError(f"Index destination is a symlink: {INDEX_PATH}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".index.md.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(render_index(records))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return INDEX_PATH


def outcome_for(result: SearchResult, **changes: object) -> tuple[str, UrlOutcome]:
    outcome = UrlOutcome.model_validate({"rank": result.rank, "url": result.url, **changes})
    return str(result.url), outcome


def corpus_state(run: RunState, outcomes: dict[str, UrlOutcome]) -> RunState:
    """Validate the replacement so a partial outcome map can never be saved."""
    return run.replaced(url_outcomes=outcomes)
