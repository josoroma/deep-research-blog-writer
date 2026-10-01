"""Static checks keeping prompts in the catalog and provider clients in services."""

import ast
from dataclasses import dataclass
from pathlib import Path

PROVIDER_MODULES = (
    "langchain_openrouter",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_google_genai",
    "openrouter",
    "openai",
    "anthropic",
)
PROVIDER_CONSTRUCTORS = {
    "ChatOpenRouter",
    "ChatOpenAI",
    "ChatAnthropic",
    "ChatGoogleGenerativeAI",
    "OpenRouter",
    "OpenAI",
    "Anthropic",
    "init_chat_model",
}


@dataclass(frozen=True)
class ArchitectureViolation:
    path: Path
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}"


def _is_inline(node: ast.AST, assignments: dict[str, ast.AST], visited: set[str]) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp):
        return _is_inline(node.left, assignments, visited) or _is_inline(
            node.right, assignments, visited
        )
    if isinstance(node, ast.Name) and node.id in assignments and node.id not in visited:
        return _is_inline(assignments[node.id], assignments, visited | {node.id})
    return False


def find_agent_architecture_violations(root: Path) -> list[ArchitectureViolation]:
    if not root.is_dir():
        raise ValueError(f"Agent directory does not exist: {root}")
    violations: list[ArchitectureViolation] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assignments: dict[str, ast.AST] = {}
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id] = node.value
            elif (
                isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value
            ):
                assignments[node.target.id] = node.value
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
                aliases.update({alias.asname or alias.name: alias.name for alias in node.names})
            else:
                names = []
            for name in names:
                if any(
                    name == module or name.startswith(f"{module}.") for module in PROVIDER_MODULES
                ):
                    assert isinstance(node, ast.Import | ast.ImportFrom)
                    violations.append(
                        ArchitectureViolation(
                            path, node.lineno, f"provider import {name}; use LLMService"
                        )
                    )
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "system_prompt"
                        and _is_inline(value, assignments, set())
                    ):
                        violations.append(
                            ArchitectureViolation(
                                path,
                                node.lineno,
                                "inline system prompt; use prompts.catalog.load_prompt",
                            )
                        )
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg in {"system_prompt", "instructions", "prompt"} and _is_inline(
                    keyword.value, assignments, set()
                ):
                    violations.append(
                        ArchitectureViolation(
                            path,
                            node.lineno,
                            "inline system prompt; use prompts.catalog.load_prompt",
                        )
                    )
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if aliases.get(name, name) in PROVIDER_CONSTRUCTORS:
                violations.append(
                    ArchitectureViolation(
                        path, node.lineno, f"provider construction {name}; use LLMService"
                    )
                )
    return violations
