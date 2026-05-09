from __future__ import annotations

import pytest

from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import get_capability_spec


def test_policy_rejects_capability_not_in_allow_list():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("run_variant")
    assert spec is not None
    with pytest.raises(PolicyError):
        enforcer.validate_action_execution(
            run={"allowed_capabilities": ["seed_hypotheses"], "budgets": {}},
            action={"id": "a1"},
            spec=spec,
            all_actions=[],
            inputs={"experiment_id": "exp-1"},
        )


def test_policy_rejects_missing_required_input():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("run_variant")
    assert spec is not None
    with pytest.raises(PolicyError):
        enforcer.validate_action_execution(
            run={"allowed_capabilities": ["run_variant"], "budgets": {}},
            action={"id": "a1"},
            spec=spec,
            all_actions=[],
            inputs={},
        )


def test_policy_enforces_max_actions_budget():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("seed_hypotheses")
    assert spec is not None
    with pytest.raises(PolicyError):
        enforcer.validate_action_execution(
            run={
                "allowed_capabilities": ["seed_hypotheses"],
                "budgets": {"max_actions": 1},
            },
            action={"id": "a2"},
            spec=spec,
            all_actions=[{"status": "executed", "capability_name": "seed_hypotheses"}],
            inputs={"experiment_id": "exp-1"},
        )


def test_policy_enforces_max_variant_runs_budget():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("run_variant")
    assert spec is not None
    with pytest.raises(PolicyError):
        enforcer.validate_action_execution(
            run={
                "allowed_capabilities": ["run_variant"],
                "budgets": {"max_variant_runs": 1},
            },
            action={"id": "a2"},
            spec=spec,
            all_actions=[{"status": "executed", "capability_name": "run_variant"}],
            inputs={"experiment_id": "exp-1"},
        )


def test_policy_enforces_max_cost_budget():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("seed_hypotheses")
    assert spec is not None
    with pytest.raises(PolicyError):
        enforcer.validate_action_execution(
            run={
                "allowed_capabilities": ["seed_hypotheses"],
                "budgets": {"max_cost_usd": 1.5},
            },
            action={"id": "a2"},
            spec=spec,
            all_actions=[
                {
                    "status": "executed",
                    "capability_name": "request_synthetic_validation",
                    "outputs": {"cost_usd": 1.0},
                },
                {
                    "status": "executed",
                    "capability_name": "run_variant",
                    "outputs": {
                        "costs": [{"validation_cost_usd": 0.3}],
                        "meta": {"estimated_cost_usd": 0.2},
                    },
                },
            ],
            inputs={"experiment_id": "exp-1"},
        )


def test_observe_policy_rejects_side_effecting_tool():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("run_variant")
    assert spec is not None
    with pytest.raises(PolicyError):
        enforcer.validate_action_execution(
            run={
                "allowed_capabilities": ["run_variant"],
                "policy_profile_id": "observe",
                "budgets": {},
            },
            action={"id": "a3", "tool_id": spec.tool_id},
            spec=spec,
            all_actions=[],
            inputs={"experiment_id": "exp-1"},
        )


def test_safe_auto_policy_rejects_external_side_effect_execution():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("request_synthetic_validation")
    assert spec is not None
    with pytest.raises(PolicyError, match="forbids auto execution"):
        enforcer.validate_action_execution(
            run={
                "allowed_capabilities": ["request_synthetic_validation"],
                "policy_profile_id": "safe_auto",
                "budgets": {},
            },
            action={"id": "a4", "tool_id": spec.tool_id},
            spec=spec,
            all_actions=[],
            inputs={"experiment_id": "exp-1"},
        )


def test_safe_auto_policy_rejects_governed_approval_for_high_risk_tool():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("publish_copy_revision")
    assert spec is not None
    with pytest.raises(PolicyError, match="requires governed approval"):
        enforcer.validate_action_approval(
            run={
                "allowed_capabilities": ["publish_copy_revision"],
                "policy_profile_id": "safe_auto",
                "budgets": {},
            },
            action={"id": "a5", "tool_id": spec.tool_id},
            spec=spec,
            inputs={"experiment_id": "exp-1"},
        )


def test_human_approval_required_allows_low_risk_approval_not_execution():
    enforcer = PolicyEnforcer()
    spec = get_capability_spec("run_variant")
    assert spec is not None
    run = {
        "allowed_capabilities": ["run_variant"],
        "policy_profile_id": "human_approval_required",
        "budgets": {},
    }
    enforcer.validate_action_approval(
        run=run,
        action={"id": "a6", "tool_id": spec.tool_id},
        spec=spec,
        inputs={"experiment_id": "exp-1"},
    )
    with pytest.raises(PolicyError, match="forbids auto execution"):
        enforcer.validate_action_execution(
            run=run,
            action={"id": "a6", "tool_id": spec.tool_id},
            spec=spec,
            all_actions=[],
            inputs={"experiment_id": "exp-1"},
        )
