from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import skill_id_for_tool_id
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import get_capability_spec


def _hash_payload(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except Exception:
        encoded = str(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()



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
        capability_version=str(action.get("capability_version") or "") if action else None,
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
            blockers.append("Change-plan needs at least one allowed recovery capability.")
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
        if (
            str(run.get("policy_profile_id") or "").strip().lower() == "observe"
            and spec.effect_class not in {"read", "recommend"}
        ):
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
        warnings.append("Canceling a run is terminal and should be treated as an operator intervention.")
    if command_type == "pause":
        warnings.append("Pausing preserves state but stops autonomous progress until resumed.")

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


def _rollback_guidance(
    *, command_type: str, effect_class: str, side_effects: List[str]
) -> str:
    if command_type == "reject":
        return "Rejection is reversible by creating a new proposed action if needed."
    if command_type == "pause":
        return "Resume with start once the operator is ready."
    if command_type == "cancel":
        return "Cancel is terminal. Create a new run to continue from the same objective."
    if effect_class == "write_high_risk":
        return "High-risk writes may need a compensating action or manual rollback after execution."
    if effect_class == "external_side_effect":
        return "External side effects may not be fully reversible; confirm provider/job state before retrying."
    if side_effects:
        return "Low-risk writes can usually be superseded by a later action, but the audit trail is permanent."
    return "No direct side effects are expected from this command."


def _capability_side_effects(capability_name: str) -> List[str]:
    spec = get_capability_spec(capability_name)
    return list(spec.side_effects) if spec else []


def _capability_rollback_guidance(capability_name: str, effect_class: str | None) -> str:
    return _rollback_guidance(
        command_type="execute",
        effect_class=str(effect_class or ""),
        side_effects=_capability_side_effects(capability_name),
    )


def _compensating_actions_for_capability(
    *,
    capability_name: str,
    effect_class: str | None,
    allowed_capabilities: List[str],
) -> List[Dict[str, Any]]:
    allowed = {
        str(item).strip()
        for item in list(allowed_capabilities or [])
        if str(item).strip()
    }
    effect = str(effect_class or "").strip()
    side_effects = _capability_side_effects(capability_name)
    recommendations: List[Dict[str, Any]] = []

    def add_capability(
        *,
        capability: str,
        label: str,
        rationale: str,
        priority: str,
    ) -> None:
        if capability not in allowed:
            return
        recommendations.append(
            {
                "kind": "capability",
                "command_type": "change_plan",
                "capability_name": capability,
                "label": label,
                "rationale": rationale,
                "priority": priority,
            }
        )

    if effect == "external_side_effect":
        add_capability(
            capability="review_validation_readiness",
            label="Review provider and validation state before retry",
            rationale=(
                "External validation jobs may keep running outside this system; "
                "inspect provider/job state before creating another external request."
            ),
            priority="high",
        )
    if effect == "write_high_risk":
        add_capability(
            capability="review_validation_readiness",
            label="Re-check promotion readiness before any further high-risk write",
            rationale=(
                "High-risk writes may need manual rollback or a compensating change; "
                "re-run readiness gates before approving more promotion/publish work."
            ),
            priority="high",
        )
    if side_effects and effect not in {"read", "recommend"}:
        add_capability(
            capability="recommend_next_action",
            label="Ask policy for the safest compensating next action",
            rationale=(
                "If the side effect is wrong or stale, create a recommendation "
                "proposal instead of mutating the completed action."
            ),
            priority="medium" if effect == "write_low_risk" else "high",
        )
    return recommendations


def _recovery_template_for_capability(
    *,
    capability_name: str,
    run: Dict[str, Any],
    source_action: Optional[Dict[str, Any]],
    strategy: str,
) -> Dict[str, Any]:
    source_capability = str((source_action or {}).get("capability_name") or "").strip()
    source_error = str((source_action or {}).get("error") or "").strip()
    variant_id = str((source_action or {}).get("variant_id") or "").strip()
    validation_job_id = str((source_action or {}).get("validation_job_id") or "").strip()
    template: Dict[str, Any] = {
        "id": f"recovery.{capability_name}",
        "strategy": strategy,
        "inputs": {
            "recovery_context": {
                "source_action_id": (source_action or {}).get("id"),
                "source_capability_name": source_capability or None,
                "source_error": source_error or None,
                "strategy": strategy,
            }
        },
        "rationale": "Use the registry recovery template for this capability.",
        "rollback_guidance": None,
    }
    if run.get("experiment_id"):
        template["inputs"]["experiment_id"] = run.get("experiment_id")
    if variant_id and capability_name in {
        "review_validation_readiness",
        "request_synthetic_validation",
        "update_posterior_and_decisions",
        "promote_variant_lab",
        "promote_variant_prod",
        "publish_copy_revision",
    }:
        template["inputs"]["variant_id"] = variant_id
    if validation_job_id:
        template["inputs"]["validation_job_id"] = validation_job_id

    if capability_name == "request_synthetic_validation":
        template["inputs"]["auto_run"] = False
        template["rationale"] = (
            "Prepare a validation recovery request without auto-running the provider; "
            "the operator should inspect provider/job state before execution."
        )
        template["rollback_guidance"] = (
            "Because this may create external provider work, keep auto_run disabled until "
            "provider state and duplicate-job risk are reviewed."
        )
    elif capability_name == "review_validation_readiness":
        template["rationale"] = (
            "Re-check readiness gates before creating more recovery work or promotion actions."
        )
    elif capability_name == "recommend_next_action":
        template["rationale"] = (
            "Ask policy for the safest next action using the failed action as recovery context."
        )
    elif capability_name in {"promote_variant_lab", "promote_variant_prod"}:
        template["rationale"] = (
            "Recreate promotion as a proposed action only after readiness and rollback context are reviewed."
        )
    elif capability_name == "publish_copy_revision":
        template["rationale"] = (
            "Recreate publish as a proposed action only after copy diff, promotion evidence, and rollback owner are reviewed."
        )
    return template


def _apply_recovery_template(
    *,
    capability_name: str,
    inputs: Dict[str, Any],
    run: Dict[str, Any],
    source_action: Optional[Dict[str, Any]],
    strategy: str,
) -> Dict[str, Any]:
    template = _recovery_template_for_capability(
        capability_name=capability_name,
        run=run,
        source_action=source_action,
        strategy=strategy,
    )
    merged_inputs = dict(template.get("inputs") or {})
    merged_inputs.update(inputs)
    recovery_context = dict(merged_inputs.get("recovery_context") or {})
    recovery_context.setdefault("template_id", template.get("id"))
    recovery_context.setdefault("strategy", strategy)
    merged_inputs["recovery_context"] = recovery_context
    return {**template, "inputs": merged_inputs}


def _preflight_summary(
    *, command_type: str, risk_level: str, blockers: List[str], warnings: List[str]
) -> str:
    if blockers:
        return f"Preflight blocked {command_type}: {blockers[0]}"
    if warnings:
        return f"Preflight passed with {risk_level} risk: {warnings[0]}"
    return f"Preflight passed with {risk_level} risk."


def _requested_recovery_capability(metadata: Optional[Dict[str, Any]]) -> str:
    if not isinstance(metadata, dict):
        return ""
    raw = metadata.get("capability_name") or metadata.get("target_capability")
    return str(raw or "").strip()


