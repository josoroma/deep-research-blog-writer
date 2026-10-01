#!/bin/sh
# Check a built wheel from an isolated environment outside the repository.
set -eu

project_root=$(git rev-parse --show-toplevel)
wheel_root=$(mktemp -d "${TMPDIR:-/tmp}/epic1-wheel.XXXXXX")
trap 'rm -rf "$wheel_root"' EXIT HUP INT TERM

uv venv --python 3.12 "$wheel_root/.venv"
uv pip install --python "$wheel_root/.venv/bin/python" --no-deps "$project_root/dist/deep_research_blog_writer-0.1.0-py3-none-any.whl"
cd "$wheel_root"
"$wheel_root/.venv/bin/python" -I - <<'PY'
import importlib
import importlib.metadata
import sys
from pathlib import Path

distribution = importlib.metadata.distribution("deep-research-blog-writer")
files = distribution.files
assert files is not None
assert not any(str(path).startswith(("tests/", "docs/")) for path in files)
for name in ("agents", "tools", "workflows", "prompts", "schemas", "services", "evaluations"):
    package = importlib.import_module(name)
    assert package.__file__ is not None
    assert Path(package.__file__).is_relative_to(Path(sys.prefix))
    print(f"{name}: {package.__file__}")
from evaluations.agent_boundary import FORBIDDEN_MODULES

assert len(FORBIDDEN_MODULES) == 6
print(f"Wheel {distribution.version} installed; all seven packages import outside the checkout.")
print("Tests and documentation are excluded from the application wheel.")
PY
