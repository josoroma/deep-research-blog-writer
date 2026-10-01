"""Regression coverage for the architectural rule in SPECS.md US-1.3 / PD-001."""

from pathlib import Path

import pytest

from evaluations.agent_boundary import FORBIDDEN_MODULES, find_forbidden_imports, main

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_all_project_agent_modules_respect_boundary() -> None:
    """Future agents, nested packages, and __init__.py are included automatically."""
    violations = find_forbidden_imports(PROJECT_ROOT / "agents")
    assert not violations, "Agents must use tools for external calls:\n" + "\n".join(
        str(violation) for violation in violations
    )


@pytest.mark.parametrize("module", FORBIDDEN_MODULES)
@pytest.mark.parametrize(
    "statement", ["import {module}", "import {module} as client", "from {module} import client"]
)
def test_rejects_every_forbidden_module(tmp_path: Path, module: str, statement: str) -> None:
    agent = tmp_path / "writer.py"
    agent.write_text(statement.format(module=module) + "\n", encoding="utf-8")
    violations = find_forbidden_imports(tmp_path)
    assert len(violations) == 1
    violation = violations[0]
    assert violation.path == agent
    assert violation.line == 1
    assert violation.module == module or violation.module.startswith(f"{module}.")
    assert f"{agent}:1: forbidden HTTP import" in str(violation)


@pytest.mark.parametrize(
    "statement",
    [
        "from urllib import request",
        "from urllib import request as client",
        "from http import client",
        "from http import client as connection",
        "import httpx._client",
        "from urllib.request import urlopen",
        "from requests.sessions import Session",
        "from aiohttp import *",
        "import os, requests, httpx",
        "if False:\n    import requests",
        "def fetch() -> None:\n    import httpx",
    ],
)
def test_rejects_parent_imports_submodules_and_nested_scopes(
    tmp_path: Path, statement: str
) -> None:
    (tmp_path / "agent.py").write_text(statement + "\n", encoding="utf-8")
    assert find_forbidden_imports(tmp_path)


def test_scans_nested_packages_and_package_initializers(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "deeper"
    nested.mkdir(parents=True)
    (tmp_path / "__init__.py").write_text("import requests\n", encoding="utf-8")
    (nested / "worker.py").write_text("import httpx\n", encoding="utf-8")
    violations = find_forbidden_imports(tmp_path)
    assert {violation.path for violation in violations} == {
        tmp_path / "__init__.py",
        nested / "worker.py",
    }


def test_reports_multiple_imports_and_correct_line_numbers(tmp_path: Path) -> None:
    (tmp_path / "agent.py").write_text(
        "import os\nimport requests, httpx\nfrom urllib import request\n", encoding="utf-8"
    )
    violations = find_forbidden_imports(tmp_path)
    assert [(violation.line, violation.module) for violation in violations] == [
        (2, "requests"),
        (2, "httpx"),
        (3, "urllib.request"),
    ]


@pytest.mark.parametrize(
    "statement",
    [
        "import tools, services, schemas",
        "from tools import fetch_url",
        "import urllib.parse",
        "from urllib import parse",
        "from http import HTTPStatus",
        "import requests_cache",
        "from .httpx import local_helper",
        "from . import worker",
        "# import httpx\nDESCRIPTION = 'import requests'",
        '"""Agent module documentation."""',
    ],
)
def test_allows_tools_non_http_stdlib_and_relative_imports(tmp_path: Path, statement: str) -> None:
    (tmp_path / "agent.py").write_text(statement + "\n", encoding="utf-8")
    assert find_forbidden_imports(tmp_path) == []


def test_missing_agent_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Agent directory does not exist"):
        find_forbidden_imports(tmp_path / "missing")


def test_invalid_python_is_not_silently_skipped(tmp_path: Path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("def invalid(\n", encoding="utf-8")
    with pytest.raises(SyntaxError) as error:
        find_forbidden_imports(tmp_path)
    assert error.value.filename == str(path)


def test_cli_succeeds_for_clean_agents(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "clean.py").write_text("from tools import fetch_url\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 0
    assert "Agent boundary passed" in capsys.readouterr().out


def test_cli_names_the_offending_module(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "bad.py"
    path.write_text("import requests\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 1
    assert f"{path}:1: forbidden HTTP import 'requests'" in capsys.readouterr().err


@pytest.mark.parametrize("invalid_syntax", [False, True])
def test_cli_fails_on_scan_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalid_syntax: bool
) -> None:
    root = tmp_path / "agents"
    if invalid_syntax:
        root.mkdir()
        (root / "broken.py").write_text("def invalid(\n", encoding="utf-8")
    assert main([str(root)]) == 1
    assert "Agent boundary failed" in capsys.readouterr().err
