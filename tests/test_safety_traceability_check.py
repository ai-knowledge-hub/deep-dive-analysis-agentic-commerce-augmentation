from __future__ import annotations

from copy import deepcopy

from scripts.checks import safety_traceability_check


EXPECTED_LIFECYCLE_TEST_REFS = [
    "tests/modules/test_workflow_lifecycle.py::test_allowed_transitions_match_the_complete_contract",
    "tests/modules/test_workflow_lifecycle.py::test_every_declared_transition_is_executable",
    "tests/modules/test_workflow_lifecycle.py::test_every_undeclared_transition_is_rejected",
    "tests/modules/test_workflow_lifecycle.py::test_terminal_statuses_are_explicit_and_have_no_outgoing_transitions",
]


def _catalog() -> dict:
    return safety_traceability_check.load_catalog()


def test_canonical_safety_catalog_is_fully_traceable() -> None:
    errors = safety_traceability_check.validate_catalog(
        _catalog(),
        root=safety_traceability_check.ROOT,
    )

    assert errors == []


def test_uca_requires_control_feedback_and_verification_mappings() -> None:
    catalog = deepcopy(_catalog())
    catalog["unsafe_control_actions"][0]["control_ids"] = []
    catalog["unsafe_control_actions"][0]["feedback_ids"] = []
    catalog["unsafe_control_actions"][0]["verification_ids"] = []

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "UCA-01: control_ids must not be empty" in errors
    assert "UCA-01: feedback_ids must not be empty" in errors
    assert "UCA-01: verification_ids must not be empty" in errors


def test_every_control_action_requires_all_four_uca_categories() -> None:
    catalog = deepcopy(_catalog())
    catalog["unsafe_control_actions"] = [
        uca for uca in catalog["unsafe_control_actions"] if uca["id"] != "UCA-04"
    ]

    errors = safety_traceability_check.validate_catalog(catalog)

    assert any(
        error.startswith("CA-01: missing UCA categories")
        and "stopped_too_soon_or_applied_too_long" in error
        for error in errors
    )


def test_schema_v1_rejects_empty_safety_sections() -> None:
    catalog = deepcopy(_catalog())
    for section in safety_traceability_check.SECTIONS:
        catalog[section] = []

    errors = safety_traceability_check.validate_catalog(catalog)

    assert any(
        error.startswith("control_actions: schema 1.0 missing required ids:")
        for error in errors
    )
    assert any(
        error.startswith("unsafe_control_actions: schema 1.0 missing required ids:")
        for error in errors
    )


def test_schema_v1_rejects_removing_ca_07_and_its_ucas() -> None:
    catalog = deepcopy(_catalog())
    catalog["control_actions"] = [
        action for action in catalog["control_actions"] if action["id"] != "CA-07"
    ]
    catalog["unsafe_control_actions"] = [
        uca
        for uca in catalog["unsafe_control_actions"]
        if uca["control_action_id"] != "CA-07"
    ]

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "control_actions: schema 1.0 missing required ids: CA-07" in errors
    assert any(
        error.startswith("unsafe_control_actions: schema 1.0 missing required ids:")
        and "UCA-25" in error
        and "UCA-28" in error
        for error in errors
    )


def test_catalog_ids_are_globally_unique() -> None:
    catalog = deepcopy(_catalog())
    catalog["feedback_requirements"][0]["id"] = "H-01"

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "duplicate id across catalog: H-01" in errors


def test_references_must_resolve() -> None:
    catalog = deepcopy(_catalog())
    catalog["unsafe_control_actions"][0]["hazard_ids"] = ["H-404"]

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "UCA-01: hazard_ids references unknown H-404" in errors


def test_every_uca_hazard_requires_a_mapped_constraint() -> None:
    catalog = deepcopy(_catalog())
    catalog["unsafe_control_actions"][0]["hazard_ids"].append("H-09")

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "UCA-01: hazard H-09 is not covered by a mapped constraint" in errors


def test_planned_items_require_owner_and_target_phase() -> None:
    catalog = deepcopy(_catalog())
    catalog["controls"][1].pop("owner")
    catalog["verification_tests"][1].pop("target_phase")

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "CTRL-02: planned control needs owner" in errors
    assert "VT-02: planned verification needs target_phase" in errors


def test_implemented_control_requires_an_implemented_verification() -> None:
    catalog = deepcopy(_catalog())
    catalog["controls"][0]["verification_ids"] = ["VT-02"]

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "CTRL-01: implemented control needs an implemented verification" in errors


def test_implemented_verification_rejects_an_existing_non_test_file() -> None:
    catalog = deepcopy(_catalog())
    catalog["verification_tests"][0]["test_refs"] = ["README.md"]

    errors = safety_traceability_check.validate_catalog(
        catalog,
        root=safety_traceability_check.ROOT,
    )

    assert "VT-01: test_ref must be a pytest node under tests/: README.md" in errors


def test_implemented_verification_requires_an_existing_test_file() -> None:
    catalog = deepcopy(_catalog())
    catalog["verification_tests"][0]["test_refs"] = [
        "tests/test_does_not_exist.py::test_verification"
    ]

    errors = safety_traceability_check.validate_catalog(
        catalog,
        root=safety_traceability_check.ROOT,
    )

    assert "VT-01: test_ref file does not exist: tests/test_does_not_exist.py" in errors


def test_implemented_verification_requires_at_least_one_test_node() -> None:
    catalog = deepcopy(_catalog())
    catalog["verification_tests"][0]["test_refs"] = []

    errors = safety_traceability_check.validate_catalog(catalog)

    assert "VT-01: implemented verification needs non-empty test_refs" in errors


def test_vt_01_declares_the_complete_lifecycle_verification() -> None:
    verification = _catalog()["verification_tests"][0]

    assert verification["test_refs"] == EXPECTED_LIFECYCLE_TEST_REFS


def test_canonical_implemented_verification_nodes_execute() -> None:
    errors = safety_traceability_check.run_implemented_verifications(
        _catalog(),
        root=safety_traceability_check.ROOT,
    )

    assert errors == []


def test_uncollected_pytest_node_cannot_certify_a_verification() -> None:
    catalog = deepcopy(_catalog())
    catalog["verification_tests"][0]["test_refs"] = [
        "tests/modules/test_workflow_lifecycle.py::test_does_not_exist"
    ]

    errors = safety_traceability_check.run_implemented_verifications(
        catalog,
        root=safety_traceability_check.ROOT,
    )

    assert len(errors) == 1
    assert errors[0].startswith(
        "implemented verification pytest execution failed with exit code"
    )
