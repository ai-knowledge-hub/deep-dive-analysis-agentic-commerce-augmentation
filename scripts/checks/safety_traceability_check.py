"""Validate the versioned STPA safety traceability catalog."""

from __future__ import annotations

import argparse
import json
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
DEFAULT_CATALOG = ROOT / "docs/safety/safety-controls-v1.yaml"
SECTIONS = (
    "losses",
    "hazards",
    "control_actions",
    "constraints",
    "controls",
    "feedback_requirements",
    "verification_tests",
    "unsafe_control_actions",
)
UCA_CATEGORIES = {
    "not_provided_when_required",
    "provided_when_unsafe",
    "wrong_timing_or_order",
    "stopped_too_soon_or_applied_too_long",
}
REFERENCE_RULES = {
    "hazards": {"loss_ids": "losses"},
    "constraints": {"hazard_ids": "hazards"},
    "controls": {
        "constraint_ids": "constraints",
        "verification_ids": "verification_tests",
    },
    "feedback_requirements": {"hazard_ids": "hazards"},
    "unsafe_control_actions": {
        "control_action_id": "control_actions",
        "hazard_ids": "hazards",
        "constraint_ids": "constraints",
        "control_ids": "controls",
        "feedback_ids": "feedback_requirements",
        "verification_ids": "verification_tests",
    },
}


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    """Load the JSON-compatible YAML catalog without a YAML dependency."""

    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("catalog root must be an object")
    return loaded


def _records(catalog: dict[str, Any], section: str, errors: list[str]) -> list[dict[str, Any]]:
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
                for value in values:
                    if value not in indexes[target_section]:
                        errors.append(
                            f"{record['id']}: {field} references unknown {value}"
                        )


def _validate_uca_coverage(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, dict[str, Any]]],
    errors: list[str],
) -> None:
    categories_by_action: dict[str, list[str]] = {
        record["id"]: [] for record in records["control_actions"]
    }
    for uca in records["unsafe_control_actions"]:
        category = uca.get("category")
        if category not in UCA_CATEGORIES:
            errors.append(f"{uca['id']}: unknown UCA category {category!r}")
        action_id = uca.get("control_action_id")
        if action_id in categories_by_action and isinstance(category, str):
            categories_by_action[action_id].append(category)
        if not isinstance(uca.get("context"), str) or not uca["context"].strip():
            errors.append(f"{uca['id']}: context must not be empty")

        mapped_constraints = set(_reference_values(uca, "constraint_ids"))
        mapped_verifications = set(_reference_values(uca, "verification_ids"))
        control_constraints: set[str] = set()
        control_verifications: set[str] = set()
        for control_id in _reference_values(uca, "control_ids"):
            control = indexes["controls"].get(control_id)
            if control:
                control_constraints.update(_reference_values(control, "constraint_ids"))
                control_verifications.update(_reference_values(control, "verification_ids"))
        for constraint_id in sorted(mapped_constraints - control_constraints):
            errors.append(
                f"{uca['id']}: constraint {constraint_id} is not covered by a mapped control"
            )
        for verification_id in sorted(mapped_verifications - control_verifications):
            errors.append(
                f"{uca['id']}: verification {verification_id} is not linked by a mapped control"
            )

    for action_id, categories in categories_by_action.items():
        counts = Counter(categories)
        missing = sorted(UCA_CATEGORIES - counts.keys())
        duplicates = sorted(category for category, count in counts.items() if count > 1)
        if missing:
            errors.append(f"{action_id}: missing UCA categories {', '.join(missing)}")
        if duplicates:
            errors.append(f"{action_id}: duplicate UCA categories {', '.join(duplicates)}")


def _validate_statuses(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, dict[str, Any]]],
    root: Path | None,
    errors: list[str],
) -> None:
    for verification in records["verification_tests"]:
        status = verification.get("status")
        if status == "implemented":
            test_ref = verification.get("test_ref")
            if not isinstance(test_ref, str) or not test_ref.strip():
                errors.append(f"{verification['id']}: implemented verification needs test_ref")
            elif root is not None and not (root / test_ref).is_file():
                errors.append(f"{verification['id']}: test_ref does not exist: {test_ref}")
        elif status == "planned":
            for field in ("owner", "target_phase"):
                if not isinstance(verification.get(field), str) or not verification[field].strip():
                    errors.append(f"{verification['id']}: planned verification needs {field}")
        else:
            errors.append(f"{verification['id']}: status must be implemented or planned")

    for control in records["controls"]:
        status = control.get("status")
        if status == "planned":
            for field in ("owner", "target_phase"):
                if not isinstance(control.get(field), str) or not control[field].strip():
                    errors.append(f"{control['id']}: planned control needs {field}")
        elif status == "implemented":
            verification_ids = _reference_values(control, "verification_ids")
            implemented = [
                verification_id
                for verification_id in verification_ids
                if indexes["verification_tests"].get(verification_id, {}).get("status")
                == "implemented"
            ]
            if not implemented:
                errors.append(
                    f"{control['id']}: implemented control needs an implemented verification"
                )
        else:
            errors.append(f"{control['id']}: status must be implemented or planned")


def validate_catalog(catalog: dict[str, Any], *, root: Path | None = None) -> list[str]:
    """Return every traceability violation in deterministic order."""

    errors: list[str] = []
    if catalog.get("schema_version") != "1.0":
        errors.append("schema_version: expected '1.0'")

    records = {section: _records(catalog, section, errors) for section in SECTIONS}
    indexes = {
        section: {record["id"]: record for record in section_records}
        for section, section_records in records.items()
    }

    all_ids = [record["id"] for section in SECTIONS for record in records[section]]
    for identifier, count in sorted(Counter(all_ids).items()):
        if count > 1:
            errors.append(f"duplicate id across catalog: {identifier}")

    _validate_references(records, indexes, errors)
    _validate_uca_coverage(records, indexes, errors)
    _validate_statuses(records, indexes, root, errors)
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Safety traceability check failed: {exc}", file=sys.stderr)
        return 1

    errors = validate_catalog(catalog, root=ROOT)
    if errors:
        print("Safety traceability check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Safety traceability check passed: "
        f"{len(catalog['control_actions'])} control actions, "
        f"{len(catalog['unsafe_control_actions'])} unsafe control actions, "
        f"{len(catalog['controls'])} controls."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
