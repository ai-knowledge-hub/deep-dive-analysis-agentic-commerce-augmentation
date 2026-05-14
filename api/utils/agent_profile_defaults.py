from __future__ import annotations

from typing import Any, Dict, List

from application.services.agent_runtime.registry import list_static_agent_profile_defaults
from infrastructure.db.agent.agent_profiles import (
    ensure_agent_profiles,
    get_agent_profile,
    list_agent_profiles,
)


def registry_agent_profile_defaults(*, client_id: str | None = None) -> List[Dict[str, Any]]:
    profiles = ensure_agent_profiles(
        profiles=list_static_agent_profile_defaults(),
        tenant_id=None,
    )
    if not client_id:
        return profiles or list_agent_profiles()
    profile_by_id = {str(profile.get("id")): profile for profile in profiles}
    for profile in list_agent_profiles(tenant_id=client_id):
        profile_by_id[str(profile.get("id"))] = profile
    return sorted(profile_by_id.values(), key=lambda item: str(item.get("id") or ""))


def agent_profile_defaults(
    *, agent_profile_id: str | None, client_id: str | None = None
) -> Dict[str, Any]:
    profile_id = str(agent_profile_id or "").strip()
    if not profile_id:
        return {}
    ensure_agent_profiles(profiles=list_static_agent_profile_defaults(), tenant_id=None)
    return get_agent_profile(profile_id=profile_id, tenant_id=client_id) or {}


__all__ = ["agent_profile_defaults", "registry_agent_profile_defaults"]
