"""Paused-only admission for the sequential runtime's existing start mapping."""

from __future__ import annotations

from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.commands.preflight import _command_preflight
from application.services.agent_runtime.registry import registry_contract_payload
from application.services.agent_runtime.runtime.stopping import (
    evaluate_stopping_conditions,
)
from application.services.conversation.operator_snapshot import (
    MAX_ACTIONS,
)
from application.services.conversation.operator_control_snapshot import (
    build_control_snapshot,
)
from domain.workflow.operator_commands import canonical_digest, RESUME_MODES


def build_resume_snapshot(**kwargs: Any) -> dict[str, Any]:
    return build_control_snapshot(**kwargs)


def conversational_resume_preflight(
    *, deps: AppDeps, tenant_id: str, run_id: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    if run is None:
        raise LookupError("Agent run not found")
    result = _command_preflight(
        deps=deps,
        run=run,
        command_type="start",
        action=None,
        metadata={"origin": "operator_conversation"},
    )
    blockers = list(result["blockers"])
    # Read-only snapshots retain integrity warnings, but an unreadable or
    # missing authority view cannot authorize a new resume. A verified legacy
    # view is a real reader result even when it has no completion decision.
    completion_verified = snapshot.get("completion_verified") is True
    if not completion_verified:
        blockers.append(
            "Completion authority could not be verified; restore verified completion evidence before resuming."
        )
    if run.get("status") != "paused":
        blockers.append("Only an existing paused run can be resumed.")
    if run.get("run_mode") not in RESUME_MODES:
        blockers.append("The run mode is not supported for resume.")
    if run.get("lock_token"):
        blockers.append(
            "The run has in-flight or unreconciled locked work; settle it before resuming."
        )
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=MAX_ACTIONS + 1
    )
    if len(actions) > MAX_ACTIONS:
        blockers.append(
            "The complete action state exceeds the supported confirmation bound."
        )
    stop = evaluate_stopping_conditions(run=run, actions=actions)
    if stop:
        blockers.append(f"Stopping condition remains effective: {stop.condition}.")
    for action in actions:
        if action.get("status") == "executing":
            blockers.append(
                "An action is still executing; reconcile it before resuming."
            )
        effect = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id=tenant_id, workflow_id=run_id, action_id=action["id"]
        )
        if effect and effect.get("status") in {"started", "uncertain"}:
            blockers.append(
                "An effect is unreconciled; resume cannot authorize or repeat it."
            )
    # Stop events are immutable history. Clear only a recorded operator-pause
    # marker; never remove other markers or infer a cause for a legacy pause.
    # Compatibility starts do not prove that any particular stop was resolved.
    events = deps.agent_events.list_run_control_events(agent_run_id=run_id, limit=501)
    operator_pause_id = None
    cleared = set()
    unresolved = []
    for event in reversed(events):
        event_type = event.get("event_type")
        anchors = event.get("anchors") or {}
        if event_type == "run_stopping_condition_cleared":
            cleared.add(anchors.get("cleared_event_id"))
        elif event_type == "run_stopping_condition_met" and event["id"] not in cleared:
            condition = anchors.get("stopping_condition")
            unresolved.append({"event_id": event["id"], "condition": condition})
            if condition == "operator_pause":
                operator_pause_id = operator_pause_id or event["id"]
            else:
                blockers.append(
                    f"Recorded stopping condition requires resolution: {condition or 'unknown'}."
                )
    if len(events) > 500:
        blockers.append(
            "The stopping-condition history is incomplete; resume is blocked."
        )
    target = "planned" if run.get("run_mode") == "plan_only" else "running"
    return {
        **result,
        "command_type": "resume",
        "allowed": not blockers,
        "completion_verified": completion_verified,
        "blockers": blockers,
        "requires_confirmation": True,
        "confirmation_scope": "exact_resume_proposal",
        "governing_registry_digest": canonical_digest(registry_contract_payload()),
        "predicted_run_status": target,
        "operator_pause_event_id": operator_pause_id,
        "unresolved_stopping_conditions": unresolved,
        "warnings": [
            "Confirmation changes control-plane eligibility only. Normal approval and pre-effect checks still apply."
        ],
        "summary": f"Preflight blocked resume: {blockers[0]}"
        if blockers
        else f"Resume will return this run to {target}.",
    }


__all__ = ["build_resume_snapshot", "conversational_resume_preflight"]
