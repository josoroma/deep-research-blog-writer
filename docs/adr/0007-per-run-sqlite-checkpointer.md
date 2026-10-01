# 0007: Per-run SQLite checkpointer

Date: 2026-10-01
Status: Accepted

## Context

NFR-2 requires a run to resume from its last completed phase, and PD-019 names
`langgraph-checkpoint-sqlite` with the LangGraph thread id set to the run id.
The unit tests use an in-memory saver, which dies with the process, so a crash
late in a run would repeat the search, fetch, and extraction work. PostgreSQL
is the standards' stack, but v1 runs locally as a CLI.

## Decision

Each run checkpoints to `runs/<run_id>/checkpoints.sqlite` through
`langgraph-checkpoint-sqlite`, with the thread id equal to the run id. The tool
that finishes a phase records it in `RunState.completed_phases`, and
`collect_source` skips any URL whose source file already exists. The in-memory
saver stays for tests. PostgreSQL is the upgrade path when runs move to a
server.

## Consequences

### Pros

- A crash resumes from the last completed phase without repeating finished work.
- The checkpoint file lives inside the run workspace, so it is inspected and
  deleted with the run.

### Cons

- SQLite is single-writer. Concurrent runs are separate files, so this holds
  only while one process owns a run.
