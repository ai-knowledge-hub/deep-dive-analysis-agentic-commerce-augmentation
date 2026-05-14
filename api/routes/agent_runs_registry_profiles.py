from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.utils.agent_profile_defaults import registry_agent_profile_defaults
from api.utils.agent_registry_profile_defaults import (
    registry_agent_profile_default_preflight,
)
from api.utils.agent_registry_auth import require_registry_write_access
from api.utils.agent_registry_runtime import registry_payload_and_fingerprint
from infrastructure.db.agent.agent_profiles import update_agent_profile_defaults
from infrastructure.db.agent.agent_registry import (
    create_agent_registry_audit_event,
    ensure_agent_registry_version,
)

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


class AgentRegistryProfileDefaultUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1)
    default_harness_id: Optional[str] = None
    default_policy_profile_id: Optional[str] = None
    risk_tier: Optional[str] = None
    channel_type: Optional[str] = None
    dry_run: bool = True
    preflight_confirmed: bool = False


@router.patch("/registry/agent-profiles/{profile_id}")
def update_agent_runtime_registry_agent_profile_default(
    profile_id: str,
    payload: AgentRegistryProfileDefaultUpdateRequest,
    request: Request,
) -> Dict[str, Any]:
    current = _current_agent_profile_default(profile_id)
    if not current:
        raise HTTPException(status_code=404, detail="Registry agent profile default not found")
    patch = payload.model_dump(exclude_unset=True, exclude={"user_id", "dry_run", "preflight_confirmed"})
    preflight = registry_agent_profile_default_preflight(
        profile_id=profile_id,
        current_profile=current,
        proposed_patch=patch,
    )
    if payload.dry_run:
        return {"dry_run": True, "preflight": preflight, "agent_profile": current}
    if not payload.preflight_confirmed:
        raise HTTPException(
            status_code=409,
            detail="Registry agent profile default preflight confirmation required",
        )
    principal = require_registry_write_access(request)
    if not preflight.get("allowed"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Registry agent profile default preflight blocked this update",
                "preflight": preflight,
            },
        )
    proposed = preflight["proposed_profile"]
    updated = update_agent_profile_defaults(
        profile_id=profile_id,
        principal_id=str(current.get("principal_id") or profile_id),
        principal_type=str(current.get("principal_type") or "external_agent"),
        name=str(proposed.get("name") or profile_id),
        tenant_id=current.get("tenant_id"),
        default_harness_id=proposed.get("default_harness_id"),
        default_policy_profile_id=proposed.get("default_policy_profile_id"),
        risk_tier=proposed.get("risk_tier"),
        channel_type=proposed.get("channel_type"),
    )
    registry_payload, fingerprint = registry_payload_and_fingerprint()
    snapshot = ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    audit_event = create_agent_registry_audit_event(
        event_type="registry_agent_profile_default_updated",
        registry_version=str(snapshot.get("registry_version") or ""),
        registry_fingerprint=str(snapshot.get("registry_fingerprint") or ""),
        source=principal.principal_id,
        diff={
            "agent_profile_id": profile_id,
            "actor_principal_id": principal.principal_id,
            "actor_principal_type": principal.principal_type,
            "preflight": preflight,
            "changed_fields": preflight.get("changed_fields") or [],
        },
    )
    return {
        "dry_run": False,
        "preflight": preflight,
        "agent_profile": updated,
        "audit_event": audit_event,
        "registry_version": snapshot.get("registry_version"),
        "registry_fingerprint": snapshot.get("registry_fingerprint"),
        "registry_status": snapshot.get("status"),
    }


def _current_agent_profile_default(profile_id: str) -> Dict[str, Any]:
    return next(
        (
            profile
            for profile in registry_agent_profile_defaults()
            if profile.get("id") == profile_id
        ),
        {},
    )
