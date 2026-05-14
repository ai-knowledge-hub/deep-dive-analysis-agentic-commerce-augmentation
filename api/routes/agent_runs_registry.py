from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.agent_registry_approvals import (
    registry_ownership_approval_receipt,
    registry_ownership_preflight,
    verify_registry_approval_receipt,
)
from api.utils.agent_registry_runtime import (
    registry_ownership,
    registry_payload_and_fingerprint,
)
from api.utils.principals import resolve_principal_context
from api.utils.tenancy import require_admin, require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    skill_id_for_tool_id,
)
from application.services.agent_runtime.registry import (
    default_tool_ownership_records,
    version_context_for_capability,
)
from infrastructure.db.agent.agent_registry import (
    create_agent_registry_audit_event,
    ensure_agent_registry_version,
    get_agent_registry_release_detail,
    list_agent_registry_audit_events,
    list_agent_registry_versions,
    update_agent_registry_tool_ownership,
)


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])
_REGISTRY_READ_SCOPES = {
    "*",
    "agent_runs:read",
    "agent_runs:write",
    "external_agent_jobs:read",
    "external_agent_jobs:write",
}


def _deps() -> AppDeps:
    return default_deps()


class AgentRegistryBackfillPinsRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    dry_run: bool = True
    limit: int = 200


class AgentRegistryOwnershipUpdateRequest(BaseModel):
    user_id: Optional[str] = None
    owner_principal_id: str = Field(..., min_length=1)
    steward_team: str = Field(..., min_length=1)
    dry_run: bool = True
    preflight_confirmed: bool = False


class AgentRegistryApprovalReceiptVerifyRequest(BaseModel):
    approval_receipt: Dict[str, Any] = Field(default_factory=dict)
    registry_fingerprint: Optional[str] = None
    audit_event_id: Optional[str] = None
    require_audit_event: bool = False


def _registry_ownership() -> List[Dict[str, Any]]:
    return registry_ownership()


def _require_registry_read_access(
    *, request: Request, client_id: Optional[str], user_id: Optional[str]
) -> str:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    scheme, _, token = str(auth_header or "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        principal = resolve_principal_context(
            request=request,
            client_id=client_id,
            user_id=user_id,
            principal_type=None,
            principal_id=None,
            agent_profile_id=None,
        )
        if not set(principal.scopes or ()).intersection(_REGISTRY_READ_SCOPES):
            raise HTTPException(
                status_code=403, detail="Missing required registry read scope"
            )
        return principal.client_id
    return require_client_id(client_id, user_id)


@router.get("/registry")
def get_agent_runtime_registry(
    request: Request,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_client_id = _require_registry_read_access(
        request=request, client_id=client_id, user_id=user_id
    )
    registry_payload, fingerprint = registry_payload_and_fingerprint(
        client_id=resolved_client_id
    )
    snapshot = ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    return {
        **registry_payload,
        "registry_fingerprint": fingerprint,
        "registry_hash_algorithm": "sha256",
        "registry_snapshot_id": snapshot.get("id"),
        "registry_snapshot_created_at": snapshot.get("created_at"),
        "registry_source": snapshot.get("source"),
        "registry_status": snapshot.get("status"),
    }


@router.get("/registry/audit")
def get_agent_runtime_registry_audit(
    request: Request,
    registry_fingerprint: Optional[str] = None,
    limit: int = 20,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    _require_registry_read_access(request=request, client_id=client_id, user_id=user_id)
    bounded_limit = max(1, min(int(limit), 100))
    return {
        "events": list_agent_registry_audit_events(
            registry_fingerprint=registry_fingerprint,
            limit=bounded_limit,
        )
    }


@router.get("/registry/releases")
def get_agent_runtime_registry_releases(
    request: Request,
    status: Optional[str] = None,
    limit: int = 20,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    _require_registry_read_access(request=request, client_id=client_id, user_id=user_id)
    normalized_status = str(status).strip().lower() if status else None
    if normalized_status and normalized_status not in {"active", "retired"}:
        raise HTTPException(
            status_code=400, detail="Unsupported registry release status"
        )
    bounded_limit = max(1, min(int(limit), 100))
    return {
        "releases": list_agent_registry_versions(
            status=normalized_status,
            limit=bounded_limit,
        )
    }


@router.get("/registry/releases/{registry_fingerprint}")
def get_agent_runtime_registry_release_detail(
    registry_fingerprint: str,
    request: Request,
    audit_limit: int = 20,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    _require_registry_read_access(request=request, client_id=client_id, user_id=user_id)
    bounded_audit_limit = max(1, min(int(audit_limit), 100))
    release = get_agent_registry_release_detail(
        registry_fingerprint=registry_fingerprint,
        audit_limit=bounded_audit_limit,
    )
    if not release:
        raise HTTPException(status_code=404, detail="Registry release not found")
    return {"release": release}


@router.patch("/registry/ownership/{tool_id:path}")
def update_agent_runtime_registry_tool_ownership(
    tool_id: str,
    payload: AgentRegistryOwnershipUpdateRequest,
) -> Dict[str, Any]:
    existing_tool_ids = {item["tool_id"] for item in default_tool_ownership_records()}
    if tool_id not in existing_tool_ids:
        raise HTTPException(status_code=404, detail="Registry tool not found")
    current_ownership = _registry_ownership()
    preflight = registry_ownership_preflight(
        tool_id=tool_id,
        owner_principal_id=payload.owner_principal_id,
        steward_team=payload.steward_team,
        current_ownership=current_ownership,
    )
    if payload.dry_run:
        return {
            "dry_run": True,
            "preflight": preflight,
            "ownership": next(
                (item for item in current_ownership if item.get("tool_id") == tool_id),
                {},
            ),
        }
    if not payload.preflight_confirmed:
        raise HTTPException(
            status_code=409,
            detail="Registry ownership preflight confirmation required",
        )
    require_admin(payload.user_id)
    if not preflight.get("allowed"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Registry ownership preflight blocked this update",
                "preflight": preflight,
            },
        )
    ownership = update_agent_registry_tool_ownership(
        tool_id=tool_id,
        owner_principal_id=payload.owner_principal_id,
        steward_team=payload.steward_team,
        source="operator_override",
    )
    if not ownership:
        raise HTTPException(
            status_code=400, detail="Invalid registry ownership payload"
        )
    registry_payload, fingerprint = registry_payload_and_fingerprint()
    snapshot = ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    approval_receipt = registry_ownership_approval_receipt(
        tool_id=tool_id,
        actor_user_id=payload.user_id,
        ownership=ownership,
        preflight=preflight,
        registry_version=str(snapshot.get("registry_version") or ""),
        registry_fingerprint=str(snapshot.get("registry_fingerprint") or ""),
    )
    approval_event = create_agent_registry_audit_event(
        event_type="registry_ownership_approved",
        registry_version=str(snapshot.get("registry_version") or ""),
        registry_fingerprint=str(snapshot.get("registry_fingerprint") or ""),
        source="operator_approval",
        diff={
            "tool_id": tool_id,
            "approval_receipt": approval_receipt,
            "preflight": preflight,
        },
    )
    return {
        "dry_run": False,
        "preflight": preflight,
        "ownership": ownership,
        "approval_receipt": approval_receipt,
        "approval_event": approval_event,
        "registry_version": snapshot.get("registry_version"),
        "registry_fingerprint": snapshot.get("registry_fingerprint"),
        "registry_status": snapshot.get("status"),
    }


@router.post("/registry/approval-receipts/verify")
def verify_agent_runtime_registry_approval_receipt(
    payload: AgentRegistryApprovalReceiptVerifyRequest,
) -> Dict[str, Any]:
    if not payload.approval_receipt:
        raise HTTPException(status_code=400, detail="Missing approval receipt")
    return {
        "verification": verify_registry_approval_receipt(
            receipt=payload.approval_receipt,
            registry_fingerprint=payload.registry_fingerprint,
            audit_event_id=payload.audit_event_id,
            require_audit_event=payload.require_audit_event,
        )
    }


@router.post("/registry/backfill-pins")
def backfill_agent_runtime_registry_pins(
    payload: AgentRegistryBackfillPinsRequest,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    bounded_limit = max(1, min(int(payload.limit), 500))
    registry_payload, active_registry_fingerprint = registry_payload_and_fingerprint()
    snapshot = ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=active_registry_fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    run_candidates = deps.agent_runs.list_agent_runs_missing_registry_pins(
        client_id=client_id,
        limit=bounded_limit,
    )
    action_candidates = deps.agent_actions.list_agent_actions_missing_registry_pins(
        client_id=client_id,
        limit=bounded_limit,
    )
    updated_runs = 0
    updated_actions = 0
    if not payload.dry_run:
        updated_runs = deps.agent_runs.backfill_agent_run_registry_pins(
            client_id=client_id,
            registry_version=str(snapshot["registry_version"]),
            registry_fingerprint=str(snapshot["registry_fingerprint"]),
            limit=bounded_limit,
        )
        for action in action_candidates:
            capability_name = str(action.get("capability_name") or "")
            tool_id = action.get("tool_id") or capability_to_tool_id(capability_name)
            skill_id = action.get("skill_id") or skill_id_for_tool_id(tool_id)
            version_context = version_context_for_capability(
                capability_name,
                tool_id=tool_id,
                skill_id=skill_id,
                registry_version_override=str(snapshot["registry_version"]),
                registry_fingerprint_override=str(snapshot["registry_fingerprint"]),
            )
            deps.agent_actions.update_agent_action_registry_pins(
                action_id=str(action["id"]),
                tool_id=tool_id,
                skill_id=skill_id,
                registry_version=str(snapshot["registry_version"]),
                registry_fingerprint=str(snapshot["registry_fingerprint"]),
                tool_version=version_context["tool_version"],
                skill_version=version_context["skill_version"],
            )
            updated_actions += 1
        if updated_runs or updated_actions:
            create_agent_registry_audit_event(
                event_type="registry_pin_backfill_applied",
                registry_version=str(snapshot["registry_version"]),
                registry_fingerprint=str(snapshot["registry_fingerprint"]),
                source="operator_backfill",
                diff={
                    "client_id": client_id,
                    "runs": {
                        "matched": len(run_candidates),
                        "updated": updated_runs,
                        "sample_ids": [item["id"] for item in run_candidates[:10]],
                    },
                    "actions": {
                        "matched": len(action_candidates),
                        "updated": updated_actions,
                        "sample_ids": [item["id"] for item in action_candidates[:10]],
                    },
                },
            )
    return {
        "client_id": client_id,
        "dry_run": bool(payload.dry_run),
        "registry_version": snapshot["registry_version"],
        "registry_fingerprint": snapshot["registry_fingerprint"],
        "runs": {
            "matched": len(run_candidates),
            "updated": updated_runs,
            "sample_ids": [item["id"] for item in run_candidates[:10]],
        },
        "actions": {
            "matched": len(action_candidates),
            "updated": updated_actions,
            "sample_ids": [item["id"] for item in action_candidates[:10]],
        },
    }
