from __future__ import annotations

from typing import Any, Dict, List

from application.services.agent_runtime.registry import get_capability_spec

_LEARNING_MEMORY_MUTATION_CAPABILITIES = {"update_posterior_and_decisions"}


class HarnessPostureError(ValueError):
    pass


def validate_harness_capability_effects(
    *, harness_profile: Dict[str, Any], allowed_capabilities: List[str]
) -> None:
    harness_id = str(harness_profile.get("id") or "").strip()
    allowed_effect_classes = {
        str(item).strip()
        for item in list(harness_profile.get("allowed_effect_classes") or [])
        if str(item).strip()
    }
    if not allowed_effect_classes:
        return
    blocked: List[str] = []
    for capability_name in allowed_capabilities:
        spec = get_capability_spec(str(capability_name or "").strip())
        effect_class = str(getattr(spec, "effect_class", "") or "").strip() if spec else ""
        if effect_class and effect_class not in allowed_effect_classes:
            blocked.append(f"{capability_name} ({effect_class})")
    if blocked:
        raise HarnessPostureError(
            f"Harness '{harness_id}' does not allow capability effect class: "
            + ", ".join(blocked)
        )


def validate_harness_memory_policy(
    *, harness_profile: Dict[str, Any], allowed_capabilities: List[str]
) -> None:
    memory_policy = str(harness_profile.get("memory_policy") or "").strip()
    if memory_policy != "no_mutation":
        return
    blocked = [
        str(capability).strip()
        for capability in allowed_capabilities
        if str(capability).strip() in _LEARNING_MEMORY_MUTATION_CAPABILITIES
    ]
    if blocked:
        harness_id = str(harness_profile.get("id") or "").strip()
        raise HarnessPostureError(
            f"Harness '{harness_id}' memory_policy forbids learning/memory mutation: "
            + ", ".join(blocked)
        )


def validate_harness_runtime_posture(
    *, harness_profile: Dict[str, Any], run_mode: str, policy_profile_id: str
) -> None:
    harness_id = str(harness_profile.get("id") or "").strip()
    allowed_run_modes = {
        str(item).strip()
        for item in list(harness_profile.get("allowed_run_modes") or [])
        if str(item).strip()
    }
    if allowed_run_modes and run_mode not in allowed_run_modes:
        raise HarnessPostureError(
            f"Harness '{harness_id}' does not allow run_mode: {run_mode}"
        )
    allowed_policy_profiles = {
        str(item).strip()
        for item in list(harness_profile.get("allowed_policy_profile_ids") or [])
        if str(item).strip()
    }
    if allowed_policy_profiles and policy_profile_id not in allowed_policy_profiles:
        raise HarnessPostureError(
            f"Harness '{harness_id}' does not allow policy_profile_id: {policy_profile_id}"
        )


__all__ = [
    "HarnessPostureError",
    "validate_harness_capability_effects",
    "validate_harness_memory_policy",
    "validate_harness_runtime_posture",
]
