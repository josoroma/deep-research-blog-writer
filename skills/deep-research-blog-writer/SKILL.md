---
name: deep-research-blog-writer
description: >-
  Given a topic, run paged Google searches (3 pages × 10 = up to 30 URLs), fetch
  and clean each result into a local Markdown source file with front-matter, then
  write a 2000–5000 word evidence-grounded blog post that cites only those sources.
  Use when the user asks to "research a topic and write a blog post", "gather
  sources and draft an article", or names a topic to research end-to-end.
---

# Deep Research Blog Writer

Autonomous research→corpus→blog pipeline built on the `deepagents` harness
(planning tool + virtual filesystem + sub-agents on LangGraph). One topic in;
a cited Markdown blog post plus a traceable source corpus out.

## When to use

Trigger when the user gives a research topic/goal and wants a sourced long-form
article (e.g. "2026 agentic AI frameworks"). Not for quick Q&A, single-page
summaries, or publishing to a CMS.

## Contract

**Input:** `topic` (3–250 chars). Optional: `pages=3`, `per_page=10`, `max_urls=30`.

**Output (under `runs/<run_id>/`):**
- `research/NNN_<slug>.md` — one cleaned source per URL, with front-matter
- `research/index.md` — corpus table (`source_id | title | host | words | url`)
- `research/summary.md` — synthesized themes + outline, each theme citing `source_id`s
- `output/blog.md` — the cited article
- `output/run.json` — metrics, provenance, failures

## Operating rules (hard constraints)

1. **Agents orchestrate; tools execute.** Never fetch URLs or call search APIs from
   agent reasoning — only through the typed tools below.
2. **Every source is a file.** Raw HTML never enters the writer's context; the writer
   reads only clean `.md` files via `read_file`.
3. **Cite only the corpus.** Every non-obvious claim in the blog carries an inline
   `[S-NN]` that resolves to a source file. No source → no claim.
4. **Never abort on one failure.** A dead URL or thin page is recorded and skipped.
5. **Respect the budget:** `max_urls=30`, fetch retries ≤ 3, blog generated once
   (plus citation-fix passes only). Respect `robots.txt` and rate-limit per host.
6. **No paywalled/gated content, no CAPTCHA solving, no SERP scraping** — searches go
   through an approved search API.

## Workflow

Track these phases with `write_todos`; each is resumable from the LangGraph checkpoint.

1. **Plan** — validate `topic`, derive 2–3 query variants, create `run_id`, seed todos.
2. **Search** (`search_agent`) — for `page in 1..pages`: `google_search(query, page)`.
   Collect up to `max_urls`; persist `search_results.json`.
3. **Normalize** — canonicalize URLs (strip `utm_*`, fragments), dedupe, apply host
   denylist, keep ranking order → `clean_results.json`.
4. **Fetch + extract** (`research_agent`) — loop over clean URLs:
   `fetch_url` → `extract_markdown` (trafilatura → readability → bs4 fallback) →
   `write_file("research/NNN_<slug>.md", …)`. Skip bodies < 200 words as `too_thin`.
5. **Index** — write `research/index.md`.
6. **Synthesize** (`analyst_agent`) — `read_file` the corpus → `research/summary.md`
   (themes, frameworks/vendors, agreements/disagreements, gaps, suggested outline).
7. **Write** (`writer_agent`) — draft `output/blog.md`, 2000–5000 words:
   Title · Intro · Landscape · Key frameworks · Analysis/trade-offs · Outlook ·
   Conclusion · References. Inline `[S-NN]` citations throughout.
8. **Citation gate** — verify every `[S-NN]` resolves to a source file; re-invoke the
   writer to fix/drop any dangling citation. Not done until zero remain.
9. **Report** — write `output/run.json`.

## Source file format

```markdown
---
source_id: S-07
url: https://example.com/article
title: The article title
author: Jane Doe
published: 2026-08-14
fetched: 2026-09-30T12:00:00Z
word_count: 1420
---
# The article title

<clean markdown body>
```

## Sub-agents & tools

| Sub-agent | Does | Tools |
|---|---|---|
| `search_agent` | paged queries → URLs | `google_search` |
| `research_agent` | fetch + extract + write one file per URL | `fetch_url`, `extract_markdown`, `write_file` |
| `analyst_agent` | synthesize corpus → summary | `ls`, `read_file`, `write_file` |
| `writer_agent` | draft cited blog | `ls`, `read_file`, `write_file` |

Typed tool signatures (Pydantic v2 I/O — never raw dicts):
- `google_search(query: str, page: int) -> list[SearchResult]`
- `fetch_url(url: HttpUrl) -> FetchedPage`
- `extract_markdown(page: FetchedPage) -> Source`
- filesystem tools (`ls`/`read_file`/`write_file`/`edit_file`) come from the harness.

## Wiring (reference)

```python
from deepagents import create_deep_agent

RESEARCH_INSTRUCTIONS = "…paste the Operating rules + Workflow above…"

subagents = [
    {"name": "search_agent",   "description": "Run paged Google searches, collect URLs.",
     "prompt": "…", "tools": ["google_search"]},
    {"name": "research_agent", "description": "Fetch each URL and write one clean markdown source.",
     "prompt": "…", "tools": ["fetch_url", "extract_markdown", "write_file"]},
    {"name": "analyst_agent",  "description": "Read the corpus, synthesize themes into summary.md.",
     "prompt": "…"},
    {"name": "writer_agent",   "description": "Draft the cited blog from corpus + summary.",
     "prompt": "…"},
]

agent = create_deep_agent(
    tools=[google_search, fetch_url, extract_markdown],
    instructions=RESEARCH_INSTRUCTIONS,
    subagents=subagents,
    model="openrouter:deepseek/deepseek-v4.1-flash",
)

result = agent.invoke({"messages": [{"role": "user",
    "content": "Research topic and write a blog post: 2026 agentic AI frameworks"}]})
```

## Failure handling

| Failure | Behavior |
|---|---|
| URL unreachable / non-200 | retry ≤3 w/ backoff, record `unreachable`, continue |
| Extraction empty/thin | fallback parser, else record `too_thin`, continue |
| < 24 usable sources | continue; status `degraded` in `run.json` |
| Dangling `[S-NN]` | re-invoke writer; block "done" until clean |
| Sub-agent exception | orchestrator logs it, retries the phase once |

## Definition of done

~30 results processed (≥80% extracted) · corpus + `index.md` · `summary.md` ·
`output/blog.md` 2000–5000 words with **zero dangling citations** + References ·
`output/run.json` written · trace visible in LangSmith.
