# FastAPI migration runbook

Date: 2026-10-02, verified against PostgreSQL 17 on 2026-10-03
Status: implemented; exercised end to end on real PostgreSQL with `API_RUN_PROFILE=fixture`. A server run with live providers is still pending.

This runbook covers the HTTP entry point added by `docs/workspace/plan/FASTAPI-MIGRATION.md`.
The API and the worker share the existing business use cases; the local CLI keeps
working. Product decision PD-023 records the durable job queue and server
execution rules; ADRs 0009–0011 record the queue, checkpoint/ownership, and
artifact-access decisions.

## What was added

| Area | Module | Responsibility |
| --- | --- | --- |
| Transport | `api/` | App factory, middleware, routers, typed errors, bearer auth |
| Use cases | `application/` | Job admission, phase execution, migrations, fixture profile |
| Scheduling | `workers/research_worker.py` | Claim, execute, record, shut down |
| Contracts | `schemas/api.py`, `schemas/jobs.py` | HTTP bodies and durable job records |
| Adapters | `services/postgres_jobs.py`, `services/job_store.py`, `services/artifact_reader.py` | PostgreSQL queue, in-memory queue, contained reads |
| Operations | `ops/api/` | Compose stack, Dockerfile, SQL migrations |

Importing any API module starts no worker, creates no run directory, and calls no
provider. Domain modules never import FastAPI.

## Configuration

`ApiSettings` reads the `API_` environment prefix (and `.env`).

| Variable | Meaning |
| --- | --- |
| `API_DATABASE` | PostgreSQL DSN. Required unless the fixture profile is selected. |
| `API_TOKEN` | Shared bearer token. When unset, only loopback use is intended. |
| `API_RUNS_DIR` | Server workspace root (default `runs-api`, separate from the CLI's `runs`). |
| `API_QUEUE_LIMIT` | Maximum active jobs before `429`. |
| `API_WORKER_LEASE_SECONDS` | Lease length for a claimed job. |
| `API_WORKER_HEARTBEAT_SECONDS` | Heartbeat interval while running. |
| `API_ALLOWED_ORIGINS` | Comma-separated CORS origins. |
| `API_RUN_PROFILE` | `production` (default) or `fixture` for local integration checks. |
| `API_MAX_PAGES`, `API_MAX_PER_PAGE`, `API_MAX_MAX_URLS` | Server-side budget caps. |

Existing provider and telemetry settings (OpenRouter, SerpApi/Serper,
`CRAWLER_CONTACT`, LangSmith, OTLP) still apply to real execution. Only
`API_RUN_PROFILE=fixture` swaps in fake providers; clients cannot select it.

## Local fixture demo (no database, no keys, no network)

```sh
make demo-api
```

This starts the app in-process with an in-memory store, submits a research job,
drives one worker attempt, then reads the job, run status, final report, an
artifact download, and a bounded log page. It uses temporary storage and prints
the checks it performs.

## Single-host stack

```sh
docker compose -f ops/api/compose.yaml up -d postgres
uv run --locked python -m application.migrations
uv run --locked uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000
```

In a separate terminal:

```sh
uv run --locked python -m workers.research_worker
```

`make api-up` starts only PostgreSQL; `make migrate-api`, `make run-api`, and
`make worker-api` wrap the three commands.

## Manual walkthrough

```sh
curl --fail --silent --show-error http://127.0.0.1:8000/health/ready
curl --include --silent --show-error \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: pm-fastapi-demo-1' \
  -d '{"mode":"research","topic":"Research telemetry quality","pages":1,"per_page":10,"max_urls":2}' \
  http://127.0.0.1:8000/v1/runs
```

Copy the returned job ID and poll `/v1/jobs/<job_id>`. Once the worker assigns a
run ID, read `/v1/runs/<run_id>`, `/v1/runs/<run_id>/report`, and
`/v1/runs/<run_id>/artifacts/output/blog.md` through the returned links.

## Endpoints

| Endpoint | Result |
| --- | --- |
| `GET /health/live` | Process health; no provider calls |
| `GET /health/ready` | Database/schema and queue readiness; `503` when submission cannot proceed |
| `POST /v1/runs` | `202` accepted job (search or research) |
| `GET /v1/jobs/{job_id}` | Job status, phase, run ID, safe reasons |
| `GET /v1/runs` | Paginated registered runs |
| `GET /v1/runs/{run_id}` | Phase progress and artifact availability |
| `GET /v1/runs/{run_id}/report` | Validated final `RunReport`; `409` before reporting |
| `GET /v1/runs/{run_id}/artifacts` | Allowlisted artifacts with sizes and links |
| `GET /v1/runs/{run_id}/artifacts/{path}` | Authorized download; Markdown as an attachment |
| `GET /v1/runs/{run_id}/logs` | Bounded log records with a next cursor |
| `POST /v1/runs/{run_id}/resume` | `202` new attempt for an eligible interrupted run |

## Operate: pause, drain, resume

1. Stop admitting new work by scaling the API to zero or by relying on the queue
   limit; accepted jobs stay durable.
2. Let the worker finish, or interrupt it. An interrupted attempt is marked
   `interrupted` when its lease expires or when the process is killed.
3. Deploy compatible code and schema, then confirm `/health/ready`.
4. Restart the worker. It re-claims the job and resumes from the last completed
   phase without rewriting existing source files.

Resume requires an interrupted job with an allocated run. Completed runs cannot
be resumed; conflicting writers are denied by the workspace lock.

## Evidence and verification

- Offline gate: `make check` (lock, lint, format, strict typing, tests, coverage ≥ 80%).
- Fixture acceptance: `make demo-api`, which reports the submitted job, terminal
  outcome, validated report, artifact list, and log page.
- Live-provider demos still use the CLI and `make eval`.

## Rollback

Switch clients back to local CLI execution. Do not remove the PostgreSQL volume
or the server run storage: jobs, checkpoints, and artifacts created by the newer
version may not be readable by an older one. Use additive migrations and
versioned contracts, and pause admission before reverting.
