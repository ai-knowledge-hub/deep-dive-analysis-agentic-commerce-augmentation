"""Static architecture and complexity guardrails.

This repository is mid-migration to a Clean Architecture layout:

- `domain/` must remain pure.
- `application/` must not depend on API, infrastructure, or web.
- `infrastructure/` must not depend on application or API.

The checker is intentionally dependency-free so it can run in CI.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / "Makefile").exists():
            return parent
    return Path.cwd()


ROOT = _repo_root()

SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "tmp",
    "venv",
    "web",
}
SOURCE_ROOTS = {"api", "application", "domain", "infrastructure", "scripts", "shared"}
INTERNAL_ROOTS = SOURCE_ROOTS | {"tests"}

DOMAIN_FORBIDDEN = {
    "api",
    "application",
    "fastapi",
    "infrastructure",
    "llm",
    "pydantic_settings",
    "requests",
    "shared",
    "sqlalchemy",
    "web",
}
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

# Known complexity hotspots with tailored caps. These preserve current behavior
# while blocking additional growth in the same functions.
FUNCTION_MAX_COMPLEXITY = {
    ("application/services/agent_runtime/capabilities/executor.py", "execute_capability"): 181,
    ("application/services/agent_runtime/commands/preflight.py", "_command_preflight"): 86,
    ("application/services/experiment/runner.py", "run_experiment"): 56,
    (
        "application/services/experiment/runner.py",
        "_build_and_apply_decision_policy",
    ): 48,
}


@dataclass(frozen=True)
class ArchitectureViolation:
    path: Path
    line: int
    rule: str
    import_name: str
    message: str

    def format(self, root: Path) -> str:
        return (
            f"{_display_path(self.path, root)}:{self.line}: {self.rule}: "
            f"{self.message} ({self.import_name})"
        )


@dataclass(frozen=True)
class ImportRecord:
    path: Path
    line: int
    module: str
    symbol: str | None = None

    @property
    def import_name(self) -> str:
        if self.symbol and self.symbol != "*":
            return f"{self.module}.{self.symbol}"
        return self.module


@dataclass(frozen=True)
class ComplexityFinding:
    path: Path
    line: int
    name: str
    score: int

    def format(self, root: Path) -> str:
        return f"{_display_path(self.path, root)}:{self.line}: {self.name} complexity={self.score}"


@dataclass(frozen=True)
class ThresholdViolation:
    rule: str
    value: int
    limit: int
    location: str
    message: str

    def format(self) -> str:
        return (
            f"{self.rule}: {self.message} "
            f"value={self.value} limit={self.limit} location={self.location}"
        )


@dataclass(frozen=True)
class ArchitectureReport:
    violations: list[ArchitectureViolation]
    complex_functions: list[ComplexityFinding]
    top_complex_functions: list[ComplexityFinding]
    import_cycles: list[tuple[str, ...]]
    max_dependency_depth: int
    max_dependency_depth_module: str
    top_dependency_depths: list[tuple[str, int]]
    max_internal_imports: int
    max_internal_imports_path: Path | None
    top_internal_imports: list[tuple[Path, int]]


def _iter_py_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIPPED_DIRS for part in rel_parts):
            continue
        if rel_parts and rel_parts[0] in SOURCE_ROOTS:
            files.append(path)
    return files


def collect_imports(path: Path, *, root: Path) -> list[ImportRecord]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [
            ImportRecord(
                path=path,
                line=exc.lineno or 1,
                module="<syntax-error>",
            )
        ]
    return _collect_imports_from_statements(tree.body, path=path, root=root)


def _collect_imports_from_statements(
    statements: Sequence[ast.stmt],
    *,
    path: Path,
    root: Path,
) -> list[ImportRecord]:
    imports: list[ImportRecord] = []
    for node in statements:
        if isinstance(node, ast.Import):
            imports.extend(
                ImportRecord(path=path, line=node.lineno, module=alias.name)
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_import_from_module(path, root, node)
            imports.extend(
                ImportRecord(path=path, line=node.lineno, module=module, symbol=alias.name)
                for alias in node.names
            )
        elif isinstance(node, ast.If) and _is_type_checking_guard(node.test):
            imports.extend(
                _collect_imports_from_statements(node.orelse, path=path, root=root)
            )
        else:
            imports.extend(_collect_imports_from_child_statements(node, path=path, root=root))
    return imports


def _collect_imports_from_child_statements(
    node: ast.AST,
    *,
    path: Path,
    root: Path,
) -> list[ImportRecord]:
    imports: list[ImportRecord] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt):
            imports.extend(_collect_imports_from_statements([child], path=path, root=root))
    return imports


def _resolve_import_from_module(path: Path, root: Path, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""

    current_module = _module_name_for_path(path, root)
    package_parts = current_module.split(".")
    if path.name != "__init__.py":
        package_parts = package_parts[:-1]

    base_length = len(package_parts) - node.level + 1
    if base_length < 0:
        return node.module or ""

    relative_parts = node.module.split(".") if node.module else []
    return ".".join([*package_parts[:base_length], *relative_parts])


def _is_type_checking_guard(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    return False


def check_architecture(root: Path = ROOT) -> list[ArchitectureViolation]:
    return build_architecture_report(root).violations


def build_architecture_report(
    root: Path = ROOT,
    *,
    max_complexity: int = 45,
) -> ArchitectureReport:
    violations: list[ArchitectureViolation] = []
    complex_functions: list[ComplexityFinding] = []
    function_complexities: list[ComplexityFinding] = []
    internal_import_counts: dict[Path, int] = {}
    imports_by_module: dict[str, set[str]] = {}
    module_by_path: dict[Path, str] = {}

    for file in _iter_py_files(root):
        module_by_path[file] = _module_name_for_path(file, root)
        imports = collect_imports(file, root=root)
        internal_import_counts[file] = len(
            {
                import_record.module
                for import_record in imports
                if _is_internal_module(import_record.module)
            }
        )
        for import_record in imports:
            violations.extend(_check_import(root, import_record))
        imports_by_module[module_by_path[file]] = {
            import_record.module
            for import_record in imports
            if _is_internal_module(import_record.module)
        }
        file_complexities = _function_complexities(file)
        function_complexities.extend(file_complexities)
        complex_functions.extend(
            finding
            for finding in file_complexities
            if finding.score > _complexity_limit(finding, root, max_complexity)
        )

    graph = _build_internal_import_graph(imports_by_module)
    dependency_depths = _dependency_depths(graph)
    max_depth_module, max_depth = _max_dependency_depth(dependency_depths)
    max_import_path, max_imports = _max_internal_import_count(internal_import_counts)

    return ArchitectureReport(
        violations=violations,
        complex_functions=complex_functions,
        top_complex_functions=_top_complex_functions(function_complexities),
        import_cycles=_find_import_cycles(graph),
        max_dependency_depth=max_depth,
        max_dependency_depth_module=max_depth_module,
        top_dependency_depths=_top_dependency_depths(dependency_depths),
        max_internal_imports=max_imports,
        max_internal_imports_path=max_import_path,
        top_internal_imports=_top_internal_imports(internal_import_counts),
    )


def threshold_violations(
    report: ArchitectureReport,
    *,
    root: Path,
    max_internal_imports: int,
    max_dependency_depth: int,
) -> list[ThresholdViolation]:
    violations: list[ThresholdViolation] = []
    if report.max_internal_imports > max_internal_imports:
        violations.append(
            ThresholdViolation(
                rule="max-internal-imports",
                value=report.max_internal_imports,
                limit=max_internal_imports,
                location=_display_path(report.max_internal_imports_path, root),
                message="File has too many internal imports",
            )
        )
    if report.max_dependency_depth > max_dependency_depth:
        violations.append(
            ThresholdViolation(
                rule="max-dependency-depth",
                value=report.max_dependency_depth,
                limit=max_dependency_depth,
                location=report.max_dependency_depth_module,
                message="Internal import graph is too deep",
            )
        )
    return violations


def architecture_report_payload(
    report: ArchitectureReport,
    *,
    root: Path,
    max_complexity: int,
    max_internal_imports: int,
    max_dependency_depth: int,
    coupling_violations: Sequence[ThresholdViolation],
) -> dict[str, object]:
    return {
        "metrics": {
            "max_internal_imports": {
                "value": report.max_internal_imports,
                "limit": max_internal_imports,
                "path": _display_path(report.max_internal_imports_path, root),
            },
            "max_dependency_depth": {
                "value": report.max_dependency_depth,
                "limit": max_dependency_depth,
                "module": report.max_dependency_depth_module,
            },
            "complexity": {
                "threshold": max_complexity,
                "violations": len(report.complex_functions),
            },
            "import_cycles": {"violations": len(report.import_cycles)},
        },
        "hotspots": {
            "internal_imports": [
                {"path": _display_path(path, root), "count": count}
                for path, count in report.top_internal_imports
            ],
            "dependency_depths": [
                {"module": module, "depth": depth}
                for module, depth in report.top_dependency_depths
            ],
            "complexity": [
                {
                    "path": _display_path(finding.path, root),
                    "line": finding.line,
                    "name": finding.name,
                    "score": finding.score,
                }
                for finding in report.top_complex_functions
            ],
        },
        "violations": {
            "boundaries": [
                {
                    "path": _display_path(violation.path, root),
                    "line": violation.line,
                    "rule": violation.rule,
                    "import_name": violation.import_name,
                    "message": violation.message,
                }
                for violation in report.violations
            ],
            "thresholds": [
                {
                    "rule": violation.rule,
                    "value": violation.value,
                    "limit": violation.limit,
                    "location": violation.location,
                    "message": violation.message,
                }
                for violation in coupling_violations
            ],
            "complexity": [
                {
                    "path": _display_path(finding.path, root),
                    "line": finding.line,
                    "name": finding.name,
                    "score": finding.score,
                }
                for finding in report.complex_functions
            ],
            "cycles": [list(cycle) for cycle in report.import_cycles],
        },
    }


def write_architecture_report_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_import(root: Path, import_record: ImportRecord) -> list[ArchitectureViolation]:
    rel = import_record.path.relative_to(root)
    top = rel.parts[0]
    module = import_record.module
    violations: list[ArchitectureViolation] = []

    if module == "<syntax-error>":
        return [
            _violation(
                import_record,
                "python-syntax",
                "File could not be parsed for architecture checks",
            )
        ]

    if top == "domain" and _matches_import(import_record, tuple(DOMAIN_FORBIDDEN)):
        violations.append(
            _violation(
                import_record,
                "domain-boundary",
                "Domain code must not import application, infrastructure, shared, API, web, or framework modules",
            )
        )
    if top == "infrastructure" and _matches_import(import_record, tuple(INFRA_FORBIDDEN)):
        violations.append(
            _violation(
                import_record,
                "infrastructure-boundary",
                "Infrastructure code must not import API or application modules",
            )
        )
    if top == "application" and _matches_import(import_record, tuple(APP_FORBIDDEN)):
        violations.append(
            _violation(
                import_record,
                "application-boundary",
                "Application code must not import API, infrastructure, or web modules",
            )
        )
    if top in SOURCE_ROOTS and _matches_import(import_record, ("tests",)):
        violations.append(
            _violation(
                import_record,
                "production-test-boundary",
                "Production code must not import test modules",
            )
        )
    violations.extend(_check_command_route_boundary(root, import_record))
    return violations


def _check_command_route_boundary(
    root: Path,
    import_record: ImportRecord,
) -> list[ArchitectureViolation]:
    rel = import_record.path.relative_to(root)
    if rel != COMMAND_ROUTE_PATH:
        return []
    if import_record.module in COMMAND_ROUTE_FORBIDDEN_MODULES:
        return [
            _violation(
                import_record,
                "command-route-boundary",
                f"Command routes must use commands.service, not {import_record.module}",
            )
        ]
    forbidden_names = COMMAND_ROUTE_FORBIDDEN_NAMES.get(import_record.module, set())
    if import_record.symbol in forbidden_names:
        return [
            _violation(
                import_record,
                "command-route-boundary",
                f"Command routes must not import service internals from {import_record.module}",
            )
        ]
    return []


def _function_complexities(path: Path) -> list[ComplexityFinding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []

    findings: list[ComplexityFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        findings.append(
            ComplexityFinding(
                path=path,
                line=node.lineno,
                name=node.name,
                score=_cyclomatic_complexity(node),
            )
        )
    return findings


def _cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.Assert,
                ast.AsyncFor,
                ast.AsyncWith,
                ast.ExceptHandler,
                ast.For,
                ast.If,
                ast.IfExp,
                ast.Match,
                ast.While,
                ast.With,
            ),
        ):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(0, len(child.values) - 1)
    return score


def _build_internal_import_graph(imports_by_module: Mapping[str, set[str]]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    known_modules = set(imports_by_module)
    for module, imports in imports_by_module.items():
        graph[module] = set()
        for import_name in imports:
            resolved = _resolve_known_module(import_name, known_modules)
            if resolved and resolved != module:
                graph[module].add(resolved)
    return graph


def _resolve_known_module(import_name: str, known_modules: set[str]) -> str | None:
    parts = import_name.split(".")
    while parts:
        candidate = ".".join(parts)
        if candidate in known_modules:
            return candidate
        parts.pop()
    return None


def _dependency_depths(graph: Mapping[str, set[str]]) -> dict[str, int]:
    cache: dict[str, int] = {}

    def depth(module: str, stack: tuple[str, ...] = ()) -> int:
        if module in stack:
            return 0
        if module in cache:
            return cache[module]
        value = 1 + max(
            (depth(child, (*stack, module)) for child in graph.get(module, set())),
            default=0,
        )
        cache[module] = value
        return value

    return {module: depth(module) for module in graph}


def _find_import_cycles(graph: Mapping[str, set[str]]) -> list[tuple[str, ...]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(module: str) -> None:
        if module in visiting:
            cycle = stack[stack.index(module) :] + [module]
            cycles.add(_canonical_cycle(cycle))
            return
        if module in visited:
            return

        visiting.add(module)
        stack.append(module)
        for child in sorted(graph.get(module, set())):
            visit(child)
        stack.pop()
        visiting.remove(module)
        visited.add(module)

    for module in sorted(graph):
        visit(module)
    return sorted(cycles)


def _canonical_cycle(cycle: Sequence[str]) -> tuple[str, ...]:
    if len(cycle) <= 2:
        return tuple(cycle)
    nodes = list(cycle[:-1])
    rotations = [nodes[index:] + nodes[:index] for index in range(len(nodes))]
    canonical = min(rotations)
    return tuple([*canonical, canonical[0]])


def _module_name_for_path(path: Path, root: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def _max_dependency_depth(depths: Mapping[str, int]) -> tuple[str, int]:
    if not depths:
        return "", 0
    return max(depths.items(), key=lambda item: item[1])


def _top_dependency_depths(depths: Mapping[str, int]) -> list[tuple[str, int]]:
    return sorted(depths.items(), key=lambda item: (-item[1], item[0]))[:10]


def _max_internal_import_count(counts: Mapping[Path, int]) -> tuple[Path | None, int]:
    if not counts:
        return None, 0
    return max(counts.items(), key=lambda item: item[1])


def _top_internal_imports(counts: Mapping[Path, int]) -> list[tuple[Path, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0].as_posix()))[:10]


def _top_complex_functions(complexities: Sequence[ComplexityFinding]) -> list[ComplexityFinding]:
    return sorted(
        complexities,
        key=lambda finding: (
            -finding.score,
            finding.path.as_posix(),
            finding.line,
            finding.name,
        ),
    )[:10]


def _complexity_limit(
    finding: ComplexityFinding,
    root: Path,
    default_limit: int,
) -> int:
    key = (_display_path(finding.path, root), finding.name)
    return FUNCTION_MAX_COMPLEXITY.get(key, default_limit)


def _is_internal_module(module: str) -> bool:
    return _matches_any(module, tuple(INTERNAL_ROOTS))


def _matches_import(import_record: ImportRecord, prefixes: Sequence[str]) -> bool:
    if _matches_any(import_record.module, prefixes):
        return True
    if import_record.symbol and import_record.symbol != "*":
        return _matches_any(import_record.import_name, prefixes)
    return False


def _matches_any(module: str, prefixes: Sequence[str]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _violation(import_record: ImportRecord, rule: str, message: str) -> ArchitectureViolation:
    return ArchitectureViolation(
        path=import_record.path,
        line=import_record.line,
        rule=rule,
        import_name=import_record.import_name,
        message=message,
    )


def _display_path(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to scan")
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=45,
        help="Maximum allowed per-function cyclomatic complexity",
    )
    parser.add_argument(
        "--max-internal-imports",
        type=int,
        default=48,
        help="Maximum allowed internal imports in one file",
    )
    parser.add_argument(
        "--max-dependency-depth",
        type=int,
        default=9,
        help="Maximum allowed internal import graph depth",
    )
    parser.add_argument("--report-json", help="Optional path for a JSON report")
    args = parser.parse_args([] if argv is None else list(argv))

    root = Path(args.root).resolve()
    report = build_architecture_report(root, max_complexity=args.max_complexity)
    coupling_violations = threshold_violations(
        report,
        root=root,
        max_internal_imports=args.max_internal_imports,
        max_dependency_depth=args.max_dependency_depth,
    )
    payload = architecture_report_payload(
        report,
        root=root,
        max_complexity=args.max_complexity,
        max_internal_imports=args.max_internal_imports,
        max_dependency_depth=args.max_dependency_depth,
        coupling_violations=coupling_violations,
    )
    if args.report_json:
        write_architecture_report_json(Path(args.report_json), payload)

    print("Architecture hygiene report:")
    print(
        "- max_internal_imports="
        f"{report.max_internal_imports} "
        f"limit={args.max_internal_imports} "
        f"file={_display_path(report.max_internal_imports_path, root)}"
    )
    print(
        "- max_dependency_depth="
        f"{report.max_dependency_depth} "
        f"limit={args.max_dependency_depth} "
        f"module={report.max_dependency_depth_module}"
    )
    print(f"- complexity_threshold={args.max_complexity} violations={len(report.complex_functions)}")
    print(f"- import_cycles={len(report.import_cycles)}")

    if report.violations:
        print("Architecture boundary violations found:", file=sys.stderr)
        for violation in report.violations:
            print(f"- {violation.format(root)}", file=sys.stderr)
        return 1
    if report.import_cycles:
        print("Internal import cycles found:", file=sys.stderr)
        for cycle in report.import_cycles:
            print(f"- {' -> '.join(cycle)}", file=sys.stderr)
        return 1
    if coupling_violations:
        print("Coupling/dependency threshold violations found:", file=sys.stderr)
        for violation in coupling_violations:
            print(f"- {violation.format()}", file=sys.stderr)
        return 1
    if report.complex_functions:
        print("Complexity violations found:", file=sys.stderr)
        for finding in report.complex_functions:
            print(f"- {finding.format(root)}", file=sys.stderr)
        return 1

    print("Architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
