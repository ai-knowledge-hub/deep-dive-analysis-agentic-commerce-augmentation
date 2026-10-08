"""Exact, evidence-only recovery proposals and human confirmation."""

from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.effect_recovery import (
    EffectRecoveryError,
    prepare_effect_reconciliation,
    reconcile_effect_from_durable_evidence,
)
from application.services.conversation.operator_control_snapshot import (
    build_control_snapshot,
)
from application.services.conversation.operator_snapshot import MAX_ACTIONS
from domain.workflow.operator_commands import (
    RECONCILIATION_ACTION_STATUSES,
    RECONCILIATION_RUN_STATUSES,
    build_reconciliation_proposal,
    canonical_digest,
)

build_reconciliation_snapshot = build_control_snapshot


def reconciliation_preflight(
    *,
    deps: AppDeps,
    tenant_id: str,
    run_id: str,
    action_id: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=tenant_id
    )
    if not run or not action or action["agent_run_id"] != run_id:
        raise LookupError("Action not found in the selected run")
    blockers, proof = [], {}
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=MAX_ACTIONS + 1
    )
    if (
        run["status"] not in RECONCILIATION_RUN_STATUSES
        or action["status"] not in RECONCILIATION_ACTION_STATUSES
    ):
        blockers.append(
            "Select one executing, failed or executed action with a committed effect."
        )
    if run.get("lock_token") or any(
        a["status"] == "executing" and a["id"] != action_id for a in actions
    ):
        blockers.append(
            "Wait for the worker lease and other in-flight actions to settle."
        )
    if len(actions) > MAX_ACTIONS:
        blockers.append(
            "The complete action set exceeds the reconciliation safety bound."
        )
    if snapshot.get("completion_verified") is not True:
        blockers.append("Completion authority could not be verified.")
    events = deps.agent_events.list_run_control_events(agent_run_id=run_id, limit=501)
    cleared, stops = set(), []
    for event in reversed(events):
        if event["event_type"] == "run_stopping_condition_cleared":
            cleared.add((event.get("anchors") or {}).get("cleared_event_id"))
        elif (
            event["event_type"] == "run_stopping_condition_met"
            and event["id"] not in cleared
        ):
            stops.append(event["id"])
    if len(events) > 500:
        blockers.append("Stopping-condition history exceeds the verification bound.")
    try:
        proof = prepare_effect_reconciliation(deps=deps, run=run, action=action)
        # Pin the current action projection too; this never supplies outcome authority.
        proof["action_projection_digest"] = canonical_digest(action)
    except (EffectRecoveryError, ValueError, TypeError) as exc:
        blockers.append(str(exc))
    return {
        "command_type": "reconcile_effect",
        "action_id": action_id,
        "allowed": not blockers,
        "requires_confirmation": True,
        "risk_level": "medium",
        "blockers": blockers,
        "warnings": [
            "Records existing durable evidence; no provider call, new approval or retry occurs."
        ],
        "summary": blockers[0]
        if blockers
        else "Review the verified historical effect outcome before recording it.",
        "reconciliation": proof,
        "unresolved_stopping_event_ids": stops,
        # Acknowledgement of existing success must not reapply its historical
        # next state over progress made by later actions.
        "preserve_control_state": proof.get("effect_status") == "succeeded"
        or bool(stops)
        or run["status"] in {"paused", "completed", "canceled", "cancelled"},
    }


def create_reconciliation_proposal(
    *,
    deps: AppDeps,
    tenant_id: str,
    principal_id: str,
    snapshot: dict[str, Any],
    command_type: str,
    action_id: str,
    current_snapshot_digest: Any,
) -> dict[str, Any]:
    if command_type != "reconcile_effect":
        raise ValueError("Unsupported reconciliation command")
    run_id = snapshot["run"]["id"]
    preflight = reconciliation_preflight(
        deps=deps,
        tenant_id=tenant_id,
        run_id=run_id,
        action_id=action_id,
        snapshot=snapshot,
    )
    if not preflight["allowed"]:
        return {"state": "blocked", "preflight": preflight, "proposal": None}
    events = snapshot.get("events", [])
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=tenant_id
    )
    proposal = build_reconciliation_proposal(
        tenant_id=tenant_id,
        principal_id=principal_id,
        run=deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id),
        snapshot_digest=snapshot["snapshot_digest"],
        snapshot_cursor=snapshot["event_page"].get("after_cursor"),
        latest_event=events[-1] if events else None,
        preflight=preflight,
        parameters={
            "action_id": action_id,
            "action_status": action["status"],
            "effect_execution_id": preflight["reconciliation"]["effect_execution_id"],
            "reconciliation": preflight["reconciliation"],
        },
    )

    # Also reverify adapter evidence under proposal creation's write lock.
    def current_digest():
        latest = reconciliation_preflight(
            deps=deps,
            tenant_id=tenant_id,
            run_id=run_id,
            action_id=action_id,
            snapshot=snapshot,
        )
        return (
            current_snapshot_digest()
            if canonical_digest(latest) == proposal["preflight"]["digest"]
            else "changed"
        )

    durable = deps.operator_commands.create_proposal(
        proposal=proposal, current_snapshot_digest=current_digest
    )
    return {"state": "proposed", "preflight": preflight, "proposal": durable}


def confirm_reconciliation(
    *,
    deps: AppDeps,
    proposal: dict[str, Any],
    authority: Any,
    completion_reader: Any,
    require_access: Any,
) -> dict[str, Any]:
    tenant_id, run_id, action_id = (
        proposal["tenant_id"],
        proposal["run_id"],
        proposal["parameters"]["action_id"],
    )

    def confirmation_state():
        require_access()
        snapshot = build_reconciliation_snapshot(
            deps=deps,
            tenant_id=tenant_id,
            principal_id=authority.principal_id,
            run_id=run_id,
            completion_reader=completion_reader,
        )
        return {
            "snapshot_digest": snapshot["snapshot_digest"],
            "preflight": reconciliation_preflight(
                deps=deps,
                tenant_id=tenant_id,
                run_id=run_id,
                action_id=action_id,
                snapshot=snapshot,
            ),
        }

    def reconcile():
        return reconcile_effect_from_durable_evidence(
            deps=deps,
            run=deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id),
            action=deps.agent_actions.get_agent_action(
                action_id=action_id, client_id=tenant_id
            ),
            preserve_control_state=proposal["preflight"]["result"][
                "preserve_control_state"
            ],
            infer_legacy_completion=False,
        )

    receipt = deps.operator_commands.commit_reconciliation(
        proposal=proposal,
        principal_id=authority.principal_id,
        require_access=require_access,
        confirmation_state=confirmation_state,
        reconcile=reconcile,
    )
    return {
        "contract": "operator-command-confirmation.v1",
        "run_id": run_id,
        "proposal_id": proposal["proposal_id"],
        "receipt": receipt,
        "command": {
            "id": receipt["event_ids"]["command"],
            "event_type": "operator_command_reconcile_effect",
            "status": "completed",
        },
        "run": deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id),
    }
