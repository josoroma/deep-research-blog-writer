# 0009: Durable job queue and HTTP contract

Date: 2026-10-02
Status: Accepted

## Context

The FastAPI migration adds an HTTP entry point for long-running research jobs.
Clients need to submit work, poll status, and read results, but a research job
runs for minutes and cannot execute inside a request handler. A request-scoped
background task dies with the API process, so an accepted job would be lost on
restart. The plan requires a durable acceptance step, idempotent submission, and
a bounded queue before work begins.

## Decision

The API accepts a job into a PostgreSQL `jobs` table and returns `202` with an
opaque job UUID and `Location: /v1/jobs/<job_id>`. The job is the operator's
acceptance of work; it is distinct from a run. A separate worker process claims
jobs transactionally with `FOR UPDATE SKIP LOCKED`, updates ownership, and
commits before performing any research.

The jobs table is both the durable record of truth and the queue, so acceptance
and idempotency agree inside one transaction and there is no database/broker
dual-write gap. Submissions require an `Idempotency-Key`: within one transaction
the same key and normalized payload return the original job, and a changed
payload returns `409`. The canonical run ID is assigned by the worker after
provider and configuration preflight; `run_id` is null while queued. Job states
are `queued`, `running`, `succeeded`, `degraded`, `failed`, and `interrupted`,
with legal transitions enforced by the store.

## Consequences

### Pros

- An accepted job survives an API restart; the worker re-claims it by lease.
- Idempotency prevents duplicate work from a retried client request.
- No broker dependency; the queue is inspectable with SQL.

### Cons

- PostgreSQL becomes a required server dependency (already the PD-019 upgrade
  path).
- Leases, recovery policy, and exclusive workspace ownership are still required
  on top of database ownership; a lease alone cannot stop two writers.
