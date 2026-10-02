# writer_agent — skill

The writer sub-agent drafts the cited blog from the corpus and the summary. It is assembled in `agents/deep_research.py` and prompted by `prompts/writer_agent.md`.

## Purpose

Read only the corpus and `research/summary.md`, then write `output/blog.md` once: a 2000–5000 word draft with one title, the seven required sections in order, inline `[S-NN]` citations, and a References section listing each cited source with its title and URL.

## Capabilities

- Reads the source files, `research/index.md`, and `research/summary.md`.
- Writes `output/blog.md` exactly once.
- Cites every non-obvious claim with an inline `[S-NN]` that resolves to a corpus file.
- On a citation repair request, fixes or removes only the named dangling citations.

## Non-Capabilities

- Never accesses the network.
- Never modifies a source file; source files are immutable.
- Never starts new research or rewrites the draft beyond the named citations during a repair.
- Never regenerates the draft to satisfy the length rule; an out-of-range draft is kept as written (PD-015).
- Never cites a source id that is not in the corpus.

## Inputs

- The corpus under `research/`: the source files, `research/index.md`, and `research/summary.md`. Each source file is described by `Source` and `SourceMetadata`.
- `RunState` — the run's progress, carried in `ResearchAgentState.run`.
- A repair request naming the dangling source ids, when the citation gate fails.

## Outputs

- `output/blog.md` — the draft. The agent returns its path.
- `RunState` — the updated run state, with the write phase recorded.

## Available Tools

The sub-agent receives no registered application tools (`SUBAGENT_TOOLS["writer_agent"]` is empty). It uses the harness filesystem tools (`ls`, `read_file`, `write_file`) against the run workspace.

## Security

- The workspace backend is `ImmutableSourceBackend`, so a source file cannot be overwritten, edited, or deleted.
- The agent has no network access and no provider client.
- The static boundary check forbids HTTP imports in agent modules.

## Observability

- The draft write is a tool span in the LangSmith trace and a log record.
- The run's token and cost totals include the writer's model calls, including repair passes.

## Evaluation Criteria

- `check_blog` passes: one title, the seven sections in order, and a word count within 2000–5000.
- `validate_citations` passes: every `[S-NN]` resolves and its References entry matches the source title and URL.
- The offline authoring demo (`make demo-epic-7`) asserts the heading check and the citation gate.

## Failure Modes

| Failure | Behavior |
| --- | --- |
| The draft is missing or its headings are out of order | The run fails with reason `blog_structure` |
| The draft is outside 2000–5000 words | The run is `degraded` with reason `blog_length`; the draft is kept |
| A citation does not resolve, or its References entry mismatches | The gate requests a repair; after two passes the run fails with reason `dangling_citations` |
| The model call raises | The authoring phase fails and the run records the failure |

## Example

For the committed example run, the writer produced a 3,193-word draft titled "Python LangChain Deep Agents Startup Ideas: Building on the Harness, Not the Model", citing 17 sources. Two of them, S-14 and S-24, had a References mismatch that two repair passes did not fix, so the run ended `failed` with reason `dangling_citations` and the draft was kept.
