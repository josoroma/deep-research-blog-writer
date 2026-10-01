#!/bin/sh
# Verify locked runtime dependencies, typed contracts, and packaged prompts outside the checkout.
set -eu

project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic2-wheel.XXXXXX")
trap 'rm -rf "$wheel_root"' EXIT HUP INT TERM

uv export --locked --no-dev --no-editable --no-emit-project --format requirements.txt \
    --output-file "$wheel_root/requirements.txt" >/dev/null
uv venv --python 3.12 "$wheel_root/.venv"
uv pip install --python "$wheel_root/.venv/bin/python" --no-deps \
    --require-hashes -r "$wheel_root/requirements.txt"
uv pip install --python "$wheel_root/.venv/bin/python" --no-deps \
    "$project_root/dist/deep_research_blog_writer-0.1.0-py3-none-any.whl"
cd "$wheel_root"
"$wheel_root/.venv/bin/python" -I - <<'PY'
import importlib.metadata
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import prompts.catalog
import schemas.requests
import services.llm_service
from evaluations.epic2_demo import main
from schemas.config import AGENT_NAMES

for module in (prompts.catalog, schemas.requests, services.llm_service):
    assert Path(module.__file__).is_relative_to(Path(sys.prefix))
    print(f"Installed module: {module.__name__}")
for agent in AGENT_NAMES:
    prompt = prompts.catalog.load_prompt(agent)
    assert prompt.strip()
    print(f"Packaged prompt: {agent} ({len(prompt)} characters)")
output = StringIO()
with redirect_stdout(output):
    assert main() == 0
result = json.loads(output.getvalue())
assert result["checkpoint_restored"] is True
assert result["fake_injection_verified"] is True
assert result["run"]["completed_phases"] == ["search"]
assert len(result["expected_rejections"]) == 4
assert len(result["rejected_agent_patterns"]) == 3
print(f"Wheel version: {importlib.metadata.version('deep-research-blog-writer')}")
print("Installed-wheel contracts, five prompts, ToolNode, and typed checkpoint passed.")
PY
