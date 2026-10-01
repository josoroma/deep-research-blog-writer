# EPIC-3: Deep Agent Skeleton

Date: 2026-10-01

Status: PLANNED. Commands and acceptance evidence will be recorded in [EPIC-3-RUNBOOK.md](EPIC-3-RUNBOOK.md) and `docs/evidence/epic-3/`.

## Objective and scope

Implement US-3.1 through US-3.4 from [SPECS.md](SPECS.md#epic-3-deep-agent-skeleton), PRD.md milestone M1. Build on the committed EPIC-2 building blocks:

- `ResearchRequest`, `RunState`, and `ResearchAgentState`;
- the `TOOLS` registry and `TypedTool` adapter;
- the prompt catalog;
- `LLMService` with fake injection.

Deliverables:

- every run gets a validated, collision-safe workspace at `runs/<run_id>/`;
- one `create_deep_agent` orchestrator with exactly four declarative sub-agents and the PD-005 tool assignment;
- typed, offline stub tools so the whole skeleton runs end to end;
- real-disk filesystem persistence through `FilesystemBackend(virtual_mode=True)`;
- the `deep-research-blog` console script.

Out of scope, kept for their owning stories:

- Real search, normalization, fetching, extraction, source-file writing, and indexing (EPIC-4 to EPIC-6).
- Synthesis and writer content rules, and citation validation (EPIC-7).
- `run.json`, PD-017 outcome classification, retries, the SQLite checkpointer, and `--resume` (EPIC-8).
- Tracing, logs, and metrics (EPIC-9).
- Source immutability permissions (US-6.1#4) and writer read restrictions (US-7.2#3).

Each stub's contract may change in the story that replaces it. Stub descriptions say that they are M1 stubs, so a live model is told that no real research happens.

## Verified framework facts (locked DeepAgents 0.7.21)

These facts were confirmed against the installed package before planning, using scratch probes that are not committed:

- `create_deep_agent(model, tools, *, system_prompt, middleware, subagents, backend, state_schema, ...)` is the 0.7 API. Sub-agent specs use `system_prompt`, not `prompt`; the orchestrator uses `system_prompt`, not `instructions`.
- `write_todos` is **not** bound by default in 0.7.21. Adding `TodoListMiddleware()` binds it to the orchestrator.
- A `general-purpose` sub-agent is added automatically. It inherits the orchestrator's tools, plus its own filesystem tools. That would be a fifth, unplanned agent with orchestrator tools, contradicting PD-005 and PD-006. Registering a harness profile with `GeneralPurposeSubagentProfile(enabled=False)` for the model's provider removes it. A `task` call naming `general-purpose` then returns "does not exist".
- Declarative sub-agents with `tools=[...]` get only those tools plus the harness filesystem tools: `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, and `grep`. The `task` and `write_todos` tools stay with the orchestrator.
- `FilesystemBackend(root_dir=..., virtual_mode=True)` writes to disk immediately. It returns `Error: Path traversal not allowed` for `..` or `~`, and it refuses resolved paths outside the root, including symlinks.

## Implementation sequence

1. **US-3.1: Run workspace** (`services/workspace.py`, `schemas/workspace.py`).
   - The slug is lowercase ASCII from NFKD normalization. Non-alphanumeric runs collapse to `-`, and the slug is at most 60 characters. A topic with no ASCII content falls back to `topic`.
   - `run_id = <slug>-<YYYYMMDDTHHMMSSZ>`, from a timezone-aware clock converted to UTC. Naive datetimes are rejected.
   - `create_run_workspace(request: ResearchRequest, runs_root)` accepts only an already-validated request. It creates `runs/<run_id>/` with `exist_ok=False`, so another run is never overwritten. It then writes `request.json` from the validated model.
   - The `RunWorkspace` contract carries the run_id and the absolute root.
   - Invalid topics fail in `ResearchRequest` validation, before any directory is touched.
2. **US-3.2: Typed stub tools** (`schemas/tool_io.py`, `tools/stubs.py`, registered in `TOOLS`).
   - `google_search(query, page) -> GoogleSearchOutput[SearchResult]` and `normalize_results(max_urls) -> NormalizeResultsOutput`.
   - `fetch_url(url) -> FetchedPage`, whose stub HTML contains a unique `RAW_HTML_MARKER`.
   - `extract_markdown(page, source_id) -> Source`, whose clean body excludes the marker.
   - `collect_source(rank, url) -> SourceMetadata`. It calls `fetch_url` and `extract_markdown` internally through the registry, so both sides are validated. It returns only the source_id, path, title, and word_count.
   - `build_index`, `validate_citations`, and `write_run_report` return fixed typed outputs.
   - The stubs are deterministic and offline, and write nothing.
3. **US-3.2: Assembly** (`agents/deep_research.py`).
   - `build_deep_agent(llm: LLMService, workspace: RunWorkspace)` calls `create_deep_agent`. It passes the orchestrator's model from `LLMService`, its `system_prompt` from the catalog, `state_schema=ResearchAgentState`, and `TodoListMiddleware`.
   - It also passes the orchestrator tools: `normalize_results`, `build_index`, `validate_citations`, and `write_run_report`.
   - There are four `SubAgent` specs. Each gets its own catalog prompt and its own `LLMService` model:
     - `search_agent`: `google_search`
     - `research_agent`: `collect_source`
     - `analyst_agent`: filesystem tools only
     - `writer_agent`: filesystem tools only
   - Tool lists come from the `TOOLS` registry by name; a missing name fails at build time.
   - The auto-added general-purpose sub-agent is disabled. The builder fails if the model's provider cannot be resolved, rather than silently keeping a fifth agent.
   - Keep `agents/` free of HTTP clients, provider clients, and inline prompts. The existing EPIC-1 and EPIC-2 checks run over the new module.
4. **US-3.2#4: SKILL.md.** Update the wiring example to the 0.7 API: `system_prompt`, catalog prompts, `LLMService` models, `FilesystemBackend`, and `TodoListMiddleware`. Update the sub-agent/tool table and workflow step 4 to the PD-005 assignment.
5. **US-3.3: Real-disk workspace.**
   - Configure `FilesystemBackend(root_dir=<runs/<run_id>>, virtual_mode=True)` as the deep agent's backend.
   - Record ADR 0003 for the filesystem backend. Record ADR 0004 for disabling the general-purpose sub-agent.
   - Prove the behavior through the real built agent:
     - a sub-agent's `write_file` of `research/summary.md` is on disk before its next model step;
     - traversal and symlink-escape writes are refused, and no file appears outside the workspace.
6. **US-3.4: CLI** (`workflows/research_run.py`, `workflows/cli.py`, `[project.scripts] deep-research-blog`).
   - Positional topic, plus `--pages`, `--per-page`, and `--max-urls`. Defaults come from `RunSettings`, and `ResearchRequest` validates them.
   - Order of operations: validate the request, then preflight the model service, then create the workspace, then build and invoke the agent. The initial message carries the validated request JSON. A configurable recursion limit applies.
   - Print `run_id`, `workspace`, `status`, and `blog_path`, and whether the blog exists.
   - Exit codes:
     - `0`: the skeleton invocation completed (`status: completed`).
     - `1`: the invocation raised (`status: failed`); the workspace is kept.
     - `2`: invalid topic or budgets, or a missing model key. No workspace is created.
   - PD-017 statuses and exit 3 arrive with US-8.2. Add `RUNS_DIR` and `RECURSION_LIMIT` settings.
7. **Offline fake and demo** (`evaluations/fakes.py`, `evaluations/epic3_demo.py`, `make demo-epic-3`).
   - The `ScriptedChatModel` accepts one tool call per step, binds tool names per call through `Runnable.bind`, and records every model input across all agents.
   - The demo runs the real CLI path, with the scripted fake injected through `LLMService`, into `runs/`. It reports:
     - sub-agents and their tools, the orchestrator's tools, and the tools each agent was actually bound to;
     - prompt provenance and the nine todos;
     - the files on disk and the containment probe;
     - the marker's absence from model contexts;
     - the general-purpose rejection, the budget override, and the invalid-topic exit 2 with no new directory.
8. **Verify and deliver.**
   - Keep Ruff 0.13.0, strict mypy 1.18.1, offline pytest, and the ≥80% coverage gate.
   - Add tests for every acceptance scenario.
   - Run setup, check, hooks, the EPIC-2 and EPIC-3 demos, the CLI invalid-topic path, build, and an installed-wheel console-script check.
   - Optionally run one bounded live skeleton run, recorded separately; offline acceptance does not depend on it.
   - Record transcripts, `commands.jsonl`, coverage, and source hashes under `docs/evidence/epic-3/`. Write `EPIC-3-RUNBOOK.md`.
   - Commit with hooks active. Run fresh-checkout verification. Update only the verified EPIC-3 statuses in SPECS.md.

## Acceptance and evidence matrix

| Story | Scenario | Planned evidence |
| --- | --- | --- |
| US-3.1 | Run id is slug + `-` + UTC timestamp; directory created | Workspace unit tests with a fixed clock; demo `run_id` and workspace |
| US-3.1 | Validated request stored | `request.json` equals the validated request; budget override test |
| US-3.1 | Invalid topic starts no run | CLI test and demo: exit 2, `runs/` listing unchanged |
| US-3.2 | Four sub-agents with PD-005 tools and catalog prompts | Spec tests, plus the tools and system prompts recorded at each sub-agent's model call |
| US-3.2 | Orchestrator holds deterministic tools, never fetch/extract/collect | The real graph's ToolNode and recorded orchestrator bindings |
| US-3.2 | Raw pages stay out of every model context | Marker present in stub `fetch_url` HTML; absent from every recorded model input and from final state |
| US-3.2 | Plan as todos | Orchestrator binds `write_todos`; final state holds the nine phase todos |
| US-3.2 | Skeleton runs end to end with fakes | Full scripted invocation completes; CLI exit 0 |
| US-3.3 | Files reach disk before the next step | Script hook asserts that `research/summary.md` exists at the analyst's next model call |
| US-3.3 | Writes outside the workspace refused | Traversal and symlink probes return errors; no outside file; ADR 0003 |
| US-3.4 | Start a run and print the summary | CLI tests and demo print run_id, workspace, status, and blog_path |
| US-3.4 | Override budgets | `--pages 2 --per-page 5 --max-urls 10` stored in `request.json` and in the orchestrator input |
| US-3.4 | Reject invalid topic | Exit 2 with an explanation of the topic rule; no workspace |

## Demo and evidence of done

- `make setup`, `make check`, and `make hooks` show that the retained quality gates still pass.
- `make demo-epic-3` runs the real CLI path offline, writes a real workspace under `runs/`, and prints the acceptance facts above.
- `uv run deep-research-blog ""` shows the invalid-topic exit 2 with no workspace created.
- Running `make build` and the EPIC-3 wheel verifier shows the console script and the skeleton working outside the checkout.
- An optional bounded live `uv run deep-research-blog "<topic>" --pages 1 --per-page 1 --max-urls 1` is recorded separately and labeled as stub data.

## Completion checklist

- [ ] US-3.1 implemented and verified.
- [ ] US-3.2 implemented and verified, including the SKILL.md wiring update.
- [ ] US-3.3 implemented and verified; ADR 0003 (and ADR 0004) recorded.
- [ ] US-3.4 implemented and verified.
- [ ] Setup, quality gates, hooks, demos, build, and installed-wheel check pass.
- [ ] Runbook, raw transcripts, coverage, and source hashes saved.
- [ ] Implementation committed with hooks; fresh-checkout verification passes; SPECS.md statuses updated.
