"""Validate canonical script entrypoint layout.

Executable script implementations should live under a purpose-specific package:
`scripts.checks`, `scripts.seed`, or `scripts.ops`. Root-level script modules
make the command surface ambiguous and tend to become stale compatibility
wrappers.
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
ALLOWED_ROOT_SCRIPT_FILES = {"__init__.py"}


def main() -> int:
    scripts_dir = ROOT / "scripts"
    unexpected = sorted(
        path.relative_to(ROOT).as_posix()
        for path in scripts_dir.glob("*.py")
        if path.name not in ALLOWED_ROOT_SCRIPT_FILES
    )
    if unexpected:
        print("Script entrypoint check failed:", file=sys.stderr)
        for rel in unexpected:
            print(f"- move {rel} under scripts/checks, scripts/seed, or scripts/ops", file=sys.stderr)
        return 1
    print("Script entrypoint check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
