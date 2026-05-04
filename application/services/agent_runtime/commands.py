from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    skill_id_for_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import (
    get_capability_spec,
)
from application.services.agent_runtime.recovery import (
    _requested_recovery_capability,
    _rollback_guidance,
)


def _record_command_event(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    command_type: str,
    status: str,
    action: Optional[Dict[str, Any]] = None,
    note: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return deps.agent_events.create_agent_event(
        agent_run_id=str(run.get("id") or ""),
        action_id=str(action.get("id") or "") if action else None,
        sequence=int(action.get("sequence") or 0) if action else 0,
        event_type=f"operator_command_{command_type}",
        status=status,
        capability_name=str(action.get("capability_name") or "") if action else None,
        capability_version=str(action.get("capability_version") or "")
        if action
        else None,
        principal_type=run.get("principal_type"),
        principal_id=run.get("principal_id"),
        tool_id=action.get("tool_id") if action else None,
        skill_id=(
            action.get("skill_id") or skill_id_for_tool_id(action.get("tool_id"))
            if action
            else None
        ),
        effect_class=action.get("effect_class") if action else None,
        trace_id=run.get("trace_id"),
        note=note or f"Operator command: {command_type}",
        is_policy_event=False,
        anchors={
            "experiment_id": run.get("experiment_id"),
            "variant_id": action.get("variant_id") if action else None,
            "validation_job_id": action.get("validation_job_id") if action else None,
            "hypothesis_id": action.get("hypothesis_id") if action else None,
            "snapshot_version": action.get("snapshot_version") if action else None,
            "metric_id": None,
            "command_type": command_type,
            "metadata": metadata or {},
        },
    )


def _command_preflight(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    command_type: str,
    action: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    run_status = str(run.get("status") or "").lower()
    run_mode = str(run.get("run_mode") or "plan_only").lower()
    effect_class = action.get("effect_class") if action else None
    tool_id = action.get("tool_id") if action else None
    capability_name = str(action.get("capability_name") or "") if action else None
    spec = get_capability_spec(capability_name or "") if capability_name else None
    if spec:
        effect_class = effect_class or spec.effect_class
        tool_id = tool_id or spec.tool_id

    blockers: List[str] = []
    warnings: List[str] = []
    side_effects = list(spec.side_effects) if spec else []

    if command_type in {"approve", "reject", "retry"} and not action:
        blockers.append("This command requires an action_id.")
    if command_type == "approve" and action:
        if str(action.get("status") or "").lower() != "proposed":
            blockers.append("Only proposed actions can be approved.")
    if command_type == "reject" and action:
        if str(action.get("status") or "").lower() not in {"proposed", "approved"}:
            blockers.append("Only proposed or approved actions can be rejected.")
    if command_type == "retry" and action:
        if str(action.get("status") or "").lower() != "failed":
            blockers.append("Retry is only available for failed actions.")
    if command_type == "step":
        if run_mode == "plan_only":
            blockers.append("Run is plan-only. Switch mode before executing steps.")
        if run_status in {"canceled", "completed"}:
            blockers.append("Run is not executable in its current status.")
    if command_type == "start" and run_status in {"canceled", "completed"}:
        blockers.append("Canceled or completed runs cannot be started.")
    if command_type == "cancel" and run_status in {"canceled", "completed"}:
        blockers.append("Run is already terminal.")
    if command_type == "change_plan":
        allowed = [
            str(item).strip()
            for item in list(run.get("allowed_capabilities") or [])
            if str(item).strip()
        ]
        requested_capability = _requested_recovery_capability(metadata)
        if not allowed:
            blockers.append(
                "Change-plan needs at least one allowed recovery capability."
            )
        elif requested_capability and requested_capability not in allowed:
            blockers.append(
                f"Recovery capability '{requested_capability}' is not allowed for this run."
            )
        if requested_capability and not get_capability_spec(requested_capability):
            blockers.append(
                f"Recovery capability '{requested_capability}' has no executable registry spec."
            )
        warnings.append(
            "Change-plan creates a proposed recovery action for operator review; it does not execute immediately."
        )
    if command_type == "retry" and action:
        retry_strategy = str((metadata or {}).get("retry_strategy") or "").strip()
        requested_capability = _requested_recovery_capability(metadata)
        if retry_strategy == "create_recovery_action" and requested_capability:
            allowed = [
                str(item).strip()
                for item in list(run.get("allowed_capabilities") or [])
                if str(item).strip()
            ]
            if requested_capability not in allowed:
                blockers.append(
                    f"Recovery capability '{requested_capability}' is not allowed for this run."
                )
            elif not get_capability_spec(requested_capability):
                blockers.append(
                    f"Recovery capability '{requested_capability}' has no executable registry spec."
                )

    if action and spec and command_type == "retry":
        inputs = spec.normalize_inputs(action.get("inputs") or {})
        all_actions = deps.agent_actions.list_agent_actions(
            agent_run_id=str(run.get("id") or ""), limit=500
        )
        try:
            PolicyEnforcer().validate_action_execution(
                run=run,
                action=action,
                spec=spec,
                all_actions=all_actions,
                inputs=inputs,
            )
        except PolicyError as exc:
            blockers.append(str(exc))
    elif action and spec:
        allowed_capabilities = {
            str(item).strip()
            for item in list(run.get("allowed_capabilities") or [])
            if str(item).strip()
        }
        if spec.name not in allowed_capabilities:
            blockers.append(f"Capability '{spec.name}' is not allowed for this run")
        if str(
            run.get("policy_profile_id") or ""
        ).strip().lower() == "observe" and spec.effect_class not in {
            "read",
            "recommend",
        }:
            blockers.append(
                f"Policy profile 'observe' forbids effect class '{spec.effect_class}' "
                f"for tool '{tool_id or '<unknown>'}'"
            )
    elif action and not spec:
        warnings.append(
            f"No executable capability spec was found for '{capability_name or 'unknown'}'."
        )

    if command_type in {"approve", "retry", "step"} and effect_class in {
        "write_high_risk",
        "external_side_effect",
    }:
        warnings.append(
            f"This command may trigger {effect_class} work through tool '{tool_id or 'unknown'}'."
        )
    if command_type == "cancel":
        warnings.append(
            "Canceling a run is terminal and should be treated as an operator intervention."
        )
    if command_type == "pause":
        warnings.append(
            "Pausing preserves state but stops autonomous progress until resumed."
        )

    risk_level = "low"
    if command_type == "cancel" or effect_class == "write_high_risk":
        risk_level = "high"
    elif effect_class == "external_side_effect" or command_type in {
        "change_plan",
        "retry",
        "step",
    }:
        risk_level = "medium"

    return {
        "allowed": not blockers,
        "command_type": command_type,
        "risk_level": risk_level,
        "requires_confirmation": command_type in {"retry", "step"}
        or risk_level == "high"
        or bool(blockers),
        "requires_approval": bool(run.get("requires_approval")) or risk_level == "high",
        "effect_class": effect_class,
        "tool_id": tool_id,
        "skill_id": action.get("skill_id") if action else None,
        "side_effects": side_effects,
        "blockers": blockers,
        "warnings": warnings,
        "rollback_guidance": _rollback_guidance(
            command_type=command_type,
            effect_class=str(effect_class or ""),
            side_effects=side_effects,
        ),
        "summary": _preflight_summary(
            command_type=command_type,
            risk_level=risk_level,
            blockers=blockers,
            warnings=warnings,
        ),
    }


def _preflight_summary(
    *, command_type: str, risk_level: str, blockers: List[str], warnings: List[str]
) -> str:
    if blockers:
        return f"Preflight blocked {command_type}: {blockers[0]}"
    if warnings:
        return f"Preflight passed with {risk_level} risk: {warnings[0]}"
    return f"Preflight passed with {risk_level} risk."


def apply_command_action_decision(
    *,
    deps: AppDeps,
    run_id: str,
    run: Dict[str, Any],
    action: Dict[str, Any],
    command_type: str,
) -> Dict[str, Any]:
    status = "rejected" if command_type == "reject" else "approved"
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
    updated = deps.agent_actions.update_agent_action_status(
        action_id=action_id,
        status="approved" if normalized_decision == "approve" else "rejected",
    )
    current = updated or action
    run_row = deps.agent_runs.get_agent_run(
        run_id=str(current.get("agent_run_id") or ""), client_id=client_id
    )
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
