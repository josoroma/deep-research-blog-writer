#!/bin/sh
# Verify the installed wheel runs the EPIC-10 evaluation path outside the checkout.
set -eu
project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic10-wheel.XXXXXX")
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

import evaluations.scoring
from evaluations.epic10_demo import run_demo
from evaluations.judge import AlwaysSupportedJudge
from evaluations.offline_eval import fixture_topic, run_offline_topic
from evaluations.run_eval import score_workspace

assert Path(evaluations.scoring.__file__).is_relative_to(Path(sys.prefix))
topic = fixture_topic()
workspace = run_offline_topic(topic, Path("runs"))
score = score_workspace(workspace, topic, AlwaysSupportedJudge())
assert score.passed, score.failures
assert score.coverage == 1.0
assert score.definition_of_done.passed
summary = run_demo(Path("demo-runs"))
assert summary["passed"] is True
assert summary["release_passing_tagged"] is True
assert summary["release_blocked_failures"]
print("Installed-wheel scoring, Definition of Done, and release gate passed.")
PY
printf 'Installed-wheel EPIC-10 evaluation checks passed.\n'
