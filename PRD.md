# PRD — Deep Research Blog Writer

A DeepAgent (LangChain `deepagents` on LangGraph) that, given a topic, runs paged
Google searches, fetches and cleans every result into local Markdown, then writes
an evidence-grounded blog post citing those sources.

- **Status:** Draft v1
- **Owner:** pablo.orozco@cox.com
- **Last updated:** 2026-09-30
- **References:** [DeepAgents docs](https://www.langchain.com/deep-agents) · [DeepAgents course](https://academy.langchain.com/courses/foundation-introduction-to-deepagents)

---

## 1. Problem & Goal

Producing a well-sourced technical blog post means running many searches, opening
dozens of tabs, skimming each page, saving notes, and only then writing. It is slow,
inconsistent, and the sourcing is rarely traceable.

**Goal:** one command — a topic string — produces a corpus of ~30 cleaned Markdown
sources plus a long-form, cited blog post, fully autonomously and reproducibly.

**Example**
```
Input:  "2026 agentic AI frameworks"
Output: research/001..030_*.md   (cleaned sources, each with front-matter + URL)
        research/index.md         (corpus table)
        research/summary.md       (synthesized themes)
        output/blog.md            (2000–5000 words, [S-NN] citations, References)
        output/run.json           (metrics + provenance)
```

## 2. Non-Goals

- Not a general web agent or chatbot; single well-defined pipeline.
- No paid/gated content, no paywall bypass, no CAPTCHA solving.
- No image generation or CMS publishing (blog is Markdown on disk only).
- No multi-topic batching in v1 (one topic per run).

## 3. Users

Developer advocates, architects, and technical content teams who need a defensible,
source-grounded first draft they can edit — not auto-published copy.

## 4. Why DeepAgents

The `deepagents` harness gives us four primitives this pipeline needs, so we don't
rebuild orchestration:

| Primitive | Built-in tool(s) | Use here |
|---|---|---|
| Planning | `write_todos` | Track the search→fetch→extract→write phases as an explicit, resumable todo list |
| Virtual filesystem | `ls`, `read_file`, `write_file`, `edit_file` | The `research/` corpus and `output/blog.md` live in agent state, flushed to a real FS backend |
| Sub-agents | `task` | Isolate context: a `researcher` sub-agent burns tokens fetching pages; the `writer` sub-agent only sees the clean corpus |
| Context offloading | filesystem backend | Raw HTML never enters the main context window — only file references and summaries |

`create_deep_agent(tools=..., instructions=..., subagents=..., model=...)` wires these
together on LangGraph, which gives us checkpointing/resume for free.

## 5. Architecture

```
topic
  │
  ▼
Orchestrator (deep agent, write_todos)
  │  spawns via `task`
  ├─► search_agent   → google_search(query, page)  ──► search_results.json
  ├─► research_agent → fetch_url + extract_markdown ──► research/NNN_*.md (×~30)
  │                    (loops over deduped URLs, one file per source)
  ├─► analyst_agent  → read_file(research/*) ──────────► research/summary.md
  └─► writer_agent   → read corpus + summary ─────────► output/blog.md
  │
  ▼
output/run.json  (metrics, provenance, failures)
```

Design rules (non-negotiable):
- **Agents orchestrate; tools execute.** No agent calls `requests`/`httpx` directly.
- **Tools are typed.** Every tool has a Pydantic input and output model — never raw dicts.
- **Sources are immutable.** Once a source `.md` is written it is read-only for the writer.
- **The writer cites only from the corpus.** No claim without an `[S-NN]` mapping to a file.

## 6. Functional Requirements

### FR-1 — Topic intake
- Accept `topic: str`, 3–250 chars, trimmed. Reject empty/oversized with a clear error.
- Derive a run id: `slug(topic) + "-" + UTC timestamp`; all artifacts go under `runs/<run_id>/`.

### FR-2 — Search (paged)
- Run Google search over the topic (plus 2–3 planner-derived query variants).
- **3 pages × 10 results = up to 30 URLs.** Config: `pages=3`, `per_page=10`, `max_urls=30`.
- Provider abstracted behind a `SearchProvider` interface (v1: Serper/SerpAPI or Tavily; see §12).
- Persist raw results to `search_results.json` (query, rank, url, title, snippet).

### FR-3 — Normalize & dedupe
- Drop duplicates by canonical URL (strip `utm_*`, fragments, trailing slash).
- Drop non-article hosts (social, video, login walls) via a configurable denylist.
- Keep ranking order; cap at `max_urls`. Output `clean_results.json`.

### FR-4 — Fetch & extract
- For each URL: fetch HTML (timeout, retries=3, backoff), then extract main content with
  `trafilatura` (fallback: `readability-lxml` → `beautifulsoup4`).
- Capture: title, author, published date, canonical URL, body (as Markdown), word count.
- Skip if extracted body < 200 words (record as `too_thin`). Never abort the run on one failure.

### FR-5 — Markdown corpus
- Write one file per source: `research/NNN_<slug>.md`, `NNN` zero-padded, in ranking order.
- Front-matter block per file:
  ```markdown
  ---
  source_id: S-07
  url: https://…
  title: …
  author: …
  published: …
  fetched: 2026-09-30T…Z
  word_count: 1420
  ---
  # <title>
  <clean markdown body>
  ```

### FR-6 — Corpus index
- Generate `research/index.md`: a table of `source_id | title | host | word_count | url`.

### FR-7 — Synthesis
- `analyst_agent` reads the whole corpus and produces `research/summary.md`: recurring
  themes, named frameworks/vendors, points of agreement/disagreement, gaps, and a
  suggested outline. Each theme references the `source_id`s that support it.

### FR-8 — Blog generation
- `writer_agent` writes `output/blog.md`, 2000–5000 words:
  Title → Intro → Landscape → Key frameworks → Analysis/trade-offs → Outlook → Conclusion → References.
- Every non-obvious claim carries an inline `[S-NN]` citation resolvable to a corpus file.
- Closing `## References` lists each cited `source_id` with title + URL.

### FR-9 — Citation integrity (hard gate)
- After generation, validate every `[S-NN]` in the blog resolves to an existing source file.
- Any dangling citation → the writer is re-invoked to fix or drop it. The run is not "done"
  until zero dangling citations remain.

### FR-10 — Run report
- Write `output/run.json`: topic, run_id, model, timings per phase, counts
  (urls found / fetched / extracted / thin / failed), citation count, token/cost totals.

## 7. Non-Functional Requirements

- **NFR-1 Reliability:** a single URL/parser/LLM failure never aborts the run; ≥80% of the
  ~30 URLs must extract successfully for a run to be `succeeded` (else `degraded`).
- **NFR-2 Reproducibility:** all inputs and artifacts persisted under `runs/<run_id>/`;
  LangGraph checkpointing enables resume from the last completed phase.
- **NFR-3 Observability:** LangSmith tracing on; structured logs to `logs/execution.log`;
  metrics in `run.json` (see FR-10).
- **NFR-4 Cost control:** budgets enforced — `max_urls=30`, `retries=3`, blog generated once
  (plus at most N citation-fix passes). Fetch concurrency capped and rate-limited.
- **NFR-5 Politeness:** respect `robots.txt`, set a descriptive User-Agent, throttle per host.
- **NFR-6 Extensibility:** search provider and extractor are swappable behind interfaces.

## 8. Contracts (Pydantic v2)

```python
class ResearchRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=250)
    pages: int = 3
    per_page: int = 10
    max_urls: int = 30

class SearchResult(BaseModel):
    url: HttpUrl; title: str; snippet: str; rank: int; query: str

class Source(BaseModel):
    source_id: str            # "S-07"
    url: HttpUrl; title: str
    author: str | None; published: str | None
    body_markdown: str; word_count: int
    fetched_at: datetime

class RunReport(BaseModel):
    run_id: str; topic: str; status: Literal["succeeded","degraded","failed"]
    urls_found: int; urls_extracted: int; extraction_failures: int
    blog_path: str; citation_count: int
    tokens_used: int; duration_seconds: float
```

## 9. Sub-agents & Tools

| Sub-agent | Responsibility | Tools |
|---|---|---|
| `search_agent` | run paged queries, collect URLs | `google_search` |
| `research_agent` | fetch + extract + write one source file per URL | `fetch_url`, `extract_markdown`, `write_file` |
| `analyst_agent` | synthesize corpus into themes/outline | `ls`, `read_file`, `write_file` |
| `writer_agent` | draft cited blog from corpus + summary | `ls`, `read_file`, `write_file` |

Tool interfaces (typed I/O, no raw dicts):
- `google_search(query: str, page: int) -> list[SearchResult]`
- `fetch_url(url: HttpUrl) -> FetchedPage`  (html + status + final_url)
- `extract_markdown(page: FetchedPage) -> Source`
- filesystem tools (`ls`/`read_file`/`write_file`/`edit_file`) are provided by the harness.

## 10. Failure handling

| Failure | Behavior |
|---|---|
| URL unreachable / non-200 | retry ×3 w/ backoff, then record `unreachable`, continue |
| Extraction empty/thin | try fallback parser, else record `too_thin`, continue |
| < 24 usable sources | run continues, status `degraded`, noted in `run.json` |
| Dangling `[S-NN]` citation | re-invoke writer to fix; block "done" until clean (FR-9) |
| LLM/tool exception in a sub-agent | caught by orchestrator, logged, phase retried once |

## 11. Milestones

1. **M1 — Skeleton:** `create_deep_agent` wired with the four sub-agents; virtual FS backed by real disk; typed tool stubs.
2. **M2 — Ingest:** real search + fetch + extract → 30 files + `index.md` for one topic.
3. **M3 — Author:** synthesis + cited blog + citation-integrity gate.
4. **M4 — Prod:** LangSmith tracing, `run.json`, resume-from-checkpoint, rate limiting.
5. **M5 — Eval:** golden topics + rubric scoring in `evaluations/` (coverage, citation validity, length, groundedness).

## 12. Open decisions

- **Search provider:** Serper.dev vs SerpAPI vs Tavily (Google TOS prohibits scraping SERPs directly — use an API). *Recommendation: Serper.dev for cost + Google parity.*
- **FS backend:** virtual (state) flushed to `runs/<id>/` vs `CompositeBackend` with a store. *Recommendation: real-disk backend so artifacts survive the process.*
- **Model (decided):** DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`) through OpenRouter for every agent.

## 13. Definition of Done

A run is complete when: ~30 results processed (≥80% extracted) · corpus + `index.md` written ·
`summary.md` written · `output/blog.md` (2000–5000 words) with **zero dangling citations** and a
References section · `run.json` written · trace visible in LangSmith.
