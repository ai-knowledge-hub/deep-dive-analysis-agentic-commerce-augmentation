"""Production recovery command for a governed effect with durable evidence."""

from __future__ import annotations

from typing import Any, Mapping

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    reconcile_authorized_effect,
)
from application.services.agent_runtime.approval_registry import (
    ApprovalRegistryError,
    capability_spec_from_contract_json,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from application.services.agent_runtime.runtime.status import compute_next_run_status
from domain.workflow.approval_execution import canonical_json


class EffectRecoveryError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int = 409,
        mismatches: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.mismatches = mismatches


def reconcile_effect_from_durable_evidence(
    *, deps: AppDeps, run: Mapping[str, Any], action: Mapping[str, Any]
) -> dict[str, Any]:
    """Reconcile one effect without accepting caller-supplied outcome evidence."""

    tenant_id = _identifier("tenant_id", run.get("client_id"))
    workflow_id = _identifier("workflow_id", run.get("id"))
    action_id = _identifier("action_id", action.get("id"))
    if action.get("agent_run_id") != workflow_id:
        raise EffectRecoveryError(
            "action does not belong to the requested workflow",
            code="effect_identity_conflict",
            status_code=404,
            mismatches=("workflow_id",),
        )
    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        action_id=action_id,
    )
    if execution is None:
        raise EffectRecoveryError(
            "no durable effect start exists for reconciliation",
            code="effect_execution_not_found",
            status_code=404,
        )
    execution_id = _identifier("execution_id", execution.get("execution_id"))
    job = deps.validation_jobs.get_job_for_effect_execution(
        approval_effect_execution_id=execution_id,
        client_id=tenant_id,
    )
    if job is None:
        raise EffectRecoveryError(
            "no tenant-scoped provider evidence is bound to this effect start",
            code="effect_receipt_unavailable",
        )

    outputs = {"validation_job_id": _identifier("validation_job_id", job.get("id"))}
    try:
        reconciled = reconcile_authorized_effect(
            deps=deps,
            run=dict(run),
            action=dict(action),
            spec=None,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"validation-job:{outputs['validation_job_id']}",
        )
        frozen_spec = _frozen_capability_spec(execution)
    except ApprovalAuthorizationError as exc:
        raise EffectRecoveryError(
            str(exc), code=exc.code, mismatches=exc.mismatches
        ) from exc
    except ApprovalRegistryError as exc:
        raise EffectRecoveryError(
            str(exc),
            code="effect_start_authority_invalid",
            mismatches=exc.mismatches,
        ) from exc

    updated_action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=tenant_id
    )
    if updated_action is None:
        raise EffectRecoveryError(
            "reconciled action projection is unavailable",
            code="effect_projection_unavailable",
        )
    current_run = deps.agent_runs.get_agent_run(run_id=workflow_id, client_id=tenant_id)
    if current_run is None:
        raise EffectRecoveryError(
            "reconciled run projection is unavailable",
            code="effect_projection_unavailable",
        )
    current_status = str(current_run.get("status") or "").strip().lower()
    preserves_control_plane_state = current_status in {
        "canceled",
        "cancelled",
        "completed",
        "paused",
    }
    next_status = (
        current_status
        if preserves_control_plane_state
        else compute_next_run_status(deps=deps, run=current_run, run_id=workflow_id)
    )
    updated_run = deps.agent_runs.restore_agent_run_after_effect_reconciliation(
        run_id=workflow_id,
        client_id=tenant_id,
        state=(
            current_run.get("state")
            if preserves_control_plane_state
            else frozen_spec.next_state or current_run.get("state")
        ),
        status=next_status,
    )
    return {
        "effect_execution": reconciled,
        "validation_job": job,
        "action": updated_action,
        "run": updated_run or current_run,
    }


def _frozen_capability_spec(execution: Mapping[str, Any]):
    snapshot = execution.get("authorization_snapshot")
    if (
        type(snapshot) is not dict
        or type(snapshot.get("capability_contract")) is not dict
    ):
        raise ApprovalRegistryError(
            "effect start has no frozen capability contract",
            mismatches=("capability_contract",),
        )
    return capability_spec_from_contract_json(
        canonical_json(snapshot["capability_contract"])
    )


def _identifier(field: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise EffectRecoveryError(
            f"{field} must be a canonical identifier",
            code="effect_identity_invalid",
            status_code=400,
            mismatches=(field,),
        )
    return value


__all__ = [
    "EffectRecoveryError",
    "reconcile_effect_from_durable_evidence",
]
