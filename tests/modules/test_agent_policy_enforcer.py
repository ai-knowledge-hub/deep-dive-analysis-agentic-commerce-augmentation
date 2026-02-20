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
