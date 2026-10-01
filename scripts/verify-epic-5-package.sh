#!/bin/sh
# Verify locked installed code/fixtures outside the source checkout.
set -eu
project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic5-wheel.XXXXXX")
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
import services.fetch_service
from evaluations.epic5_demo import run_demo
assert Path(services.fetch_service.__file__).is_relative_to(Path(sys.prefix))
report = run_demo(Path("runs"))
assert report["summary"]["outcomes"] == {
    "extracted": 6, "unreachable": 2, "robots_disallowed": 1,
    "unsupported_content": 1, "too_thin": 1,
}
assert report["thirty_host_probe"]["max_active"] == 5
assert report["raw_html_absent_from_artifacts"]
assert report["no_corpus_files_written"]
state = json.loads((Path(report["workspace"]) / "fetch_state.json").read_text())
assert len(state["url_outcomes"]) == 11
print("Installed-wheel fetch tools, real parsers, packaged fixtures, limits, fallback and artifacts passed.")
PY
"$wheel_root/.venv/bin/deep-research-blog" --help
"$wheel_root/.venv/bin/deep-research-blog" --fetch-only >/dev/null 2>&1 && exit 1 || test $? -eq 2
printf 'Installed console script rejected missing fetch workspace with exit 2.\n'
