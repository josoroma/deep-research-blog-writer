#!/bin/sh
# Verify the installed wheel: the console script and the skeleton run outside the checkout.
set -eu

project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic3-wheel.XXXXXX")
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
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import agents.deep_research
import services.workspace
from evaluations.epic3_demo import main
from schemas.config import AGENT_NAMES

for module in (agents.deep_research, services.workspace):
    assert Path(module.__file__).is_relative_to(Path(sys.prefix))
    print(f"Installed module: {module.__name__}")
output = StringIO()
with redirect_stdout(output):
    assert main() == 0
result = json.loads(output.getvalue())
assert result["subagents"] == {
    "search_agent": ["google_search"],
    "research_agent": ["collect_source"],
    "analyst_agent": [],
    "writer_agent": [],
}
assert result["marker_in_model_contexts"] is False
assert result["general_purpose_rejected"] is True
assert result["containment_refused"] is True
assert result["blog_exists"] is True
assert set(result["prompts_loaded"]) == set(AGENT_NAMES)
print("Installed-wheel skeleton, four sub-agents, containment, and demo passed.")
PY
"$wheel_root/.venv/bin/deep-research-blog" "" >/dev/null 2>&1 && exit 1 || test $? -eq 2
printf 'Installed console script rejected an invalid topic with exit 2.\n'
