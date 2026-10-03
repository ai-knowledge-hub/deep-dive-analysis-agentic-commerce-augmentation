"""Terminal cancellation of quiescent sequential runs without resolving stops."""

from __future__ import annotations

from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.commands.preflight import _command_preflight
from application.services.agent_runtime.registry import registry_contract_payload
from application.services.conversation.operator_control_snapshot import (
    build_control_snapshot as build_cancel_snapshot,
)
from application.services.conversation.operator_snapshot import MAX_ACTIONS
from domain.workflow.operator_commands import (
    CANCEL_MODES,
    CANCEL_SOURCE_STATUSES,
    canonical_digest,
)


def conversational_cancel_preflight(
    *, deps: AppDeps, tenant_id: str, run_id: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    if run is None:
        raise LookupError("Agent run not found")
    result = _command_preflight(
        deps=deps,
        run=run,
        command_type="cancel",
        action=None,
        metadata={"origin": "operator_conversation"},
    )
    blockers = list(result["blockers"])
    completion_verified = snapshot.get("completion_verified") is True
    if not completion_verified:
        blockers.append(
            "Completion authority could not be verified; restore verified evidence before canceling."
        )
    if run.get("status") not in CANCEL_SOURCE_STATUSES:
        blockers.append("Only an existing nonterminal run can be canceled.")
    if run.get("run_mode") not in CANCEL_MODES:
        blockers.append(
            "The run mode is not supported for conversational cancellation."
        )
    if run.get("lock_token"):
        blockers.append(
            "The run has in-flight or unreconciled locked work; wait for it to settle or use governed recovery."
        )
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=MAX_ACTIONS + 1
    )
    if len(actions) > MAX_ACTIONS:
        blockers.append(
            "The complete action state exceeds the supported confirmation bound."
        )
    for action in actions:
        if action.get("status") == "executing":
            blockers.append(
                "An action is still executing; reconcile it before canceling."
            )
        effect = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id=tenant_id,
            workflow_id=run_id,
            action_id=action["id"],
        )
        if effect and effect.get("status") in {"started", "uncertain"}:
            blockers.append(
                "An effect is unreconciled; cancellation cannot interrupt or undo it. Use governed recovery."
            )
    # Existing budget/policy/operator stops are reasons to cancel, not proof
    # that cancellation is unsafe. Retain them without recording a clearance.
    return {
        **result,
        "command_type": "cancel",
        "allowed": not blockers,
        "blockers": blockers,
        "completion_verified": completion_verified,
        "requires_confirmation": True,
        "confirmation_scope": "exact_cancel_proposal",
        "governing_registry_digest": canonical_digest(registry_contract_payload()),
        "predicted_run_status": "canceled",
        "warnings": [
            "Cancellation is terminal. Continue only through a separately authorized new run.",
            "This changes control-plane state and does not undo completed effects or certify worker interruption.",
        ],
        "summary": f"Preflight blocked cancel: {blockers[0]}"
        if blockers
        else "Cancel will make this run terminal; it cannot be resumed or receive new work.",
    }


__all__ = ["build_cancel_snapshot", "conversational_cancel_preflight"]
