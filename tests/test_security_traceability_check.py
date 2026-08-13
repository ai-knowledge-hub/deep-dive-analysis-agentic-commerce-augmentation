from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.checks import security_traceability_check


EXPECTED_POLICY_TEST_REFS = [
    "tests/modules/test_agent_policy_enforcer.py::test_policy_rejects_capability_not_in_allow_list",
    "tests/modules/test_agent_policy_enforcer.py::test_policy_rejects_missing_required_input",
    "tests/modules/test_agent_policy_enforcer.py::test_policy_enforces_max_actions_budget",
    "tests/modules/test_agent_policy_enforcer.py::test_policy_enforces_max_variant_runs_budget",
    "tests/modules/test_agent_policy_enforcer.py::test_policy_enforces_max_cost_budget",
    "tests/modules/test_agent_policy_enforcer.py::test_observe_policy_rejects_side_effecting_tool",
    "tests/modules/test_agent_policy_enforcer.py::test_safe_auto_policy_rejects_external_side_effect_execution",
    "tests/test_agent_runs_api.py::test_create_agent_run_enforces_harness_effect_class_boundaries",
    "tests/test_agent_runs_api.py::test_harness_memory_policy_blocks_learning_mutation_plans",
]
EXPECTED_CRITICAL_THREAT_EXCLUSIONS = {
    "THR-01": {
        "automatic_global_harness_promotion",
        "unreviewed_memory_promotion",
    },
    "THR-02": {"write_capable_dynamic_child_delegation"},
    "THR-04": {"public_durable_workflow_and_peer_messages"},
    "THR-05": {"parallel_multi_tenant_worker_execution"},
    "THR-10": {"expanded_connectors_without_secret_egress_ssrf_controls"},
    "THR-16": {"expanded_production_telemetry_and_parallel_context_logging"},
}


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


def _mark_threat_mitigated(catalog: dict, threat_id: str) -> dict:
    threat = next(threat for threat in catalog["threats"] if threat["id"] == threat_id)
    for gap in catalog["implementation_gaps"]:
        if threat_id in gap["threat_ids"]:
            gap["threat_ids"].remove(threat_id)
    threat["status"] = "mitigated"
    threat["gap_ids"] = []
    return threat


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


def test_schema_v1_rejects_unversioned_scope_additions() -> None:
    catalog = deepcopy(_catalog())
    catalog["assets"].append(
        {"id": "ASSET-99", "description": "Unversioned security scope."}
    )

    errors = _validate(catalog)

    assert "assets: schema 1.0 has unexpected ids: ASSET-99" in errors


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


def test_assets_controls_and_detections_require_threat_coverage() -> None:
    catalog = deepcopy(_catalog())
    for threat in catalog["threats"]:
        threat["asset_ids"] = [
            identifier for identifier in threat["asset_ids"] if identifier != "ASSET-10"
        ]
        threat["control_ids"] = [
            identifier for identifier in threat["control_ids"] if identifier != "SEC-15"
        ]
        threat["detection_ids"] = [
            identifier
            for identifier in threat["detection_ids"]
            if identifier != "SDET-09"
        ]

    errors = _validate(catalog)

    assert "ASSET-10: asset has no mapped threat" in errors
    assert "SEC-15: security control has no mapped threat" in errors
    assert "SDET-09: detection requirement has no mapped threat" in errors


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


def test_mitigated_threat_accepts_executable_closure_without_gaps() -> None:
    catalog = deepcopy(_catalog())
    threat = _mark_threat_mitigated(catalog, "THR-04")
    threat["control_ids"] = ["SEC-03", "SEC-04", "SEC-05"]
    threat["verification_ids"] = ["SVT-03", "SVT-04", "SVT-05"]
    threat["closure"] = {
        "approved_by": "security-review-board",
        "closed_at": "2026-08-13",
        "implemented_control_ids": ["SEC-03", "SEC-04", "SEC-05"],
        "verification_ids": ["SVT-03", "SVT-04", "SVT-05"],
    }

    assert _validate(catalog) == []


def test_mitigated_threat_requires_executable_closure_evidence() -> None:
    catalog = deepcopy(_catalog())
    _mark_threat_mitigated(catalog, "THR-04")

    errors = _validate(catalog)

    assert "THR-04: mitigated threat needs closure evidence" in errors


def test_mitigation_closure_cannot_certify_only_a_subset_of_mapped_controls() -> None:
    catalog = deepcopy(_catalog())
    threat = _mark_threat_mitigated(catalog, "THR-04")
    threat["closure"] = {
        "approved_by": "security-review-board",
        "closed_at": "2026-08-13",
        "implemented_control_ids": ["SEC-03", "SEC-04", "SEC-05"],
        "verification_ids": ["SVT-03", "SVT-04", "SVT-05"],
    }

    errors = _validate(catalog)

    assert "THR-04: closure controls must exactly match mapped controls" in errors
    assert (
        "THR-04: closure verifications must exactly match mapped verifications"
        in errors
    )


def test_gap_relationships_must_be_bidirectional() -> None:
    catalog = deepcopy(_catalog())
    catalog["implementation_gaps"][0]["threat_ids"].remove("THR-02")

    errors = _validate(catalog)

    assert "THR-02: gap GAP-01 does not link back to the threat" in errors


def test_critical_active_threat_requires_an_explicit_blocking_decision() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0].pop("blocking_decision")

    errors = _validate(catalog)

    assert "THR-01: blocking_decision must be an object" in errors


def test_critical_active_threat_rejects_free_text_release_decision() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0]["blocking_decision"] = "ship anyway"

    errors = _validate(catalog)

    assert "THR-01: blocking_decision must be an object" in errors


def test_release_decision_requires_exact_capability_gate_controls() -> None:
    catalog = deepcopy(_catalog())
    catalog["threats"][0]["blocking_decision"]["required_control_ids"] = [
        "SEC-11"
    ]

    errors = _validate(catalog)

    assert (
        "THR-01: blocking_decision required_control_ids must exactly match its "
        "capability release gates" in errors
    )


def test_schema_v1_pins_each_critical_threat_release_boundary() -> None:
    assert security_traceability_check.SCHEMA_REQUIRED_CAPABILITY_EXCLUSIONS[
        "1.0"
    ] == {
        threat_id: frozenset(exclusion_ids)
        for threat_id, exclusion_ids in EXPECTED_CRITICAL_THREAT_EXCLUSIONS.items()
    }


@pytest.mark.parametrize(
    ("threat_id", "removed_exclusion_id", "removed_control_id"),
    [
        ("THR-01", "unreviewed_memory_promotion", "SEC-11"),
        ("THR-02", "write_capable_dynamic_child_delegation", "SEC-06"),
        ("THR-04", "public_durable_workflow_and_peer_messages", "SEC-07"),
        ("THR-05", "parallel_multi_tenant_worker_execution", "SEC-09"),
        (
            "THR-10",
            "expanded_connectors_without_secret_egress_ssrf_controls",
            "SEC-14",
        ),
        (
            "THR-16",
            "expanded_production_telemetry_and_parallel_context_logging",
            "SEC-18",
        ),
    ],
)
def test_critical_threat_rejects_coordinated_capability_exclusion_downgrade(
    threat_id: str,
    removed_exclusion_id: str,
    removed_control_id: str,
) -> None:
    catalog = deepcopy(_catalog())
    threat = next(item for item in catalog["threats"] if item["id"] == threat_id)
    decision = threat["blocking_decision"]
    decision["capability_exclusion_ids"].remove(removed_exclusion_id)
    decision["required_control_ids"].remove(removed_control_id)

    errors = _validate(catalog)

    assert (
        f"{threat_id}: blocking_decision capability_exclusion_ids must exactly "
        "match the schema-v1 threat release boundary" in errors
    )


@pytest.mark.parametrize(
    ("field", "downgraded_value"),
    [("severity", "high"), ("exposure", "planned")],
)
def test_release_gated_threat_cannot_downgrade_its_critical_exposure(
    field: str,
    downgraded_value: str,
) -> None:
    catalog = deepcopy(_catalog())
    threat = next(item for item in catalog["threats"] if item["id"] == "THR-01")
    threat[field] = downgraded_value

    errors = _validate(catalog)

    assert (
        "THR-01: schema 1.0 release-gated threat must remain critical and active "
        "until mitigated" in errors
    )


def test_each_planned_threat_control_requires_a_mutually_linked_gap() -> None:
    catalog = deepcopy(_catalog())
    threat = next(item for item in catalog["threats"] if item["id"] == "THR-13")
    gap = next(
        item for item in catalog["implementation_gaps"] if item["id"] == "GAP-03"
    )
    threat["gap_ids"].remove("GAP-03")
    gap["threat_ids"].remove("THR-13")

    errors = _validate(catalog)

    assert (
        "THR-13: planned control SEC-08 needs a mutually linked threat gap"
        in errors
    )


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


def test_svt_02_certifies_the_complete_policy_control() -> None:
    verification = next(
        item for item in _catalog()["verification_tests"] if item["id"] == "SVT-02"
    )

    assert verification["test_refs"] == EXPECTED_POLICY_TEST_REFS


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
