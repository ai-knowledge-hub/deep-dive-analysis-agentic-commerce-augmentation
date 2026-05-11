from __future__ import annotations

from typing import Any, Dict, List

from application.services.agent_runtime.registry import (
    policy_profile_supported,
    run_mode_supported,
)

_EDITABLE_FIELDS = (
    "name",
    "description",
    "default_run_mode",
    "default_policy_profile_id",
    "allowed_run_modes",
    "allowed_policy_profile_ids",
    "planner_mode",
    "retry_strategy",
    "fallback_order",
    "approval_strategy",
    "memory_policy",
    "stopping_conditions",
)
_LIST_FIELDS = {
    "allowed_run_modes",
    "allowed_policy_profile_ids",
    "fallback_order",
    "stopping_conditions",
}


def registry_harness_profile_preflight(
    *, harness_id: str, current_profile: Dict[str, Any], proposed_patch: Dict[str, Any]
) -> Dict[str, Any]:
    proposed = _merged_profile(current_profile, proposed_patch)
    changes = {
        field: {
            "from": current_profile.get(field),
            "to": proposed.get(field),
            "changed": current_profile.get(field) != proposed.get(field),
        }
        for field in _EDITABLE_FIELDS
    }
    changed_fields = [field for field, value in changes.items() if value["changed"]]
    blockers: List[str] = []
    warnings: List[str] = []
    default_run_mode = str(proposed.get("default_run_mode") or "").strip()
    default_policy = str(proposed.get("default_policy_profile_id") or "").strip()
    allowed_modes = [str(item).strip() for item in proposed.get("allowed_run_modes") or []]
    allowed_policies = [
        str(item).strip() for item in proposed.get("allowed_policy_profile_ids") or []
    ]
    if not changed_fields:
        blockers.append("No harness profile fields will change.")
    if not run_mode_supported(default_run_mode):
        blockers.append(f"Unsupported default_run_mode: {default_run_mode or 'missing'}")
    if not policy_profile_supported(default_policy):
        blockers.append(
            f"Unsupported default_policy_profile_id: {default_policy or 'missing'}"
        )
    if default_run_mode and default_run_mode not in allowed_modes:
        blockers.append("allowed_run_modes must include default_run_mode.")
    if default_policy and default_policy not in allowed_policies:
        blockers.append("allowed_policy_profile_ids must include default_policy_profile_id.")
    if proposed.get("id") != harness_id:
        blockers.append("Harness profile id cannot be changed.")
    if proposed.get("status") and proposed.get("status") != "active":
        blockers.append("Harness profile status changes are not supported by this flow.")
    if not proposed.get("fallback_order"):
        warnings.append("Harness has no fallback order; recovery may require manual routing.")
    return {
        "allowed": not blockers,
        "requires_confirmation": True,
        "risk_level": "medium" if changed_fields else "low",
        "effect_class": "registry_harness_profile_change",
        "harness_id": harness_id,
        "blockers": blockers,
        "warnings": warnings,
        "changes": changes,
        "changed_fields": changed_fields,
        "proposed_profile": proposed,
        "rollback_guidance": "Re-apply the previous harness profile values to produce a compensating registry release.",
        "summary": (
            "Harness profile update will create a new active registry release."
            if changed_fields
            else "Harness profile update has no effective metadata changes."
        ),
    }


def _merged_profile(current_profile: Dict[str, Any], proposed_patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(current_profile)
    for field in _EDITABLE_FIELDS:
        if field not in proposed_patch:
            continue
        value = proposed_patch[field]
        if field in _LIST_FIELDS:
            merged[field] = [str(item).strip() for item in list(value or []) if str(item).strip()]
        elif value is not None:
            merged[field] = str(value).strip()
    merged["id"] = str(current_profile.get("id") or "")
    merged["source"] = "operator_override"
    merged["status"] = "active"
    return merged
