"""Read-only same-action retry plans and exact human confirmation."""

from dataclasses import asdict
from typing import Any

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_registry import (
    prepare_action_for_exact_approval,
)
from application.services.agent_runtime.commands.recovery import (
    build_retry_action_payload,
)
from application.services.agent_runtime.policy import PolicyEnforcer
from application.services.agent_runtime.registry import (
    get_capability_spec,
    registry_contract_payload,
)
from application.services.conversation.operator_control_snapshot import (
    build_control_snapshot,
)
from application.services.conversation.operator_snapshot import MAX_ACTIONS
from domain.workflow.operator_commands import (
    REVIEW_SOURCE_STATUSES,
    RESUME_MODES,
    build_retry_proposal,
    canonical_digest,
)

build_retry_snapshot = build_control_snapshot


def retry_preflight(
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
    blockers: list[str] = []
    plan: dict[str, Any] = {}
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=MAX_ACTIONS + 1
    )
    if (
        run["status"] not in REVIEW_SOURCE_STATUSES
        or run["run_mode"] not in RESUME_MODES
    ):
        blockers.append(
            "Retry requires a planned, running or paused run in a supported mode. Terminal runs require a separately authorized new run; inspect recovery in Interventions."
        )
    if action["status"] != "failed":
        blockers.append("Select one exact failed source action for retry.")
    if run.get("lock_token") or any(a["status"] == "executing" for a in actions):
        blockers.append("Wait for in-flight work to settle before retrying.")
    if snapshot.get("completion_verified") is not True:
        blockers.append("Completion authority could not be verified.")
    completion = snapshot.get("completion", {})
    if (
        completion.get("state") not in {"legacy", "awaiting_decision", "current"}
        or (
            completion.get("state") == "current"
            and (completion.get("projection") or {}).get("state") != "current"
        )
        or completion.get("evidence_completeness", {}).get("state") != "complete"
    ):
        blockers.append(
            "Completion evidence or its projection is incomplete or stale; inspect recovery in Interventions."
        )
    if len(actions) >= MAX_ACTIONS:
        blockers.append(
            "Adding a retry would exceed the full confirmation action bound."
        )
    if snapshot.get("completeness", {}).get("experiment", {}).get("state") in {
        "partial",
        "missing",
        "unavailable",
        "contradictory",
    } or any(
        w.get("code", "").startswith(("linked_validation_", "linked_experiment_"))
        for w in snapshot.get("warnings", [])
    ):
        blockers.append("Required linked evidence is incomplete or contradictory.")
    lineage, lineage_blockers = _source_lineage(action, actions)
    blockers.extend(lineage_blockers)
    effect_family = _retry_effect_family(lineage, actions)
    held = deps.operator_commands.active_retry_source_ids(
        tenant_id=tenant_id, workflow_id=run_id
    )
    if any(a["status"] == "failed" and a["id"] not in lineage | held for a in actions):
        blockers.append(
            "Another unresolved failed action prevents continuation; inspect recovery in Interventions."
        )
    for item in actions:
        effect = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id=tenant_id, workflow_id=run_id, action_id=item["id"]
        )
        if effect and (item["id"] in effect_family or effect["status"] != "succeeded"):
            blockers.append(
                "A committed source effect or unresolved run effect blocks retry. Reconcile it in Interventions; successful effects cannot be repeated through this proposal."
            )
    if (
        action.get("validation_job_id")
        or action.get("outputs")
        or action.get("receipt_id")
    ):
        blockers.append(
            "The source contains outcome evidence; inspect and reconcile it before retrying."
        )
    spec = get_capability_spec(action.get("capability_name", ""))
    try:
        if spec is None:
            raise ValueError("The capability is absent from the executable registry.")
        if spec.effect_class not in {
            "read",
            "recommend",
            "external_side_effect",
            "write_high_risk",
        }:
            raise ValueError(
                "This effect class has no durable effect-start fence; use operator recovery in Interventions."
            )
        # Independently verify source identity as well as the new plan's identity.
        prepare_action_for_exact_approval(deps=deps, run=run, action=action, spec=spec)
        payload = build_retry_action_payload(
            run_id=run_id,
            run=run,
            action=action,
            metadata={"retry_strategy": "same_action"},
        )
        payload["rationale"] = (
            f"Same-action retry proposed from failed action {action_id}."
        )
        payload["admissible_run_statuses"] = sorted(REVIEW_SOURCE_STATUSES)
        prepared, authority = prepare_action_for_exact_approval(
            deps=deps, run=run, action=payload, spec=spec
        )
        payload["inputs"], payload["inputs_hash"] = (
            prepared["inputs"],
            prepared["inputs_hash"],
        )
        PolicyEnforcer().validate_action_retry_proposal(
            run=run,
            action=prepared,
            spec=spec,
            inputs=prepared["inputs"],
            all_actions=actions,
        )
        plan = {
            "strategy": "same_action",
            "capability_name": spec.name,
            "normalized_inputs": prepared["inputs"],
            "inputs_hash": prepared["inputs_hash"],
            "registry_authority": asdict(authority),
            "side_effects": list(spec.side_effects),
            "review_checklist": list(spec.review_checklist),
            "action_payload": payload,
        }
    except (ValueError, TypeError) as exc:
        blockers.append(str(exc))
    return {
        "command_type": "retry",
        "allowed": not blockers,
        "requires_confirmation": True,
        "risk_level": "medium",
        "warnings": ["Creates a proposed action only; fresh approval is required."],
        "blockers": blockers,
        "summary": blockers[0]
        if blockers
        else "Review the exact same-action retry before confirming.",
        "action_id": action_id,
        "retry_plan": plan,
        "registry_digest": canonical_digest(registry_contract_payload()),
    }


def _source_lineage(
    action: dict[str, Any], actions: list[dict[str, Any]]
) -> tuple[set[str], list[str]]:
    """A legacy retry child cannot erase an ancestor's committed effect."""
    by_id = {item["id"]: item for item in actions}
    lineage: set[str] = set()
    while action["id"] not in lineage:
        lineage.add(action["id"])
        key = str(action.get("dedupe_key") or "")
        if not key.startswith("retry:"):
            return lineage, [] if not action.get("retry_count") else [
                "Retry lineage cannot be verified; inspect recovery in Interventions."
            ]
        parts = key.split(":")
        parent = by_id.get(parts[1]) if len(parts) == 4 else None
        if parent is None:
            return lineage, [
                "Retry source lineage is incomplete; inspect recovery in Interventions."
            ]
        action = parent
    return lineage, [
        "Retry source lineage contains a cycle; inspect recovery in Interventions."
    ]


def _retry_effect_family(
    ancestors: set[str], actions: list[dict[str, Any]]
) -> set[str]:
    """A succeeded child/sibling cannot be repeated via its still-failed source."""
    family = set(ancestors)
    while True:
        previous = len(family)
        for action in actions:
            parts = str(action.get("dedupe_key") or "").split(":")
            if len(parts) == 4 and parts[0] == "retry" and parts[1] in family:
                family.add(action["id"])
        if len(family) == previous:
            return family


def create_retry_action_proposal(
    *,
    deps: AppDeps,
    tenant_id: str,
    principal_id: str,
    snapshot: dict[str, Any],
    command_type: str,
    action_id: str,
    current_snapshot_digest: Any,
) -> dict[str, Any]:
    if command_type != "retry":
        raise ValueError("Unsupported retry command")
    run_id = snapshot["run"]["id"]
    preflight = retry_preflight(
        deps=deps,
        tenant_id=tenant_id,
        run_id=run_id,
        action_id=action_id,
        snapshot=snapshot,
    )
    if not preflight["allowed"]:
        return {"state": "blocked", "preflight": preflight, "proposal": None}
    events = snapshot.get("events", [])
    proposal = build_retry_proposal(
        tenant_id=tenant_id,
        principal_id=principal_id,
        run=deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id),
        snapshot_digest=snapshot["snapshot_digest"],
        snapshot_cursor=snapshot["event_page"].get("after_cursor"),
        latest_event=events[-1] if events else None,
        preflight=preflight,
        parameters={
            "action_id": action_id,
            "action_status": "failed",
            "retry_strategy": "same_action",
            "retry_plan": preflight["retry_plan"],
        },
    )
    durable = deps.operator_commands.create_proposal(
        proposal=proposal, current_snapshot_digest=current_snapshot_digest
    )
    return {"state": "proposed", "preflight": preflight, "proposal": durable}


def confirm_retry(
    *,
    deps: AppDeps,
    proposal: dict[str, Any],
    authority: Any,
    completion_reader: Any,
    require_access: Any,
) -> dict[str, Any]:
    def confirmation_state():
        require_access()
        snapshot = build_retry_snapshot(
            deps=deps,
            tenant_id=proposal["tenant_id"],
            principal_id=authority.principal_id,
            run_id=proposal["run_id"],
            completion_reader=completion_reader,
        )
        return {
            "snapshot_digest": snapshot["snapshot_digest"],
            "preflight": retry_preflight(
                deps=deps,
                tenant_id=proposal["tenant_id"],
                run_id=proposal["run_id"],
                action_id=proposal["parameters"]["action_id"],
                snapshot=snapshot,
            ),
        }

    receipt = deps.operator_commands.commit_retry(
        proposal=proposal,
        principal_id=authority.principal_id,
        confirmation_state=confirmation_state,
        create_action=lambda: deps.agent_actions.create_agent_action(
            **proposal["parameters"]["retry_plan"]["action_payload"]
        ),
    )
    return {
        "contract": "operator-command-confirmation.v1",
        "run_id": proposal["run_id"],
        "proposal_id": proposal["proposal_id"],
        "receipt": receipt,
        "command": {
            "id": receipt["event_ids"]["command"],
            "event_type": "operator_command_retry",
            "status": "completed",
        },
        "run": deps.agent_runs.get_agent_run(
            run_id=proposal["run_id"], client_id=proposal["tenant_id"]
        ),
    }
