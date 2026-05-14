from __future__ import annotations

from typing import Any, Dict

_DEFAULT_AGENT_PROFILE_HARNESSES = {
    "buyer-assistant-v1": "safe_autonomy_b2b",
    "external-buyer-assistant": "safe_autonomy_b2b",
    "external_agent": "safe_autonomy_b2b",
    "internal_agent": "operator_supervised",
    "human": "operator_supervised",
}


def list_static_agent_profile_defaults() -> list[Dict[str, Any]]:
    return [
        {
            "id": "human",
            "principal_type": "human",
            "principal_id": "human:default",
            "name": "Human Operator",
            "default_harness_id": "operator_supervised",
            "default_policy_profile_id": "human_approval_required",
            "risk_tier": "operator_reviewed",
            "channel_type": "web_ui",
            "source": "static_code",
        },
        {
            "id": "internal_agent",
            "principal_type": "internal_agent",
            "principal_id": "internal_agent:default",
            "name": "Internal Agent",
            "default_harness_id": "operator_supervised",
            "default_policy_profile_id": "human_approval_required",
            "risk_tier": "operator_reviewed",
            "channel_type": "runtime",
            "source": "static_code",
        },
        {
            "id": "buyer-assistant-v1",
            "principal_type": "external_agent",
            "principal_id": "external_agent:buyer-assistant-v1",
            "name": "Buyer Assistant v1",
            "default_harness_id": "safe_autonomy_b2b",
            "default_policy_profile_id": "safe_auto",
            "risk_tier": "bounded_low_risk",
            "channel_type": "external_job_api",
            "source": "static_code",
        },
        {
            "id": "external-buyer-assistant",
            "principal_type": "external_agent",
            "principal_id": "external_agent:buyer-assistant-v1",
            "name": "External Buyer Assistant",
            "default_harness_id": "safe_autonomy_b2b",
            "default_policy_profile_id": "safe_auto",
            "risk_tier": "bounded_low_risk",
            "channel_type": "external_job_api",
            "source": "static_code",
        },
    ]


def list_static_harness_profiles() -> list[Dict[str, Any]]:
    return [
        {
            "id": "operator_supervised",
            "name": "Operator Supervised",
            "description": "Plan-first harness for human-reviewed execution.",
            "default_run_mode": "plan_only",
            "default_policy_profile_id": "human_approval_required",
            "allowed_run_modes": ["plan_only"],
            "allowed_policy_profile_ids": ["human_approval_required"],
            "planner_mode": "operator_review",
            "retry_strategy": "operator_confirmed",
            "fallback_order": ["operator_chat", "manual_intervention"],
            "approval_strategy": "human_required",
            "memory_policy": "write_learnings_after_review",
            "stopping_conditions": ["all_actions_decided", "operator_pause", "policy_block"],
        },
        {
            "id": "safe_autonomy_b2b",
            "name": "Safe Autonomy B2B",
            "description": "Bounded external-agent harness for approved low-risk work.",
            "default_run_mode": "auto_execute_safe",
            "default_policy_profile_id": "safe_auto",
            "allowed_run_modes": ["auto_execute_safe"],
            "allowed_policy_profile_ids": ["safe_auto"],
            "planner_mode": "bounded_single_or_workflow",
            "retry_strategy": "last_safe_checkpoint",
            "fallback_order": ["registry_recovery_template", "operator_intervention"],
            "approval_strategy": "auto_low_risk_human_governed_high_risk",
            "memory_policy": "write_execution_receipts_and_learnings",
            "stopping_conditions": [
                "budget_exhausted",
                "policy_block",
                "external_side_effect_required",
                "all_actions_completed",
            ],
        },
        {
            "id": "observe_only",
            "name": "Observe Only",
            "description": "Read/recommend-only harness for audit and explanation flows.",
            "default_run_mode": "plan_only",
            "default_policy_profile_id": "observe",
            "allowed_run_modes": ["plan_only"],
            "allowed_policy_profile_ids": ["observe"],
            "planner_mode": "inspect_and_recommend",
            "retry_strategy": "none",
            "fallback_order": ["operator_chat"],
            "approval_strategy": "read_only",
            "memory_policy": "no_mutation",
            "stopping_conditions": ["recommendation_produced", "operator_pause"],
        },
    ]


def list_harness_profiles() -> list[Dict[str, Any]]:
    return list_static_harness_profiles()


def get_harness_profile(harness_id: str | None) -> Dict[str, Any] | None:
    normalized = str(harness_id or "").strip()
    if not normalized:
        return None
    for profile in list_harness_profiles():
        if profile["id"] == normalized:
            return profile
    return None


def harness_profile_supported(harness_id: str | None) -> bool:
    if not harness_id:
        return True
    return get_harness_profile(harness_id) is not None


def default_harness_id_for_agent_profile(
    *, agent_profile_id: str | None, principal_type: str | None
) -> str:
    profile_key = str(agent_profile_id or "").strip()
    if profile_key in _DEFAULT_AGENT_PROFILE_HARNESSES:
        return _DEFAULT_AGENT_PROFILE_HARNESSES[profile_key]
    principal_key = str(principal_type or "human").strip()
    return _DEFAULT_AGENT_PROFILE_HARNESSES.get(principal_key, "operator_supervised")
