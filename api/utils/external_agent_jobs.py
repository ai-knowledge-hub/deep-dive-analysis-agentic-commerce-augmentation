from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException, Response

from application.ports.deps import AppDeps
from infrastructure.db.agent.external_agent_jobs import (
    create_external_agent_job_receipt,
    get_external_agent_job_receipt_for_context_hash,
    update_external_agent_job_receipt,
    update_external_agent_job_status,
)
from shared.config.env import get_settings

POLL_RETRY_AFTER_SECONDS = 3
POLL_INTERVAL_SECONDS = 3
ACTION_EVIDENCE_LIMIT = 500
EVENT_EVIDENCE_LIMIT = 2000


def job_status_from_run(run: Dict[str, Any]) -> str:
    status = str(run.get("status") or "planned").strip().lower()
    if status in {"completed", "failed", "paused"}:
        return status
    if status in {"canceled", "cancelled"}:
        return "canceled"
    if status in {"running", "executing"}:
        return "running"
    return "accepted"


def job_status_payload(*, job: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    status = job_status_from_run(run)
    receipt_payload = job.get("receipt_payload") or {}
    receipt_matches_status = receipt_payload.get("status") == status
    return {
        "id": job["id"],
        "client_id": job["client_id"],
        "principal_id": job["principal_id"],
        "agent_profile_id": job.get("agent_profile_id"),
        "idempotency_key": job["idempotency_key"],
        "run_id": job["run_id"],
        "status": status,
        "run_status": run.get("status"),
        "run_state": run.get("state"),
        "trace_id": job.get("trace_id") or run.get("trace_id"),
        "requested_skill_id": job.get("requested_skill_id"),
        "requested_tool_id": job.get("requested_tool_id"),
        "receipt_id": job.get("receipt_id") if receipt_matches_status else None,
        "receipt_type": job.get("receipt_type") if receipt_matches_status else None,
        "receipt_signature_algorithm": job.get("receipt_signature_algorithm")
        if receipt_matches_status
        else None,
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def sync_job_status_from_run(*, job: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    status = job_status_from_run(run)
    if status == job.get("status"):
        return job
    return update_external_agent_job_status(
        job_id=job["id"],
        status=status,
        response={**(job.get("response") or {}), "status": status},
    ) or job


def ensure_external_agent_job_receipt(
    *, deps: AppDeps, job: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    current_status = job_status_from_run(run)
    evidence = job_evidence_summary(deps=deps, run=run)
    context_hash = receipt_context_hash(
        job=job, run=run, current_status=current_status, evidence=evidence
    )
    if (
        job.get("receipt_id")
        and job.get("receipt_signature")
        and (job.get("receipt_payload") or {}).get("status") == current_status
        and (job.get("receipt_payload") or {}).get("receipt_context_hash")
        == context_hash
    ):
        return {
            **(job.get("receipt_payload") or {}),
            "signature": job.get("receipt_signature"),
            "signature_algorithm": job.get("receipt_signature_algorithm"),
        }
    receipt_payload = {
        "receipt_id": str(uuid.uuid4()),
        "receipt_type": f"external_agent_job_{current_status}",
        "job_id": job["id"],
        "run_id": job["run_id"],
        "client_id": job["client_id"],
        "principal_id": job["principal_id"],
        "agent_profile_id": job.get("agent_profile_id"),
        "idempotency_key": job["idempotency_key"],
        "status": current_status,
        "trace_id": job.get("trace_id") or run.get("trace_id"),
        "requested_skill_id": job.get("requested_skill_id"),
        "requested_tool_id": job.get("requested_tool_id"),
        "run_status": run.get("status"),
        "run_state": run.get("state"),
        "registry_version": run.get("registry_version"),
        "registry_fingerprint": run.get("registry_fingerprint"),
        "key_id": external_agent_job_receipt_key_id(),
        "receipt_context_hash": context_hash,
        "evidence": evidence,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    existing_receipt = get_external_agent_job_receipt_for_context_hash(
        job_id=job["id"],
        client_id=job["client_id"],
        principal_id=job["principal_id"],
        status=current_status,
        receipt_context_hash=context_hash,
    )
    if existing_receipt:
        receipt_payload = existing_receipt.get("payload") or receipt_payload
        signature = existing_receipt.get("signature")
        stored = update_external_agent_job_receipt(
            job_id=job["id"],
            receipt_id=existing_receipt.get("id") or receipt_payload["receipt_id"],
            receipt_type=existing_receipt.get("receipt_type")
            or receipt_payload["receipt_type"],
            receipt_signature=signature,
            receipt_signature_algorithm=existing_receipt.get("signature_algorithm")
            or "hmac-sha256",
            receipt_payload=receipt_payload,
        )
        job.update(stored or {})
        return {
            **receipt_payload,
            "signature": signature,
            "signature_algorithm": existing_receipt.get("signature_algorithm")
            or "hmac-sha256",
        }
    signature = sign_external_agent_job_receipt(receipt_payload)
    receipt_row = create_external_agent_job_receipt(
        receipt_id=receipt_payload["receipt_id"],
        job_id=job["id"],
        client_id=job["client_id"],
        principal_id=job["principal_id"],
        run_id=job["run_id"],
        receipt_type=receipt_payload["receipt_type"],
        status=current_status,
        receipt_context_hash=context_hash,
        signature=signature,
        signature_algorithm="hmac-sha256",
        payload=receipt_payload,
    )
    receipt_payload = receipt_row.get("payload") or receipt_payload
    signature = receipt_row.get("signature") or signature
    stored = update_external_agent_job_receipt(
        job_id=job["id"],
        receipt_id=receipt_row.get("id") or receipt_payload["receipt_id"],
        receipt_type=receipt_row.get("receipt_type") or receipt_payload["receipt_type"],
        receipt_signature=signature,
        receipt_signature_algorithm=receipt_row.get("signature_algorithm")
        or "hmac-sha256",
        receipt_payload=receipt_payload,
    )
    job.update(stored or {})
    return {
        **receipt_payload,
        "signature": signature,
        "signature_algorithm": "hmac-sha256",
    }


def stored_external_agent_job_receipt(
    *, job: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any] | None:
    payload = job.get("receipt_payload") or {}
    signature = job.get("receipt_signature")
    if not payload or not signature:
        return None
    current_status = job_status_from_run(run)
    stale_context = not stored_receipt_context_matches_run(
        payload=payload, run=run, current_status=current_status
    )
    return {
        **payload,
        "signature": signature,
        "signature_algorithm": job.get("receipt_signature_algorithm"),
        "stale_context": stale_context,
        "refresh_required_for_latest_context": stale_context,
    }


def stored_receipt_context_matches_run(
    *, payload: Dict[str, Any], run: Dict[str, Any], current_status: str
) -> bool:
    return bool(
        payload.get("status") == current_status
        and payload.get("run_status") == run.get("status")
        and payload.get("run_state") == run.get("state")
        and payload.get("registry_version") == run.get("registry_version")
        and payload.get("registry_fingerprint") == run.get("registry_fingerprint")
    )


def external_agent_activity_items(
    *,
    job: Dict[str, Any],
    run: Dict[str, Any],
    receipts: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = [
        {
            "type": "job",
            "subtype": "external_agent_job_created",
            "status": job.get("status"),
            "timestamp": job.get("created_at"),
            "job_id": job.get("id"),
            "run_id": job.get("run_id"),
            "trace_id": job.get("trace_id") or run.get("trace_id"),
        }
    ]
    for receipt in receipts:
        payload = receipt.get("payload") or {}
        items.append(
            {
                "type": "receipt",
                "subtype": payload.get("receipt_type") or receipt.get("receipt_type"),
                "status": payload.get("status") or receipt.get("status"),
                "timestamp": payload.get("issued_at") or receipt.get("created_at"),
                "job_id": payload.get("job_id") or receipt.get("job_id"),
                "run_id": payload.get("run_id") or receipt.get("run_id"),
                "trace_id": payload.get("trace_id"),
                "receipt_id": payload.get("receipt_id") or receipt.get("id"),
                "signature_algorithm": receipt.get("signature_algorithm"),
            }
        )
    for event in events:
        items.append(
            {
                "type": "run_event",
                "subtype": event.get("event_type"),
                "status": event.get("status"),
                "timestamp": event.get("timestamp"),
                "job_id": job.get("id"),
                "run_id": event.get("run_id") or job.get("run_id"),
                "trace_id": event.get("trace_id") or job.get("trace_id"),
                "event_id": event.get("id"),
                "action_id": event.get("action_id"),
                "sequence": event.get("sequence"),
                "tool_id": event.get("tool_id"),
                "skill_id": event.get("skill_id"),
                "effect_class": event.get("effect_class"),
                "capability_name": event.get("capability_name"),
                "capability_version": event.get("capability_version"),
                "is_policy_event": event.get("is_policy_event"),
                "note": event.get("note"),
                "anchors": event.get("anchors") or {},
            }
        )
    return sorted(items, key=lambda item: str(item.get("timestamp") or ""))


def verify_external_agent_job_receipt(
    *, receipt: Dict[str, Any] | None, job: Dict[str, Any], client_id: str
) -> Dict[str, Any]:
    receipt = dict(receipt or {})
    decoded_payload, valid_signature = decode_external_agent_job_receipt_signature(
        str(receipt.get("signature") or "")
    )
    unsigned_receipt = {
        key: value
        for key, value in receipt.items()
        if key not in {"signature", "signature_algorithm"}
    }
    valid_payload = bool(valid_signature and decoded_payload == unsigned_receipt)
    valid_scope = bool(
        decoded_payload.get("job_id") == job["id"]
        and decoded_payload.get("run_id") == job["run_id"]
        and decoded_payload.get("client_id") == client_id
        and decoded_payload.get("principal_id") == job["principal_id"]
    )
    blockers: List[str] = []
    if not valid_signature:
        blockers.append("Receipt signature is invalid.")
    if valid_signature and not valid_payload:
        blockers.append("Receipt payload does not match the signed payload.")
    if valid_signature and not valid_scope:
        blockers.append("Receipt does not belong to the scoped external-agent job.")
    return {
        "valid": not blockers,
        "valid_signature": valid_signature,
        "valid_payload": valid_payload,
        "valid_scope": valid_scope,
        "key_id": decoded_payload.get("key_id") or receipt.get("key_id"),
        "signature_algorithm": receipt.get("signature_algorithm"),
        "receipt_payload": decoded_payload,
        "blockers": blockers,
    }


def sign_external_agent_job_receipt(payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    signature = hmac.new(
        external_agent_job_receipt_secret().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_external_agent_job_receipt_signature(
    signature: str,
) -> tuple[Dict[str, Any], bool]:
    try:
        payload_b64, provided_signature = signature.rsplit(".", 1)
    except ValueError:
        return {}, False
    expected_signature = hmac.new(
        external_agent_job_receipt_secret().encode("utf-8"),
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


def job_evidence_summary(*, deps: AppDeps, run: Dict[str, Any]) -> Dict[str, Any]:
    run_id = str(run.get("id") or "")
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=ACTION_EVIDENCE_LIMIT + 1
    )
    events = deps.agent_events.list_agent_events(
        agent_run_id=run_id, limit=EVENT_EVIDENCE_LIMIT + 1
    )
    actions_truncated = len(actions) > ACTION_EVIDENCE_LIMIT
    events_truncated = len(events) > EVENT_EVIDENCE_LIMIT
    actions = actions[:ACTION_EVIDENCE_LIMIT]
    events = events[-EVENT_EVIDENCE_LIMIT:]
    action_items = [
        {
            "id": action.get("id"),
            "sequence": action.get("sequence"),
            "status": action.get("status"),
            "capability_name": action.get("capability_name"),
            "capability_version": action.get("capability_version"),
            "tool_id": action.get("tool_id"),
            "skill_id": action.get("skill_id"),
            "effect_class": action.get("effect_class"),
            "inputs_hash": action.get("inputs_hash"),
            "outputs_hash": action.get("outputs_hash"),
            "registry_version": action.get("registry_version"),
            "registry_fingerprint": action.get("registry_fingerprint"),
            "tool_version": action.get("tool_version"),
            "skill_version": action.get("skill_version"),
            "receipt_id": action.get("receipt_id"),
            "error": action.get("error"),
        }
        for action in actions
    ]
    event_items = [
        {
            "id": event.get("id"),
            "sequence": event.get("sequence"),
            "event_type": event.get("event_type"),
            "status": event.get("status"),
            "action_id": event.get("action_id"),
            "capability_name": event.get("capability_name"),
            "capability_version": event.get("capability_version"),
            "tool_id": event.get("tool_id"),
            "skill_id": event.get("skill_id"),
            "effect_class": event.get("effect_class"),
            "is_policy_event": event.get("is_policy_event"),
            "timestamp": event.get("timestamp"),
            "anchors": event.get("anchors") or {},
        }
        for event in events
    ]
    latest_event = event_items[-1] if event_items else {}
    return {
        "action_count": len(action_items),
        "event_count": len(event_items),
        "complete": not actions_truncated and not events_truncated,
        "actions_complete": not actions_truncated,
        "events_complete": not events_truncated,
        "action_limit": ACTION_EVIDENCE_LIMIT,
        "event_limit": EVENT_EVIDENCE_LIMIT,
        "digest_scope": "complete"
        if not actions_truncated and not events_truncated
        else "bounded_window",
        "latest_event_id": latest_event.get("id"),
        "latest_event_timestamp": latest_event.get("timestamp"),
        "action_digest": stable_digest(action_items),
        "event_digest": stable_digest(event_items),
        "terminal_action_statuses": [
            {
                "id": action.get("id"),
                "sequence": action.get("sequence"),
                "status": action.get("status"),
                "inputs_hash": action.get("inputs_hash"),
                "outputs_hash": action.get("outputs_hash"),
                "error": action.get("error"),
            }
            for action in action_items
            if action.get("status") in {"executed", "failed", "rejected", "skipped"}
        ],
    }


def receipt_context_hash(
    *,
    job: Dict[str, Any],
    run: Dict[str, Any],
    current_status: str,
    evidence: Dict[str, Any],
) -> str:
    return stable_digest(
        {
            "job_id": job.get("id"),
            "run_id": job.get("run_id"),
            "client_id": job.get("client_id"),
            "principal_id": job.get("principal_id"),
            "status": current_status,
            "trace_id": job.get("trace_id") or run.get("trace_id"),
            "requested_skill_id": job.get("requested_skill_id"),
            "requested_tool_id": job.get("requested_tool_id"),
            "run_status": run.get("status"),
            "run_state": run.get("state"),
            "registry_version": run.get("registry_version"),
            "registry_fingerprint": run.get("registry_fingerprint"),
            "evidence": evidence,
        }
    )


def stable_digest(payload: Any) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def list_receipt_payloads(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        [
            {
                **(row.get("payload") or {}),
                "signature": row.get("signature"),
                "signature_algorithm": row.get("signature_algorithm"),
            }
            for row in rows
        ],
        key=lambda item: str(item.get("issued_at") or item.get("created_at") or ""),
        reverse=True,
    )


def set_external_agent_poll_headers(response: Response) -> None:
    response.headers["Retry-After"] = str(POLL_RETRY_AFTER_SECONDS)
    response.headers["X-Agent-Poll-Interval-Seconds"] = str(POLL_INTERVAL_SECONDS)
    response.headers["X-Agent-Receipt-Refresh"] = "explicit"


def external_agent_job_receipt_key_id() -> str:
    settings = get_settings()
    if settings.registry_approval_signing_secret:
        return "registry-approval-signing-secret:v1"
    if settings.agent_principal_signing_secret:
        return "agent-principal-signing-secret:v1"
    return "local-development-external-agent-job-secret:v1"


def external_agent_job_receipt_secret() -> str:
    settings = get_settings()
    secret = (
        settings.registry_approval_signing_secret
        or settings.agent_principal_signing_secret
    )
    if secret:
        return secret
    if settings.app_env != "prod":
        return "local-development-external-agent-job-secret"
    raise HTTPException(
        status_code=500,
        detail="AGENT_PRINCIPAL_SIGNING_SECRET is not configured",
    )
