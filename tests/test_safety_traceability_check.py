from __future__ import annotations

from copy import deepcopy

from scripts.checks import safety_traceability_check


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


def test_implemented_verification_must_point_to_an_existing_test() -> None:
    catalog = deepcopy(_catalog())
    catalog["verification_tests"][0]["test_ref"] = "tests/does-not-exist.py"

    errors = safety_traceability_check.validate_catalog(
        catalog,
        root=safety_traceability_check.ROOT,
    )

    assert "VT-01: test_ref does not exist: tests/does-not-exist.py" in errors
