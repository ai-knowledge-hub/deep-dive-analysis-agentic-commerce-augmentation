"""Read-only preparation and exact confirmation of one pending action."""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_ledger import (
    ApprovalLedgerError,
    build_action_approval_binding,
    get_authoritative_approval,
    issue_action_approval_command,
)
from application.services.agent_runtime.approval_registry import (
    ApprovalRegistryError,
    prepare_action_for_exact_approval,
)
from application.services.agent_runtime.commands.preflight import _command_preflight
from application.services.agent_runtime.registry import (
    get_capability_spec,
    registry_contract_payload,
)
from application.services.conversation.operator_control_snapshot import (
    build_control_snapshot,
)
from application.services.conversation.operator_snapshot import MAX_ACTIONS
from domain.workflow.approval import ApprovalAuthority
from domain.workflow.approval_serialization import approval_envelope_from_payload
from domain.workflow.operator_commands import (
    REVIEW_SOURCE_STATUSES,
    RESUME_MODES,
    build_action_review_proposal,
    canonical_digest,
)


build_action_review_snapshot = build_control_snapshot


def action_review_preflight(
    *,
    deps: AppDeps,
    tenant_id: str,
    run_id: str,
    action_id: str,
    command_type: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=tenant_id
    )
    if not run or not action or action["agent_run_id"] != run_id:
        raise LookupError("Action not found in the selected run")
    blockers: list[str] = []
    review: dict[str, Any] = {}
    if command_type not in {"approve", "reject"}:
        raise ValueError("Unsupported review decision")
    if (
        run["status"] not in REVIEW_SOURCE_STATUSES
        or run["run_mode"] not in RESUME_MODES
    ):
        blockers.append(
            "Action review requires a planned, running or paused run in a supported mode."
        )
    if action["status"] != "proposed":
        blockers.append("Only one pending proposed action can be reviewed.")
    if run.get("lock_token"):
        blockers.append(
            "Wait for in-flight run work to settle before reviewing the action."
        )
    if snapshot.get("completion_verified") is not True:
        blockers.append("Completion authority could not be verified.")
    if (
        len(
            deps.agent_actions.list_agent_actions(
                agent_run_id=run_id, limit=MAX_ACTIONS + 1
            )
        )
        > MAX_ACTIONS
    ):
        blockers.append(
            "The full action state exceeds the supported confirmation bound."
        )
    experiment_state = (
        snapshot.get("completeness", {}).get("experiment", {}).get("state")
    )
    if experiment_state in {"partial", "missing", "unavailable", "contradictory"}:
        blockers.append("The linked experiment evidence is incomplete or unavailable.")
    if any(
        w.get("code", "").startswith("linked_validation_")
        or w.get("code", "").startswith("linked_experiment_")
        for w in snapshot.get("warnings", [])
    ):
        blockers.append("Required linked evidence is incomplete or contradictory.")
    scope = {"tenant_id": tenant_id, "workflow_id": run_id, "action_id": action_id}
    if deps.approval_ledger.get_effect_execution_for_action(**scope):
        blockers.append(
            "An action with a committed effect cannot receive a new review decision."
        )
    spec = get_capability_spec(action.get("capability_name", ""))
    result = {"risk_level": "high", "warnings": [], "side_effects": []}
    try:
        if spec is None:
            raise ValueError("The capability is absent from the executable registry.")
        prepared, authority = prepare_action_for_exact_approval(
            deps=deps, run=run, action=action, spec=spec
        )
        result = _command_preflight(
            deps=deps,
            run=run,
            command_type=command_type,
            action=prepared,
            metadata={"origin": "operator_conversation"},
        )
        blockers.extend(result.get("blockers", []))
        approval = deps.approval_ledger.get_current_approval_for_action(**scope)
        if approval:
            approval = get_authoritative_approval(
                deps=deps,
                tenant_id=tenant_id,
                workflow_id=run_id,
                approval_id=approval["approval_id"],
            )
            envelope = approval_envelope_from_payload(approval["envelope"])
            binding = build_action_approval_binding(
                run=run,
                action=prepared,
                approval_id=envelope.binding.approval_id,
                requested_at=envelope.binding.requested_at,
                expires_at=envelope.binding.expires_at,
                native_target=envelope.binding.native_target,
            )
            if binding != envelope.binding:
                blockers.append(
                    "The pending approval no longer matches the current action and authority. Refresh it through governed review."
                )
            if datetime.now(timezone.utc) >= envelope.binding.expires_at:
                blockers.append("The pending approval request has expired.")
            if approval["status"] != "requested":
                blockers.append(
                    "Only a pending requested approval can be decided through chat."
                )
        review = {
            "capability_name": prepared["capability_name"],
            "normalized_inputs": prepared["inputs"],
            "inputs_hash": prepared["inputs_hash"],
            "registry_authority": asdict(authority),
            "approval_id": approval["approval_id"] if approval else None,
            "approval_sequence": approval["sequence"] if approval else None,
            "approval_envelope_digest": approval["envelope_digest"]
            if approval
            else None,
            "review_checklist": list(spec.review_checklist),
            "side_effects": list(spec.side_effects),
        }
    except (ApprovalRegistryError, ApprovalLedgerError, ValueError, TypeError) as exc:
        blockers.append(str(exc))
    return {
        **result,
        "command_type": command_type,
        "allowed": not blockers,
        "blockers": blockers,
        "requires_confirmation": True,
        "summary": blockers[0]
        if blockers
        else f"Review the exact action before {command_type}.",
        "review": review,
        "action_id": action_id,
        "registry_digest": canonical_digest(registry_contract_payload()),
    }


def create_action_review_proposal(
    *,
    deps: AppDeps,
    tenant_id: str,
    principal_id: str,
    snapshot: dict[str, Any],
    command_type: str,
    action_id: str,
    current_snapshot_digest: Any,
) -> dict[str, Any]:
    run_id = snapshot["run"]["id"]
    preflight = action_review_preflight(
        deps=deps,
        tenant_id=tenant_id,
        run_id=run_id,
        action_id=action_id,
        command_type=command_type,
        snapshot=snapshot,
    )
    if not preflight["allowed"]:
        return {"state": "blocked", "preflight": preflight, "proposal": None}
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    events = snapshot.get("events", [])
    proposal = build_action_review_proposal(
        command_type=command_type,
        tenant_id=tenant_id,
        principal_id=principal_id,
        run=run,
        snapshot_digest=snapshot["snapshot_digest"],
        snapshot_cursor=snapshot["event_page"].get("after_cursor"),
        latest_event=events[-1] if events else None,
        preflight=preflight,
        parameters={
            "action_id": action_id,
            "action_status": "proposed",
            "review": preflight["review"],
        },
    )
    durable = deps.operator_commands.create_proposal(
        proposal=proposal, current_snapshot_digest=current_snapshot_digest
    )
    return {"state": "proposed", "preflight": preflight, "proposal": durable}


def commit_review_decision(
    *, deps: AppDeps, proposal: dict[str, Any], authority: ApprovalAuthority
) -> dict[str, Any]:
    run = deps.agent_runs.get_agent_run(
        run_id=proposal["run_id"], client_id=proposal["tenant_id"]
    )
    action = deps.agent_actions.get_agent_action(
        action_id=proposal["parameters"]["action_id"], client_id=proposal["tenant_id"]
    )
    review = proposal["parameters"]["review"]
    return issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type=proposal["command_type"],
        approving_authority=authority,
        approval_id=review["approval_id"],
        expected_sequence=review["approval_sequence"],
        idempotency_key=proposal["idempotency_key"],
        audit_context="operator_command",
        command_context_digest=proposal["proposal_digest"],
    )
