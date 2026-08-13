"""Validate the versioned agent-workflow security traceability catalog."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists() or (parent / "Makefile").exists():
            return parent
    return Path.cwd()


ROOT = _repo_root()
DEFAULT_CATALOG = ROOT / "docs/security/security-controls-v1.yaml"
DEFAULT_SAFETY_CATALOG = ROOT / "docs/safety/safety-controls-v1.yaml"
SECTIONS = (
    "assets",
    "trust_boundaries",
    "threats",
    "controls",
    "detection_requirements",
    "verification_tests",
    "implementation_gaps",
)
STRIDE_CATEGORIES = {
    "spoofing",
    "tampering",
    "repudiation",
    "information_disclosure",
    "denial_of_service",
    "elevation_of_privilege",
}
THREAT_STATUSES = {"mitigated", "partially_mitigated", "planned", "blocked"}
EXPOSURES = {"active", "planned", "excluded"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
CONTROL_KINDS = {"preventive", "detective", "both"}
REFERENCE_RULES = {
    "threats": {
        "asset_ids": "assets",
        "trust_boundary_ids": "trust_boundaries",
        "control_ids": "controls",
        "detection_ids": "detection_requirements",
        "verification_ids": "verification_tests",
        "gap_ids": "implementation_gaps",
    },
    "controls": {
        "verification_ids": "verification_tests",
    },
    "implementation_gaps": {
        "control_ids": "controls",
        "threat_ids": "threats",
    },
}


def _numbered_ids(prefix: str, count: int) -> frozenset[str]:
    return frozenset(f"{prefix}-{number:02d}" for number in range(1, count + 1))


SCHEMA_REQUIRED_IDS = {
    "1.0": {
        "assets": _numbered_ids("ASSET", 10),
        "trust_boundaries": _numbered_ids("TB", 11),
        "threats": _numbered_ids("THR", 17),
        "controls": _numbered_ids("SEC", 20),
        "detection_requirements": _numbered_ids("SDET", 14),
        "verification_tests": _numbered_ids("SVT", 20),
        "implementation_gaps": _numbered_ids("GAP", 15),
    }
}


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    """Load a JSON-compatible YAML catalog without a YAML dependency."""

    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("catalog root must be an object")
    return loaded


def _records(
    catalog: dict[str, Any], section: str, errors: list[str]
) -> list[dict[str, Any]]:
    value = catalog.get(section)
    if not isinstance(value, list):
        errors.append(f"{section}: expected a list")
        return []
    records: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{section}[{index}]: expected an object")
            continue
        if not isinstance(item.get("id"), str) or not item["id"].strip():
            errors.append(f"{section}[{index}]: missing non-empty id")
            continue
        records.append(item)
    return records


def _reference_values(record: dict[str, Any], field: str) -> list[str]:
    value = record.get(field)
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _require_text(
    record: dict[str, Any], fields: tuple[str, ...], errors: list[str]
) -> None:
    for field in fields:
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append(f"{record['id']}: {field} must not be empty")


def _validate_required_scope(
    schema_version: Any,
    records: dict[str, list[dict[str, Any]]],
    errors: list[str],
) -> None:
    requirements = SCHEMA_REQUIRED_IDS.get(schema_version)
    if requirements is None:
        return
    for section, required_ids in requirements.items():
        actual_ids = {record["id"] for record in records[section]}
        missing = sorted(required_ids - actual_ids)
        if missing:
            errors.append(
                f"{section}: schema {schema_version} missing required ids: "
                f"{', '.join(missing)}"
            )


def _validate_references(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, dict[str, Any]]],
    errors: list[str],
) -> None:
    for section, fields in REFERENCE_RULES.items():
        for record in records[section]:
            for field, target_section in fields.items():
                values = _reference_values(record, field)
                if not values:
                    errors.append(f"{record['id']}: {field} must not be empty")
                    continue
                if len(values) != len(set(values)):
                    errors.append(f"{record['id']}: {field} must be unique")
                for value in values:
                    if value not in indexes[target_section]:
                        errors.append(
                            f"{record['id']}: {field} references unknown {value}"
                        )


def _safety_indexes(
    safety_catalog: dict[str, Any], errors: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    safety_errors: list[str] = []
    hazards = _records(safety_catalog, "hazards", safety_errors)
    constraints = _records(safety_catalog, "constraints", safety_errors)
    for error in safety_errors:
        errors.append(f"safety catalog: {error}")
    return (
        {record["id"]: record for record in hazards},
        {record["id"]: record for record in constraints},
    )


def _validate_threats(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, dict[str, Any]]],
    safety_catalog: dict[str, Any],
    errors: list[str],
) -> None:
    hazards, constraints = _safety_indexes(safety_catalog, errors)
    boundaries_used: set[str] = set()
    for threat in records["threats"]:
        _require_text(
            threat,
            (
                "title",
                "adversary",
                "capabilities",
                "preconditions",
                "attack_path",
                "impact",
                "beta_capability",
            ),
            errors,
        )
        categories = _reference_values(threat, "categories")
        if not categories:
            errors.append(f"{threat['id']}: categories must not be empty")
        for category in categories:
            if category not in STRIDE_CATEGORIES:
                errors.append(f"{threat['id']}: unknown STRIDE category {category!r}")

        for field in ("likelihood", "severity"):
            if threat.get(field) not in RISK_LEVELS:
                errors.append(f"{threat['id']}: {field} must be a risk level")
        if threat.get("exposure") not in EXPOSURES:
            errors.append(f"{threat['id']}: exposure is invalid")
        if threat.get("status") not in THREAT_STATUSES:
            errors.append(f"{threat['id']}: status is invalid")
        if threat.get("status") == "mitigated" and _reference_values(
            threat, "gap_ids"
        ):
            errors.append(f"{threat['id']}: mitigated threat must not have gaps")
        if threat.get("status") != "mitigated" and not _reference_values(
            threat, "gap_ids"
        ):
            errors.append(f"{threat['id']}: unresolved threat needs gap_ids")
        if threat.get("severity") == "critical" and threat.get("exposure") == "active":
            _require_text(threat, ("blocking_decision",), errors)

        boundaries_used.update(_reference_values(threat, "trust_boundary_ids"))
        mapped_hazards = set(_reference_values(threat, "stpa_hazard_ids"))
        mapped_constraints = set(_reference_values(threat, "stpa_constraint_ids"))
        if not mapped_hazards:
            errors.append(f"{threat['id']}: stpa_hazard_ids must not be empty")
        if not mapped_constraints:
            errors.append(f"{threat['id']}: stpa_constraint_ids must not be empty")
        for hazard_id in mapped_hazards:
            if hazard_id not in hazards:
                errors.append(
                    f"{threat['id']}: stpa_hazard_ids references unknown {hazard_id}"
                )
        constraint_hazards: set[str] = set()
        for constraint_id in mapped_constraints:
            constraint = constraints.get(constraint_id)
            if constraint is None:
                errors.append(
                    f"{threat['id']}: stpa_constraint_ids references unknown "
                    f"{constraint_id}"
                )
            else:
                constraint_hazards.update(
                    _reference_values(constraint, "hazard_ids")
                )
        for hazard_id in sorted(mapped_hazards - constraint_hazards):
            errors.append(
                f"{threat['id']}: STPA hazard {hazard_id} is not covered by "
                "a mapped safety constraint"
            )

        mapped_controls = set(_reference_values(threat, "control_ids"))
        mapped_verifications = set(_reference_values(threat, "verification_ids"))
        control_verifications: set[str] = set()
        for control_id in mapped_controls:
            control = indexes["controls"].get(control_id)
            if control:
                control_verifications.update(
                    _reference_values(control, "verification_ids")
                )
        for verification_id in sorted(mapped_verifications - control_verifications):
            errors.append(
                f"{threat['id']}: verification {verification_id} is not linked "
                "by a mapped control"
            )

        for gap_id in _reference_values(threat, "gap_ids"):
            gap = indexes["implementation_gaps"].get(gap_id)
            if gap and threat["id"] not in _reference_values(gap, "threat_ids"):
                errors.append(
                    f"{threat['id']}: gap {gap_id} does not link back to the threat"
                )
            if gap and not mapped_controls.intersection(
                _reference_values(gap, "control_ids")
            ):
                errors.append(
                    f"{threat['id']}: gap {gap_id} covers no mapped control"
                )

    required_boundaries = set(indexes["trust_boundaries"])
    for boundary_id in sorted(required_boundaries - boundaries_used):
        errors.append(f"{boundary_id}: trust boundary has no mapped threat")


def _validate_test_node_ref(
    verification_id: str,
    test_ref: str,
    root: Path | None,
    errors: list[str],
) -> None:
    node_parts = test_ref.split("::")
    relative_path = Path(node_parts[0])
    selector_parts = node_parts[1:]
    is_test_path = (
        not relative_path.is_absolute()
        and len(relative_path.parts) >= 2
        and relative_path.parts[0] == "tests"
        and ".." not in relative_path.parts
        and relative_path.suffix == ".py"
        and relative_path.name.startswith("test_")
    )
    has_test_selector = (
        bool(selector_parts)
        and all(selector_parts)
        and selector_parts[-1].split("[", 1)[0].startswith("test_")
    )
    if not is_test_path or not has_test_selector:
        errors.append(
            f"{verification_id}: test_ref must be a pytest node under tests/: "
            f"{test_ref}"
        )
        return
    if root is not None and not (root / relative_path).is_file():
        errors.append(f"{verification_id}: test_ref file does not exist: {relative_path}")


def _validate_statuses(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, dict[str, Any]]],
    root: Path | None,
    errors: list[str],
) -> None:
    for verification in records["verification_tests"]:
        _require_text(verification, ("description",), errors)
        status = verification.get("status")
        if status == "implemented":
            test_refs = verification.get("test_refs")
            if not isinstance(test_refs, list) or not test_refs:
                errors.append(
                    f"{verification['id']}: implemented verification needs "
                    "non-empty test_refs"
                )
                continue
            valid_test_refs = [
                test_ref
                for test_ref in test_refs
                if isinstance(test_ref, str) and test_ref.strip()
            ]
            if len(valid_test_refs) != len(test_refs):
                errors.append(
                    f"{verification['id']}: test_refs must contain only "
                    "non-empty strings"
                )
            if len(valid_test_refs) != len(set(valid_test_refs)):
                errors.append(f"{verification['id']}: test_refs must be unique")
            for test_ref in valid_test_refs:
                _validate_test_node_ref(verification["id"], test_ref, root, errors)
        elif status == "planned":
            _require_text(verification, ("owner", "target_phase"), errors)
        else:
            errors.append(
                f"{verification['id']}: status must be implemented or planned"
            )

    for control in records["controls"]:
        _require_text(control, ("description",), errors)
        if control.get("kind") not in CONTROL_KINDS:
            errors.append(f"{control['id']}: kind is invalid")
        status = control.get("status")
        gap_ids = _reference_values(control, "gap_ids")
        if status == "planned":
            _require_text(control, ("owner", "target_phase"), errors)
            if not gap_ids:
                errors.append(f"{control['id']}: planned control needs gap_ids")
            for gap_id in gap_ids:
                gap = indexes["implementation_gaps"].get(gap_id)
                if gap is None:
                    errors.append(f"{control['id']}: gap_ids references unknown {gap_id}")
                elif control["id"] not in _reference_values(gap, "control_ids"):
                    errors.append(
                        f"{control['id']}: gap {gap_id} does not link back to control"
                    )
        elif status == "implemented":
            if gap_ids:
                errors.append(f"{control['id']}: implemented control must not have gaps")
            implemented = [
                verification_id
                for verification_id in _reference_values(control, "verification_ids")
                if indexes["verification_tests"]
                .get(verification_id, {})
                .get("status")
                == "implemented"
            ]
            if not implemented:
                errors.append(
                    f"{control['id']}: implemented control needs an implemented "
                    "verification"
                )
        else:
            errors.append(f"{control['id']}: status must be implemented or planned")

    for gap in records["implementation_gaps"]:
        _require_text(
            gap, ("description", "owner", "target_phase", "status"), errors
        )
        if gap.get("status") != "open":
            errors.append(f"{gap['id']}: schema v1 implementation gap must be open")
        for control_id in _reference_values(gap, "control_ids"):
            control = indexes["controls"].get(control_id)
            if control and gap["id"] not in _reference_values(control, "gap_ids"):
                errors.append(
                    f"{gap['id']}: control {control_id} does not link back to gap"
                )
        for threat_id in _reference_values(gap, "threat_ids"):
            threat = indexes["threats"].get(threat_id)
            if threat and gap["id"] not in _reference_values(threat, "gap_ids"):
                errors.append(
                    f"{gap['id']}: threat {threat_id} does not link back to gap"
                )


def _validate_descriptions(
    records: dict[str, list[dict[str, Any]]], errors: list[str]
) -> None:
    for section in ("assets", "trust_boundaries", "detection_requirements"):
        for record in records[section]:
            _require_text(record, ("description",), errors)


def validate_catalog(
    catalog: dict[str, Any],
    safety_catalog: dict[str, Any],
    *,
    root: Path | None = None,
) -> list[str]:
    """Return every security traceability violation in deterministic order."""

    errors: list[str] = []
    schema_version = catalog.get("schema_version")
    if schema_version != "1.0":
        errors.append("schema_version: expected '1.0'")

    records = {section: _records(catalog, section, errors) for section in SECTIONS}
    _validate_required_scope(schema_version, records, errors)
    indexes = {
        section: {record["id"]: record for record in section_records}
        for section, section_records in records.items()
    }
    all_ids = [record["id"] for section in SECTIONS for record in records[section]]
    for identifier, count in sorted(Counter(all_ids).items()):
        if count > 1:
            errors.append(f"duplicate id across catalog: {identifier}")

    _validate_descriptions(records, errors)
    _validate_references(records, indexes, errors)
    _validate_threats(records, indexes, safety_catalog, errors)
    _validate_statuses(records, indexes, root, errors)
    return sorted(set(errors))


def run_implemented_verifications(
    catalog: dict[str, Any],
    *,
    root: Path = ROOT,
) -> list[str]:
    """Execute every pytest node that certifies an implemented verification."""

    test_nodes = sorted(
        {
            test_ref
            for verification in catalog.get("verification_tests", [])
            if isinstance(verification, dict)
            and verification.get("status") == "implemented"
            and isinstance(verification.get("test_refs"), list)
            for test_ref in verification["test_refs"]
            if isinstance(test_ref, str)
        }
    )
    if not test_nodes:
        return ["implemented verification execution found no pytest nodes"]

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *test_nodes],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return []
    output = "\n".join(
        line for line in (completed.stdout + completed.stderr).splitlines() if line.strip()
    )
    return [
        "implemented verification pytest execution failed "
        f"with exit code {completed.returncode}: {output}"
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--safety-catalog", type=Path, default=DEFAULT_SAFETY_CATALOG
    )
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        safety_catalog = load_catalog(args.safety_catalog)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Security traceability check failed: {exc}", file=sys.stderr)
        return 1

    errors = validate_catalog(catalog, safety_catalog, root=ROOT)
    if errors:
        print("Security traceability check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    execution_errors = run_implemented_verifications(catalog, root=ROOT)
    if execution_errors:
        print("Security traceability check failed:", file=sys.stderr)
        for error in execution_errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Security traceability check passed: "
        f"{len(catalog['assets'])} assets, "
        f"{len(catalog['trust_boundaries'])} trust boundaries, "
        f"{len(catalog['threats'])} threats, "
        f"{len(catalog['controls'])} controls, "
        f"{len(catalog['implementation_gaps'])} owned gaps, "
        "implemented verification nodes executed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
