-- Queue and job metadata. This table is both the durable record of truth and the
-- work queue, so acceptance and idempotency agree inside one transaction and there
-- is no database/broker dual-write gap. Checkpoint tables are intentionally
-- separate: a graph checkpoint does not mean a job was accepted or completed.

CREATE TABLE IF NOT EXISTS jobs (
    job_id           UUID PRIMARY KEY,
    operation        TEXT NOT NULL CHECK (operation IN ('search', 'research')),
    state            TEXT NOT NULL CHECK (
        state IN ('queued', 'running', 'succeeded', 'degraded', 'failed', 'interrupted')
    ),
    request_hash     TEXT NOT NULL,
    idempotency_key  TEXT NOT NULL,
    payload          JSONB NOT NULL,
    run_id           TEXT,
    phase            TEXT,
    attempt          INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    worker_identity  TEXT,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at     TIMESTAMPTZ,
    status_reasons   JSONB NOT NULL DEFAULT '[]'::jsonb,
    error            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One idempotency key maps to exactly one job for its lifetime.
CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency_key_key ON jobs (idempotency_key);

-- Claiming scans by (state, created_at); keep it an index-only walk.
CREATE INDEX IF NOT EXISTS jobs_claim_idx ON jobs (state, created_at);

-- Recovering expired leases filters running jobs by their deadline.
CREATE INDEX IF NOT EXISTS jobs_lease_idx ON jobs (state, lease_expires_at);
