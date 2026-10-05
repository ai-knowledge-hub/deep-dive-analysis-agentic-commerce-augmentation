"""Compose exact human approval with a conversational receipt under one lock."""

from typing import Any

from application.ports.deps import AppDeps
from application.services.conversation.operator_action_review import (
    action_review_preflight,
    build_action_review_snapshot,
    commit_review_decision,
)
from domain.workflow.approval import ApprovalAuthority


def confirm_action_review(
    *,
    deps: AppDeps,
    proposal: dict[str, Any],
    authority: ApprovalAuthority,
    completion_reader: Any,
    require_access: Any,
) -> dict[str, Any]:
    scope = {
        "deps": deps,
        "tenant_id": proposal["tenant_id"],
        "principal_id": authority.principal_id,
        "run_id": proposal["run_id"],
        "completion_reader": completion_reader,
    }

    def confirmation_state():
        require_access()
        snapshot = build_action_review_snapshot(**scope)
        preflight = action_review_preflight(
            deps=deps,
            tenant_id=proposal["tenant_id"],
            run_id=proposal["run_id"],
            action_id=proposal["parameters"]["action_id"],
            command_type=proposal["command_type"],
            snapshot=snapshot,
        )
        return {"snapshot_digest": snapshot["snapshot_digest"], "preflight": preflight}

    receipt = deps.operator_commands.commit_review(
        proposal=proposal,
        principal_id=authority.principal_id,
        confirmation_state=confirmation_state,
        commit_decision=lambda: commit_review_decision(
            deps=deps, proposal=proposal, authority=authority
        ),
    )
    return {
        "contract": "operator-command-confirmation.v1",
        "run_id": proposal["run_id"],
        "proposal_id": proposal["proposal_id"],
        "command": {
            "id": receipt["event_ids"]["command"],
            "event_type": f"operator_command_{proposal['command_type']}",
            "status": "completed",
        },
        "receipt": receipt,
        "run": deps.agent_runs.get_agent_run(
            run_id=proposal["run_id"], client_id=proposal["tenant_id"]
        ),
    }
