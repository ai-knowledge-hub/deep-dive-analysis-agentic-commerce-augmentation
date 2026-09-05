from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    skill_id_for_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.registry import (
    get_capability_spec,
    get_harness_profile,
    version_context_for_capability,
)


class RecoveryActionCreationError(RuntimeError):
    """Raised when recovery action admission loses a terminal-state race."""


_RECOVERY_ACTION_RUN_STATUSES = ("planned", "running", "failed", "paused")


def _hash_payload(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except Exception:
        encoded = str(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rollback_guidance(
    *, command_type: str, effect_class: str, side_effects: List[str]
) -> str:
    if command_type == "reject":
        return "Rejection is reversible by creating a new proposed action if needed."
    if command_type == "pause":
        return "Resume with start once the operator is ready."
    if command_type == "cancel":
        return (
            "Cancel is terminal. Create a new run to continue from the same objective."
        )
    if command_type == "reconcile_effect":
        return (
            "Reconciliation does not invoke the provider. Invalid or incomplete "
            "evidence leaves the effect uncertain for later recovery."
        )
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


def _capability_rollback_guidance(
    capability_name: str, effect_class: str | None
) -> str:
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
    validation_job_id = str(
        (source_action or {}).get("validation_job_id") or ""
    ).strip()
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


def _requested_recovery_capability(metadata: Optional[Dict[str, Any]]) -> str:
    if not isinstance(metadata, dict):
        return ""
    raw = metadata.get("capability_name") or metadata.get("target_capability")
    return str(raw or "").strip()


def _active_harness(run: Dict[str, Any]) -> Dict[str, Any]:
    return get_harness_profile(str(run.get("harness_id") or "")) or {}


def _harness_context(run: Dict[str, Any]) -> Dict[str, Any]:
    harness = _active_harness(run)
    return {
        "harness_id": harness.get("id") or run.get("harness_id"),
        "retry_strategy": harness.get("retry_strategy"),
        "fallback_order": list(harness.get("fallback_order") or []),
        "approval_strategy": harness.get("approval_strategy"),
        "memory_policy": harness.get("memory_policy"),
        "stopping_conditions": list(harness.get("stopping_conditions") or []),
    }


def _default_retry_strategy(run: Dict[str, Any]) -> str:
    strategy = str(_active_harness(run).get("retry_strategy") or "").strip()
    if strategy in {"last_safe_checkpoint", "same_action", "create_recovery_action"}:
        return strategy
    if strategy in {"operator_confirmed", "none"}:
        return "same_action"
    return "same_action"


def _fallback_capability_for_run(
    *, run: Dict[str, Any], requested_capability: str, allowed: List[str]
) -> str:
    if requested_capability in allowed:
        return requested_capability
    harness = _active_harness(run)
    fallback_order = [
        str(item).strip() for item in list(harness.get("fallback_order") or [])
    ]
    if "registry_recovery_template" in fallback_order:
        for candidate in (
            "review_validation_readiness",
            "recommend_next_action",
        ):
            if candidate in allowed:
                return candidate
    if "operator_chat" in fallback_order and "recommend_next_action" in allowed:
        return "recommend_next_action"
    if "recommend_next_action" in allowed:
        return "recommend_next_action"
    return allowed[0] if allowed else ""


def create_change_plan_recovery_action(
    *,
    deps: AppDeps,
    run_id: str,
    run: Dict[str, Any],
    source_action: Optional[Dict[str, Any]],
    command_receipt: Dict[str, Any],
    message: Optional[str],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    allowed = [
        str(item).strip()
        for item in list(run.get("allowed_capabilities") or [])
        if str(item).strip()
    ]
    requested_capability = _requested_recovery_capability(metadata)
    capability_name = _fallback_capability_for_run(
        run=run,
        requested_capability=requested_capability,
        allowed=allowed,
    )
    tool_id = capability_to_tool_id(capability_name)
    skill_id = skill_id_for_tool_id(
        tool_id,
        preferred_skill_id=metadata.get("skill_id")
        or metadata.get("preferred_skill_id"),
    )
    effect_class = tool_effect_class(tool_id)
    version_context = version_context_for_capability(
        capability_name,
        tool_id=tool_id,
        skill_id=skill_id,
        registry_version_override=run.get("registry_version"),
        registry_fingerprint_override=run.get("registry_fingerprint"),
    )
    recovery_inputs = metadata.get("inputs")
    inputs = dict(recovery_inputs) if isinstance(recovery_inputs, dict) else {}
    if run.get("experiment_id") and not inputs.get("experiment_id"):
        inputs["experiment_id"] = run.get("experiment_id")
    recovery_template = _apply_recovery_template(
        capability_name=capability_name,
        inputs=inputs,
        run=run,
        source_action=source_action,
        strategy=str(metadata.get("recovery_strategy") or "propose_next_action"),
    )
    inputs = dict(recovery_template.get("inputs") or {})
    recovery_context = dict(inputs.get("recovery_context") or {})
    recovery_context.setdefault("harness", _harness_context(run))
    recovery_context.setdefault(
        "selection_reason",
        "requested_capability"
        if requested_capability and requested_capability == capability_name
        else "harness_fallback",
    )
    inputs["recovery_context"] = recovery_context
    rollback_guidance = recovery_template.get(
        "rollback_guidance"
    ) or _capability_rollback_guidance(capability_name, effect_class)
    recovery_action = deps.agent_actions.create_agent_action(
        agent_run_id=run_id,
        sequence=0,
        status="proposed",
        capability_name=capability_name,
        capability_version=None,
        inputs=inputs,
        outputs={},
        inputs_hash=_hash_payload(inputs),
        outputs_hash=None,
        rationale=message
        or str(recovery_template.get("rationale") or "")
        or "Recovery action proposed from operator change-plan command.",
        confidence=0.5,
        snapshot_version=source_action.get("snapshot_version")
        if source_action
        else None,
        hypothesis_id=source_action.get("hypothesis_id") if source_action else None,
        variant_id=source_action.get("variant_id") if source_action else None,
        validation_job_id=source_action.get("validation_job_id")
        if source_action
        else None,
        tool_id=tool_id,
        skill_id=skill_id,
        registry_version=version_context["registry_version"],
        registry_fingerprint=version_context["registry_fingerprint"],
        tool_version=version_context["tool_version"],
        skill_version=version_context["skill_version"],
        effect_class=effect_class,
        side_effects=_capability_side_effects(capability_name),
        rollback_guidance=str(rollback_guidance),
        compensating_actions=_compensating_actions_for_capability(
            capability_name=capability_name,
            effect_class=effect_class,
            allowed_capabilities=allowed,
        ),
        dedupe_key=f"change_plan:{command_receipt.get('id')}",
        client_id=str(run.get("client_id") or ""),
        admissible_run_statuses=_RECOVERY_ACTION_RUN_STATUSES,
        allocate_run_sequence=True,
    )
    if not recovery_action:
        raise RecoveryActionCreationError(
            "Run became terminal before the recovery action could be committed; "
            "create a new run to continue."
        )
    deps.agent_events.create_agent_event(
        agent_run_id=run_id,
        action_id=str(recovery_action.get("id") or ""),
        sequence=int(recovery_action.get("sequence") or 0),
        event_type="action_recovery_proposed",
        status="proposed",
        capability_name=str(recovery_action.get("capability_name") or "") or None,
        capability_version=None,
        principal_type=run.get("principal_type"),
        principal_id=run.get("principal_id"),
        tool_id=recovery_action.get("tool_id"),
        skill_id=recovery_action.get("skill_id"),
        effect_class=recovery_action.get("effect_class"),
        trace_id=run.get("trace_id"),
        note="Recovery action proposed by operator change-plan command",
        is_policy_event=False,
        anchors={
            "experiment_id": run.get("experiment_id"),
            "variant_id": recovery_action.get("variant_id"),
            "validation_job_id": recovery_action.get("validation_job_id"),
            "hypothesis_id": recovery_action.get("hypothesis_id"),
            "snapshot_version": recovery_action.get("snapshot_version"),
            "metric_id": None,
            "source_command_id": command_receipt.get("id"),
            "source_action_id": source_action.get("id") if source_action else None,
            "recovery_strategy": metadata.get(
                "recovery_strategy", "propose_next_action"
            ),
            "recovery_template_id": recovery_template.get("id"),
            "harness_id": run.get("harness_id"),
            "harness_retry_strategy": _harness_context(run).get("retry_strategy"),
            "harness_fallback_order": _harness_context(run).get("fallback_order"),
            "side_effects": recovery_action.get("side_effects"),
            "rollback_guidance": recovery_action.get("rollback_guidance"),
            "compensating_actions": recovery_action.get("compensating_actions"),
        },
    )
    return recovery_action


def create_retry_action(
    *,
    deps: AppDeps,
    run_id: str,
    run: Dict[str, Any],
    action: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    retry_count = int(action.get("retry_count") or 0) + 1
    retry_strategy = str(
        metadata.get("retry_strategy") or _default_retry_strategy(run)
    ).strip()
    allowed = [
        str(item).strip()
        for item in list(run.get("allowed_capabilities") or [])
        if str(item).strip()
    ]
    if retry_strategy == "create_recovery_action":
        requested_capability = _requested_recovery_capability(metadata)
        capability_name = _fallback_capability_for_run(
            run=run,
            requested_capability=requested_capability,
            allowed=allowed,
        )
        if not capability_name:
            capability_name = str(action.get("capability_name") or "")
    else:
        capability_name = str(action.get("capability_name") or "")
    retry_inputs = dict(action.get("inputs") or {})
    if retry_strategy == "last_safe_checkpoint":
        retry_inputs["retry_from"] = "last_safe_checkpoint"
        retry_inputs["harness_retry_strategy"] = _harness_context(run).get(
            "retry_strategy"
        )
    if retry_strategy == "create_recovery_action":
        retry_inputs["recovery_from_action_id"] = action.get("id")
    tool_id = capability_to_tool_id(capability_name)
    skill_id = skill_id_for_tool_id(
        tool_id,
        preferred_skill_id=metadata.get("skill_id")
        or metadata.get("preferred_skill_id"),
    )
    effect_class = tool_effect_class(tool_id)
    version_context = version_context_for_capability(
        capability_name,
        tool_id=tool_id,
        skill_id=skill_id,
        registry_version_override=run.get("registry_version"),
        registry_fingerprint_override=run.get("registry_fingerprint"),
    )
    recovery_template: Dict[str, Any] = {}
    if retry_strategy == "create_recovery_action":
        recovery_template = _apply_recovery_template(
            capability_name=capability_name,
            inputs=retry_inputs,
            run=run,
            source_action=action,
            strategy=retry_strategy,
        )
        retry_inputs = dict(recovery_template.get("inputs") or retry_inputs)
    retry_context = dict(retry_inputs.get("recovery_context") or {})
    if retry_strategy in {"last_safe_checkpoint", "create_recovery_action"}:
        retry_context.setdefault("harness", _harness_context(run))
        retry_context.setdefault("strategy", retry_strategy)
        retry_inputs["recovery_context"] = retry_context
    rollback_guidance = recovery_template.get(
        "rollback_guidance"
    ) or _capability_rollback_guidance(capability_name, effect_class)
    retry_action = deps.agent_actions.create_agent_action(
        agent_run_id=run_id,
        sequence=0,
        status="proposed",
        capability_name=capability_name,
        capability_version=(
            None
            if retry_strategy == "create_recovery_action"
            else action.get("capability_version")
        ),
        inputs=retry_inputs,
        outputs={},
        inputs_hash=_hash_payload(retry_inputs),
        outputs_hash=None,
        rationale=(
            f"{retry_strategy} proposed from failed action {str(action.get('id') or '')[:8]}. "
            f"{recovery_template.get('rationale') or action.get('error') or action.get('rationale') or ''}"
        ).strip(),
        confidence=action.get("confidence"),
        snapshot_version=action.get("snapshot_version"),
        hypothesis_id=action.get("hypothesis_id"),
        variant_id=action.get("variant_id"),
        validation_job_id=action.get("validation_job_id"),
        tool_id=tool_id,
        skill_id=skill_id,
        registry_version=version_context["registry_version"],
        registry_fingerprint=version_context["registry_fingerprint"],
        tool_version=version_context["tool_version"],
        skill_version=version_context["skill_version"],
        effect_class=effect_class,
        side_effects=_capability_side_effects(capability_name),
        rollback_guidance=str(rollback_guidance),
        compensating_actions=_compensating_actions_for_capability(
            capability_name=capability_name,
            effect_class=effect_class,
            allowed_capabilities=allowed,
        ),
        retry_count=retry_count,
        dedupe_key=None,
        client_id=str(run.get("client_id") or ""),
        admissible_run_statuses=_RECOVERY_ACTION_RUN_STATUSES,
        allocate_run_sequence=True,
        retry_identity_prefix=f"retry:{action.get('id')}:{retry_strategy}:",
    )
    if not retry_action:
        raise RecoveryActionCreationError(
            "Run became terminal before the retry action could be committed; "
            "create a new run to continue."
        )
    deps.agent_events.create_agent_event(
        agent_run_id=run_id,
        action_id=str(retry_action.get("id") or ""),
        sequence=int(retry_action.get("sequence") or 0),
        event_type=(
            "action_recovery_proposed"
            if retry_strategy == "create_recovery_action"
            else "action_retry_proposed"
        ),
        status="proposed",
        capability_name=str(retry_action.get("capability_name") or "") or None,
        capability_version=str(retry_action.get("capability_version") or "") or None,
        principal_type=run.get("principal_type"),
        principal_id=run.get("principal_id"),
        tool_id=retry_action.get("tool_id"),
        skill_id=retry_action.get("skill_id"),
        effect_class=retry_action.get("effect_class"),
        trace_id=run.get("trace_id"),
        note="Retry action proposed by operator chat",
        is_policy_event=False,
        anchors={
            "experiment_id": run.get("experiment_id"),
            "variant_id": retry_action.get("variant_id"),
            "validation_job_id": retry_action.get("validation_job_id"),
            "hypothesis_id": retry_action.get("hypothesis_id"),
            "snapshot_version": retry_action.get("snapshot_version"),
            "metric_id": None,
            "original_action_id": action.get("id"),
            "retry_count": retry_action.get("retry_count"),
            "retry_strategy": retry_strategy,
            "recovery_template_id": recovery_template.get("id"),
            "harness_id": run.get("harness_id"),
            "harness_retry_strategy": _harness_context(run).get("retry_strategy"),
            "harness_fallback_order": _harness_context(run).get("fallback_order"),
            "side_effects": retry_action.get("side_effects"),
            "rollback_guidance": retry_action.get("rollback_guidance"),
            "compensating_actions": retry_action.get("compensating_actions"),
        },
    )
    return retry_action


__all__ = [
    "RecoveryActionCreationError",
    "create_change_plan_recovery_action",
    "create_retry_action",
]
