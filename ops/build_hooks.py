"""Build hook: copy the operator SQL migrations beside the packaged module.

The canonical migrations live in ``ops/api/migrations/``. Operators read and may
apply them directly, but an installed wheel cannot reach outside its package, so
the same files are copied into ``application/_migrations/`` at build time and at
import time for editable installs that omit them.
"""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _copy(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob("*.sql")):
        (destination / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


class MigrationsBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        del version
        root = Path(self.root)
        _copy(root / "ops" / "api" / "migrations", root / "application" / "_migrations")
        force = build_data.get("force_include")
        if not isinstance(force, dict):
            force = {}
            build_data["force_include"] = force
        for path in sorted((root / "application" / "_migrations").glob("*.sql")):
            force[str(path)] = f"application/_migrations/{path.name}"
