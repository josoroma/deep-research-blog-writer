# 0001: Use DeepAgents on LangGraph

Date: 2026-09-30  
Status: Accepted

## Context

[PRD.md §4](../../PRD.md#4-why-deepagents) requires a research-to-blog workflow with planning, a source corpus on disk, isolated specialist agents, and resumable execution. Building these primitives ourselves would add orchestration and state-management work before the search, extraction, synthesis, and writing requirements can be delivered.

The project's design rules require agents to orchestrate, typed tools to execute external operations, immutable source files, and a writer that cites only the corpus. [SPECS.md US-1.4](../../SPECS.md#us-14-establish-the-architecture-decision-record-log) calls for this initial decision.

## Decision

Build on LangChain's `deepagents` harness, which runs on LangGraph. Use its planning/todo primitive, filesystem backend and context offloading, and specialist sub-agent support. Use LangGraph's stateful execution and checkpointing capabilities when the run lifecycle is implemented. Keep provider access behind typed tools and services; keep prompts in the catalog.

EPIC-1 installs and locks LangChain, LangGraph, DeepAgents, `langchain-openrouter`, and Pydantic v2. Agent wiring, real-disk workspace integration, state contracts, and checkpoint configuration are implemented in their subsequent stories. This ADR records the framework choice rather than claiming those behaviors already exist.

## Consequences

### Pros

- Reuse planning, filesystem operations, and sub-agent context isolation described in PRD §4.
- Offload raw source content to files so the writer can work from a clean corpus.
- Extend a shared LangGraph execution model for later checkpointing and resume support.
- Keep application responsibilities in typed tools, services, and schemas.

### Cons

- Depend on framework APIs and their compatible release versions; keep `uv.lock` under version control.
- Learn the harness's state, filesystem, and sub-agent semantics.
- Validate artifact permissions, checkpoint behavior, and tool contracts in later epics; framework selection alone does not enforce them.
- Carry a larger dependency set than a minimal sequential script.
