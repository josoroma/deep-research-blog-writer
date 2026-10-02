# research_agent — contract

## Input

- `CollectSourceInput` — the `rank` and `url` of one clean result. The rank must be a clean URL in the active run.

## Output

- `CollectSourceOutput` — the `SourceMetadata` (`source_id`, `path`, `title`, `word_count`) when a source file was written or already existed, otherwise `None`, plus the updated `RunState` with the URL's outcome recorded.

## Success criteria

| Criterion | Source |
| --- | --- |
| Fetch and extract one source file per URL | PRD.md §9 |
| Write an immutable `research/NNN_<slug>.md` with front-matter and a title heading | PRD.md FR-6, SPECS.md PD-014 |
| A single URL failure never aborts the run | PRD.md NFR-1 |
| Respect `robots.txt`, the User-Agent, and per-host throttling | PRD.md NFR-5 |
| Bodies under 200 words are `too_thin` | SPECS.md US-5.3 |
| An existing source file is never rewritten | SPECS.md BR-003 |

## Failure conditions

- The URL is unreachable, blocked by robots, not HTML, or too thin: the outcome is recorded and the run continues.
- Every parser raises: the outcome is `extraction_failed` and the run continues.
- The rank is not a clean URL in the run, or the URL does not match the rank: `ValueError`.
- The source file already exists: its metadata is returned and the file is left unchanged.
