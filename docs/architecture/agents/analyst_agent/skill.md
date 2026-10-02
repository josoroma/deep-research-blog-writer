# analyst_agent — skill

The analyst sub-agent reads the corpus and writes the research summary. It is assembled in `agents/deep_research.py` and prompted by `prompts/analyst_agent.md`.

## Purpose

Read every source file and `research/index.md`, then write `research/summary.md` with the recurring themes, named frameworks, points of agreement and disagreement, gaps, and a suggested outline, each theme citing its supporting source ids.

## Capabilities

- Reads the whole corpus through the filesystem tools.
- Writes `research/summary.md` with the six required level-2 sections.
- Cites at least one `[S-NN]` per theme, using only ids that exist in the corpus.

## Non-Capabilities

- Never searches, fetches, or invents evidence.
- Never modifies a source file; source files are immutable.
- Never writes the blog or the run report.
- Never cites a source id that is not in the corpus.

## Inputs

- The corpus under `research/`: the source files and `research/index.md`. Each source file is described by `Source` and `SourceMetadata`.
- `RunState` — the run's progress, carried in `ResearchAgentState.run`.
- The run workspace, provided by the harness filesystem backend.

## Outputs

- `research/summary.md` — the summary file. The agent returns its path.
- `RunState` — the updated run state, with the synthesize phase recorded.

## Available Tools

The sub-agent receives no registered application tools (`SUBAGENT_TOOLS["analyst_agent"]` is empty). It uses the harness filesystem tools (`ls`, `read_file`, `write_file`) against the run workspace.

## Security

- The workspace backend is `ImmutableSourceBackend`, so a source file cannot be overwritten, edited, or deleted.
- The agent has no network access and no provider client.
- The static boundary check forbids HTTP imports in agent modules.

## Observability

- The summary write is a tool span in the LangSmith trace and a log record.
- The run's token and cost totals include the analyst's model calls.

## Evaluation Criteria

- `check_summary` passes: the six required sections are present, every theme cites a source, and every cited id exists in the corpus.
- The offline authoring demo (`make demo-epic-7`) asserts the summary check passes.

## Failure Modes

| Failure | Behavior |
| --- | --- |
| A required section is missing | `check_summary` reports the missing sections and the run fails the summary check |
| A theme cites no source | `check_summary` reports the theme as unsourced |
| A theme cites an unknown source id | `check_summary` reports the unknown ids |
| The model call raises | The authoring phase fails and the run records the failure |

## Example

For a 21-source corpus, the analyst reads all 21 files and the index, then writes a summary whose themes each cite a real source id, such as `[S-01]`. The committed example run's `research/summary.md` is 3,535 words.
