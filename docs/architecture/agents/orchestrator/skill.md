# Orchestrator — skill

The orchestrator deep agent coordinates one topic through the nine-phase pipeline and owns the run's typed state. It is assembled in `agents/deep_research.py` and prompted by `prompts/orchestrator.md`.

## Purpose

Turn one validated topic into a cited blog draft by coordinating four sub-agents and the deterministic tools, while keeping every artifact under `runs/<run_id>/` and every phase recorded in `RunState`.

## Capabilities

- Derives 2 or 3 query variants from the topic and persists the bounded search plan.
- Normalizes raw search results into at most `max_urls` clean, ranked URLs.
- Delegates paged searching to `search_agent` and corpus collection to `research_agent`.
- Delegates synthesis to `analyst_agent` and drafting to `writer_agent`.
- Builds the corpus index, runs the citation gate, and requests at most two writer repairs.
- Writes the run report and applies the failed, degraded, and succeeded rules.
- Tracks phases with `write_todos` and the explicit `RunState`.

## Non-Capabilities

- Never fetches a URL, calls a search API, or constructs a provider client (BR-001).
- Never writes a source file, the index, the summary, or the blog itself; those belong to tools and sub-agents.
- Never receives raw HTML in its context.
- Never invents a tool, a completed artifact, or a source id.
- Never scrapes result pages, solves a CAPTCHA, or reads paywalled content.
- Never publishes to a CMS or generates images.

## Inputs

- `ResearchRequest` — the validated topic and the `pages`, `per_page`, and `max_urls` budgets.
- `QueryVariants` — the 2 or 3 variants the planner derives, each distinct from the topic.
- `RunState` — the run's progress, carried in `ResearchAgentState.run`.
- `NormalizeResultsInput`, `BuildIndexInput`, `ValidateCitationsInput`, `WriteRunReportInput` — the no-argument inputs of the deterministic tools it calls.

## Outputs

- `SearchPlanOutput` — the persisted plan and the updated `RunState`.
- `NormalizeResultsOutput` — the clean results, the `NormalizationCounts`, and the updated `RunState`.
- `BuildIndexOutput` — the index path, the source count, and the updated `RunState`.
- `ValidateCitationsOutput` — the citation counts, the dangling and mismatched ids, and the updated `RunState`.
- `WriteRunReportOutput` — the report path.
- `RunReport` — the persisted `output/run.json`.

## Available Tools

Registered tools the orchestrator receives (`ORCHESTRATOR_TOOLS`):

| Tool | Input | Output |
| --- | --- | --- |
| `plan_search` | `QueryVariants` | `SearchPlanOutput` |
| `normalize_results` | `NormalizeResultsInput` | `NormalizeResultsOutput` |
| `build_index` | `BuildIndexInput` | `BuildIndexOutput` |
| `validate_citations` | `ValidateCitationsInput` | `ValidateCitationsOutput` |
| `write_run_report` | `WriteRunReportInput` | `WriteRunReportOutput` |

It also uses the harness `task` tool to delegate to sub-agents and `write_todos` to track phases. It does not receive `google_search`, `collect_source`, `fetch_url`, or `extract_markdown`.

## Security

- Credentials and provider clients stay outside agent and checkpoint state; the registry binds tools to a run-owned session.
- The workspace backend is `ImmutableSourceBackend`, so a source file cannot be overwritten, edited, or deleted.
- The static boundary check (`evaluations/agent_boundary.py`) forbids HTTP imports in agent modules, and the architecture check (`evaluations/agent_architecture.py`) forbids provider clients and inline prompts.
- The general-purpose sub-agent is disabled (ADR 0004), so only the four documented sub-agents exist.

## Observability

- Every run appends JSON Lines to `runs/<run_id>/logs/execution.log` and totals to `logs/telemetry.json`.
- LangSmith traces carry the `run_id` and `topic` as metadata on the root and every descendant span.
- Optional OTLP metrics cover tokens, cost, retries, tool calls, URL outcomes, and dangling citations.

## Evaluation Criteria

- The run report's status follows PD-017: `failed` for `no_results`, `no_sources`, `phase_failed`, or `dangling_citations`; `degraded` for `too_few_sources` or `blog_length`; `succeeded` otherwise.
- The citation gate reports zero dangling citations for a `succeeded` run (FR-9).
- The offline suite and the golden-dataset evaluation in EPIC-10 score the run.

## Failure Modes

| Failure | Behavior |
| --- | --- |
| The planner cannot produce valid variants after two attempts | `SearchPlanningError`; the run fails before a workspace is created |
| A search page request fails | The provider error is recorded; the run fails and the plan is preserved |
| One URL is unreachable, blocked, unsupported, or thin | The outcome is recorded and skipped; the run continues |
| The draft has dangling or mismatched citations after two repairs | The run ends `failed` with reason `dangling_citations`; the last draft is kept |
| A phase raises | `run_phase` retries once, then the failure propagates and the report records `phase_failed` |
| Fewer than 80% of clean URLs extract | The run is `degraded` with reason `too_few_sources` |

## Example

For the topic "2026 agentic AI frameworks", the orchestrator derives three variants, calls `plan_search`, delegates six `google_search` calls to `search_agent`, calls `normalize_results` to keep 30 clean URLs, delegates 30 `collect_source` calls to `research_agent`, calls `build_index`, delegates the summary to `analyst_agent` and the draft to `writer_agent`, calls `validate_citations`, and calls `write_run_report`. The committed example run under `runs.example/` shows the resulting artifacts.
