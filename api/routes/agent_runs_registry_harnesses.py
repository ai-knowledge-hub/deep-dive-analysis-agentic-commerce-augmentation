from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.utils.agent_registry_harnesses import registry_harness_profile_preflight
from api.utils.agent_registry_runtime import (
    registry_harness_profiles,
    registry_payload_and_fingerprint,
)
from api.utils.tenancy import require_admin
from infrastructure.db.agent.agent_registry import (
    create_agent_registry_audit_event,
    ensure_agent_registry_version,
    update_agent_registry_harness_profile,
)

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


class AgentRegistryHarnessProfileUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    default_run_mode: Optional[str] = None
    default_policy_profile_id: Optional[str] = None
    allowed_run_modes: Optional[List[str]] = None
    allowed_policy_profile_ids: Optional[List[str]] = None
    planner_mode: Optional[str] = None
    retry_strategy: Optional[str] = None
    fallback_order: Optional[List[str]] = None
    approval_strategy: Optional[str] = None
    memory_policy: Optional[str] = None
    stopping_conditions: Optional[List[str]] = None
    dry_run: bool = True
    preflight_confirmed: bool = False


@router.patch("/registry/harnesses/{harness_id}")
def update_agent_runtime_registry_harness_profile(
    harness_id: str,
    payload: AgentRegistryHarnessProfileUpdateRequest,
) -> Dict[str, Any]:
    current = _current_harness_profile(harness_id)
    if not current:
        raise HTTPException(status_code=404, detail="Registry harness profile not found")
    patch = payload.model_dump(exclude_unset=True, exclude={"user_id", "dry_run", "preflight_confirmed"})
    preflight = registry_harness_profile_preflight(
        harness_id=harness_id,
        current_profile=current,
        proposed_patch=patch,
    )
    if payload.dry_run:
        return {"dry_run": True, "preflight": preflight, "harness_profile": current}
    if not payload.preflight_confirmed:
        raise HTTPException(
            status_code=409,
            detail="Registry harness profile preflight confirmation required",
        )
    require_admin(payload.user_id)
    if not preflight.get("allowed"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Registry harness profile preflight blocked this update",
                "preflight": preflight,
            },
        )
    updated = update_agent_registry_harness_profile(
        profile_id=harness_id,
        profile=preflight["proposed_profile"],
        source="operator_override",
    )
    registry_payload, fingerprint = registry_payload_and_fingerprint()
    snapshot = ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    audit_event = create_agent_registry_audit_event(
        event_type="registry_harness_profile_updated",
        registry_version=str(snapshot.get("registry_version") or ""),
        registry_fingerprint=str(snapshot.get("registry_fingerprint") or ""),
        source="operator_approval",
        diff={
            "harness_id": harness_id,
            "preflight": preflight,
            "changed_fields": preflight.get("changed_fields") or [],
        },
    )
    return {
        "dry_run": False,
        "preflight": preflight,
        "harness_profile": updated,
        "audit_event": audit_event,
        "registry_version": snapshot.get("registry_version"),
        "registry_fingerprint": snapshot.get("registry_fingerprint"),
        "registry_status": snapshot.get("status"),
    }


def _current_harness_profile(harness_id: str) -> Dict[str, Any]:
    return next(
        (profile for profile in registry_harness_profiles() if profile.get("id") == harness_id),
        {},
    )
