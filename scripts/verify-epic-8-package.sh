#!/bin/sh
# Verify locked installed code/fixtures outside the source checkout.
set -eu
project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic8-wheel.XXXXXX")
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
import services.reporting
from evaluations.epic8_demo import run_demo
assert Path(services.reporting.__file__).is_relative_to(Path(sys.prefix))
report = run_demo(Path("runs"))
assert report["status"] == "degraded"
assert report["exit_status"] == 3
assert report["retry_recovered"]
assert report["checkpoint"]
assert report["outcomes"]
print("Installed-wheel report, classification, retry, and checkpoint checks passed.")
PY
"$wheel_root/.venv/bin/deep-research-blog" --resume missing-run >/dev/null 2>&1 && exit 1 || test $? -eq 2
printf 'Installed console script rejected an unknown run with exit 2.\n'
