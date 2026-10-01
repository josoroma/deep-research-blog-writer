"""Enforce SPECS.md PD-001's static HTTP import boundary for agent modules."""

import argparse
import ast
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_MODULES: tuple[str, ...] = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "urllib.request",
    "http.client",
)


@dataclass(frozen=True, slots=True)
class ImportViolation:
    """A forbidden import with enough context to fix the offending module."""

    path: Path
    line: int
    module: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: forbidden HTTP import '{self.module}'"


def _imported_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return tuple(f"{node.module}.{alias.name}" for alias in node.names)
    return ()


def find_forbidden_imports(agents_root: Path) -> list[ImportViolation]:
    """Recursively scan imports, including nested scopes and parent-package imports.

    Missing directories and unparseable modules fail loudly. This is a static import
    check, not a sandbox: computed dynamic imports and indirect calls are outside it.
    """
    if not agents_root.is_dir():
        raise ValueError(f"Agent directory does not exist: {agents_root}")

    violations: list[ImportViolation] = []
    for path in sorted(agents_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                if any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in FORBIDDEN_MODULES
                ):
                    # _imported_modules only produces names for import nodes.
                    assert isinstance(node, ast.Import | ast.ImportFrom)
                    violations.append(ImportViolation(path, node.lineno, module))
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Run the boundary check without importing or executing any agent module."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agents_root", nargs="?", type=Path, default=Path("agents"))
    args = parser.parse_args(argv)
    try:
        violations = find_forbidden_imports(args.agents_root)
    except (OSError, SyntaxError, ValueError) as error:
        print(f"Agent boundary failed: {error}", file=sys.stderr)
        return 1
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1
    print(f"Agent boundary passed: {args.agents_root}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
