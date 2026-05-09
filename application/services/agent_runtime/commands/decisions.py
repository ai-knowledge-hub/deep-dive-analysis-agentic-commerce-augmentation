from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    skill_id_for_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import get_capability_spec


def apply_command_action_decision(
    *,
    deps: AppDeps,
    run_id: str,
    run: Dict[str, Any],
    action: Dict[str, Any],
    command_type: str,
) -> Dict[str, Any]:
    status = "rejected" if command_type == "reject" else "approved"
    if status == "approved":
        _validate_approval_policy(deps=deps, run=run, action=action)
    updated = deps.agent_actions.update_agent_action_status(
        action_id=str(action.get("id")),
        status=status,
    )
    current = updated or action
    deps.agent_events.create_agent_event(
        agent_run_id=run_id,
        action_id=str(current.get("id") or ""),
        sequence=int(current.get("sequence") or 0),
        event_type=f"action_{status}",
        status=status,
        capability_name=str(current.get("capability_name") or "") or None,
        capability_version=str(current.get("capability_version") or "") or None,
        principal_type=run.get("principal_type"),
        principal_id=run.get("principal_id"),
        tool_id=current.get("tool_id")
        or capability_to_tool_id(current.get("capability_name")),
        skill_id=current.get("skill_id")
        or skill_id_for_tool_id(
            current.get("tool_id")
            or capability_to_tool_id(current.get("capability_name"))
        ),
        effect_class=current.get("effect_class")
        or tool_effect_class(
            current.get("tool_id")
            or capability_to_tool_id(current.get("capability_name"))
        ),
        trace_id=run.get("trace_id"),
        note=f"Action {command_type} by operator chat",
        is_policy_event=False,
        anchors={
            "experiment_id": run.get("experiment_id"),
            "variant_id": current.get("variant_id"),
            "validation_job_id": current.get("validation_job_id"),
            "hypothesis_id": current.get("hypothesis_id"),
            "snapshot_version": current.get("snapshot_version"),
            "metric_id": None,
        },
    )
    return updated or action


def decide_agent_action(
    *,
    deps: AppDeps,
    action_id: str,
    client_id: str,
    user_id: Optional[str],
    decision: str,
) -> Dict[str, Any]:
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=client_id
    )
    if not action:
        raise ValueError("Agent action not found")
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("Invalid decision")
    run_row = deps.agent_runs.get_agent_run(
        run_id=str(action.get("agent_run_id") or ""), client_id=client_id
    )
    if normalized_decision == "approve" and run_row:
        _validate_approval_policy(deps=deps, run=run_row, action=action)
    updated = deps.agent_actions.update_agent_action_status(
        action_id=action_id,
        status="approved" if normalized_decision == "approve" else "rejected",
    )
    current = updated or action
    deps.agent_events.create_agent_event(
        agent_run_id=str(current.get("agent_run_id") or ""),
        action_id=str(current.get("id") or action_id),
        sequence=int(current.get("sequence") or 0),
        event_type=f"action_{'approved' if normalized_decision == 'approve' else 'rejected'}",
        status="approved" if normalized_decision == "approve" else "rejected",
        capability_name=str(current.get("capability_name") or "") or None,
        capability_version=str(current.get("capability_version") or "") or None,
        principal_type=run_row.get("principal_type") if run_row else "human",
        principal_id=run_row.get("principal_id") if run_row else (user_id or None),
        tool_id=current.get("tool_id")
        or capability_to_tool_id(current.get("capability_name")),
        skill_id=current.get("skill_id")
        or skill_id_for_tool_id(
            current.get("tool_id")
            or capability_to_tool_id(current.get("capability_name"))
        ),
        effect_class=current.get("effect_class")
        or tool_effect_class(
            current.get("tool_id")
            or capability_to_tool_id(current.get("capability_name"))
        ),
        trace_id=run_row.get("trace_id") if run_row else None,
        note=f"Action {normalized_decision} by operator",
        is_policy_event=False,
        anchors={
            "experiment_id": run_row.get("experiment_id") if run_row else None,
            "variant_id": current.get("variant_id"),
            "validation_job_id": current.get("validation_job_id"),
            "hypothesis_id": current.get("hypothesis_id"),
            "snapshot_version": current.get("snapshot_version"),
            "metric_id": None,
        },
    )
    return updated or action


def _validate_approval_policy(
    *, deps: AppDeps, run: Dict[str, Any], action: Dict[str, Any]
) -> None:
    capability_name = str(action.get("capability_name") or "")
    spec = get_capability_spec(capability_name)
    if not spec:
        return
    action_with_defaults = {
        **action,
        "tool_id": action.get("tool_id") or capability_to_tool_id(capability_name),
        "effect_class": action.get("effect_class")
        or tool_effect_class(action.get("tool_id") or capability_to_tool_id(capability_name)),
    }
    try:
        PolicyEnforcer().validate_action_approval(
            run=run,
            action=action_with_defaults,
            spec=spec,
            inputs=spec.normalize_inputs(action.get("inputs") or {}),
        )
    except PolicyError as exc:
        raise ValueError(str(exc)) from exc
