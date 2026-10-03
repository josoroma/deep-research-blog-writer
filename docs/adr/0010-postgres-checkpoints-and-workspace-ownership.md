# 0010: PostgreSQL checkpoints and exclusive workspace ownership

Date: 2026-10-02
Status: Accepted

## Context

PD-019 and ADR 0007 use a per-run SQLite checkpointer for local CLI execution,
and named PostgreSQL as the upgrade path when runs move to a server. Server
execution introduces a second writer case: a worker may crash while a second
worker (or a resumed attempt) targets the same run. An expired heartbeat alone
cannot authorize a second process to write into the same workspace, because the
crashed process may still hold open file handles.

## Decision

Server graphs use PostgreSQL savers so a worker restart resumes a run instead of
restarting it. The checkpoint schema is created or migrated once by the startup
migration command (`python -m application.migrations`), never on every request.
Local execution keeps `runs/<run_id>/checkpoints.sqlite` unchanged. Both paths
share one restricted serializer: typed `RunState`, `UrlOutcome`, and
`RunStateUpdate` round-trip without a general pickle fallback.

Ownership has two gates. The job row carries a lease with a heartbeat; an expired
lease marks the attempt `interrupted`. In addition, each attempt holds an
exclusive OS lock on `.run.lock` inside the run workspace. A second writer that
cannot take the lock is denied, so an expired lease never lets two processes
mutate one workspace.

## Consequences

### Pros

- A worker restart resumes the saved graph and phase history.
- The OS lock prevents conflicting writers even when a lease expires.
- The checkpoint schema is prepared explicitly, keeping startup predictable.

### Cons

- The single-host assumption holds: a shared filesystem plus a coordinated lock
  is required before running workers on multiple hosts.
- Checkpoint tables must not be treated as proof that a job was accepted or
  completed; the queue tables remain the record of truth.
