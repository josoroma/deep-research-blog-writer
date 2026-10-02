# writer_agent — contract

## Input

- The corpus under `research/`: the source files, `research/index.md`, and `research/summary.md`.
- A repair request naming the dangling source ids, when the citation gate fails.

## Output

- `output/blog.md` — the draft, with one title, the seven required sections in order, inline `[S-NN]` citations, and a References section. The agent returns the draft path.

## Success criteria

| Criterion | Source |
| --- | --- |
| Draft the cited blog from the corpus and the summary | PRD.md §9, FR-8 |
| One title and the seven required sections in order | PRD.md FR-8 |
| 2000–5000 words | PRD.md FR-8 |
| Every non-obvious claim carries an inline `[S-NN]` citation | PRD.md FR-9 |
| The References section lists each cited source with its title and URL | PRD.md FR-9 |
| The draft is written once and never regenerated for length | SPECS.md PD-015 |

## Failure conditions

- The draft is missing or its headings are out of order: the run fails with reason `blog_structure`.
- The draft is outside 2000–5000 words: the run is `degraded` with reason `blog_length`, and the draft is kept.
- A citation does not resolve, or its References entry mismatches: the gate requests a repair; after two passes the run fails with reason `dangling_citations`.
- The model call raises: the authoring phase fails and the run records the failure.
