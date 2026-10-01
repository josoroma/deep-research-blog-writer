# 0004: Disable the auto-added general-purpose sub-agent

Date: 2026-10-01

Status: Accepted

## Context

[SPECS.md PD-005](../../SPECS.md#pd-005--deterministic-steps-run-as-tools) assigns tools to exactly four sub-agents, and [PD-006](../../SPECS.md#pd-006--the-citation-gate-is-the-review-step) states that v1 has no reviewer sub-agent. US-3.2 requires that the orchestrator's tools exclude `fetch_url`, `extract_markdown`, and `collect_source`, and that only `search_agent`, `research_agent`, `analyst_agent`, and `writer_agent` are registered.

DeepAgents 0.7.21 adds a `general-purpose` sub-agent automatically when the caller does not supply one. That sub-agent inherits the orchestrator's tools, so it would expose `normalize_results`, `build_index`, `validate_citations`, and `write_run_report` to a fifth agent that PD-005 does not define. It also appears in the `task` tool's available-agent list, so a model could route work to it.

## Decision

Register a harness profile for the model's provider with `GeneralPurposeSubagentProfile(enabled=False)` before building the agent. The builder resolves the provider from the model and fails with `UnsupportedModelProvider` when it cannot, rather than silently keeping a fifth agent.

## Consequences

### Pros

- The built agent has exactly the four PD-005 sub-agents and no others.
- The orchestrator's deterministic tools stay with the orchestrator.
- A `task` call naming `general-purpose` returns "does not exist", which the demo asserts.
- The failure mode is explicit: an unresolvable provider stops the build instead of changing the agent topology.

### Cons

- The profile is registered per provider, so it also applies to other agents built with the same provider in the same process.
- It depends on a beta `deepagents.profiles` API that may change in a minor release.
- A future story that wants a general-purpose agent must re-enable it deliberately.
