"""Governed lab-promotion commit boundary."""

from __future__ import annotations

from typing import Any, Mapping

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
    experiment: Mapping[str, Any],
    source_metric_id: object,
    metric_payload: Mapping[str, Any],
    reason: str,
    posterior: Any,
    decision_action: object,
    promotion_tier: object,
    confidence: float,
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
            brand_id=experiment.get("brand_id"),
            product_id=experiment.get("product_id"),
            reason=reason,
            source_metric_id=_required_identifier("source_metric_id", source_metric_id),
            posterior=posterior,
            decision_action=(
                str(decision_action) if decision_action is not None else None
            ),
            promotion_tier=str(promotion_tier or "lab"),
            policy_version=_optional_text(
                metric_payload.get("decision_policy_version")
            ),
            uncertainty=max(0.0, min(1.0, 1.0 - confidence)),
            expected_gain=confidence,
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


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _workflow_id_for_action(*, deps: AppDeps, action_id: str, client_id: str) -> str:
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=client_id
    )
    if action is None:
        raise CapabilityExecutionError("governed lab-promotion action is unavailable")
    return _required_identifier("workflow_id", action.get("agent_run_id"))


__all__ = ["commit_governed_lab_promotion"]
