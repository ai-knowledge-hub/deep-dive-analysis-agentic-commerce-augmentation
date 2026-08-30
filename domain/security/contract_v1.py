"""Immutable authority for the agent-runtime beta security boundary."""

from __future__ import annotations

from dataclasses import dataclass


SECURITY_CONTRACT_VERSION = "1.0"
BLOCKING_DISPOSITION = "excluded_until_required_controls_implemented"
AUTHORIZED_CLOSURE_AUTHORITY_IDS = frozenset({"security-review-board"})
IMPLEMENTED_CONTROL_IDS = frozenset(
    {"SEC-01", "SEC-02", "SEC-03", "SEC-04", "SEC-05", "SEC-06"}
)
IMPLEMENTED_VERIFICATION_TEST_REFS = {
    "SVT-01": (
        "tests/test_agent_run_external_agent_auth.py::test_bearer_principal_cannot_use_parameter_tenancy_for_human_run",
        "tests/test_agent_run_external_agent_auth.py::test_create_external_agent_run_requires_bearer_principal",
        "tests/test_agent_run_external_agent_auth.py::test_agent_principal_token_requires_exp_claim",
        "tests/test_agent_run_external_agent_auth.py::test_inactive_external_principal_token_is_rejected",
        "tests/test_agent_run_external_agent_auth.py::test_bearer_token_cannot_self_assert_agent_profile",
        "tests/test_agent_runs_api.py::test_create_agent_run_rejects_client_scope_mismatch_for_machine_principal",
    ),
    "SVT-02": (
        "tests/modules/test_agent_policy_enforcer.py::test_beta_release_policy_classifies_every_runtime_capability",
        "tests/modules/test_agent_policy_enforcer.py::test_beta_release_policy_rejects_coordinated_disposition_downgrade",
        "tests/modules/test_agent_policy_enforcer.py::test_policy_rejects_capability_not_in_allow_list",
        "tests/modules/test_agent_policy_enforcer.py::test_policy_rejects_beta_blocked_capability_before_execution",
        "tests/modules/test_agent_policy_enforcer.py::test_policy_rejects_missing_required_input",
        "tests/modules/test_agent_policy_enforcer.py::test_policy_enforces_max_actions_budget",
        "tests/modules/test_agent_policy_enforcer.py::test_policy_enforces_max_variant_runs_budget",
        "tests/modules/test_agent_policy_enforcer.py::test_policy_enforces_max_cost_budget",
        "tests/modules/test_agent_policy_enforcer.py::test_observe_policy_rejects_side_effecting_tool",
        "tests/modules/test_agent_policy_enforcer.py::test_safe_auto_policy_rejects_external_side_effect_execution",
        "tests/modules/test_agent_runtime_service.py::test_step_once_rechecks_beta_release_gate_before_capability_effect",
        "tests/test_agent_runs_api.py::test_create_agent_run_rejects_beta_blocked_production_capability",
        "tests/test_agent_runs_api.py::test_create_agent_run_enforces_harness_effect_class_boundaries",
        "tests/test_agent_runs_api.py::test_harness_memory_policy_blocks_learning_mutation_plans",
    ),
    "SVT-03": (
        "tests/test_external_agent_jobs_api.py::test_external_agent_job_create_is_idempotent_and_status_is_scoped",
        "tests/test_external_agent_jobs_api.py::test_external_agent_job_rejects_idempotency_payload_mismatch",
        "tests/test_external_agent_jobs_api.py::test_external_agent_job_requires_machine_auth_and_scopes",
        "tests/test_external_agent_jobs_api.py::test_external_agent_job_checks_scopes_for_allowed_capabilities",
    ),
    "SVT-04": (
        "tests/test_validation_provider_callback_security.py::test_provider_callback_valid_once_then_replay_rejected",
        "tests/test_validation_provider_callback_security.py::test_provider_callback_rejects_wrong_provider_run_id",
        "tests/test_validation_provider_callback_security.py::test_provider_callback_rejects_expired_token",
    ),
    "SVT-05": (
        "tests/test_external_agent_jobs_api.py::test_external_agent_job_receipt_is_signed_and_tracks_run_status",
        "tests/test_agent_runs_api.py::test_operator_command_endpoint_records_receipt_and_delegates_approval",
    ),
    "SVT-06": (
        "tests/modules/test_approval_effect_authorization.py::test_governed_effect_cannot_execute_from_action_status_alone",
        "tests/modules/test_approval_effect_authorization.py::test_exact_approval_is_consumed_fulfilled_and_linked_to_receipt",
        "tests/modules/test_approval_effect_authorization.py::test_every_mutable_binding_dimension_fails_closed",
        "tests/modules/test_approval_effect_authorization.py::test_expiry_is_checked_again_at_execution_time",
        "tests/modules/test_approval_effect_authorization.py::test_approval_cannot_cross_tenant_or_action_scope",
        "tests/modules/test_approval_effect_authorization.py::test_superseded_approval_stays_terminal_at_execution_boundary",
        "tests/modules/test_approval_effect_authorization.py::test_revocation_wins_when_it_commits_before_pre_effect_authorization",
        "tests/modules/test_approval_effect_authorization.py::test_pre_effect_commit_wins_race_and_prevents_late_revocation",
        "tests/modules/test_approval_effect_authorization.py::test_effect_identity_and_outcome_state_cannot_be_rewritten",
        "tests/modules/test_approval_effect_authorization.py::test_uncertain_same_effect_reconciles_after_restart_without_second_execution",
        "tests/modules/test_approval_effect_authorization.py::test_same_effect_identity_cannot_be_reused_by_a_second_action",
    ),
}


@dataclass(frozen=True)
class ThreatClosureRequirement:
    control_ids: frozenset[str]
    verification_ids: frozenset[str]


@dataclass(frozen=True)
class BlockedCapabilityRequirement:
    capability_id: str
    tool_id: str
    effect_class: str
    release_gate_id: str
    required_control_ids: frozenset[str]
    required_verification_ids: frozenset[str]


CAPABILITY_RELEASE_GATES = {
    "autonomous_production_publishing": frozenset({"SEC-06", "SEC-16"}),
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

REQUIRED_CAPABILITY_EXCLUSIONS_BY_THREAT = {
    "THR-01": frozenset(
        {"automatic_global_harness_promotion", "unreviewed_memory_promotion"}
    ),
    "THR-02": frozenset(
        {
            "autonomous_production_publishing",
            "write_capable_dynamic_child_delegation",
        }
    ),
    "THR-04": frozenset({"public_durable_workflow_and_peer_messages"}),
    "THR-05": frozenset({"parallel_multi_tenant_worker_execution"}),
    "THR-10": frozenset({"expanded_connectors_without_secret_egress_ssrf_controls"}),
    "THR-16": frozenset({"expanded_production_telemetry_and_parallel_context_logging"}),
}

THREAT_CLOSURE_REQUIREMENTS = {
    "THR-01": ThreatClosureRequirement(
        frozenset({"SEC-02", "SEC-09", "SEC-10", "SEC-11", "SEC-12"}),
        frozenset({"SVT-02", "SVT-09", "SVT-10", "SVT-11", "SVT-12"}),
    ),
    "THR-02": ThreatClosureRequirement(
        frozenset({"SEC-01", "SEC-02", "SEC-06", "SEC-09", "SEC-16"}),
        frozenset({"SVT-01", "SVT-02", "SVT-06", "SVT-09", "SVT-16"}),
    ),
    "THR-03": ThreatClosureRequirement(
        frozenset({"SEC-02", "SEC-06", "SEC-07", "SEC-18"}),
        frozenset({"SVT-02", "SVT-06", "SVT-07", "SVT-18"}),
    ),
    "THR-04": ThreatClosureRequirement(
        frozenset(
            {
                "SEC-03",
                "SEC-04",
                "SEC-05",
                "SEC-07",
                "SEC-08",
                "SEC-18",
                "SEC-20",
            }
        ),
        frozenset(
            {
                "SVT-03",
                "SVT-04",
                "SVT-05",
                "SVT-07",
                "SVT-08",
                "SVT-18",
                "SVT-20",
            }
        ),
    ),
    "THR-05": ThreatClosureRequirement(
        frozenset(
            {
                "SEC-01",
                "SEC-03",
                "SEC-09",
                "SEC-13",
                "SEC-16",
                "SEC-19",
                "SEC-20",
            }
        ),
        frozenset(
            {
                "SVT-01",
                "SVT-03",
                "SVT-09",
                "SVT-13",
                "SVT-16",
                "SVT-19",
                "SVT-20",
            }
        ),
    ),
    "THR-06": ThreatClosureRequirement(
        frozenset({"SEC-07", "SEC-08", "SEC-16", "SEC-17", "SEC-20"}),
        frozenset({"SVT-07", "SVT-08", "SVT-16", "SVT-17", "SVT-20"}),
    ),
    "THR-07": ThreatClosureRequirement(
        frozenset({"SEC-09", "SEC-10", "SEC-20"}),
        frozenset({"SVT-09", "SVT-10", "SVT-20"}),
    ),
    "THR-08": ThreatClosureRequirement(
        frozenset({"SEC-10", "SEC-11", "SEC-12"}),
        frozenset({"SVT-10", "SVT-11", "SVT-12"}),
    ),
    "THR-09": ThreatClosureRequirement(
        frozenset({"SEC-12", "SEC-15", "SEC-18"}),
        frozenset({"SVT-12", "SVT-15", "SVT-18"}),
    ),
    "THR-10": ThreatClosureRequirement(
        frozenset({"SEC-01", "SEC-09", "SEC-13", "SEC-14", "SEC-19"}),
        frozenset({"SVT-01", "SVT-09", "SVT-13", "SVT-14", "SVT-19"}),
    ),
    "THR-11": ThreatClosureRequirement(
        frozenset({"SEC-13", "SEC-14", "SEC-16", "SEC-19"}),
        frozenset({"SVT-13", "SVT-14", "SVT-16", "SVT-19"}),
    ),
    "THR-12": ThreatClosureRequirement(
        frozenset({"SEC-12", "SEC-15"}),
        frozenset({"SVT-12", "SVT-15"}),
    ),
    "THR-13": ThreatClosureRequirement(
        frozenset({"SEC-02", "SEC-08", "SEC-16", "SEC-17", "SEC-19", "SEC-20"}),
        frozenset({"SVT-02", "SVT-08", "SVT-16", "SVT-17", "SVT-19", "SVT-20"}),
    ),
    "THR-14": ThreatClosureRequirement(
        frozenset({"SEC-06", "SEC-07", "SEC-08", "SEC-17"}),
        frozenset({"SVT-06", "SVT-07", "SVT-08", "SVT-17"}),
    ),
    "THR-15": ThreatClosureRequirement(
        frozenset({"SEC-03", "SEC-04", "SEC-05", "SEC-07", "SEC-18"}),
        frozenset({"SVT-03", "SVT-04", "SVT-05", "SVT-07", "SVT-18"}),
    ),
    "THR-16": ThreatClosureRequirement(
        frozenset({"SEC-09", "SEC-13", "SEC-18", "SEC-19", "SEC-20"}),
        frozenset({"SVT-09", "SVT-13", "SVT-18", "SVT-19", "SVT-20"}),
    ),
    "THR-17": ThreatClosureRequirement(
        frozenset({"SEC-14", "SEC-16", "SEC-17", "SEC-19"}),
        frozenset({"SVT-14", "SVT-16", "SVT-17", "SVT-19"}),
    ),
}

REQUIRED_BLOCKED_CAPABILITIES = {
    item.capability_id: item
    for item in (
        BlockedCapabilityRequirement(
            capability_id="promote_variant_prod",
            tool_id="promotion.promote_prod",
            effect_class="write_high_risk",
            release_gate_id="autonomous_production_publishing",
            required_control_ids=frozenset({"SEC-06", "SEC-16"}),
            required_verification_ids=frozenset({"SVT-06", "SVT-16"}),
        ),
        BlockedCapabilityRequirement(
            capability_id="publish_copy_revision",
            tool_id="copy.publish_revision",
            effect_class="write_high_risk",
            release_gate_id="autonomous_production_publishing",
            required_control_ids=frozenset({"SEC-06", "SEC-16"}),
            required_verification_ids=frozenset({"SVT-06", "SVT-16"}),
        ),
    )
}


def required_blocked_capabilities_for_gate(
    release_gate_id: str,
) -> tuple[BlockedCapabilityRequirement, ...]:
    return tuple(
        requirement
        for requirement in REQUIRED_BLOCKED_CAPABILITIES.values()
        if requirement.release_gate_id == release_gate_id
    )


__all__ = [
    "AUTHORIZED_CLOSURE_AUTHORITY_IDS",
    "BLOCKING_DISPOSITION",
    "CAPABILITY_RELEASE_GATES",
    "IMPLEMENTED_CONTROL_IDS",
    "IMPLEMENTED_VERIFICATION_TEST_REFS",
    "REQUIRED_BLOCKED_CAPABILITIES",
    "REQUIRED_CAPABILITY_EXCLUSIONS_BY_THREAT",
    "SECURITY_CONTRACT_VERSION",
    "THREAT_CLOSURE_REQUIREMENTS",
    "BlockedCapabilityRequirement",
    "ThreatClosureRequirement",
    "required_blocked_capabilities_for_gate",
]
