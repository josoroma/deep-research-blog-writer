#!/bin/sh
# Exercise the installed Search milestone and packaged prompts outside the checkout.
set -eu
project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic4-wheel.XXXXXX")
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
from pathlib import Path
import services.search_provider
from evaluations.epic4_demo import run_demo
assert Path(services.search_provider.__file__).is_relative_to(Path(sys.prefix))
result = run_demo(Path("runs"))
assert result["completed_phases"] == ["plan", "search", "normalize"]
assert result["counts"] == {"raw": 50, "denied": 3, "duplicates": 1, "capped": 16, "kept": 30}
assert result["merge_order_verified"] and result["contiguous_clean_ranks"]
assert result["repeated_call_cached"] and result["unplanned_call_rejected"]
workspace = Path(result["workspace"])
assert len(json.loads((workspace / "clean_results.json").read_text())) == 30
print("Installed-wheel Search, actual sub-agent tools/state, packaged prompts, and artifacts passed.")
PY
"$wheel_root/.venv/bin/deep-research-blog" --help
"$wheel_root/.venv/bin/deep-research-blog" "" --search-only >/dev/null 2>&1 && exit 1 || test $? -eq 2
printf 'Installed console script rejected an invalid search topic with exit 2.\n'
