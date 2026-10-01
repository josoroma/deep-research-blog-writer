# EPIC-6: Research Corpus

Date: 2026-10-01

Status: Done. This plan is written before implementation. Successful commands and PM evidence will be recorded in `EPIC-6-RUNBOOK.md` and `docs/evidence/epic-6/` after verification.

## Objective

Implement US-6.1–US-6.3 from [SPECS.md](SPECS.md#epic-6-research-corpus), building on the completed EPIC-5 fetch and extraction milestone. Turn every clean URL into one immutable, rank-numbered Markdown source with front-matter, index the written corpus, and keep building it when individual sources fail. Record one typed outcome per clean URL in `RunState`.

Synthesis, blog authoring, citation validation, run reporting, outcome classification, and durable resume remain in their owning later epics. This milestone produces the corpus and its index, not a blog.

## Current baseline

- `fetch_url` and `extract_markdown` are real internal tools bound to a run-owned `FetchService` and an `ExtractionService` (`tools/content_tools.py`). Agents do not receive them (PD-005).
- `workflows/fetch_run.py` already processes every clean URL concurrently through those tools, isolates per-URL exceptions, and persists `fetch_outcomes.json`, `extraction_results.json`, and `fetch_state.json`. It writes no corpus files.
- `collect_source` and `build_index` are labelled M1 stubs in `tools/stubs.py` that write nothing. `research_agent` already receives `collect_source`; the orchestrator already receives `build_index`.
- `Source` (`schemas/responses.py`) carries `source_id`, `url`, `title`, `author`, `published`, `body_markdown`, `word_count`, and `fetched_at`. `SourceMetadata` returns only `source_id`, `path`, `title`, and `word_count`.
- `UrlOutcome` (`schemas/state.py`) already enumerates `pending`, `extracted`, `unreachable`, `too_thin`, `robots_disallowed`, `unsupported_content`, and `extraction_failed`. It does not yet enumerate the US-6.3 `failed` outcome.
- `services/workspace.py` already slugifies topics (lowercase ASCII, hyphen-joined, 60 characters, `topic` fallback). PD-014 needs the same rules for titles, with a URL host-and-path fallback instead.
- `FilesystemBackend(root_dir=..., virtual_mode=True)` (ADR 0003) writes immediately and blocks traversal, but it overwrites existing files. Source immutability (BR-003, US-6.1#4) is not yet enforced.
- `pyyaml` 6.0.3 is present only transitively. It is not a direct locked dependency and has no type stubs.

## Implementation sequence

1. **Contracts and dependencies.**
   - Add `failed` to the `UrlOutcome.outcome` literal so a contained exception is distinguishable from a fetch or extraction outcome.
   - Add a `CorpusSource` contract: a `Source` plus its relative `path` and clean `rank`. The index and the corpus state are derived from these records, never re-parsed from prose.
   - Add `pyyaml` as a direct locked dependency and install `types-PyYAML` as a dev dependency so strict mypy covers the front-matter round trip.
   - Keep `SourceMetadata` metadata-only. No tool output may include `body_markdown` or raw HTML.

2. **US-6.1: Source rendering and naming** (`services/corpus.py`).
   - Render a source as YAML front-matter (`source_id`, `url`, `title`, `author`, `published`, `fetched` as a UTC timestamp, `word_count`) followed by a level-1 heading of the title and the extracted Markdown body unchanged. Quote every scalar so titles containing colons stay valid YAML. Write `null` for absent author or publication date.
   - Parse front-matter back into a validated `CorpusSource` and reject files whose body does not start with the recorded title heading or whose word count disagrees with the body. This is what `build_index` and the immutability check rely on.
   - Name files `research/{rank:03d}_{slug}.md` with `source_id = S-{rank:02d}` (PD-014). The slug comes from the title using the existing slug rules, capped at 60 characters. When the title yields no ASCII slug, derive it from the URL host and path. Failed ranks leave numbering gaps.
   - Write each file once, atomically, rejecting symlink destinations the way `services/artifacts.py` does. Creating an existing source file is an error, not an overwrite.

3. **US-6.1: `collect_source`** (`tools/corpus_tools.py`, replacing the stub).
   - Bind the tool to one run-owned corpus session that holds the workspace, the clean results, the shared fetcher, and the extractor. Register it through `create_tool_registry`, mirroring the search and content bindings, so the global `TOOLS` registry keeps labelled stubs and never opens a network client.
   - The handler validates the rank against `clean_results.json`, fetches, extracts, renders, and writes one file, then returns `SourceMetadata` only. It calls the registered `fetch_url` and `extract_markdown` tools internally, so both sides stay validated (PD-005).
   - On any non-success outcome, write no file and return no metadata. Record the outcome and reason in `RunState` instead, and return a validated `RunState` replacement so the orchestrator sees progress (PD-003).
   - A second call for a URL whose source file already exists returns the recorded metadata and does not fetch again. This is the US-8.4#4 behavior, implemented now because the file is immutable. It is not durable resume; checkpointing stays in EPIC-8.

4. **US-6.1#4: Refuse agent writes and edits to existing source files.**
   - Subclass `FilesystemBackend` as `ImmutableSourceBackend`. `write` and `edit` on an existing `research/NNN_<slug>.md` return an error result and leave the bytes unchanged. `delete` is refused the same way, since deleting a source would violate immutability just as surely as editing it. Reads, listings, and writes to `research/index.md`, `research/summary.md`, and `output/` stay allowed.
   - Give this backend to the deep agent in `agents/deep_research.py`. The agent boundary is unchanged: the subclass lives in `services/`, and `agents/` only passes it through.
   - Prove it through the built agent: a scripted `write_file` and `edit_file` against an existing source file are refused, and the file's bytes are identical afterwards.

5. **US-6.2: `build_index`.**
   - Replace the stub with a typed tool that reads every source file's front-matter, validates each record, and writes `research/index.md`. The index is a Markdown table with the columns `source_id`, `title`, `host`, `word_count`, and `url`, one row per source file, in rank order. The host comes from the recorded URL.
   - Escape table-breaking characters in titles so a title containing `|` cannot shift a column. The index is regenerated from the files, so re-running it is safe and idempotent.
   - Record the `index` phase complete in `RunState` and return the validated replacement plus `index_path` and `sources_indexed`.
   - Refuse to index when any clean URL is still `pending`, so the index can never describe a partial corpus as finished.

6. **US-6.3: Keep building when sources fail.**
   - `collect_source` catches fetch and extraction exceptions per URL and records that URL as `failed` with the exception type as its reason. The reason never includes exception text, so a filesystem or network message cannot leak into agent context or artifacts.
   - One URL's failure does not affect the others. A run with one unreachable URL and one thin page writes source files for the rest and continues to indexing.
   - Persist `corpus_state.json`, a validated `RunState` with one outcome per clean URL, alongside the source files. `fetch_outcomes.json` and `extraction_results.json` remain the EPIC-5 previews; the corpus adds the source files and the index.

7. **Runnable corpus milestone and demo.**
   - Add `--corpus-only --workspace <existing-search-run>` to `deep-research-blog`. It consumes the validated request and `clean_results.json`, runs `collect_source` for every clean URL through the registered tools, then runs `build_index`, and prints a typed summary: files written, outcomes, and the index path. Exit 0 means every URL was processed, including recorded failures; exit 1 is a fatal milestone error; exit 2 rejects invalid input. It does not call a model.
   - Add `make demo-epic-6`. It reuses the EPIC-5 mock HTTP transport, virtual clock, and packaged HTML fixtures, then runs the real registered tools and real parsers. It asserts the acceptance facts: rank-numbered files with gaps, front-matter, the title slug, the URL-slug fallback, metadata-only tool output, an index row per file, contained failures, and a refused overwrite.
   - Add `scripts/inspect-corpus.py` to validate a workspace or a committed snapshot: contiguous ranks, one outcome per clean URL, front-matter that round-trips, source ids, the 200-word floor, and index rows that match the files.
   - Add `scripts/create-live-corpus-workspace.py` to seed one known public URL, so the live CLI demo needs no search call. The normal hand-off remains an EPIC-4 workspace.

8. **Verification and delivery.**
   - Test rendering and parsing, both slug rules, rank gaps, metadata-only output, immutability through the built agent, index rows, per-URL exception containment, symlink rejection, and continuation after mixed failures.
   - Keep the offline suite network-blocked. The live corpus smoke stays opt-in behind `CRAWLER_CONTACT` and out of the coverage gate.
   - Run locked setup, strict quality and coverage checks, hooks, the EPIC-2 through EPIC-5 demos, the new demo, the wheel and sdist build, an installed-wheel check, and a committed fresh-checkout verification.
   - Record exact command transcripts, UTC timestamps, artifact snapshots, coverage, and source hashes under `docs/evidence/epic-6/`. Write `EPIC-6-RUNBOOK.md`.
   - Update only the verified EPIC-6 story and task statuses in `SPECS.md`, and commit with hooks active.

## Acceptance matrix

| Story | Evidence |
| --- | --- |
| US-6.1 | `collect_source` for rank 7 writes `research/007_<slug>.md` and returns only `source_id`, `path`, `title`, and `word_count`; front-matter carries `source_id`, `url`, `title`, `author`, `published`, `fetched`, and `word_count`; the body starts with the title heading and keeps the extracted Markdown unchanged |
| US-6.1 | Rank 3 failing leaves no `003` file; rank 4 is `research/004_<slug>.md` with `source_id` `S-04` |
| US-6.1 | "LangGraph vs CrewAI: A 2026 Comparison" slugs to `langgraph-vs-crewai-a-2026-comparison`; a non-ASCII title falls back to the URL host and path |
| US-6.1 | A scripted agent `write_file` and `edit_file` against an existing source file are refused and the bytes are unchanged |
| US-6.2 | `research/index.md` has columns `source_id`, `title`, `host`, `word_count`, and `url`, with exactly one row per source file, and the `S-03` row matches that file |
| US-6.3 | One unreachable and one thin URL among the clean set produce source files for the rest, record `unreachable` and `too_thin`, and the run still indexes |
| US-6.3 | An extraction exception records that URL as `failed` with the error type, and the remaining URLs are still processed |

## Completion checklist

- [x] Contracts, front-matter rendering, and the PyYAML dependency added.
- [x] US-6.1 implemented and verified, including immutability.
- [x] US-6.2 implemented and verified.
- [x] US-6.3 implemented and verified.
- [x] Runnable corpus-only workflow and offline PM demo pass.
- [x] Strict gates, hooks, prior demos, and installed wheel pass.
- [ ] Live corpus check recorded separately from offline evidence. Optional; needs CRAWLER_CONTACT.
- [x] Runbook, command transcripts, artifact snapshots, coverage, and source hashes saved.
- [x] Implementation committed; evidence commit follows.

## Scope boundaries

- `collect_source` skipping an existing source file is implemented because the file is immutable. SQLite checkpointing, `--resume`, and phase-level resume stay in US-8.4.
- The analyst and writer prompts, `research/summary.md`, and `output/blog.md` stay in EPIC-7. The corpus demo stops at the index.
- `validate_citations` and `write_run_report` remain labelled stubs. Outcome classification and exit status 3 stay in EPIC-8.
- No new ADR is required. Source immutability is BR-003, and the filesystem backend decision in ADR 0003 already covers real-disk writes. The subclass only narrows what agents may overwrite.

## Technical references

- [PyYAML documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) for `safe_dump` and `safe_load`, which keep front-matter free of arbitrary object construction.
- [DeepAgents filesystem backend](https://github.com/langchain-ai/deepagents) `write`, `edit`, and `delete` results, which this milestone subclasses to enforce BR-003.
- The installed locked APIs already used by EPIC-5: HTTPX, trafilatura, readability-lxml, and Beautiful Soup.
