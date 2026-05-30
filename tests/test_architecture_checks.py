from __future__ import annotations

from pathlib import Path

from scripts.checks import arch_check


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_architecture_boundaries_pass():
    assert arch_check.main() == 0


def test_architecture_check_blocks_domain_importing_infrastructure(tmp_path: Path):
    _write(
        tmp_path,
        "domain/example.py",
        "from infrastructure.db.core.connection import get_connection\n",
    )

    violations = arch_check.check_architecture(tmp_path)

    assert len(violations) == 1
    assert violations[0].rule == "domain-boundary"
    assert violations[0].import_name == "infrastructure.db.core.connection.get_connection"


def test_architecture_check_resolves_relative_imports(tmp_path: Path):
    _write(
        tmp_path,
        "domain/sub/example.py",
        "from ...infrastructure.db.core.connection import get_connection\n",
    )

    violations = arch_check.check_architecture(tmp_path)

    assert len(violations) == 1
    assert violations[0].rule == "domain-boundary"
    assert violations[0].import_name == "infrastructure.db.core.connection.get_connection"


def test_architecture_report_tracks_coupling_depth_and_complexity(tmp_path: Path):
    _write(tmp_path, "domain/types.py", "class Product:\n    pass\n")
    _write(
        tmp_path,
        "application/service.py",
        "\n".join(
            [
                "from domain.types import Product",
                "",
                "def complicated(value):",
                "    if value:",
                "        return Product()",
                "    if value is None:",
                "        return None",
                "    return value",
            ]
        ),
    )
    _write(
        tmp_path,
        "api/route.py",
        "from application.service import complicated\n",
    )

    report = arch_check.build_architecture_report(tmp_path, max_complexity=2)

    assert report.violations == []
    assert report.max_internal_imports == 1
    assert report.max_dependency_depth == 3
    assert len(report.complex_functions) == 1
    assert report.complex_functions[0].name == "complicated"


def test_architecture_report_flags_threshold_violations(tmp_path: Path):
    _write(tmp_path, "domain/types.py", "class Product:\n    pass\n")
    _write(
        tmp_path,
        "application/service.py",
        "from domain.types import Product\n",
    )
    _write(
        tmp_path,
        "api/route.py",
        "from application.service import Product\n",
    )

    report = arch_check.build_architecture_report(tmp_path)
    violations = arch_check.threshold_violations(
        report,
        root=tmp_path,
        max_internal_imports=0,
        max_dependency_depth=2,
    )

    assert [violation.rule for violation in violations] == [
        "max-internal-imports",
        "max-dependency-depth",
    ]


def test_architecture_report_detects_import_cycles(tmp_path: Path):
    _write(tmp_path, "application/a.py", "from application.b import b\n")
    _write(tmp_path, "application/b.py", "from application.a import a\n")

    report = arch_check.build_architecture_report(tmp_path)

    assert report.import_cycles == [("application.a", "application.b", "application.a")]
