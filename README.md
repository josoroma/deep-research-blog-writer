# Deep Research Blog Writer

[![Quality gates](https://github.com/josoroma/deep-research-blog-writer/actions/workflows/quality.yml/badge.svg)](https://github.com/josoroma/deep-research-blog-writer/actions/workflows/quality.yml)

**Give it a topic. Get back a researched blog draft where every citation is checked.**

Deep Research Blog Writer searches the web, saves the pages worth reading as sources, writes a research summary, and drafts a 2,000–5,000-word article that cites only those sources. Before it calls a draft done, it checks every citation. If one doesn't hold up, the run is marked failed, the draft is kept, and the reason is written down.

![Topic in, researched and cited draft out](docs/images/01-overview.png)

[Live walkthrough](https://josoroma.github.io/deep-research-blog-writer) · [Example run](runs.example/python-langchain-deep-agents-startup-ideas-20261001T195605Z) · [Engineering standard](docs/ENGINEERING.md)

---

## A run, step by step

![Nine phases in three stages](docs/images/02-how-a-run-works.png)

A run moves through nine phases in three stages. Each stage writes its results to disk before the next one starts, so you can stop, inspect, and continue. The numbers below come from the committed [example run](runs.example/python-langchain-deep-agents-startup-ideas-20261001T195605Z).

### 1. Search

```sh
SEARCH_TIMEOUT_SECONDS=60 uv run deep-research-blog \
  "Python LangChain Deep Agents Startup Ideas" \
  --search-only --pages 3 --per-page 10 --max-urls 30
```

A planner adds two or three query variants, searches each one, and cleans the results. In the example, 52 raw results became 30 clean URLs after removing 9 denied hosts, 2 duplicates, and 11 results over the cap. The command prints the run's workspace path.

### 2. Collect

```sh
RUN=runs/python-langchain-deep-agents-startup-ideas-20261001T195605Z
uv run deep-research-blog --corpus-only --workspace "$RUN"
```

Each URL is fetched politely: it honors `robots.txt`, sends one request per host per second, and identifies itself with your contact address. The page is then turned into a Markdown source file. One failed page never stops the rest. In the example, 21 of the 30 URLs became sources.

### 3. Write and check

```sh
uv run deep-research-blog --author-only --workspace "$RUN"
```

The analyst writes `research/summary.md`, the writer drafts `output/blog.md`, and the citation gate checks every citation. When a citation fails, the writer gets up to two repair passes.

### 4. Read the outcome

The example draft is 3,193 words with 17 cited sources. Two references, `S-14` and `S-24`, still didn't match their sources after two repairs, so the run is **failed** and the draft is kept for review. That's the point: a run that looks finished but isn't gets flagged, not shipped.

| Exit | Meaning |
| --- | --- |
| `0` | The phase completed |
| `1` | The phase ran and failed; its summary JSON says why |
| `2` | Input or configuration was rejected before any work started |

---

## Get started

![Start in two minutes](docs/images/09-quickstart.png)

You need Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Make. uv installs Python 3.12 for you.

```sh
make setup      # locked dependencies and the Git hook
make check      # lint, strict typing, offline tests, coverage
make demo-api   # a full research job end to end, offline, no keys
```

To run against real providers, create `.env` and add your keys:

```sh
cp -n .env.example .env
```

```dotenv
SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=<your SerpApi key>
OPENROUTER_API_KEY=<your OpenRouter key>
CRAWLER_CONTACT=<a URL or email for the crawler's User-Agent>
```

Then start with the search step above. `.env` and `runs/` are Git-ignored.

---

## Run it as a service

![Submit over HTTP, a worker does the research](docs/images/06-api-and-worker.png)

The HTTP API accepts a job and returns right away. A separate worker claims it from a PostgreSQL queue, runs all nine phases, and writes a workspace the API can read back.

```sh
make api-up                 # PostgreSQL 17 on 127.0.0.1:5432
export API_DATABASE=postgresql://research:research@127.0.0.1:5432/research
make migrate-api            # idempotent
make run-api                # API on 127.0.0.1:8000
make worker-api             # in a second terminal
```

Set `API_RUN_PROFILE=fixture` on both the API and the worker to exercise the whole stack with no model, search, or website calls. This is a real exchange:

```console
$ curl -i -H 'Content-Type: application/json' -H 'Idempotency-Key: doc-research-1' \
    -d '{"mode":"research","topic":"Research telemetry quality","pages":1,"per_page":10,"max_urls":3}' \
    http://127.0.0.1:8000/v1/runs
HTTP/1.1 202 Accepted
location: /v1/jobs/f65fa89e-08da-4e78-9e7e-ef364e4ac7a9

$ curl http://127.0.0.1:8000/v1/jobs/f65fa89e-08da-4e78-9e7e-ef364e4ac7a9
{"status":"succeeded","run_id":"research-telemetry-quality-20261003T040357Z","phase":"report","attempt":1,...}
```

| Endpoint | Result |
| --- | --- |
| `POST /v1/runs` | `202` queued job; requires `Idempotency-Key` |
| `GET /v1/jobs/{job_id}` | State, phase, attempt, run id |
| `GET /v1/runs/{run_id}` | Phase progress and artifact availability |
| `GET /v1/runs/{run_id}/report` | The validated final report |
| `GET /v1/runs/{run_id}/artifacts` | Allowlisted files with download links |
| `GET /v1/runs/{run_id}/logs` | Bounded log records with a cursor |
| `POST /v1/runs/{run_id}/resume` | Continue an interrupted run |

- **Idempotent:** the same key and body return the original job; a different body returns `409`.
- **Recoverable:** a run interrupted mid-way resumes from the last completed phase without redoing saved work.
- **Errors:** all errors share one envelope, `{"error":{"code","message","request_id"}}`: `422` for bad input, `404` for an unknown resource, `409` for a conflict, `413` for an oversized artifact, `429` with `Retry-After` when the queue is full, `401` for a bad token, and `503` when the database is down.

The OpenAPI schema is generated at runtime, so there is no file in the repo. While the API runs, it is at [`/openapi.json`](http://127.0.0.1:8000/openapi.json), with interactive docs at [`/docs`](http://127.0.0.1:8000/docs) and [`/redoc`](http://127.0.0.1:8000/redoc).

![Swagger UI listing the health, jobs, and runs endpoints](docs/pages/images/swagger-endpoints.png)

---

## Inside a run

![Everything lands in one folder](docs/images/04-run-workspace.png)

Every run gets its own folder, named from the topic plus a UTC timestamp. Nothing is hidden in a database you can't open.

| File | Written by | What it holds |
| --- | --- | --- |
| `request.json`, `search_plan.json` | Search | The topic, budgets, and planned queries |
| `search_results.json`, `clean_results.json` | Search | Raw results and the ranked clean URLs |
| `research/NNN_<slug>.md` | Collect | One immutable source per page, with front-matter |
| `research/index.md` | Collect | An index of every source |
| `research/summary.md` | Write | The analyst's research summary |
| `output/blog.md` | Write | The cited draft |
| `output/authoring.json` | Write | The citation-gate record |
| `output/run.json` | Report | The final report: status, reasons, counts, cost |
| `logs/execution.log` | Every phase | Structured JSON log lines |

---

## Who does what

![One coordinator, four specialists](docs/images/03-agents.png)

| Agent | Job |
| --- | --- |
| `orchestrator` | Owns phase order and hands work to the specialists |
| `search_agent` | Plans query variants and ranks the results |
| `research_agent` | Collects and indexes sources |
| `analyst_agent` | Writes the research summary |
| `writer_agent` | Drafts the article and repairs citations |

Built with [DeepAgents](https://docs.langchain.com/oss/python/deepagents/overview) on [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview). Every agent uses DeepSeek V4.1 Flash through OpenRouter, and each model is configurable. Agents never call HTTP directly; every external call goes through a typed, validated tool. Each agent's job and contract are in [`docs/architecture/`](docs/architecture/README.md).

---

## Honest by design

![A draft counts only when every citation checks out](docs/images/05-citation-gate.png)

Every run ends in one of three states:

| Status | When | Exit |
| --- | --- | --- |
| **succeeded** | Every check passed | `0` |
| **degraded** | The draft is usable but thin: fewer than 80% of the URL budget became sources, or the length is out of range | `3` |
| **failed** | No results, no sources, a phase failed, or a citation doesn't match its source | `1` |

The citation gate checks that each cited source exists and that its title and URL match the References section. It doesn't judge whether a source is on topic.

---

## See every run

![Local metrics and hosted traces](docs/images/07-observability.png)

Every run writes `logs/execution.log` and `logs/telemetry.json` to its workspace. Metrics and traces are opt-in:

```sh
make observability-up   # OpenTelemetry collector, Prometheus, Grafana on 127.0.0.1
make demo-epic-9        # an offline run that exports real metrics
```

The [Grafana dashboard](http://127.0.0.1:3001/d/research-runs) shows runs by status, tokens, cost, phase latency, tool calls, retries, URL outcomes, and dangling citations. For hosted step-by-step traces, set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env`.

---

## Built to be checked

![Every change passes the same gate](docs/images/08-quality-gates.png)

| Command | What it checks |
| --- | --- |
| `make check` | Lock file, Ruff, formatting, `mypy --strict`, offline tests with sockets blocked, 80% coverage floor |
| `make audit` | Known vulnerabilities in the locked runtime dependencies |
| `make eval-offline` | Golden-topic scoring against the fixture pipeline, no keys |
| `make eval` | The same scoring with live models and search |

A release needs zero dangling citations, 2,000–5,000 words, coverage of at least 0.5, groundedness of at least 0.9, and a hallucination rate of at most 0.05. CI runs the gate on every push. The rules, and what enforces each one, are in [`docs/ENGINEERING.md`](docs/ENGINEERING.md).

---

## Configuration

Settings come from `.env`; environment variables override it.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SEARCH_PROVIDER` | `serpapi` | `serpapi` or `serper`; each has its own key, with no fallback between them |
| `SERPAPI_API_KEY` / `SERPER_API_KEY` | — | Search credentials |
| `OPENROUTER_API_KEY` | — | Model access for all five agents |
| `MODELS__<AGENT>` | `openrouter:deepseek/deepseek-v4.1-flash` | Per-agent model override |
| `CRAWLER_CONTACT` | — | URL or email sent in the crawler's User-Agent |
| `SEARCH_TIMEOUT_SECONDS` | `15` | Per-request search timeout |
| `PAGES` / `PER_PAGE` / `MAX_URLS` | `3` / `10` / `30` | Search budget |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` | off | Hosted traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Metrics export |
| `API_DATABASE`, `API_TOKEN`, `API_RUN_PROFILE` | — | API and worker; see [the walkthrough](https://josoroma.github.io/deep-research-blog-writer/docs/pages/running-a-run.html#api) |

---

## Known limits

- The CLI runs the pipeline as three phase commands. The API worker runs all nine phases in one job.
- The CLI's `--resume` only prints the phase a run would restart at. To continue a run, use `POST /v1/runs/{run_id}/resume`.
- The API and worker have run end to end on real PostgreSQL with fixture providers. A server run with live providers is still pending.
- One worker runs one job at a time. Running more in parallel needs shared crawler rate limits first.

---

## Useful links

| Service | URL |
| --- | --- |
| Live walkthrough | https://josoroma.github.io/deep-research-blog-writer |
| Research API · Swagger UI | http://127.0.0.1:8000 · http://127.0.0.1:8000/docs |
| Grafana · Prometheus | http://127.0.0.1:3001/d/research-runs · http://127.0.0.1:9090 |
| LangSmith | https://smith.langchain.com |
| OpenRouter · SerpApi · Serper | https://openrouter.ai · https://serpapi.com · https://serper.dev |

Local URLs work while `make run-api` or `make observability-up` is running.

## Project docs

- [Live walkthrough](https://josoroma.github.io/deep-research-blog-writer): every command, API request, and real output
- [`docs/ENGINEERING.md`](docs/ENGINEERING.md): the coding standard `make check` enforces
- [`docs/architecture/`](docs/architecture/README.md): each agent's job and contract
- [`docs/adr/`](docs/adr/): architecture decisions 0001–0011
- [`docs/SPECS-LOGS/FASTAPI-MIGRATION-RUNBOOK.md`](docs/SPECS-LOGS/FASTAPI-MIGRATION-RUNBOOK.md): operating the API and worker
