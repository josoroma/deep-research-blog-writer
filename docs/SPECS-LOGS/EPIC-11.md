# EPIC-11: Agent Documentation

Date: 2026-10-02

Status: Planned. This plan is written before implementation. Successful commands and PM evidence will be recorded in `EPIC-11-RUNBOOK.md` and `docs/evidence/epic-11/` after verification.

## Objective

Implement US-11.1 and PD-022 in [SPECS.md](../../SPECS.md#epic-11-agent-documentation): document the orchestrator and each of its four sub-agents with a `skill.md` and a `contract.md` under `docs/architecture/agents/`, so the system stays understandable as agents are added.

## Current baseline

- The five agents exist and are assembled in `agents/deep_research.py`. `ORCHESTRATOR_TOOLS` and `SUBAGENT_TOOLS` name the registered tools each agent receives; `SUBAGENT_DESCRIPTIONS` gives each sub-agent's one-line role.
- Each agent has a packaged prompt under `prompts/`: `orchestrator.md`, `search_agent.md`, `research_agent.md`, `analyst_agent.md`, and `writer_agent.md`. These are runtime prompts, not the human documentation PD-022 asks for.
- The typed contracts live in `schemas/`: `ResearchRequest`, `RunState`, `RunStateUpdate`, `QueryVariants`, `SearchPlan`, `SearchPlanOutput`, `GoogleSearchInput`, `GoogleSearchOutput`, `SearchResult`, `NormalizeResultsInput`, `NormalizeResultsOutput`, `CollectSourceInput`, `CollectSourceOutput`, `SourceMetadata`, `BuildIndexInput`, `BuildIndexOutput`, `ValidateCitationsInput`, `ValidateCitationsOutput`, `WriteRunReportInput`, `WriteRunReportOutput`, `Source`, `RunReport`, and `UrlOutcome`.
- `docs/` holds `adr/`, `SPECS-LOGS/`, `evidence/`, and `pages/`. There is no `docs/architecture/` yet. `docs/__init__.py` marks the package, and `pyproject.toml` includes `docs` in the mypy file list.
- The senior-level template PD-022 names is not in the repository. PD-022 lists the required sections explicitly, so the plan follows that list.
- `evaluations/agent_architecture.py` and `evaluations/agent_boundary.py` already enforce the static rules the docs describe: prompts come from the catalog, provider clients stay in services, and agent modules never import an HTTP client.

## Implementation sequence

1. **Create the documentation tree.** Add `docs/architecture/README.md` as the index, then `docs/architecture/agents/<agent>/` for `orchestrator`, `search_agent`, `research_agent`, `analyst_agent`, and `writer_agent`.
2. **Write each `skill.md`.** Use the PD-022 sections in order: Purpose, Capabilities, Non-Capabilities, Inputs, Outputs, Available Tools, Security, Observability, Evaluation Criteria, Failure Modes, and Example. Inputs and Outputs name their Pydantic contract types.
3. **Write each `contract.md`.** State the input, the output, the success criteria, and the failure conditions. Each success criterion cites the PRD.md or SPECS.md item it comes from.
4. **Add a documentation check.** Add `tests/test_agent_docs.py`, which reads `docs/architecture/agents/` and asserts every agent has both files, that `skill.md` carries every PD-022 section, that Inputs and Outputs name contract types, and that `contract.md` states input, output, success criteria, and failure conditions with a traceable source.
5. **Verify.** Run locked setup, lint/format/strict typing/tests and coverage, hooks, existing demos, build, installed-wheel, and committed fresh-checkout verification. Save exact command outputs, coverage, and source hashes. Update only verified EPIC-11 story/task statuses and finalize `docs/SPECS-LOGS/EPIC-11-RUNBOOK.md`.

## Acceptance matrix

| Story | Scenario | Evidence |
| --- | --- | --- |
| US-11.1 | Every agent has a skill file | `tests/test_agent_docs.py` asserts each of the five agents has `skill.md` with all eleven PD-022 sections, and that Inputs and Outputs name contract types |
| US-11.1 | Every agent has a contract | `tests/test_agent_docs.py` asserts each agent's `contract.md` states input, output, success criteria, and failure conditions, and that each success criterion cites PRD.md or SPECS.md |

## Completion checklist

- [ ] `docs/architecture/agents/` holds `skill.md` and `contract.md` for all five agents.
- [ ] Every `skill.md` carries the eleven PD-022 sections and names its contract types.
- [ ] Every `contract.md` states input, output, success criteria, and failure conditions with a traceable source.
- [ ] The documentation check passes and is part of the offline suite.
- [ ] Offline demo, meaningful tests, coverage, and hooks pass.
- [ ] Build, installed package, existing demos, and fresh checkout pass.
- [ ] Runbook, exact command transcripts, snapshots, and hashes saved.
- [ ] Implementation and evidence committed.

## Scope boundary

- The documents describe the agents as they exist today. They do not add tools, change prompts, or alter runtime behavior.
- The `skill.md` files are human documentation. They are not loaded as runtime skills, and the orchestrator prompt already says so.
- No new ADR is required: PD-022 fixes the format and location, and this epic only follows it.
