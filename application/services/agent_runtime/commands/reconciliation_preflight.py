from __future__ import annotations

from typing import Any, Mapping

from application.ports.deps import AppDeps


def effect_reconciliation_preflight(
    *,
    deps: AppDeps,
    run: Mapping[str, Any],
    action: Mapping[str, Any] | None,
    command_type: str,
    current_side_effects: list[str],
) -> dict[str, Any]:
    if command_type != "reconcile_effect" or action is None:
        return {
            "blockers": [],
            "warnings": [],
            "side_effects": current_side_effects,
        }

    blockers: list[str] = []
    action_status = str(action.get("status") or "").strip().lower()
    if action_status not in {"executing", "failed", "executed"}:
        blockers.append(
            "Effect reconciliation requires an executing, failed, or already executed action."
        )
    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=str(run.get("client_id") or ""),
        workflow_id=str(run.get("id") or ""),
        action_id=str(action.get("id") or ""),
    )
    if execution is None:
        blockers.append("No durable governed-effect start exists for this action.")
    else:
        execution_status = str(execution.get("status") or "").strip().lower()
        if execution_status not in {"started", "uncertain", "succeeded"}:
            blockers.append("The governed effect is not awaiting reconciliation.")
        if not _has_bound_durable_evidence(
            deps=deps,
            execution=execution,
            tenant_id=str(run.get("client_id") or ""),
        ):
            blockers.append(
                "No tenant-scoped durable evidence is bound to this effect start."
            )
    return {
        "blockers": blockers,
        "warnings": [
            "Reconciliation never invokes the capability; it validates and records existing durable evidence."
        ],
        "side_effects": [],
    }


def _has_bound_durable_evidence(
    *, deps: AppDeps, execution: Mapping[str, Any], tenant_id: str
) -> bool:
    execution_id = str(execution.get("execution_id") or "")
    snapshot = execution.get("authorization_snapshot")
    contract = snapshot.get("capability_contract") if type(snapshot) is dict else None
    capability_name = contract.get("name") if type(contract) is dict else None
    if capability_name == "request_synthetic_validation":
        return bool(
            deps.validation_jobs.get_job_for_effect_execution(
                approval_effect_execution_id=execution_id,
                client_id=tenant_id,
            )
        )
    if capability_name == "promote_variant_lab":
        receipt = deps.governed_effect_receipts.get_receipt_for_effect_execution(
            approval_effect_execution_id=execution_id,
            tenant_id=tenant_id,
        )
        return bool(receipt and receipt.get("scope_status") == "validated")
    return False


__all__ = ["effect_reconciliation_preflight"]
