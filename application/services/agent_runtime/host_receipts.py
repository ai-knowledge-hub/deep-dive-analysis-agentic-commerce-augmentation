"""Host completion evidence for the closed, bounded workspace capabilities.

Only the executing host can attest a new local completion. Recovery callers
must supply evidence already committed by that host; uncertain local effects
remain held rather than accepting caller-authored outputs or executing again.
"""

from typing import Any, Mapping

from application.ports.deps import AppDeps
from application.services.agent_runtime.registry import CapabilitySpec
from domain.workflow.approval import ApprovalBinding


HOST_RECEIPT_CAPABILITIES = frozenset(
    {
        "freeze_retrieval_protocol",
        "run_control_baseline",
        "seed_hypotheses",
        "generate_variants",
        "run_variant",
        "review_validation_readiness",
        "update_posterior_and_decisions",
        "recommend_next_action",
    }
)


def host_receipt_id(
    *,
    deps: AppDeps,
    spec: CapabilitySpec,
    binding: ApprovalBinding,
    effect_execution_id: str,
    outputs: Mapping[str, Any],
    outputs_hash: str,
    receipt_id: str | None,
    host_completed: bool,
) -> str | None:
    if spec.name not in HOST_RECEIPT_CAPABILITIES or spec.effect_class not in {
        "read",
        "recommend",
        "write_low_risk",
    }:
        return None
    expected_id = f"host-completion:{effect_execution_id}"
    if receipt_id is not None and receipt_id != expected_id:
        return None
    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=binding.tenant_id,
        workflow_id=binding.workflow_id,
        action_id=binding.action_id,
    )
    if execution is None or any(
        execution.get(field) != expected
        for field, expected in {
            "execution_id": effect_execution_id,
            "approval_id": binding.approval_id,
            "effect_idempotency_key": binding.effect_idempotency_key,
        }.items()
    ):
        return None
    if host_completed and execution.get("status") == "started":
        return expected_id
    action = deps.agent_actions.get_agent_action(action_id=binding.action_id)
    if (
        execution.get("status") == "succeeded"
        and execution.get("receipt_id") == expected_id
        and execution.get("outputs_hash") == outputs_hash
        and action is not None
        and action.get("agent_run_id") == binding.workflow_id
        and action.get("receipt_id") == expected_id
        and action.get("outputs_hash") == outputs_hash
        and action.get("outputs") == dict(outputs)
    ):
        return expected_id
    return None
