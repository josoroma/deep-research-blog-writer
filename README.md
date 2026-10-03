# Deep Research Blog Writer

**Give it a topic. Get back a researched, cited blog draft.**

It searches the web, reads the best sources, takes notes, and writes the article. Then it checks every citation. If something doesn't add up, it says so and keeps the draft, so no work is lost.

![Deep Research Blog Writer pipeline](docs/images/pipeline.svg)

**Live walkthrough:** https://josoroma.github.io/deep-research-blog-writer

---

## How a run works

Three steps, each one picking up where the last left off.

1. **Search.** Find the most relevant pages for your topic.
2. **Collect.** Read each page and save the useful ones as sources.
3. **Write.** Summarize the sources, draft the article, and check the citations.

![The three-command live run](docs/images/live-run.svg)

Everything from a run lands in one folder, so you can open it and see exactly what happened.

![Run workspace artifacts](docs/images/workspace.svg)

---

## Get started

You need Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Make.

```sh
make setup
make check
```

That installs everything and runs the tests. No API keys needed yet.

To run it for real, copy `.env.example` to `.env` and add a search key and a model key. Then:

```sh
uv run deep-research-blog "Your topic here" --search-only
```

---

## Develop against it

The CLI is still the local path. The HTTP API admits a job; a separate worker runs the same use cases and writes a workspace the API can read back.

Offline, with no database and no keys:

```sh
make demo-api
```

On one machine, with PostgreSQL:

```sh
make api-up
make migrate-api
make run-api
```

In a second terminal:

```sh
make worker-api
```

`make api-up` starts only Postgres on `127.0.0.1:5432`. The API listens on `127.0.0.1:8000`. Set `API_DATABASE=postgresql://research:research@127.0.0.1:5432/research` before `migrate-api`, `run-api`, and `worker-api`. Server workspaces go to `runs-api/`, not `runs/`.

Submit a job, then poll the job the `Location` header points at:

```sh
curl --fail --silent --show-error http://127.0.0.1:8000/health/ready
curl --include --silent --show-error \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: dev-1' \
  -d '{"mode":"search","topic":"Your topic here","pages":1,"per_page":10,"max_urls":2}' \
  http://127.0.0.1:8000/v1/runs
```

`mode` is `search` or `research`. The same idempotency key and body return the original job; a changed body returns `409`. Once the worker assigns a run id, read `/v1/runs/<run_id>`, `/report`, and `/artifacts/...`.

| Make target | What it does |
| --- | --- |
| `make check` | Lock, lint, format, strict typing, offline tests, 80% coverage |
| `make demo-api` | In-process fixture job: submit, run one worker attempt, read the report |
| `make api-up` / `make api-down` | Start or stop local Postgres |
| `make migrate-api` | Apply server SQL migrations |
| `make run-api` | Serve the API on `127.0.0.1:8000` |
| `make worker-api` | Claim jobs and execute them |
| `make observability-up` | Local collector, Prometheus, and Grafana |

Importing `api` does not start a worker, create a run directory, or call a provider. Set `API_TOKEN` before anything other than loopback use. `API_RUN_PROFILE=fixture` is a server setting, not a client choice.

The phase commands, settings, and artifact layout are in [`README-DEV.md`](README-DEV.md). The API walkthrough is in [`docs/SPECS-LOGS/FASTAPI-MIGRATION-RUNBOOK.md`](docs/SPECS-LOGS/FASTAPI-MIGRATION-RUNBOOK.md).

---

## Who does what

One coordinator hands work to four specialists: a searcher, a researcher, an analyst, and a writer.

![Agent architecture](docs/images/agents.svg)

Each one has a short description of its job in [`docs/architecture/`](docs/architecture/README.md).

---

## Honest by design

A draft only counts as done if every citation points to a real source. The example run wrote a 3,193-word article, but two references didn't match their sources, so it was marked **failed** rather than passed off as finished.

![Quality gates](docs/images/quality-gates.svg)

Before any release, it's scored on a fixed set of topics for accuracy and coverage.

---

## See what's happening

Every run can be watched live: metrics in a local dashboard, and a step-by-step trace in LangSmith.

![Observability flow](docs/images/observability.svg)

![Grafana Deep Research Runs dashboard](docs/pages/images/grafana-dashboard.png)

![LangSmith traces](docs/pages/images/langsmith-traces.png)

![LangSmith trace tree](docs/pages/images/langsmith-trace-tree.png)

![LangSmith API keys](docs/pages/images/langsmith-api-keys.png)

---

## How it was built

One piece at a time: plan it, build it, test it, then move on.

![One epic per session](docs/images/epic-loop.svg)

---

## Useful links

Local links work while the dashboard is running (`make observability-up`).

| Service | URL | Used for |
| --- | --- | --- |
| Grafana dashboard | http://127.0.0.1:3001/d/research-runs | Run metrics panels |
| Prometheus | http://127.0.0.1:9090 | Raw run metrics |
| OTLP collector | `http://127.0.0.1:4318/v1/metrics` | CLI metrics export |
| LangSmith | https://smith.langchain.com | Hosted traces |
| LangSmith API | https://api.smith.langchain.com | `LANGSMITH_ENDPOINT` default |
| OpenRouter | https://openrouter.ai | Agent model access |
| SerpApi | https://serpapi.com | Search provider |
| Serper | https://serper.dev | Search provider |
| LangGraph | https://docs.langchain.com/oss/python/langgraph/overview | Runtime under DeepAgents |
| DeepAgents | https://docs.langchain.com/oss/python/deepagents/overview | Orchestrator and sub-agent harness |
| Documentation | https://josoroma.github.io/deep-research-blog-writer | Project explainer |
| Research API | http://127.0.0.1:8000 | `make run-api`; jobs at `/v1/runs` |
| API readiness | http://127.0.0.1:8000/health/ready | Database and queue; `503` when admission cannot proceed |

---

## Want the details?

- [`README-DEV.md`](README-DEV.md): every command, setting, and output, for developers
- [Live walkthrough](https://josoroma.github.io/deep-research-blog-writer): a visual tour of a real run
- [`docs/`](docs/): design decisions, agent docs, and delivery records
