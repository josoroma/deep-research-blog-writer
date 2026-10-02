# research_agent — skill

The research sub-agent collects the corpus: one immutable source file per clean URL. It is assembled in `agents/deep_research.py` and prompted by `prompts/research_agent.md`.

## Purpose

For every assigned clean URL, call `collect_source` so the tool fetches politely, extracts clean Markdown, and writes one immutable source file, returning metadata only.

## Capabilities

- Calls `collect_source` once per clean URL, by rank and URL.
- Records and skips unreachable, robots-disallowed, unsupported, thin, or failed pages.
- Preserves ranking gaps and source provenance.

## Non-Capabilities

- Never fetches a URL directly or calls an extraction implementation itself.
- Never carries raw HTML into agent context.
- Never overwrites, edits, or deletes a source file; source files are immutable (BR-003).
- Never writes the index or the summary.

## Inputs

- `CollectSourceInput` — the `rank` and `url` of one clean result.

## Outputs

- `CollectSourceOutput` — the `SourceMetadata` when a source file was written or already existed, otherwise `None`, plus the updated `RunState`.

## Available Tools

| Tool | Input | Output |
| --- | --- | --- |
| `collect_source` | `CollectSourceInput` | `CollectSourceOutput` |

This is the only registered tool the sub-agent receives (`SUBAGENT_TOOLS["research_agent"]`). `fetch_url` and `extract_markdown` are internal tools that `collect_source` calls; the agent does not receive them.

## Security

- The fetcher sends the configured `CRAWLER_CONTACT` User-Agent and respects `robots.txt`, per-host rate limits, and bounded concurrency.
- The workspace backend refuses to mutate an existing source file.
- The agent never receives raw HTML; only clean Markdown reaches the corpus.

## Observability

- Each `collect_source` call is a tool span and a `tool_started` and `tool_finished` pair in the log.
- Every URL outcome is logged with its URL and reason, and counted as an OTLP metric.

## Evaluation Criteria

- The corpus holds one rank-numbered file per extracted URL, with front-matter and a title heading.
- Failed ranks leave file-number gaps rather than shifting later ranks.
- The offline corpus demo (`make demo-epic-6`) asserts the outcomes and the immutability refusal.

## Failure Modes

| Failure | Behavior |
| --- | --- |
| A URL is unreachable | Outcome `unreachable` with the reason; the run continues |
| A page is blocked by robots | Outcome `robots_disallowed`; the run continues |
| A page is not HTML | Outcome `unsupported_content`; the run continues |
| A page extracts under 200 words | Outcome `too_thin`; the run continues |
| Every parser raises | Outcome `extraction_failed`; the run continues |
| The source file already exists | Its metadata is returned; the file is not rewritten |

## Example

For 30 clean URLs, the sub-agent calls `collect_source` 30 times. In the committed example run, 21 URLs extracted, 6 were unreachable, 1 was blocked by robots, and 2 were too thin, leaving 21 source files with rank gaps.
