#!/bin/sh
# Verify locked installed code/fixtures outside the source checkout.
set -eu
project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic7-wheel.XXXXXX")
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
import sys
from pathlib import Path
import services.authoring
from evaluations.epic7_demo import run_demo
assert Path(services.authoring.__file__).is_relative_to(Path(sys.prefix))
report = run_demo(Path("runs"))
assert report["summary_passed"]
assert report["headings_valid"]
assert report["citations_resolved"]
assert report["dangling_detected"] == ["S-31"]
assert report["source_ids"]
print("Installed-wheel authoring checks, citation gate, and repair detection passed.")
PY
"$wheel_root/.venv/bin/deep-research-blog" --help
"$wheel_root/.venv/bin/deep-research-blog" --author-only >/dev/null 2>&1 && exit 1 || test $? -eq 2
printf 'Installed console script rejected missing authoring workspace with exit 2.\n'
