UV ?= uv

.PHONY: help setup lint format format-check typecheck test boundary hooks check demo build demo-epic-2 smoke-epic-2 demo-epic-3 demo-epic-4 smoke-epic-4 demo-epic-5 smoke-epic-5 demo-epic-6 smoke-epic-6 demo-epic-7 demo-epic-8 demo-epic-9 demo-epic-10 migrate-api run-api worker-api demo-api api-up api-down

help:
	@printf '%s\n' 'demo-api     Run the isolated fixture acceptance demo for the HTTP API' 'run-api      Serve the FastAPI app on 127.0.0.1:8000' 'worker-api   Run the research worker against the configured database' 'migrate-api  Apply server SQL migrations and prepare checkpoints'
	@printf '%s\n' 'demo-epic-9  Verify actual run logs, local SDK traces and OTLP protobuf delivery' 'observability-up Start the local Collector, Prometheus and Grafana stack' 'smoke-epic-9 Query actual run metrics and the provisioned Grafana dashboard' 'observability-down Stop the stack and retain named volumes' 'smoke-langsmith Verify a hosted trace with local LangSmith credentials'
	@printf '%s\n' 'demo-epic-5  Demonstrate fetch policy and actual parsers with offline fixtures' 'smoke-epic-5 Fetch and extract one live public page using CRAWLER_CONTACT' 'demo-epic-6  Collect immutable sources and index them from offline fixtures' 'smoke-epic-6 Collect one live public page into a source file using CRAWLER_CONTACT'
	@printf '%s\n' 'setup        Install locked dependencies and Git hooks' 'check        Verify lock, lint, formatting, strict typing, tests and coverage' 'demo         Show installed dependencies and run the foundation checks' 'demo-epic-2  Demonstrate contracts, tools, prompts, and checkpoint restoration offline' 'smoke-epic-2 Verify one live production-model tool call using OPENROUTER_API_KEY' 'demo-epic-3  Run the deep agent skeleton end to end offline and print acceptance facts' 'demo-epic-4  Run Search through real agent tools offline; save inspectable artifacts' 'smoke-epic-4 Check one live page-2 request using the selected search provider' 'boundary     Check the agent HTTP import boundary' 'hooks        Run all pre-commit hooks' 'format       Format Python files' 'build        Build wheel and source distribution'

setup:
	$(UV) sync --locked
	$(UV) run --locked pre-commit install

lint:
	$(UV) run --locked ruff check .

format:
	$(UV) run --locked ruff format .

format-check:
	$(UV) run --locked ruff format --check .

typecheck:
	$(UV) run --locked mypy --strict

test:
	$(UV) run --locked pytest

boundary:
	$(UV) run --locked python -m evaluations.agent_boundary agents

hooks:
	$(UV) run --locked pre-commit run --all-files

check:
	$(UV) lock --check
	$(MAKE) lint format-check typecheck test

demo:
	$(UV) run --locked python -c 'import sys; from importlib.metadata import version; import agents, tools, workflows, prompts, schemas, services, evaluations; import api, application, workers; import langchain, langgraph, deepagents, langchain_openrouter, pydantic; print("Python:", sys.version.split()[0]); [print(name + ": " + version(name)) for name in ("langchain", "langgraph", "deepagents", "langchain-openrouter", "pydantic")]; print("Foundation packages and dependencies import successfully.")'
	$(MAKE) boundary check

build:
	$(UV) build

demo-epic-2:
	$(UV) run --locked python -m evaluations.epic2_demo

smoke-epic-2:
	$(UV) run --locked python -m evaluations.live_smoke

demo-epic-3:
	$(UV) run --locked python -m evaluations.epic3_demo

demo-epic-4:
	$(UV) run --locked python -m evaluations.epic4_demo

smoke-epic-4:
	$(UV) run --locked python -m evaluations.search_live_smoke

demo-epic-5:
	$(UV) run --locked python -m evaluations.epic5_demo

smoke-epic-5:
	$(UV) run --locked python -m evaluations.fetch_live_smoke

demo-epic-6:
	$(UV) run --locked python -m evaluations.epic6_demo

demo-epic-7:
	$(UV) run --locked python -m evaluations.epic7_demo

demo-epic-8:
	$(UV) run --locked python -m evaluations.epic8_demo

smoke-epic-6:
	$(UV) run --locked python -m evaluations.corpus_live_smoke

# EPIC-9: local integration checks are explicit, outside offline pytest.
.PHONY: demo-epic-9 smoke-epic-9 observability-up observability-down smoke-langsmith
demo-epic-9:
	$(UV) run --locked python -m evaluations.epic9_demo

observability-up:
	docker compose -f ops/observability/compose.yaml up -d

observability-down:
	docker compose -f ops/observability/compose.yaml down

smoke-epic-9:
	$(UV) run --locked python -m evaluations.observability_stack_smoke

smoke-langsmith:
	$(UV) run --locked python -m evaluations.langsmith_live_smoke

# EPIC-10: evaluation and release gate. `eval` is live; `eval-offline` needs no keys.
.PHONY: eval eval-offline release demo-epic-10
eval:
	$(UV) run --locked python -m evaluations.run_eval

eval-offline:
	$(UV) run --locked python -m evaluations.run_eval --offline

demo-epic-10:
	$(UV) run --locked python -m evaluations.epic10_demo

# FastAPI migration (M1-M6). API and worker share the run workspace root.
.PHONY: migrate-api run-api worker-api demo-api api-up api-down
migrate-api:
	$(UV) run --locked python -m application.migrations

run-api:
	$(UV) run --locked uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000

worker-api:
	$(UV) run --locked python -m workers.research_worker

demo-api:
	$(UV) run --locked python -m evaluations.api_fixture_demo

api-up:
	docker compose -f ops/api/compose.yaml up -d postgres

api-down:
	docker compose -f ops/api/compose.yaml down

release:
	@test -n "$(VERSION)" || { printf '%s\n' 'Usage: make release VERSION=x.y.z'; exit 2; }
	$(UV) run --locked python -m evaluations.release --version "$(VERSION)"
