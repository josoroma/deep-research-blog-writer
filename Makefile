UV ?= uv

.PHONY: help setup lint format format-check typecheck test boundary hooks check demo build

help:
	@printf '%s\n' 'setup        Install locked dependencies and Git hooks' 'check        Verify lock, lint, formatting, strict typing, tests and coverage' 'demo         Show installed dependencies and run the foundation checks' 'boundary     Check the agent HTTP import boundary' 'hooks        Run all pre-commit hooks' 'format       Format Python files' 'build        Build wheel and source distribution'

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
	$(UV) run --locked python -c 'import sys; from importlib.metadata import version; import agents, tools, workflows, prompts, schemas, services, evaluations; import langchain, langgraph, deepagents, langchain_openrouter, pydantic; print("Python:", sys.version.split()[0]); [print(name + ": " + version(name)) for name in ("langchain", "langgraph", "deepagents", "langchain-openrouter", "pydantic")]; print("Foundation packages and dependencies import successfully.")'
	$(MAKE) boundary check

build:
	$(UV) build
