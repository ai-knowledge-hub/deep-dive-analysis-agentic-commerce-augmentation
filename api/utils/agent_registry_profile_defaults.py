from __future__ import annotations

from typing import Any, Dict, List

from api.utils.agent_registry_runtime import registry_harness_profiles
from application.services.agent_runtime.registry import policy_profile_supported

_EDITABLE_FIELDS = (
    "name",
    "default_harness_id",
    "default_policy_profile_id",
    "risk_tier",
    "channel_type",
)


def registry_agent_profile_default_preflight(
    *, profile_id: str, current_profile: Dict[str, Any], proposed_patch: Dict[str, Any]
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
    harness = _harness_profile(str(proposed.get("default_harness_id") or ""))
    policy_id = str(proposed.get("default_policy_profile_id") or "").strip()
    if not changed_fields:
        blockers.append("No agent profile default fields will change.")
    if proposed.get("id") != profile_id:
        blockers.append("Agent profile id cannot be changed.")
    if not harness:
        blockers.append(
            f"Unsupported default_harness_id: {proposed.get('default_harness_id') or 'missing'}"
        )
    if not policy_profile_supported(policy_id):
        blockers.append(f"Unsupported default_policy_profile_id: {policy_id or 'missing'}")
    allowed_policies = {
        str(item).strip()
        for item in list((harness or {}).get("allowed_policy_profile_ids") or [])
        if str(item).strip()
    }
    if allowed_policies and policy_id not in allowed_policies:
        blockers.append("default_policy_profile_id must be allowed by default_harness_id.")
    return {
        "allowed": not blockers,
        "requires_confirmation": True,
        "risk_level": "medium" if changed_fields else "low",
        "effect_class": "registry_agent_profile_default_change",
        "agent_profile_id": profile_id,
        "blockers": blockers,
        "warnings": [],
        "changes": changes,
        "changed_fields": changed_fields,
        "proposed_profile": proposed,
        "rollback_guidance": "Re-apply the previous agent profile default values to produce a compensating registry release.",
        "summary": (
            "Agent profile default update will create a new active registry release."
            if changed_fields
            else "Agent profile default update has no effective metadata changes."
        ),
    }


def _merged_profile(current_profile: Dict[str, Any], proposed_patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(current_profile)
    for field in _EDITABLE_FIELDS:
        if field in proposed_patch and proposed_patch[field] is not None:
            merged[field] = str(proposed_patch[field]).strip()
    merged["id"] = str(current_profile.get("id") or "")
    merged["source"] = "operator_override"
    return merged


def _harness_profile(harness_id: str) -> Dict[str, Any]:
    return next(
        (profile for profile in registry_harness_profiles() if profile.get("id") == harness_id),
        {},
    )
