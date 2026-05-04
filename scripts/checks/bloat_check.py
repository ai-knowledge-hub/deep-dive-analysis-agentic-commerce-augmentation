"""Code bloat guardrails.

Fails CI when source files exceed line-count thresholds.
Uses stricter defaults plus explicit per-file overrides for known large modules.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / "Makefile").exists():
            return parent
    return Path.cwd()


ROOT = _repo_root()

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "tmp",
    "__pycache__",
}

DEFAULT_MAX_LINES = {
    ".py": 1200,
    ".ts": 1500,
    ".tsx": 1800,
}

# Known hotspots with tailored caps. This allows current state while blocking growth.
FILE_MAX_LINES = {
    "api/routes/agent_runs.py": 1400,
    "api/routes/agent_runs_commands.py": 320,
    "api/routes/agent_runs_registry.py": 650,
    "tests/test_agent_runs_api.py": 1400,
    "web/app/experiments/page.tsx": 5200,
    "web/app/agent-runs/page.tsx": 2600,
    "web/app/interventions/page.tsx": 460,
    "web/app/admin/page.tsx": 2800,
    "web/components/agent/OperatorConsoleChat.tsx": 520,
    "application/services/experiment/runner.py": 1800,
    "web/lib/types.ts": 1700,
}


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in IGNORE_DIRS for part in rel_parts):
            continue
        if path.suffix not in DEFAULT_MAX_LINES:
            continue
        files.append(path)
    return files


def _line_count(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def main() -> int:
    violations: list[tuple[str, int, int]] = []
    measured: list[tuple[str, int, int]] = []

    for file in _iter_source_files(ROOT):
        rel = file.relative_to(ROOT).as_posix()
        limit = FILE_MAX_LINES.get(rel, DEFAULT_MAX_LINES[file.suffix])
        lines = _line_count(file)
        measured.append((rel, lines, limit))
        if lines > limit:
            violations.append((rel, lines, limit))

    measured.sort(key=lambda item: item[1], reverse=True)

    print("Bloat check summary (top 10 by lines):")
    for rel, lines, limit in measured[:10]:
        print(f"- {rel}: {lines} lines (limit {limit})")

    if violations:
        print("\nBloat check failed:", file=sys.stderr)
        for rel, lines, limit in sorted(violations):
            print(
                f"- {rel}: {lines} lines exceeds limit {limit} by {lines - limit}",
                file=sys.stderr,
            )
        return 1

    print("\nBloat check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
