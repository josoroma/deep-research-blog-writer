# analyst_agent — contract

## Input

- The corpus under `research/`: every source file and `research/index.md`. The agent reads all of them before writing.

## Output

- `research/summary.md` — the summary, with the six required level-2 sections and at least one `[S-NN]` citation per theme. The agent returns the summary path.

## Success criteria

| Criterion | Source |
| --- | --- |
| Synthesize the corpus into themes and an outline | PRD.md §9, FR-7 |
| The summary covers recurring themes, named frameworks, agreements, disagreements, gaps, and a suggested outline | PRD.md FR-7 |
| Each theme references the source ids that support it | PRD.md FR-7 |
| Every cited id belongs to a source file in the corpus | PRD.md FR-9 |

## Failure conditions

- A required section is missing: `check_summary` reports it and the summary check fails.
- A theme cites no source: `check_summary` reports the theme as unsourced.
- A theme cites an id that is not in the corpus: `check_summary` reports the unknown ids.
- The model call raises: the authoring phase fails and the run records the failure.
