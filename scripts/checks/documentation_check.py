"""Validate the authoritative documentation inventory and local references."""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


ALLOWED_CATEGORIES = frozenset(
    {
        "canonical-plan",
        "durable-decision",
        "executable-governance",
        "current-implementation",
        "current-product-guide",
        "reference-design",
        "research-snapshot",
        "operational-record",
        "historical",
    }
)
ALLOWED_STATUSES_BY_CATEGORY = {
    "canonical-plan": {"canonical"},
    "durable-decision": {"accepted", "current"},
    "executable-governance": {"accepted", "current", "normative"},
    "current-implementation": {"current"},
    "current-product-guide": {"current"},
    "reference-design": {
        "current-contract",
        "current-rules",
        "evaluation-plan",
        "future-spec",
        "reference",
        "remaining-roadmap",
    },
    "research-snapshot": {"snapshot"},
    "operational-record": {"current", "maintained"},
    "historical": {"historical"},
}
REQUIRED_CATEGORY_BY_PATH = {
    "docs/README.md": "executable-governance",
    "docs/agentification-checkpoint.md": "historical",
    "docs/codebase-cleanup-and-modularisation-plan.md": "historical",
    "docs/platform-modernisation-plan-v2.md": "canonical-plan",
    "docs/decisions/README.md": "durable-decision",
    "docs/decisions/0001-workflow-task-delegation-schema.md": "durable-decision",
    "docs/safety/README.md": "executable-governance",
    "docs/safety/safety-controls-v1.yaml": "executable-governance",
    "docs/safety/stpa-workflow-control-analysis-v1.md": "executable-governance",
    "docs/security/README.md": "executable-governance",
    "docs/security/agent-workflow-threat-model-v1.md": "executable-governance",
    "docs/security/security-controls-v1.yaml": "executable-governance",
}
REQUIRED_CATEGORY_BY_NAMESPACE = {
    "docs/decisions/": "durable-decision",
    "docs/history/": "historical",
    "docs/safety/": "executable-governance",
    "docs/security/": "executable-governance",
}
REPOSITORY_DIRECTORIES = (
    ".agents",
    ".github",
    "api",
    "application",
    "data",
    "docs",
    "domain",
    "infrastructure",
    "scripts",
    "shared",
    "tests",
    "web",
)
ROOT_REPOSITORY_FILES = frozenset(
    {
        ".env.example",
        "AGENTS.md",
        "Makefile",
        "README.md",
        "pyproject.toml",
        "requirements.txt",
        "uv.lock",
    }
)
REPOSITORY_FILE_SUFFIXES = frozenset(
    {
        ".css",
        ".html",
        ".js",
        ".json",
        ".md",
        ".py",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".yaml",
        ".yml",
    }
)
NON_REPOSITORY_CODE_PATH_PREFIXES = ("historical-path:", "runtime-path:")
INVENTORY_ROW = re.compile(r"^\|\s*`(docs/[^`]+)`\s*\|")
INLINE_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REFERENCE_LINK = re.compile(r"(?m)^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)")
CODE_SPAN = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
STATUS_FIELD = re.compile(
    r"(?im)^\s*(?:>\s*)?(?:#{1,6}\s*)?(?:[-*]\s*)?"
    r"(?:\*\*|__)?status(?:\s+date)?"
    r"(?:\*\*|__)?\s*:\s*(.+?)\s*$"
)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class DocumentationEntry:
    path: str
    category: str
    status: str
    purpose: str
    owner: str
    last_verified: str
    baseline: str


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / "Makefile").exists():
            return parent
    return Path.cwd()


def _parse_inventory(index_path: Path) -> tuple[list[DocumentationEntry], list[str]]:
    entries: list[DocumentationEntry] = []
    errors: list[str] = []
    for line_number, line in enumerate(
        index_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not INVENTORY_ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            errors.append(
                f"{index_path.as_posix()}:{line_number}: inventory row must have 7 columns"
            )
            continue
        entries.append(
            DocumentationEntry(
                path=cells[0].strip("`"),
                category=cells[1].strip("`"),
                status=cells[2].strip("`"),
                purpose=cells[3],
                owner=cells[4],
                last_verified=cells[5],
                baseline=cells[6],
            )
        )
    return entries, errors


def _resolve_local_target(root: Path, source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    target = unquote(target.split("#", 1)[0])
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    target_path = Path(target)
    if not target_path.is_absolute():
        return (source.parent / target_path).resolve()
    return target_path


def _normalized_statuses(content: str) -> list[str]:
    return [
        re.sub(r"[*_]+", "", match).strip().lower()
        for match in STATUS_FIELD.findall(content)
    ]


def _repository_code_path(
    root: Path, source: Path, value: str
) -> tuple[str, Path] | None:
    candidate = value.strip().rstrip(".,;")
    if candidate.startswith(NON_REPOSITORY_CODE_PATH_PREFIXES):
        return None
    if any(token in candidate for token in ("*", "{", "}", " ", "->")):
        return None
    explicit_relative = candidate.startswith(("./", "../"))
    candidate = re.split(r"[:#]", candidate, maxsplit=1)[0].rstrip("/")
    if not candidate:
        return None
    candidate_path = Path(candidate)
    if candidate in ROOT_REPOSITORY_FILES or candidate.startswith(
        tuple(f"{part}/" for part in REPOSITORY_DIRECTORIES)
    ):
        target = root / candidate_path
    elif explicit_relative or (
        "/" not in candidate
        and candidate_path.suffix.lower() in REPOSITORY_FILE_SUFFIXES
    ):
        target = source.parent / candidate_path
    else:
        return None
    return candidate, target.resolve()


def check_documentation(root: Path) -> list[str]:
    root = root.resolve()
    docs_dir = root / "docs"
    index_path = docs_dir / "README.md"
    errors: list[str] = []
    if not index_path.is_file():
        return ["docs/README.md: authoritative documentation index is missing"]

    entries, parse_errors = _parse_inventory(index_path)
    errors.extend(parse_errors)
    counts = Counter(entry.path for entry in entries)
    for path, count in sorted(counts.items()):
        if count != 1:
            errors.append(
                f"{path}: appears {count} times in the documentation inventory"
            )

    actual_paths = {
        path.relative_to(root).as_posix()
        for path in docs_dir.rglob("*")
        if path.is_file()
    }
    indexed_paths = set(counts)
    for required_path in REQUIRED_CATEGORY_BY_PATH:
        if counts[required_path] != 1:
            errors.append(
                f"{required_path}: required authority must appear exactly once"
            )
    for path in sorted(actual_paths - indexed_paths):
        errors.append(f"{path}: missing from the documentation inventory")
    for path in sorted(indexed_paths - actual_paths):
        errors.append(f"{path}: indexed documentation file does not exist")

    for entry in entries:
        if entry.category not in ALLOWED_CATEGORIES:
            errors.append(f"{entry.path}: unknown category {entry.category!r}")
        elif entry.status not in ALLOWED_STATUSES_BY_CATEGORY[entry.category]:
            errors.append(
                f"{entry.path}: status {entry.status!r} is invalid for "
                f"{entry.category!r}"
            )
        required_category = REQUIRED_CATEGORY_BY_PATH.get(entry.path)
        namespace_category = next(
            (
                category
                for namespace, category in REQUIRED_CATEGORY_BY_NAMESPACE.items()
                if entry.path.startswith(namespace)
            ),
            None,
        )
        if required_category is not None and entry.category != required_category:
            errors.append(
                f"{entry.path}: must remain {required_category!r}, "
                f"not {entry.category!r}"
            )
        if namespace_category is not None and entry.category != namespace_category:
            errors.append(
                f"{entry.path}: files under its authority namespace must remain "
                f"{namespace_category!r}"
            )
        fields = {
            "status": entry.status,
            "purpose": entry.purpose,
            "owner": entry.owner,
            "last verified": entry.last_verified,
            "baseline": entry.baseline,
        }
        if entry.category != "historical":
            for name, value in fields.items():
                if not value or value in {"-", "—"}:
                    errors.append(
                        f"{entry.path}: non-historical entry is missing {name}"
                    )
            if entry.last_verified and not ISO_DATE.fullmatch(entry.last_verified):
                errors.append(f"{entry.path}: last verified must be an ISO date")
            if len(entry.purpose) < 12:
                errors.append(f"{entry.path}: purpose is not meaningful")
            if len(entry.owner) < 3:
                errors.append(f"{entry.path}: owner is not meaningful")
            if len(entry.baseline) < 5:
                errors.append(f"{entry.path}: baseline is not meaningful")
        elif entry.status != "historical":
            errors.append(f"{entry.path}: historical entry must have historical status")

        document_path = root / entry.path
        if (
            entry.category == "historical"
            and document_path.suffix == ".md"
            and document_path.is_file()
            and any(
                status.startswith("current")
                for status in _normalized_statuses(
                    document_path.read_text(encoding="utf-8")
                )
            )
        ):
            errors.append(f"{entry.path}: historical document declares current status")

    canonical_plans = [
        entry.path for entry in entries if entry.category == "canonical-plan"
    ]
    if canonical_plans != ["docs/platform-modernisation-plan-v2.md"]:
        errors.append(
            "documentation inventory must contain exactly one canonical plan: "
            "docs/platform-modernisation-plan-v2.md"
        )

    for source in sorted(docs_dir.rglob("*.md")):
        content = source.read_text(encoding="utf-8")
        link_targets = INLINE_LINK.findall(content) + REFERENCE_LINK.findall(content)
        for raw_target in link_targets:
            stripped_target = raw_target.strip().lstrip("<")
            if stripped_target.startswith("/"):
                relative_source = source.relative_to(root).as_posix()
                errors.append(
                    f"{relative_source}: local link must be repository-relative "
                    f"{raw_target!r}"
                )
                continue
            resolved = _resolve_local_target(root, source, raw_target)
            if resolved is not None and not resolved.is_relative_to(root):
                relative_source = source.relative_to(root).as_posix()
                errors.append(
                    f"{relative_source}: local link escapes the repository "
                    f"{raw_target!r}"
                )
            elif resolved is not None and not resolved.exists():
                relative_source = source.relative_to(root).as_posix()
                errors.append(f"{relative_source}: broken local link {raw_target!r}")
        for code_value in CODE_SPAN.findall(content):
            repository_reference = _repository_code_path(root, source, code_value)
            repository_path, repository_target = (
                repository_reference
                if repository_reference is not None
                else (None, None)
            )
            if repository_target is not None and not repository_target.is_relative_to(
                root
            ):
                relative_source = source.relative_to(root).as_posix()
                errors.append(
                    f"{relative_source}: referenced repository path escapes the "
                    f"repository {repository_path!r}"
                )
            elif repository_target is not None and not repository_target.exists():
                relative_source = source.relative_to(root).as_posix()
                errors.append(
                    f"{relative_source}: referenced repository path does not exist "
                    f"{repository_path!r}; use historical-path: for an intentional "
                    "former location"
                )
    return errors


def main() -> int:
    errors = check_documentation(_repo_root())
    if errors:
        print("Documentation check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Documentation check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
