"""Governed lab-promotion commit boundary."""

from __future__ import annotations

from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities.types import (
    CapabilityContext,
    CapabilityExecutionError,
)


def commit_governed_lab_promotion(
    *,
    deps: AppDeps,
    context: CapabilityContext,
    experiment_id: str,
    variant_id: str,
    source_metric_id: object,
    reason: str,
) -> dict[str, Any]:
    """Atomically persist the local effect and exact durable receipt."""

    action_id = _required_identifier("agent_action_id", context.agent_action_id)
    try:
        receipt = deps.governed_effect_receipts.commit_lab_promotion(
            tenant_id=context.client_id,
            workflow_id=_workflow_id_for_action(
                deps=deps, action_id=action_id, client_id=context.client_id
            ),
            action_id=action_id,
            approval_id=_required_identifier("approval_id", context.approval_id),
            effect_idempotency_key=_required_identifier(
                "effect_idempotency_key", context.effect_idempotency_key
            ),
            approval_effect_execution_id=_required_identifier(
                "approval_effect_execution_id",
                context.approval_effect_execution_id,
            ),
            experiment_id=experiment_id,
            variant_id=variant_id,
            reason=reason,
            source_metric_id=_required_identifier("source_metric_id", source_metric_id),
        )
    except ValueError as exc:
        raise CapabilityExecutionError(str(exc)) from exc
    return dict(receipt["outputs"])


def _required_identifier(field: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise CapabilityExecutionError(
            f"governed lab promotion requires canonical {field}"
        )
    return value


def _workflow_id_for_action(*, deps: AppDeps, action_id: str, client_id: str) -> str:
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=client_id
    )
    if action is None:
        raise CapabilityExecutionError("governed lab-promotion action is unavailable")
    return _required_identifier("workflow_id", action.get("agent_run_id"))


__all__ = ["commit_governed_lab_promotion"]
