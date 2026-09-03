from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import skill_id_for_tool_id
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import get_capability_spec
from application.services.agent_runtime.commands.recovery import (
    _default_retry_strategy,
    _harness_context,
    _requested_recovery_capability,
    _rollback_guidance,
)
from application.services.agent_runtime.commands.reconciliation_preflight import (
    effect_reconciliation_preflight,
)
from application.services.agent_runtime.commands.lifecycle_preflight import (
    command_lifecycle_blockers,
)
from domain.workflow.approval import ApprovalAuthority


def _record_command_event(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    command_type: str,
    status: str,
    action: Optional[Dict[str, Any]] = None,
    note: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    command_authority: ApprovalAuthority | None = None,
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
        principal_type=(
            command_authority.principal_type.value
            if command_authority
            else run.get("principal_type")
        ),
        principal_id=(
            command_authority.principal_id
            if command_authority
            else run.get("principal_id")
        ),
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
            "command_authority_source": (
                command_authority.authority_source if command_authority else None
            ),
            "command_authority_version": (
                command_authority.authority_version if command_authority else None
            ),
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

    if (
        command_type in {"approve", "reject", "retry", "reconcile_effect"}
        and not action
    ):
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
    blockers.extend(
        command_lifecycle_blockers(
            command_type=command_type,
            run_status=run_status,
            run_mode=run_mode,
        )
    )
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
        retry_strategy = str(
            (metadata or {}).get("retry_strategy") or _default_retry_strategy(run)
        ).strip()
        requested_capability = _requested_recovery_capability(metadata)
        harness_context = _harness_context(run)
        if not (metadata or {}).get("retry_strategy") and harness_context.get(
            "retry_strategy"
        ):
            warnings.append(
                "Retry strategy defaulted from harness "
                f"'{harness_context.get('harness_id')}': {retry_strategy}."
            )
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
    reconciliation = effect_reconciliation_preflight(
        deps=deps,
        run=run,
        action=action,
        command_type=command_type,
        current_side_effects=side_effects,
    )
    blockers.extend(reconciliation["blockers"])
    warnings.extend(reconciliation["warnings"])
    side_effects = reconciliation["side_effects"]

    if action and spec and command_type in {"approve", "retry"}:
        inputs = spec.normalize_inputs(action.get("inputs") or {})
        try:
            if command_type == "approve":
                PolicyEnforcer().validate_action_approval(
                    run=run,
                    action=action,
                    spec=spec,
                    inputs=inputs,
                )
            else:
                all_actions = deps.agent_actions.list_agent_actions(
                    agent_run_id=str(run.get("id") or ""), limit=500
                )
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
        "reconcile_effect",
        "retry",
        "step",
    }:
        risk_level = "medium"

    return {
        "allowed": not blockers,
        "command_type": command_type,
        "risk_level": risk_level,
        "requires_confirmation": command_type in {"reconcile_effect", "retry", "step"}
        or risk_level == "high"
        or bool(blockers),
        "requires_approval": bool(run.get("requires_approval")) or risk_level == "high",
        "effect_class": effect_class,
        "tool_id": tool_id,
        "skill_id": action.get("skill_id") if action else None,
        "side_effects": side_effects,
        "blockers": blockers,
        "warnings": warnings,
        "harness": _harness_context(run),
        "recommended_retry_strategy": _default_retry_strategy(run)
        if command_type == "retry"
        else None,
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
