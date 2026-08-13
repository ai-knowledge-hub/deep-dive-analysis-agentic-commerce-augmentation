"""Validate the versioned agent-workflow security traceability catalog."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import date
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
BLOCKING_DISPOSITION = "excluded_until_required_controls_implemented"
CAPABILITY_RELEASE_GATES = {
    "automatic_global_harness_promotion": frozenset({"SEC-12"}),
    "expanded_connectors_without_secret_egress_ssrf_controls": frozenset(
        {"SEC-13", "SEC-14", "SEC-19"}
    ),
    "expanded_production_telemetry_and_parallel_context_logging": frozenset(
        {"SEC-09", "SEC-13", "SEC-18", "SEC-19"}
    ),
    "parallel_multi_tenant_worker_execution": frozenset(
        {"SEC-09", "SEC-16", "SEC-19", "SEC-20"}
    ),
    "public_durable_workflow_and_peer_messages": frozenset(
        {"SEC-07", "SEC-08", "SEC-18", "SEC-20"}
    ),
    "unreviewed_memory_promotion": frozenset({"SEC-11"}),
    "write_capable_dynamic_child_delegation": frozenset({"SEC-06", "SEC-16"}),
}
SCHEMA_REQUIRED_CAPABILITY_EXCLUSIONS = {
    "1.0": {
        "THR-01": frozenset(
            {"automatic_global_harness_promotion", "unreviewed_memory_promotion"}
        ),
        "THR-02": frozenset({"write_capable_dynamic_child_delegation"}),
        "THR-04": frozenset({"public_durable_workflow_and_peer_messages"}),
        "THR-05": frozenset({"parallel_multi_tenant_worker_execution"}),
        "THR-10": frozenset(
            {"expanded_connectors_without_secret_egress_ssrf_controls"}
        ),
        "THR-16": frozenset(
            {"expanded_production_telemetry_and_parallel_context_logging"}
        ),
    }
}
REFERENCE_RULES = {
    "threats": {
        "asset_ids": "assets",
        "trust_boundary_ids": "trust_boundaries",
        "control_ids": "controls",
        "detection_ids": "detection_requirements",
        "verification_ids": "verification_tests",
    },
    "controls": {
        "verification_ids": "verification_tests",
    },
    "implementation_gaps": {
        "control_ids": "controls",
        "threat_ids": "threats",
    },
}
THREAT_COVERAGE_FIELDS = {
    "asset_ids": ("assets", "asset"),
    "trust_boundary_ids": ("trust_boundaries", "trust boundary"),
    "control_ids": ("controls", "security control"),
    "detection_ids": ("detection_requirements", "detection requirement"),
    "verification_ids": ("verification_tests", "verification"),
    "gap_ids": ("implementation_gaps", "implementation gap"),
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
        unexpected = sorted(actual_ids - required_ids)
        if unexpected:
            errors.append(
                f"{section}: schema {schema_version} has unexpected ids: "
                f"{', '.join(unexpected)}"
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


def _validate_gap_references(
    threat: dict[str, Any],
    indexes: dict[str, dict[str, dict[str, Any]]],
    *,
    required: bool,
    errors: list[str],
) -> list[str]:
    raw_gap_ids = threat.get("gap_ids")
    if not isinstance(raw_gap_ids, list):
        errors.append(f"{threat['id']}: gap_ids must be a list")
        return []
    gap_ids = _reference_values(threat, "gap_ids")
    if len(gap_ids) != len(raw_gap_ids):
        errors.append(f"{threat['id']}: gap_ids must contain only non-empty strings")
    if len(gap_ids) != len(set(gap_ids)):
        errors.append(f"{threat['id']}: gap_ids must be unique")
    if required and not gap_ids:
        errors.append(f"{threat['id']}: unresolved threat needs gap_ids")
    for gap_id in gap_ids:
        if gap_id not in indexes["implementation_gaps"]:
            errors.append(f"{threat['id']}: gap_ids references unknown {gap_id}")
    return gap_ids


def _validate_blocking_decision(
    threat: dict[str, Any],
    indexes: dict[str, dict[str, dict[str, Any]]],
    gap_ids: set[str],
    required_exclusion_ids: frozenset[str],
    errors: list[str],
) -> None:
    decision = threat.get("blocking_decision")
    if not isinstance(decision, dict):
        errors.append(f"{threat['id']}: blocking_decision must be an object")
        return
    if decision.get("disposition") != BLOCKING_DISPOSITION:
        errors.append(
            f"{threat['id']}: blocking_decision disposition must be "
            f"{BLOCKING_DISPOSITION!r}"
        )
    if not isinstance(decision.get("rationale"), str) or not decision[
        "rationale"
    ].strip():
        errors.append(f"{threat['id']}: blocking_decision needs rationale")

    raw_exclusion_ids = decision.get("capability_exclusion_ids")
    if not isinstance(raw_exclusion_ids, list):
        errors.append(
            f"{threat['id']}: blocking_decision capability_exclusion_ids must "
            "be a list"
        )
    exclusion_ids = _reference_values(decision, "capability_exclusion_ids")
    if isinstance(raw_exclusion_ids, list) and len(exclusion_ids) != len(
        raw_exclusion_ids
    ):
        errors.append(
            f"{threat['id']}: blocking_decision capability_exclusion_ids must "
            "contain only non-empty strings"
        )
    if not exclusion_ids:
        errors.append(
            f"{threat['id']}: blocking_decision needs capability_exclusion_ids"
        )
    if len(exclusion_ids) != len(set(exclusion_ids)):
        errors.append(
            f"{threat['id']}: blocking_decision capability_exclusion_ids must be unique"
        )
    unknown_exclusions = sorted(set(exclusion_ids) - CAPABILITY_RELEASE_GATES.keys())
    for exclusion_id in unknown_exclusions:
        errors.append(
            f"{threat['id']}: blocking_decision references unknown capability "
            f"exclusion {exclusion_id}"
        )
    if set(exclusion_ids) != required_exclusion_ids:
        errors.append(
            f"{threat['id']}: blocking_decision capability_exclusion_ids must "
            "exactly match the schema-v1 threat release boundary"
        )

    raw_required_control_ids = decision.get("required_control_ids")
    if not isinstance(raw_required_control_ids, list):
        errors.append(
            f"{threat['id']}: blocking_decision required_control_ids must be a list"
        )
    required_control_values = _reference_values(decision, "required_control_ids")
    if isinstance(raw_required_control_ids, list) and len(
        required_control_values
    ) != len(raw_required_control_ids):
        errors.append(
            f"{threat['id']}: blocking_decision required_control_ids must contain "
            "only non-empty strings"
        )
    if len(required_control_values) != len(set(required_control_values)):
        errors.append(
            f"{threat['id']}: blocking_decision required_control_ids must be unique"
        )
    required_control_ids = set(required_control_values)
    expected_control_ids: set[str] = set()
    for exclusion_id in exclusion_ids:
        expected_control_ids.update(CAPABILITY_RELEASE_GATES.get(exclusion_id, ()))
    if required_control_ids != expected_control_ids:
        errors.append(
            f"{threat['id']}: blocking_decision required_control_ids must exactly "
            "match its capability release gates"
        )

    mapped_controls = set(_reference_values(threat, "control_ids"))
    if not required_control_ids.issubset(mapped_controls):
        missing = sorted(required_control_ids - mapped_controls)
        errors.append(
            f"{threat['id']}: blocking_decision controls are not mapped to the "
            f"threat: {', '.join(missing)}"
        )
    for control_id in sorted(required_control_ids):
        control = indexes["controls"].get(control_id)
        if control is None:
            errors.append(
                f"{threat['id']}: blocking_decision references unknown control "
                f"{control_id}"
            )
            continue
        if control.get("status") != "planned":
            errors.append(
                f"{threat['id']}: release-gate control {control_id} must be planned"
            )
        if not gap_ids.intersection(_reference_values(control, "gap_ids")):
            errors.append(
                f"{threat['id']}: release-gate control {control_id} has no mapped "
                "threat gap"
            )


def _validate_mitigation_closure(
    threat: dict[str, Any],
    indexes: dict[str, dict[str, dict[str, Any]]],
    errors: list[str],
) -> None:
    closure = threat.get("closure")
    if not isinstance(closure, dict):
        errors.append(f"{threat['id']}: mitigated threat needs closure evidence")
        return
    for field in ("approved_by", "closed_at"):
        if not isinstance(closure.get(field), str) or not closure[field].strip():
            errors.append(f"{threat['id']}: closure needs {field}")
    closed_at = closure.get("closed_at")
    if isinstance(closed_at, str) and closed_at:
        try:
            date.fromisoformat(closed_at)
        except ValueError:
            errors.append(f"{threat['id']}: closure closed_at must be an ISO date")

    for field in ("implemented_control_ids", "verification_ids"):
        raw_values = closure.get(field)
        if not isinstance(raw_values, list):
            errors.append(f"{threat['id']}: closure {field} must be a list")
        values = _reference_values(closure, field)
        if isinstance(raw_values, list) and len(values) != len(raw_values):
            errors.append(
                f"{threat['id']}: closure {field} must contain only non-empty strings"
            )
        if len(values) != len(set(values)):
            errors.append(f"{threat['id']}: closure {field} must be unique")
    closure_controls = set(_reference_values(closure, "implemented_control_ids"))
    closure_verifications = set(_reference_values(closure, "verification_ids"))
    if not closure_controls:
        errors.append(f"{threat['id']}: closure needs implemented_control_ids")
    if not closure_verifications:
        errors.append(f"{threat['id']}: closure needs verification_ids")

    mapped_controls = set(_reference_values(threat, "control_ids"))
    mapped_verifications = set(_reference_values(threat, "verification_ids"))
    if closure_controls != mapped_controls:
        errors.append(
            f"{threat['id']}: closure controls must exactly match mapped controls"
        )
    if closure_verifications != mapped_verifications:
        errors.append(
            f"{threat['id']}: closure verifications must exactly match mapped "
            "verifications"
        )

    control_verifications: set[str] = set()
    for control_id in closure_controls:
        control = indexes["controls"].get(control_id)
        if control is None:
            errors.append(
                f"{threat['id']}: closure references unknown control {control_id}"
            )
            continue
        if control.get("status") != "implemented":
            errors.append(
                f"{threat['id']}: closure control {control_id} is not implemented"
            )
        control_verifications.update(_reference_values(control, "verification_ids"))
    for verification_id in closure_verifications:
        verification = indexes["verification_tests"].get(verification_id)
        if verification is None:
            errors.append(
                f"{threat['id']}: closure references unknown verification "
                f"{verification_id}"
            )
        elif verification.get("status") != "implemented":
            errors.append(
                f"{threat['id']}: closure verification {verification_id} is not "
                "implemented"
            )
        if verification_id not in control_verifications:
            errors.append(
                f"{threat['id']}: closure verification {verification_id} is not "
                "linked by a closure control"
            )


def _validate_threats(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, dict[str, Any]]],
    safety_catalog: dict[str, Any],
    schema_version: Any,
    errors: list[str],
) -> None:
    hazards, constraints = _safety_indexes(safety_catalog, errors)
    coverage = {section: set() for section, _label in THREAT_COVERAGE_FIELDS.values()}
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
        status = threat.get("status")
        if status not in THREAT_STATUSES:
            errors.append(f"{threat['id']}: status is invalid")
        gap_ids = set(
            _validate_gap_references(
                threat,
                indexes,
                required=status != "mitigated",
                errors=errors,
            )
        )
        if status == "mitigated":
            if gap_ids:
                errors.append(f"{threat['id']}: mitigated threat must not have gaps")
            _validate_mitigation_closure(threat, indexes, errors)
        elif threat.get("closure") is not None:
            errors.append(
                f"{threat['id']}: only a mitigated threat may declare closure"
            )
        required_exclusion_ids = SCHEMA_REQUIRED_CAPABILITY_EXCLUSIONS.get(
            schema_version, {}
        ).get(threat["id"])
        is_unresolved_critical_exposure = (
            threat.get("severity") == "critical"
            and threat.get("exposure") == "active"
            and status != "mitigated"
        )
        if required_exclusion_ids is not None and status != "mitigated":
            if not is_unresolved_critical_exposure:
                errors.append(
                    f"{threat['id']}: schema {schema_version} release-gated threat "
                    "must remain critical and active until mitigated"
                )
            _validate_blocking_decision(
                threat,
                indexes,
                gap_ids,
                required_exclusion_ids,
                errors,
            )
        elif is_unresolved_critical_exposure:
            errors.append(
                f"{threat['id']}: schema {schema_version} has no pinned "
                "critical-threat capability exclusions"
            )

        for field, (section, _label) in THREAT_COVERAGE_FIELDS.items():
            coverage[section].update(_reference_values(threat, field))
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

        for gap_id in gap_ids:
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

        for control_id in sorted(mapped_controls):
            control = indexes["controls"].get(control_id)
            if not control or control.get("status") != "planned":
                continue
            mutually_linked = any(
                gap_id in _reference_values(control, "gap_ids")
                and (gap := indexes["implementation_gaps"].get(gap_id)) is not None
                and threat["id"] in _reference_values(gap, "threat_ids")
                and control_id in _reference_values(gap, "control_ids")
                for gap_id in gap_ids
            )
            if not mutually_linked:
                errors.append(
                    f"{threat['id']}: planned control {control_id} needs a "
                    "mutually linked threat gap"
                )

    for section, label in THREAT_COVERAGE_FIELDS.values():
        for identifier in sorted(set(indexes[section]) - coverage[section]):
            errors.append(f"{identifier}: {label} has no mapped threat")


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
    _validate_threats(records, indexes, safety_catalog, schema_version, errors)
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
