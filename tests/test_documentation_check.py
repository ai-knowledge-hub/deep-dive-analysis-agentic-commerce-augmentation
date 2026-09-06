from __future__ import annotations

from pathlib import Path

import pytest

from scripts.checks import documentation_check


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _inventory_row(
    path: str,
    *,
    category: str = "current-implementation",
    status: str = "current",
    verified: str = "2026-09-05",
) -> str:
    return (
        f"| `{path}` | {category} | {status} | Document purpose. | owner | "
        f"{verified} | baseline |"
    )


def _index(*rows: str) -> str:
    own_row = _inventory_row("docs/README.md", category="executable-governance")
    return "\n".join(
        [
            "# Documentation Index",
            "",
            "| Path | Category | Status | Purpose | Owner | Last verified | Baseline |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            own_row,
            *rows,
        ]
    )


def _status_for_category(category: str) -> str:
    if category == "canonical-plan":
        return "canonical"
    if category == "durable-decision":
        return "accepted"
    if category == "historical":
        return "historical"
    return "current"


def _minimal_root(tmp_path: Path) -> None:
    required_rows = [
        _inventory_row(
            path,
            category=category,
            status=_status_for_category(category),
        )
        for path, category in documentation_check.REQUIRED_CATEGORY_BY_PATH.items()
        if path != "docs/README.md"
    ]
    _write(tmp_path, "docs/README.md", _index(*required_rows))
    for path in documentation_check.REQUIRED_CATEGORY_BY_PATH:
        if path != "docs/README.md":
            _write(tmp_path, path, f"# {Path(path).stem}\n")
    assert documentation_check.check_documentation(tmp_path) == []


def _append_inventory_rows(tmp_path: Path, *rows: str) -> None:
    index_path = tmp_path / "docs/README.md"
    content = index_path.read_text(encoding="utf-8")
    appended_rows = "\n".join(rows)
    _write(tmp_path, "docs/README.md", f"{content}\n{appended_rows}")


def test_repository_documentation_passes():
    assert (
        documentation_check.check_documentation(documentation_check._repo_root()) == []
    )


def test_unindexed_file_fails_even_when_remaining_index_is_consistent(tmp_path: Path):
    _minimal_root(tmp_path)
    _write(tmp_path, "docs/unindexed.md", "# Unindexed\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/unindexed.md: missing from the documentation inventory" in errors


def test_duplicate_category_assignment_fails(tmp_path: Path):
    row = _inventory_row("docs/design.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row, row)
    _write(tmp_path, "docs/design.md", "# Design\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/design.md: appears 2 times in the documentation inventory" in errors


def test_historical_document_cannot_declare_current(tmp_path: Path):
    row = _inventory_row("docs/old.md", category="historical", status="historical")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/old.md", "# Old\n\nStatus: current\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/old.md: historical document declares current status" in errors


def test_non_historical_document_requires_verification_metadata(tmp_path: Path):
    row = _inventory_row("docs/current.md", verified="—")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "# Current\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/current.md: non-historical entry is missing last verified" in errors


def test_broken_local_document_link_fails(tmp_path: Path):
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "[Missing](missing.md)\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/current.md: broken local link 'missing.md'" in errors


def test_missing_repository_path_link_fails(tmp_path: Path):
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "[Runtime](../application/missing.py)\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/current.md: broken local link '../application/missing.py'" in errors


def test_coordinated_authority_downgrade_fails(tmp_path: Path):
    _minimal_root(tmp_path)
    index = (tmp_path / "docs/README.md").read_text(encoding="utf-8")
    index = index.replace(
        "| `docs/README.md` | executable-governance | current |",
        "| `docs/README.md` | historical | historical |",
    ).replace(
        "| `docs/platform-modernisation-plan-v2.md` | canonical-plan | canonical |",
        "| `docs/platform-modernisation-plan-v2.md` | reference-design | reference |",
    )
    _write(tmp_path, "docs/README.md", index)

    errors = documentation_check.check_documentation(tmp_path)

    assert any("docs/README.md: must remain" in error for error in errors)
    assert any(
        "docs/platform-modernisation-plan-v2.md: must remain" in error
        for error in errors
    )
    assert any("exactly one canonical plan" in error for error in errors)


def test_every_pinned_authority_rejects_coordinated_reclassification(tmp_path: Path):
    for path, category in documentation_check.REQUIRED_CATEGORY_BY_PATH.items():
        if path == "docs/README.md":
            continue
        _minimal_root(tmp_path)
        index_path = tmp_path / "docs/README.md"
        index = index_path.read_text(encoding="utf-8")
        old_status = _status_for_category(category)
        index = index.replace(
            f"| `{path}` | {category} | {old_status} |",
            f"| `{path}` | reference-design | reference |",
        )
        _write(tmp_path, "docs/README.md", index)

        errors = documentation_check.check_documentation(tmp_path)

        assert any(f"{path}: must remain" in error for error in errors)


def test_required_authority_cannot_be_deleted_with_its_inventory_row(tmp_path: Path):
    _minimal_root(tmp_path)
    required_path = "docs/security/security-controls-v1.yaml"
    index_path = tmp_path / "docs/README.md"
    rows = [
        line
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if required_path not in line
    ]
    _write(tmp_path, "docs/README.md", "\n".join(rows))
    (tmp_path / required_path).unlink()

    errors = documentation_check.check_documentation(tmp_path)

    assert f"{required_path}: required authority must appear exactly once" in errors


def test_second_canonical_plan_is_rejected(tmp_path: Path):
    row = _inventory_row(
        "docs/other-plan.md", category="canonical-plan", status="canonical"
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/other-plan.md", "# Other plan\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any("exactly one canonical plan" in error for error in errors)


def test_docs_history_files_cannot_be_reclassified(tmp_path: Path):
    row = _inventory_row(
        "docs/history/old.md", category="reference-design", status="reference"
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/history/old.md", "# Old\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any(
        "docs/history/old.md: files under its authority namespace" in error
        for error in errors
    )


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("docs/decisions/0002-new-decision.md", "durable-decision"),
        ("docs/safety/new-analysis.md", "executable-governance"),
        ("docs/security/new-analysis.md", "executable-governance"),
    ],
)
def test_authority_namespaces_enforce_future_classifications(
    tmp_path: Path, path: str, category: str
):
    row = _inventory_row(path, category="reference-design", status="reference")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, path, "# New document\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any(
        f"{path}: files under its authority namespace must remain {category!r}" in error
        for error in errors
    )


def test_formatted_current_status_is_rejected_for_history(tmp_path: Path):
    row = _inventory_row(
        "docs/history/old.md", category="historical", status="historical"
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(
        tmp_path, "docs/history/old.md", "# Old\n\n**Status:** Current implementation\n"
    )

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/history/old.md: historical document declares current status" in errors


@pytest.mark.parametrize(
    "declaration",
    [
        "## Status: current implementation",
        "> **Status:** current implementation",
    ],
)
def test_heading_and_blockquote_current_status_are_rejected_for_history(
    tmp_path: Path, declaration: str
):
    row = _inventory_row(
        "docs/history/old.md", category="historical", status="historical"
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/history/old.md", f"# Old\n\n{declaration}\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/history/old.md: historical document declares current status" in errors


def test_reference_style_broken_link_fails(tmp_path: Path):
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "[Missing][target]\n\n[target]: absent.md\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/current.md: broken local link 'absent.md'" in errors


def test_root_absolute_repository_link_fails_even_when_target_exists(tmp_path: Path):
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "[Plan](/repository/docs/README.md)\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any("local link must be repository-relative" in error for error in errors)


def test_relative_link_cannot_escape_repository(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", f"[Outside](../../{outside.name})\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any("local link escapes the repository" in error for error in errors)


def test_symlinked_link_cannot_escape_repository(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    (tmp_path / "docs/escape.md").symlink_to(outside)
    _append_inventory_rows(
        tmp_path,
        _inventory_row(
            "docs/escape.md", category="reference-design", status="reference"
        ),
    )
    _write(tmp_path, "docs/current.md", "[Outside](escape.md)\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any("local link escapes the repository" in error for error in errors)


def test_code_spanned_missing_repository_path_fails(tmp_path: Path):
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "`application/removed_module.py`\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any("application/removed_module.py" in error for error in errors)


@pytest.mark.parametrize(
    ("reference", "missing_path"),
    [
        ("application/removed.py:handler", "application/removed.py"),
        ("data/removed.json", "data/removed.json"),
        ("scripts/removed.sh", "scripts/removed.sh"),
        ("application/removed_directory", "application/removed_directory"),
        ("Makefile", "Makefile"),
    ],
)
def test_code_spanned_repository_path_forms_fail(
    tmp_path: Path, reference: str, missing_path: str
):
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", f"`{reference}`\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any(missing_path in error for error in errors)


@pytest.mark.parametrize(
    ("source_path", "reference", "missing_path"),
    [
        (
            "docs/security/current.md",
            "missing-security-controls.yaml",
            "missing-security-controls.yaml",
        ),
        (
            "docs/history/old.md",
            "../operator-experience.md",
            "../operator-experience.md",
        ),
        (
            "docs/current.md",
            "./application/removed.py",
            "./application/removed.py",
        ),
        (
            "docs/history/old.md",
            "../missing_directory/",
            "../missing_directory",
        ),
        (
            "docs/history/old.md",
            "../missing_directory",
            "../missing_directory",
        ),
        ("docs/current.md", "./missing_file", "./missing_file"),
    ],
)
def test_document_relative_code_spanned_paths_fail_when_missing(
    tmp_path: Path, source_path: str, reference: str, missing_path: str
):
    category = (
        documentation_check.REQUIRED_CATEGORY_BY_NAMESPACE.get(
            f"{Path(source_path).parent.as_posix()}/"
        )
        or "current-implementation"
    )
    row = _inventory_row(
        source_path,
        category=category,
        status=_status_for_category(category),
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, source_path, f"`{reference}`\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert any(missing_path in error for error in errors)


def test_document_relative_code_spanned_path_resolves_from_source(tmp_path: Path):
    rows = (
        _inventory_row("docs/guide/current.md"),
        _inventory_row(
            "docs/shared-contract.yaml",
            category="executable-governance",
            status="current",
        ),
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, *rows)
    _write(tmp_path, "docs/guide/current.md", "`../shared-contract.yaml`\n")
    _write(tmp_path, "docs/shared-contract.yaml", "version: 1\n")

    assert documentation_check.check_documentation(tmp_path) == []


def test_document_relative_directory_resolves_from_source(tmp_path: Path):
    row = _inventory_row("docs/guide/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/guide/current.md", "`../assets/`\n")
    (tmp_path / "docs/assets").mkdir()

    assert documentation_check.check_documentation(tmp_path) == []


def test_explicit_relative_extensionless_file_resolves_from_source(tmp_path: Path):
    row = _inventory_row("docs/current.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "`../Makefile`\n")
    _write(tmp_path, "Makefile", "docs-check:\n")

    assert documentation_check.check_documentation(tmp_path) == []


def test_intentional_historical_code_path_has_explicit_notation(tmp_path: Path):
    row = _inventory_row(
        "docs/history/old.md", category="historical", status="historical"
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(
        tmp_path, "docs/history/old.md", "`historical-path:application/removed.py`\n"
    )

    errors = documentation_check.check_documentation(tmp_path)

    assert not any("application/removed.py" in error for error in errors)


def test_runtime_code_path_has_explicit_non_repository_notation(tmp_path: Path):
    row = _inventory_row("docs/deployment-guide.md")
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(
        tmp_path,
        "docs/deployment-guide.md",
        "`runtime-path:./tmp/generated.db`\n",
    )

    assert documentation_check.check_documentation(tmp_path) == []


def test_non_historical_metadata_must_be_meaningful_and_dated(tmp_path: Path):
    row = (
        "| `docs/current.md` | current-implementation | current | x | x | "
        "sometime | x |"
    )
    _minimal_root(tmp_path)
    _append_inventory_rows(tmp_path, row)
    _write(tmp_path, "docs/current.md", "# Current\n")

    errors = documentation_check.check_documentation(tmp_path)

    assert "docs/current.md: last verified must be an ISO date" in errors
    assert "docs/current.md: purpose is not meaningful" in errors
    assert "docs/current.md: owner is not meaningful" in errors
    assert "docs/current.md: baseline is not meaningful" in errors
