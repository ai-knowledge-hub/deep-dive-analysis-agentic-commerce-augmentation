from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.agent_registry_runtime import (
    registry_ownership,
    registry_payload_and_fingerprint,
)
from api.utils.tenancy import require_client_id
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
from shared.config.env import get_settings


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


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


def _registry_payload_and_fingerprint() -> tuple[Dict[str, Any], str]:
    return registry_payload_and_fingerprint()


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _registry_approval_signing_secret() -> str:
    settings = get_settings()
    secret = (
        settings.registry_approval_signing_secret
        or settings.agent_principal_signing_secret
    )
    if secret:
        return secret
    if settings.app_env != "prod":
        return "local-development-registry-approval-secret"
    raise HTTPException(
        status_code=500,
        detail="REGISTRY_APPROVAL_SIGNING_SECRET is not configured",
    )


def _sign_registry_approval_receipt(payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_b64 = _urlsafe_b64encode(payload_json)
    signature = hmac.new(
        _registry_approval_signing_secret().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def _decode_registry_approval_receipt_signature(
    signature: str,
) -> tuple[Dict[str, Any], bool]:
    try:
        payload_b64, provided_signature = signature.rsplit(".", 1)
    except ValueError:
        return {}, False
    expected_signature = hmac.new(
        _registry_approval_signing_secret().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        return {}, False
    try:
        padding = "=" * (-len(payload_b64) % 4)
        payload_raw = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return {}, False
    return payload if isinstance(payload, dict) else {}, True


def _unsigned_registry_approval_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in dict(receipt or {}).items()
        if key not in {"signature", "signature_algorithm"}
    }


def _registry_approval_audit_event_for_receipt(
    *,
    signature: str,
    registry_fingerprint: Optional[str],
    audit_event_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not registry_fingerprint:
        return None
    events = list_agent_registry_audit_events(
        registry_fingerprint=registry_fingerprint,
        limit=100,
    )
    for event in events:
        if event.get("event_type") != "registry_ownership_approved":
            continue
        if audit_event_id and event.get("id") != audit_event_id:
            continue
        receipt = (event.get("diff") or {}).get("approval_receipt") or {}
        if receipt.get("signature") == signature:
            return event
    return None


def _verify_registry_approval_receipt(
    *,
    receipt: Dict[str, Any],
    registry_fingerprint: Optional[str] = None,
    audit_event_id: Optional[str] = None,
    require_audit_event: bool = False,
) -> Dict[str, Any]:
    signature = str(receipt.get("signature") or "")
    decoded_payload, valid_signature = _decode_registry_approval_receipt_signature(
        signature
    )
    unsigned_receipt = _unsigned_registry_approval_receipt(receipt)
    valid_payload = bool(valid_signature and decoded_payload == unsigned_receipt)
    expected_fingerprint = registry_fingerprint or receipt.get("registry_fingerprint")
    audit_event = _registry_approval_audit_event_for_receipt(
        signature=signature,
        registry_fingerprint=expected_fingerprint,
        audit_event_id=audit_event_id,
    )
    valid_audit_event = bool(audit_event)
    blockers: List[str] = []
    if not valid_signature:
        blockers.append("Receipt signature is invalid.")
    if valid_signature and not valid_payload:
        blockers.append("Receipt payload does not match the signed payload.")
    if require_audit_event and not valid_audit_event:
        blockers.append("No matching registry approval audit event was found.")
    return {
        "valid": not blockers,
        "valid_signature": valid_signature,
        "valid_payload": valid_payload,
        "valid_audit_event": valid_audit_event,
        "blockers": blockers,
        "receipt_payload": decoded_payload,
        "audit_event": audit_event,
    }


def _registry_ownership_approval_receipt(
    *,
    tool_id: str,
    actor_user_id: Optional[str],
    ownership: Dict[str, Any],
    preflight: Dict[str, Any],
    registry_version: str,
    registry_fingerprint: str,
) -> Dict[str, Any]:
    receipt_payload: Dict[str, Any] = {
        "receipt_id": str(uuid.uuid4()),
        "receipt_type": "registry_ownership_approval",
        "actor_user_id": actor_user_id,
        "tool_id": tool_id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "registry_version": registry_version,
        "registry_fingerprint": registry_fingerprint,
        "ownership": {
            "owner_principal_id": ownership.get("owner_principal_id"),
            "steward_team": ownership.get("steward_team"),
            "source": ownership.get("source"),
        },
        "preflight": preflight,
    }
    return {
        **receipt_payload,
        "signature": _sign_registry_approval_receipt(receipt_payload),
        "signature_algorithm": "hmac-sha256",
    }


def _registry_ownership_preflight(
    *,
    tool_id: str,
    owner_principal_id: str,
    steward_team: str,
    current_ownership: List[Dict[str, Any]],
) -> Dict[str, Any]:
    current = next(
        (item for item in current_ownership if item.get("tool_id") == tool_id),
        {},
    )
    current_owner = str(current.get("owner_principal_id") or "").strip()
    current_steward = str(current.get("steward_team") or "").strip()
    proposed_owner = str(owner_principal_id or "").strip()
    proposed_steward = str(steward_team or "").strip()
    changes = {
        "owner_principal_id": {
            "from": current_owner or None,
            "to": proposed_owner,
            "changed": current_owner != proposed_owner,
        },
        "steward_team": {
            "from": current_steward or None,
            "to": proposed_steward,
            "changed": current_steward != proposed_steward,
        },
    }
    changed_fields = [
        key for key, value in changes.items() if bool(value.get("changed"))
    ]
    blockers: List[str] = []
    warnings: List[str] = []
    if not changed_fields:
        blockers.append("No ownership metadata fields will change.")
    if "." not in proposed_owner:
        warnings.append("Owner principal does not look namespace-qualified.")
    if "-" not in proposed_steward:
        warnings.append("Steward team does not use the expected dashed team format.")
    return {
        "allowed": not blockers,
        "requires_confirmation": True,
        "risk_level": "medium" if changed_fields else "low",
        "effect_class": "registry_metadata_change",
        "tool_id": tool_id,
        "blockers": blockers,
        "warnings": warnings,
        "changes": changes,
        "changed_fields": changed_fields,
        "rollback_guidance": "Re-apply the previous owner and steward values to produce a compensating registry release.",
        "summary": (
            "Registry ownership update will create a new active registry release."
            if changed_fields
            else "Registry ownership update has no effective metadata changes."
        ),
    }


@router.get("/registry")
def get_agent_runtime_registry() -> Dict[str, Any]:
    registry_payload, fingerprint = _registry_payload_and_fingerprint()
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
    registry_fingerprint: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 100))
    return {
        "events": list_agent_registry_audit_events(
            registry_fingerprint=registry_fingerprint,
            limit=bounded_limit,
        )
    }


@router.get("/registry/releases")
def get_agent_runtime_registry_releases(
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
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
    audit_limit: int = 20,
) -> Dict[str, Any]:
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
    preflight = _registry_ownership_preflight(
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
    registry_payload, fingerprint = _registry_payload_and_fingerprint()
    snapshot = ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    approval_receipt = _registry_ownership_approval_receipt(
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
        "verification": _verify_registry_approval_receipt(
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
    registry_payload, active_registry_fingerprint = _registry_payload_and_fingerprint()
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
