from __future__ import annotations

from copy import deepcopy

from scripts.checks import security_traceability_check


def _catalog() -> dict:
    return security_traceability_check.load_catalog()


def _safety_catalog() -> dict:
    return security_traceability_check.load_catalog(
        security_traceability_check.DEFAULT_SAFETY_CATALOG
    )


def _validate(catalog: dict, *, root=None) -> list[str]:
    return security_traceability_check.validate_catalog(
        catalog,
        _safety_catalog(),
        root=root,
    )


def test_canonical_security_catalog_is_fully_traceable() -> None:
    assert _validate(_catalog(), root=security_traceability_check.ROOT) == []


def test_schema_v1_rejects_empty_security_sections() -> None:
    catalog = deepcopy(_catalog())
    for section in security_traceability_check.SECTIONS:
        catalog[section] = []

    errors = _validate(catalog)

    assert any(
        error.startswith("threats: schema 1.0 missing required ids:")
        for error in errors
    )
    assert any(
        error.startswith("trust_boundaries: schema 1.0 missing required ids:")
        for error in errors
    )


def test_schema_v1_rejects_silent_threat_and_gap_deletion() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"] = [
        threat for threat in catalog["threats"] if threat["id"] != "THR-17"
    ]
    catalog["implementation_gaps"] = [
        gap for gap in catalog["implementation_gaps"] if gap["id"] != "GAP-15"
    ]

    errors = _validate(catalog)

    assert "threats: schema 1.0 missing required ids: THR-17" in errors
    assert "implementation_gaps: schema 1.0 missing required ids: GAP-15" in errors


def test_catalog_ids_are_globally_unique() -> None:
    catalog = deepcopy(_catalog())
    catalog["trust_boundaries"][0]["id"] = "ASSET-01"

    errors = _validate(catalog)

    assert "duplicate id across catalog: ASSET-01" in errors


def test_threat_requires_complete_attack_and_traceability_fields() -> None:
    catalog = deepcopy(_catalog())
    threat = catalog["threats"][0]
    threat["adversary"] = ""
    threat["preconditions"] = ""
    threat["attack_path"] = ""
    threat["control_ids"] = []
    threat["detection_ids"] = []
    threat["verification_ids"] = []

    errors = _validate(catalog)

    assert "THR-01: adversary must not be empty" in errors
    assert "THR-01: preconditions must not be empty" in errors
    assert "THR-01: attack_path must not be empty" in errors
    assert "THR-01: control_ids must not be empty" in errors
    assert "THR-01: detection_ids must not be empty" in errors
    assert "THR-01: verification_ids must not be empty" in errors


def test_references_must_resolve() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0]["asset_ids"] = ["ASSET-404"]

    errors = _validate(catalog)

    assert "THR-01: asset_ids references unknown ASSET-404" in errors


def test_every_trust_boundary_requires_a_mapped_threat() -> None:
    catalog = deepcopy(_catalog())
    for threat in catalog["threats"]:
        threat["trust_boundary_ids"] = [
            boundary
            for boundary in threat["trust_boundary_ids"]
            if boundary != "TB-07"
        ]

    errors = _validate(catalog)

    assert "TB-07: trust boundary has no mapped threat" in errors


def test_stpa_references_must_resolve_against_safety_catalog() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0]["stpa_hazard_ids"] = ["H-404"]
    catalog["threats"][0]["stpa_constraint_ids"] = ["SC-404"]

    errors = _validate(catalog)

    assert "THR-01: stpa_hazard_ids references unknown H-404" in errors
    assert "THR-01: stpa_constraint_ids references unknown SC-404" in errors


def test_every_stpa_hazard_requires_a_mapped_safety_constraint() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0]["stpa_hazard_ids"].append("H-02")

    errors = _validate(catalog)

    assert (
        "THR-01: STPA hazard H-02 is not covered by a mapped safety constraint"
        in errors
    )


def test_threat_verification_must_be_linked_by_a_mapped_control() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0]["verification_ids"].append("SVT-20")

    errors = _validate(catalog)

    assert (
        "THR-01: verification SVT-20 is not linked by a mapped control" in errors
    )


def test_unresolved_threat_requires_an_owned_gap() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0]["gap_ids"] = []

    errors = _validate(catalog)

    assert "THR-01: unresolved threat needs gap_ids" in errors


def test_gap_relationships_must_be_bidirectional() -> None:
    catalog = deepcopy(_catalog())
    catalog["implementation_gaps"][0]["threat_ids"].remove("THR-02")

    errors = _validate(catalog)

    assert "THR-02: gap GAP-01 does not link back to the threat" in errors


def test_critical_active_threat_requires_an_explicit_blocking_decision() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0].pop("blocking_decision")

    errors = _validate(catalog)

    assert "THR-01: blocking_decision must not be empty" in errors


def test_planned_control_and_verification_require_owner_and_phase() -> None:
    catalog = deepcopy(_catalog())
    catalog["controls"][5].pop("owner")
    catalog["verification_tests"][5].pop("target_phase")

    errors = _validate(catalog)

    assert "SEC-06: owner must not be empty" in errors
    assert "SVT-06: target_phase must not be empty" in errors


def test_implemented_control_requires_an_implemented_verification() -> None:
    catalog = deepcopy(_catalog())
    catalog["controls"][0]["verification_ids"] = ["SVT-06"]

    errors = _validate(catalog)

    assert (
        "SEC-01: implemented control needs an implemented verification" in errors
    )


def test_implemented_verification_rejects_non_test_and_missing_files() -> None:
    catalog = deepcopy(_catalog())
    catalog["verification_tests"][0]["test_refs"] = [
        "README.md",
        "tests/test_does_not_exist.py::test_security",
    ]

    errors = _validate(catalog, root=security_traceability_check.ROOT)

    assert "SVT-01: test_ref must be a pytest node under tests/: README.md" in errors
    assert (
        "SVT-01: test_ref file does not exist: tests/test_does_not_exist.py"
        in errors
    )


def test_canonical_implemented_verification_nodes_execute() -> None:
    assert security_traceability_check.run_implemented_verifications(
        _catalog(),
        root=security_traceability_check.ROOT,
    ) == []


def test_uncollected_pytest_node_cannot_certify_a_verification() -> None:
    catalog = deepcopy(_catalog())
    catalog["verification_tests"][0]["test_refs"] = [
        "tests/test_agent_run_external_agent_auth.py::test_does_not_exist"
    ]

    errors = security_traceability_check.run_implemented_verifications(
        catalog,
        root=security_traceability_check.ROOT,
    )

    assert len(errors) == 1
    assert errors[0].startswith(
        "implemented verification pytest execution failed with exit code"
    )
