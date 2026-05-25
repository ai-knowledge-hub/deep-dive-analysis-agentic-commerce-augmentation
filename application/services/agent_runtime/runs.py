from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    new_trace_id,
    policy_profile_for_run_mode,
    select_skill_for_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.planner import build_initial_plan
from application.services.agent_runtime.commands.recovery import (
    _capability_rollback_guidance,
    _capability_side_effects,
    _compensating_actions_for_capability,
    _hash_payload,
)
from application.services.agent_runtime.harness_posture import (
    HarnessPostureError,
    validate_harness_capability_effects,
    validate_harness_runtime_posture,
)
from application.services.agent_runtime.registry import (
    default_harness_id_for_agent_profile,
    get_capability_spec,
    get_harness_profile,
    harness_profile_supported,
    policy_profile_supported,
    run_mode_supported,
    version_context_for_capability,
)


class AgentRunPlanError(ValueError):
    pass

def create_agent_run_with_initial_plan(
    *,
    deps: AppDeps,
    client_id: str,
    brand_id: Optional[str],
    product_id: Optional[str],
    experiment_id: Optional[str],
    objective: Dict[str, Any],
    allowed_capabilities: List[str],
    capability_versions: Dict[str, Any],
    budgets: Dict[str, Any],
    approval_policy: Dict[str, Any],
    requires_approval: bool,
    run_mode: str | None,
    state: str,
    status: str,
    principal_type: str,
    principal_id: str,
    agent_profile_id: Optional[str],
    harness_id: Optional[str],
    policy_profile_id: Optional[str],
    idempotency_key: Optional[str],
    registry_payload: Dict[str, Any],
    active_registry_fingerprint: str,
    agent_profile_defaults: Optional[Dict[str, Any]] = None,
    preferred_skill_id: Optional[str] = None,
) -> Dict[str, Any]:
    _validate_plan_capabilities(allowed_capabilities or [], objective=objective or {})
    profile_defaults = dict(agent_profile_defaults or {})
    resolved_harness_id = (
        harness_id
        or profile_defaults.get("default_harness_id")
        or default_harness_id_for_agent_profile(
            agent_profile_id=agent_profile_id,
            principal_type=principal_type,
        )
    )
    harness_profile = _harness_profile_from_registry_payload(
        registry_payload=registry_payload,
        harness_id=resolved_harness_id,
    )
    if not harness_profile:
        raise AgentRunPlanError(f"Unsupported harness_id: {resolved_harness_id}")
    normalized_run_mode = str(
        run_mode or harness_profile.get("default_run_mode") or "plan_only"
    ).strip().lower()
    if not run_mode_supported(normalized_run_mode):
        raise AgentRunPlanError(f"Unsupported run_mode: {normalized_run_mode}")
    resolved_policy_profile_id = (
        policy_profile_id
        or profile_defaults.get("default_policy_profile_id")
        or harness_profile.get("default_policy_profile_id")
        or policy_profile_for_run_mode(normalized_run_mode)
    )
    if not policy_profile_supported(resolved_policy_profile_id):
        raise AgentRunPlanError(
            f"Unsupported policy_profile_id: {resolved_policy_profile_id}"
        )
    try:
        validate_harness_runtime_posture(
            harness_profile=harness_profile,
            run_mode=normalized_run_mode,
            policy_profile_id=resolved_policy_profile_id,
        )
        validate_harness_capability_effects(
            harness_profile=harness_profile,
            allowed_capabilities=allowed_capabilities or [],
        )
    except HarnessPostureError as exc:
        raise AgentRunPlanError(str(exc)) from exc
    trace_id = new_trace_id()
    run = deps.agent_runs.create_agent_run(
        client_id=client_id,
        brand_id=brand_id,
        product_id=product_id,
        experiment_id=experiment_id,
        objective=objective or {},
        allowed_capabilities=allowed_capabilities or [],
        capability_versions=capability_versions or {},
        budgets=budgets or {},
        approval_policy=approval_policy or {},
        requires_approval=bool(requires_approval),
        run_mode=normalized_run_mode,
        state=str(state or "battery_ready"),
        status=str(status or "planned"),
        principal_type=principal_type,
        principal_id=principal_id,
        agent_profile_id=agent_profile_id,
        harness_id=resolved_harness_id,
        policy_profile_id=str(resolved_policy_profile_id),
        idempotency_key=idempotency_key,
        trace_id=trace_id,
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=active_registry_fingerprint,
    )
    _seed_initial_plan(
        deps=deps,
        run=run,
        experiment_id=experiment_id,
        allowed_capabilities=allowed_capabilities or [],
        capability_versions=capability_versions or {},
        registry_payload=registry_payload,
        active_registry_fingerprint=active_registry_fingerprint,
        preferred_skill_id=preferred_skill_id,
        harness_profile=harness_profile,
    )
    return run


def _validate_plan_capabilities(
    allowed_capabilities: List[str], *, objective: Dict[str, Any]
) -> None:
    requested = [
        str(capability).strip()
        for capability in allowed_capabilities
        if str(capability).strip()
    ]
    unsupported = [item for item in requested if not get_capability_spec(item)]
    if unsupported:
        raise AgentRunPlanError(
            "Unsupported allowed_capabilities: " + ", ".join(unsupported)
        )
    if requested and not build_initial_plan(
        experiment_id=None,
        allowed_capabilities=requested,
        capability_versions={},
        objective=objective,
    ):
        raise AgentRunPlanError("allowed_capabilities did not produce any initial plan actions")


def _harness_profile_from_registry_payload(
    *, registry_payload: Dict[str, Any], harness_id: str | None
) -> Dict[str, Any] | None:
    normalized = str(harness_id or "").strip()
    for profile in list(registry_payload.get("harness_profiles") or []):
        if str(profile.get("id") or "").strip() == normalized:
            return dict(profile)
    return get_harness_profile(normalized) if harness_profile_supported(normalized) else None


def _seed_initial_plan(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    experiment_id: Optional[str],
    allowed_capabilities: List[str],
    capability_versions: Dict[str, Any],
    registry_payload: Dict[str, Any],
    active_registry_fingerprint: str,
    preferred_skill_id: Optional[str],
    harness_profile: Dict[str, Any],
) -> None:
    plan = build_initial_plan(
        experiment_id=experiment_id,
        allowed_capabilities=allowed_capabilities,
        capability_versions=capability_versions,
        objective=run.get("objective") if isinstance(run.get("objective"), dict) else {},
        planner_mode=str(harness_profile.get("planner_mode") or ""),
    )
    for idx, action in enumerate(plan, start=1):
        tool_id = capability_to_tool_id(action.capability_name)
        skill = select_skill_for_tool_id(tool_id, preferred_skill_id=preferred_skill_id)
        skill_id = skill.id if skill else None
        effect_class = tool_effect_class(tool_id)
        version_context = version_context_for_capability(
            action.capability_name,
            tool_id=tool_id,
            skill_id=skill_id,
            registry_version_override=str(registry_payload["registry_version"]),
            registry_fingerprint_override=active_registry_fingerprint,
        )
        created_action = deps.agent_actions.create_agent_action(
            agent_run_id=run.get("id"),
            sequence=idx,
            status="proposed",
            capability_name=action.capability_name,
            capability_version=action.capability_version,
            inputs=action.inputs,
            outputs={},
            inputs_hash=_hash_payload(action.inputs),
            outputs_hash=None,
            rationale=action.rationale,
            confidence=action.confidence,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
            tool_id=tool_id,
            skill_id=skill_id,
            registry_version=version_context["registry_version"],
            registry_fingerprint=version_context["registry_fingerprint"],
            tool_version=version_context["tool_version"],
            skill_version=version_context["skill_version"],
            effect_class=effect_class,
            side_effects=_capability_side_effects(action.capability_name),
            rollback_guidance=_capability_rollback_guidance(
                action.capability_name, effect_class
            ),
            compensating_actions=_compensating_actions_for_capability(
                capability_name=action.capability_name,
                effect_class=effect_class,
                allowed_capabilities=allowed_capabilities,
            ),
        )
        deps.agent_events.create_agent_event(
            agent_run_id=run.get("id"),
            action_id=created_action.get("id"),
            sequence=idx,
            event_type="action_proposed",
            status="proposed",
            capability_name=action.capability_name,
            capability_version=action.capability_version,
            principal_type=run.get("principal_type"),
            principal_id=run.get("principal_id"),
            tool_id=created_action.get("tool_id"),
            skill_id=created_action.get("skill_id"),
            effect_class=created_action.get("effect_class"),
            trace_id=run.get("trace_id"),
            note=action.rationale,
            is_policy_event=False,
            anchors={
                "experiment_id": run.get("experiment_id"),
                "variant_id": None,
                "validation_job_id": None,
                "hypothesis_id": None,
                "snapshot_version": None,
                "metric_id": None,
                "inputs_hash": created_action.get("inputs_hash"),
                "outputs_hash": created_action.get("outputs_hash"),
                "registry_version": created_action.get("registry_version"),
                "registry_fingerprint": created_action.get("registry_fingerprint"),
                "tool_version": created_action.get("tool_version"),
                "skill_version": created_action.get("skill_version"),
                "receipt_id": created_action.get("receipt_id"),
            },
        )
