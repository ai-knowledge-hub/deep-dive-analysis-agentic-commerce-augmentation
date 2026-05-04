from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from infrastructure.db.agent.agent_registry import list_agent_registry_audit_events
from shared.config.env import get_settings


def registry_ownership_approval_receipt(
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


def registry_ownership_preflight(
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


def verify_registry_approval_receipt(
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


def _unsigned_registry_approval_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in dict(receipt or {}).items()
        if key not in {"signature", "signature_algorithm"}
    }


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
