#!/bin/sh
# Demonstrate rejection paths in a temporary local clone, leaving the source untouched.
set -eu

project_root=$(git rev-parse --show-toplevel)
demo_root=$(mktemp -d "${TMPDIR:-/tmp}/epic1-gates.XXXXXX")
trap 'rm -rf "$demo_root"' EXIT HUP INT TERM

run() {
    printf '\n$ %s\n' "$*"
    "$@"
}

expect_rejection() {
    printf '\n$ %s\n' "$*"
    set +e
    "$@"
    probe_status=$?
    set -e
    if [ "$probe_status" -ne 1 ]; then
        printf 'ERROR: expected rejection with exit 1, received %s\n' "$probe_status" >&2
        exit 1
    fi
    printf 'EXPECTED REJECTION: exit 1\n'
}

run git clone --local --no-hardlinks --quiet "$project_root" "$demo_root/project"
cd "$demo_root/project"
run uv sync --locked
run uv run --locked pre-commit install

printf 'import os\n' > agents/demo_lint.py
expect_rejection uv run --locked ruff check agents/demo_lint.py
run git add agents/demo_lint.py
expect_rejection git -c user.name=EPIC-1-Demo -c user.email=epic-1@example.invalid -c commit.gpgsign=false commit -m 'Demo: lint must reject this commit'
run git restore --staged agents/demo_lint.py
rm agents/demo_lint.py

printf 'value: int=1\n' > agents/demo_format.py
expect_rejection uv run --locked ruff format --check agents/demo_format.py
rm agents/demo_format.py

cat > agents/demo_untyped.py <<'PY'
def untyped(value):
    return value
PY
expect_rejection uv run --locked mypy --strict
run git add agents/demo_untyped.py
expect_rejection git -c user.name=EPIC-1-Demo -c user.email=epic-1@example.invalid -c commit.gpgsign=false commit -m 'Demo: typing must reject this commit'
run git restore --staged agents/demo_untyped.py
rm agents/demo_untyped.py

mkdir -p agents/demo_nested
cat > agents/demo_nested/bad_agent.py <<'PY'
import httpx

__all__ = ["httpx"]
PY
expect_rejection uv run --locked python -m evaluations.agent_boundary agents
expect_rejection uv run --locked pytest -q --no-cov tests/test_agent_boundary.py::test_all_project_agent_modules_respect_boundary
run git add agents/demo_nested/bad_agent.py
expect_rejection git -c user.name=EPIC-1-Demo -c user.email=epic-1@example.invalid -c commit.gpgsign=false commit -m 'Demo: agent boundary must reject this commit'
run git restore --staged agents/demo_nested/bad_agent.py
rm agents/demo_nested/bad_agent.py
rmdir agents/demo_nested

# Unexecuted application code must count against the real configured coverage floor.
uv run --locked python - <<'PY'
from pathlib import Path

Path("services/demo_uncovered.py").write_text(
    "\n\n".join(f"def unused_{number}() -> int:\n    return {number}" for number in range(200)) + "\n",
    encoding="utf-8",
)
PY
expect_rejection uv run --locked pytest -q
rm services/demo_uncovered.py

run make check
run make hooks
run git diff --exit-code HEAD
printf '\nAll rejection probes passed; the disposable checkout is restored.\n'
