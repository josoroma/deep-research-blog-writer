# Orchestrator — contract

## Input

- `ResearchRequest` — the validated topic (3–250 characters after trimming) and the `pages`, `per_page`, and `max_urls` budgets.
- `RunState` — the run's progress, carried in `ResearchAgentState.run` and updated by every state-changing tool.
- `QueryVariants` — the 2 or 3 planner variants, each distinct from the topic and from each other.

## Output

- `RunReport` — persisted to `output/run.json` with the topic, run id, model, per-phase timings, URL counts and outcomes, citation count, tokens, cost, retries, status, and status reasons.
- The run workspace under `runs/<run_id>/`: `request.json`, `search_plan.json`, `search_results.json`, `clean_results.json`, `research/` (source files, `index.md`, `summary.md`), `output/blog.md`, `output/run.json`, and `logs/`.

## Success criteria

| Criterion | Source |
| --- | --- |
| One topic produces a corpus of up to 30 cleaned Markdown sources and a cited blog post with no manual steps | PRD.md §1 |
| Every non-obvious claim carries an inline `[S-NN]` citation that resolves to a corpus file | PRD.md FR-8, FR-9 |
| The run is not "done" until zero dangling citations remain | PRD.md FR-9 |
| `output/run.json` records the topic, run id, model, timings, counts, citation count, and token and cost totals | PRD.md FR-10 |
| A single URL, parser, or model failure never aborts the run | PRD.md NFR-1 |
| All inputs and artifacts are persisted under `runs/<run_id>/` | PRD.md NFR-2 |
| Budgets are enforced: `max_urls=30`, at most 3 fetch retries, one blog generation, at most 2 citation repairs | PRD.md NFR-4 |
| The run status follows the failed, degraded, and succeeded rules, including the 80% extraction threshold | SPECS.md PD-017 |
| The report carries the PRD §8 and FR-10 fields plus the PD-018 outcome entries | SPECS.md PD-018 |

## Failure conditions

- The planner cannot produce valid variants after two attempts: `SearchPlanningError`, and no workspace is created.
- A search provider request fails: the run fails, the plan is preserved, and no clean results are claimed.
- The draft has dangling or mismatched citations after two repair passes: the run ends `failed` with reason `dangling_citations`, and the last draft is kept.
- A phase raises twice: `run_phase` propagates the second failure and the report records `phase_failed`.
- Fewer than 80% of clean URLs extract: the run is `degraded` with reason `too_few_sources`.
- No clean results, or clean results with zero extracted sources: the run is `failed` with reason `no_results` or `no_sources`.
