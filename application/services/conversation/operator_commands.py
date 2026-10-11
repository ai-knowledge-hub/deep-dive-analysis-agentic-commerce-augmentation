"""Application boundary for closed conversational pause and resume proposals."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.commands.context import command_context
from application.services.agent_runtime.commands.preflight import (
    _command_preflight,
)
from domain.workflow.operator_commands import (
    OperatorCommandInvariantError,
    build_pause_proposal,
    build_resume_proposal,
    build_cancel_proposal,
)
from application.services.conversation.operator_resume import (
    conversational_resume_preflight,
)
from application.services.conversation.operator_cancel import (
    conversational_cancel_preflight,
)


PAUSE_PROPOSAL_CONSEQUENCES = (
    "Autonomous control-plane progress will stop until a separate resume command is authorized.",
    "Current run state and evidence are preserved.",
    "This receipt does not certify that every in-flight external operation has stopped.",
)


def conversational_pause_preflight(
    *, deps: AppDeps, tenant_id: str, run_id: str
) -> dict[str, Any]:
    run, action, command_type = command_context(
        deps=deps,
        run_id=run_id,
        client_id=tenant_id,
        command_type="pause",
        action_id=None,
    )
    result = _command_preflight(
        deps=deps,
        run=run,
        command_type=command_type,
        action=action,
        metadata={"origin": "operator_conversation"},
    )
    blockers = list(result.get("blockers") or [])
    if run.get("lock_token"):
        blockers.append(
            "The run has in-flight or unreconciled locked work. This compatibility pause cannot certify interruption, so wait for the step to settle or use governed recovery."
        )
    warnings = list(result.get("warnings") or [])
    warnings.append(
        "Confirmation pauses control-plane progress but does not certify that every in-flight external operation has stopped."
    )
    return {
        **result,
        "allowed": not blockers,
        "blockers": blockers,
        "requires_confirmation": True,
        "warnings": warnings,
        "confirmation_scope": "exact_pause_proposal",
        "summary": (
            f"Preflight blocked pause: {blockers[0]}"
            if blockers
            else result.get("summary")
        ),
    }


def create_conversational_proposal(
    *,
    command_type: str,
    deps: AppDeps,
    tenant_id: str,
    principal_id: str,
    snapshot: dict[str, Any],
    current_snapshot_digest: Callable[[], str],
) -> dict[str, Any]:
    if command_type not in {"pause", "resume", "cancel"}:
        raise OperatorCommandInvariantError("unsupported conversational command")
    run_id = str(snapshot["run"]["id"])
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    if run is None:
        raise LookupError("Agent run not found")
    scope = {"deps": deps, "tenant_id": tenant_id, "run_id": run_id}
    preflight = (
        conversational_cancel_preflight(**scope, snapshot=snapshot)
        if command_type == "cancel"
        else conversational_resume_preflight(**scope, snapshot=snapshot)
        if command_type == "resume"
        else conversational_pause_preflight(**scope)
    )
    if preflight.get("allowed") is not True:
        return {
            "state": "blocked",
            "preflight": preflight,
            "proposal": None,
        }
    events = list(snapshot.get("events") or [])
    proposal_builder = (
        build_cancel_proposal
        if command_type == "cancel"
        else build_resume_proposal
        if command_type == "resume"
        else build_pause_proposal
    )
    proposal = proposal_builder(
        tenant_id=tenant_id,
        principal_id=principal_id,
        run=run,
        snapshot_digest=str(snapshot["snapshot_digest"]),
        snapshot_cursor=snapshot["event_page"].get("after_cursor"),
        latest_event=events[-1] if events else None,
        preflight=preflight,
    )
    durable = deps.operator_commands.create_proposal(
        proposal=proposal,
        current_snapshot_digest=current_snapshot_digest,
    )
    return {"state": "proposed", "preflight": preflight, "proposal": durable}


def operator_proposal_view(proposal: dict[str, Any]) -> dict[str, Any]:
    """Add operator-facing consequences without changing the canonical proposal."""

    if proposal["command_type"] == "reconcile_effect":
        return {**proposal, "consequences": [
            "Records the existing verified effect outcome and restores its action projection.",
            "No provider call, new effect start, new approval or retry occurs.",
            "Cancellation, completed/paused state and unresolved stopping markers are preserved.",
            "Effect success alone does not certify objective completion.",
        ]}
    if proposal["command_type"] == "retry":
        return {**proposal, "consequences": [
            "Creates one new proposed action with its own retry identity.",
            "Fresh approval is required before execution; prior approval is not copied.",
            "Confirmation does not execute work, start or resume this run, or reset budgets.",
        ]}
    if proposal['command_type'] in {'approve', 'reject'}:
        return {**proposal, 'consequences': [
            'This records the decision for the exact reviewed action only.',
            'Approval does not execute the action or start or resume this run.',
            'Execution rechecks policy, budgets, revocation and the exact approval at the effect boundary.',
        ]}
    return {
        **proposal,
        "consequences": [
            "Cancellation is terminal: this run cannot be resumed or receive new work.",
            "Continue only through a separately authorized new run.",
            "Existing approvals, results, evidence, stopping markers, and completed effects are preserved.",
            "This receipt does not certify worker interruption or undo external operations.",
        ]
        if proposal["command_type"] == "cancel"
        else list(PAUSE_PROPOSAL_CONSEQUENCES)
        if proposal["command_type"] == "pause"
        else [
            f"Run mode {proposal['source']['run_mode']} returns to {proposal['predicted_run_status']}.",
            "Plan-only remains non-executing."
            if proposal["source"]["run_mode"] == "plan_only"
            else "The run becomes eligible for normal governed continuation.",
            "Resume grants no action approval, budget, policy relaxation, mode change, attempt reset, or repeated effect.",
            "The receipt acknowledges eligibility; it does not certify worker continuation or external completion.",
        ],
    }


__all__ = [
    "conversational_pause_preflight",
    "create_conversational_pause_proposal",
    "create_conversational_proposal",
    "operator_proposal_view",
    "pause_proposal_view",
]


def create_conversational_pause_proposal(**kwargs: Any) -> dict[str, Any]:
    return create_conversational_proposal(command_type="pause", **kwargs)


def pause_proposal_view(proposal: dict[str, Any]) -> dict[str, Any]:
    return operator_proposal_view(proposal)
