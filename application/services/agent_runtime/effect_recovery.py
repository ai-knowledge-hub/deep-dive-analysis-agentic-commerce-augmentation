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
from application.services.agent_runtime.runtime.status import (
    derive_next_run_status,
    record_stopping_decision,
)
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


_PROJECTION_RESTORE_ATTEMPTS = 5


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
    try:
        frozen_spec = _frozen_capability_spec(execution)
        outputs, receipt_id, evidence = _durable_evidence(
            deps=deps,
            tenant_id=tenant_id,
            execution_id=execution_id,
            capability_name=frozen_spec.name,
        )
        reconciled = reconcile_authorized_effect(
            deps=deps,
            run=dict(run),
            action=dict(action),
            spec=None,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=receipt_id,
        )
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
    updated_run = _restore_run_projection(
        deps=deps,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        next_state=frozen_spec.next_state,
    )
    return {
        "effect_execution": reconciled,
        "evidence": evidence,
        "validation_job": (
            evidence if frozen_spec.name == "request_synthetic_validation" else None
        ),
        "governed_effect_receipt": (
            evidence if frozen_spec.name == "promote_variant_lab" else None
        ),
        "action": updated_action,
        "run": updated_run,
    }


def _durable_evidence(
    *, deps: AppDeps, tenant_id: str, execution_id: str, capability_name: str
) -> tuple[dict[str, Any], str, Mapping[str, Any]]:
    if capability_name == "request_synthetic_validation":
        job = deps.validation_jobs.get_job_for_effect_execution(
            approval_effect_execution_id=execution_id,
            client_id=tenant_id,
        )
        if job is not None:
            job_id = _identifier("validation_job_id", job.get("id"))
            return (
                {"validation_job_id": job_id},
                f"validation-job:{job_id}",
                job,
            )
    elif capability_name == "promote_variant_lab":
        receipt = deps.governed_effect_receipts.get_receipt_for_effect_execution(
            approval_effect_execution_id=execution_id,
            tenant_id=tenant_id,
        )
        if receipt is not None and type(receipt.get("outputs")) is dict:
            receipt_id = _identifier("receipt_id", receipt.get("receipt_id"))
            return dict(receipt["outputs"]), receipt_id, receipt
    raise EffectRecoveryError(
        "no tenant-scoped durable evidence is bound to this effect start",
        code="effect_receipt_unavailable",
    )


def _restore_run_projection(
    *, deps: AppDeps, tenant_id: str, workflow_id: str, next_state: str | None
) -> Mapping[str, Any]:
    for _ in range(_PROJECTION_RESTORE_ATTEMPTS):
        current_run = deps.agent_runs.get_agent_run(
            run_id=workflow_id, client_id=tenant_id
        )
        if current_run is None:
            raise EffectRecoveryError(
                "reconciled run projection is unavailable",
                code="effect_projection_unavailable",
            )
        current_status = str(current_run.get("status") or "").strip().lower()
        if current_status in {"canceled", "cancelled", "completed", "paused"}:
            return current_run
        actions = deps.agent_actions.list_agent_actions(
            agent_run_id=workflow_id, limit=501
        )
        if len(actions) > 500:
            raise EffectRecoveryError(
                "run action projection exceeds the reconciliation safety bound",
                code="effect_projection_too_large",
            )
        next_status, stop = derive_next_run_status(run=current_run, actions=actions)
        restore = deps.agent_runs.restore_agent_run_after_effect_reconciliation(
            run_id=workflow_id,
            client_id=tenant_id,
            state=next_state or str(current_run.get("state") or ""),
            status=next_status,
            expected_run_state=str(current_run.get("state") or ""),
            expected_run_status=current_status,
            expected_action_projection=_action_projection(actions),
        )
        outcome = restore.get("outcome")
        restored_run = restore.get("run")
        if outcome == "restored" and restored_run is not None:
            if stop:
                record_stopping_decision(deps=deps, run_id=workflow_id, stop=stop)
            return restored_run
        if outcome == "control_plane_state_preserved" and restored_run is not None:
            return restored_run
        if outcome not in {"action_projection_changed", "run_projection_changed"}:
            raise EffectRecoveryError(
                "reconciled run projection is unavailable",
                code="effect_projection_unavailable",
            )
    raise EffectRecoveryError(
        "run or action projection changed repeatedly during reconciliation",
        code="effect_projection_conflict",
    )


def _action_projection(
    actions: list[Mapping[str, Any]],
) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            action.get("id"),
            int(action.get("sequence") or 0),
            action.get("status"),
            action.get("capability_name"),
            action.get("outputs_hash"),
            action.get("error"),
        )
        for action in sorted(
            actions,
            key=lambda item: (
                int(item.get("sequence") or 0),
                str(item.get("id") or ""),
            ),
        )
    )


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
