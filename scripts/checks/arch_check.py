"""Lightweight architecture boundary checks.

This repository is mid-migration to a Clean Architecture layout:

- `domain/` must remain pure (no imports from api/app/infra/shared/llm/web).
- `infrastructure/` must not depend on `application/` or `api/`.

We keep this check intentionally small and dependency-free so it can run in CI.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / "Makefile").exists():
            return parent
    return Path.cwd()


ROOT = _repo_root()

DOMAIN_FORBIDDEN = {"api", "application", "infrastructure", "shared", "llm", "web"}
INFRA_FORBIDDEN = {"api", "application"}
APP_FORBIDDEN = {"api", "infrastructure", "web"}
COMMAND_ROUTE_PATH = Path("api/routes/agent_runs_commands.py")
COMMAND_ROUTE_FORBIDDEN_MODULES = {
    "application.services.agent_runtime.commands.preflight",
    "application.services.agent_runtime.commands.recovery",
}
COMMAND_ROUTE_FORBIDDEN_NAMES = {
    "application.services.agent_runtime.commands": {
        "_command_preflight",
        "_record_command_event",
        "apply_command_action_decision",
        "create_change_plan_recovery_action",
        "create_retry_action",
    },
    "application.services.agent_runtime.commands.decisions": {
        "apply_command_action_decision",
    },
}


def _iter_py_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if path.name == "__pycache__":
            continue
        if "/.venv/" in str(path) or "/.git/" in str(path):
            continue
        files.append(path)
    return files


def _top_level_modules(node: ast.AST) -> set[str]:
    tops: set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            name = alias.name.split(".", 1)[0]
            tops.add(name)
        return tops
    if isinstance(node, ast.ImportFrom):
        if node.level and node.level > 0:
            return tops
        if not node.module:
            return tops
        tops.add(node.module.split(".", 1)[0])
        return tops
    return tops


def _collect_imports(tree: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.update(_top_level_modules(node))
    return imports


def _check_domain(file: Path) -> list[str]:
    rel = file.relative_to(ROOT)
    if rel.parts[0] != "domain":
        return []
    tree = ast.parse(file.read_text(encoding="utf-8"))
    imports = _collect_imports(tree)
    bad = sorted(imports & DOMAIN_FORBIDDEN)
    if not bad:
        return []
    return [f"{rel}: domain imports forbidden module(s): {', '.join(bad)}"]


def _check_infrastructure(file: Path) -> list[str]:
    rel = file.relative_to(ROOT)
    if rel.parts[0] != "infrastructure":
        return []
    tree = ast.parse(file.read_text(encoding="utf-8"))
    imports = _collect_imports(tree)
    bad = sorted(imports & INFRA_FORBIDDEN)
    if not bad:
        return []
    return [f"{rel}: infrastructure imports forbidden module(s): {', '.join(bad)}"]


def _check_application(file: Path) -> list[str]:
    rel = file.relative_to(ROOT)
    if rel.parts[0] != "application":
        return []
    tree = ast.parse(file.read_text(encoding="utf-8"))
    imports = _collect_imports(tree)
    bad = sorted(imports & APP_FORBIDDEN)
    if not bad:
        return []
    return [f"{rel}: application imports forbidden module(s): {', '.join(bad)}"]


def _check_command_route_boundary(file: Path) -> list[str]:
    rel = file.relative_to(ROOT)
    if rel != COMMAND_ROUTE_PATH:
        return []
    tree = ast.parse(file.read_text(encoding="utf-8"))
    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        module = node.module or ""
        if module in COMMAND_ROUTE_FORBIDDEN_MODULES:
            errors.append(
                f"{rel}: command routes must use commands.service, not {module}"
            )
            continue
        forbidden_names = COMMAND_ROUTE_FORBIDDEN_NAMES.get(module, set())
        bad_names = sorted(
            alias.name for alias in node.names if alias.name in forbidden_names
        )
        if bad_names:
            errors.append(
                f"{rel}: command routes must not import service internals from "
                f"{module}: {', '.join(bad_names)}"
            )
    return errors


def main() -> int:
    errors: list[str] = []
    for file in _iter_py_files(ROOT):
        errors.extend(_check_domain(file))
        errors.extend(_check_infrastructure(file))
        errors.extend(_check_application(file))
        errors.extend(_check_command_route_boundary(file))

    if errors:
        print("Architecture check failed:\n", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("Architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
