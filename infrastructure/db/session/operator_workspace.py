"""Own the transaction joining governed creation to its conversation receipt."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from domain.workflow.operator_commands import canonical_digest
from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.transactions import JoinedTransaction


def get_workspace(*, session_id: str, tenant_id: str, principal_id: str) -> dict | None:
    row = (
        get_connection()
        .execute(
            "SELECT * FROM operator_workspaces WHERE session_id=? AND tenant_id=? AND principal_id=?",
            (session_id, tenant_id, principal_id),
        )
        .fetchone()
    )
    return dict(row) if row else None


def register_workspace(
    *, session_id: str, tenant_id: str, principal_id: str, run_id: str | None = None
) -> None:
    conn = get_connection()
    tx = JoinedTransaction(conn, "register_workspace")
    try:
        conn.execute(
            "INSERT INTO operator_workspaces(session_id,tenant_id,principal_id,run_id) VALUES(?,?,?,?)",
            (session_id, tenant_id, principal_id, run_id),
        )
        tx.commit()
    except Exception:
        tx.rollback()
        raise


def _verified(row, *, digest_field: str) -> dict:
    payload = json.loads(row["payload_json"])
    identity_fields = (
        ("proposal_id", "session_id", "tenant_id", "principal_id", "created_at")
        if digest_field == "proposal_digest"
        else ("receipt_id", "proposal_id", "session_id", "run_id", "created_at")
    )
    if (
        any(payload.get(field) != row[field] for field in identity_fields)
        or canonical_digest(payload) != row[digest_field]
    ):
        raise ValueError("Workspace decision integrity failed")
    if digest_field == "receipt_digest":
        proposal = get_proposal(
            proposal_id=payload["proposal_id"],
            session_id=payload["session_id"],
            tenant_id=payload.get("tenant_id"),
            principal_id=payload.get("principal_id"),
        )
        event = (
            get_connection()
            .execute(
                "SELECT agent_run_id, principal_id, anchors_json FROM agent_events WHERE id=?",
                (payload.get("event_id"),),
            )
            .fetchone()
        )
        anchors = json.loads(event["anchors_json"]) if event else {}
        if (
            not proposal
            or payload.get("proposal_digest") != proposal["proposal_digest"]
            or not event
            or event["agent_run_id"] != payload["run_id"]
            or event["principal_id"] != payload["principal_id"]
            or anchors
            != {
                "command": "create_run",
                "proposal_id": payload["proposal_id"],
                "proposal_digest": payload["proposal_digest"],
                "session_id": payload["session_id"],
            }
            or payload.get("acknowledgement") != "governed_run_created"
            or payload.get("objective_completed") is not False
        ):
            raise ValueError("Creation receipt evidence failed verification")
    return {**payload, digest_field: row[digest_field]}


def create_proposal(*, proposal: dict) -> dict:
    conn = get_connection()
    tx = JoinedTransaction(conn, "workspace_proposal")
    try:
        conn.execute(
            "INSERT INTO operator_run_creation_proposals VALUES(?,?,?,?,?,?,?)",
            (
                proposal["proposal_id"],
                proposal["session_id"],
                proposal["tenant_id"],
                proposal["principal_id"],
                canonical_digest(proposal),
                json.dumps(proposal),
                proposal["created_at"],
            ),
        )
        tx.commit()
    except Exception:
        tx.rollback()
        raise
    return {**proposal, "proposal_digest": canonical_digest(proposal)}


def get_proposal(
    *, proposal_id: str, session_id: str, tenant_id: str, principal_id: str
) -> dict | None:
    row = (
        get_connection()
        .execute(
            "SELECT * FROM operator_run_creation_proposals WHERE proposal_id=? AND session_id=? AND tenant_id=? AND principal_id=?",
            (proposal_id, session_id, tenant_id, principal_id),
        )
        .fetchone()
    )
    return _verified(row, digest_field="proposal_digest") if row else None


def history(*, session_id: str, tenant_id: str, principal_id: str) -> dict:
    if not get_workspace(
        session_id=session_id, tenant_id=tenant_id, principal_id=principal_id
    ):
        raise LookupError("Conversation not found")
    rows = (
        get_connection()
        .execute(
            "SELECT * FROM operator_run_creation_proposals WHERE session_id=? ORDER BY created_at DESC, proposal_id DESC LIMIT 101",
            (session_id,),
        )
        .fetchall()
    )
    receipt = (
        get_connection()
        .execute(
            "SELECT * FROM operator_run_creation_receipts WHERE session_id=?",
            (session_id,),
        )
        .fetchone()
    )
    verified_receipt = (
        _verified(receipt, digest_field="receipt_digest") if receipt else None
    )
    confirmed_proposal = (
        get_proposal(
            proposal_id=verified_receipt["proposal_id"],
            session_id=session_id,
            tenant_id=tenant_id,
            principal_id=principal_id,
        )
        if verified_receipt
        else None
    )
    return {
        "confirmed_proposal": confirmed_proposal,
        "proposals": [
            _verified(r, digest_field="proposal_digest") for r in reversed(rows[:100])
        ],
        "has_more": len(rows) > 100,
        "receipt": verified_receipt,
    }


def get_creation_for_run(*, run_id: str, tenant_id: str) -> dict | None:
    """Project immutable decisions for an already-authorized run reader."""
    row = (
        get_connection()
        .execute(
            "SELECT r.* FROM operator_run_creation_receipts r "
            "JOIN operator_workspaces w ON w.session_id=r.session_id "
            "WHERE r.run_id=? AND w.tenant_id=? AND w.run_id=r.run_id",
            (run_id, tenant_id),
        )
        .fetchone()
    )
    if not row:
        return None
    receipt = _verified(row, digest_field="receipt_digest")
    proposal = get_proposal(
        proposal_id=receipt["proposal_id"],
        session_id=receipt["session_id"],
        tenant_id=tenant_id,
        principal_id=receipt["principal_id"],
    )
    return {"proposal": proposal, "receipt": receipt}


def commit_creation(
    *,
    proposal: dict,
    authorize: Any,
    current_preflight: Any,
    create_run: Any,
    audit: Any,
) -> dict:
    conn = get_connection()
    if conn.in_transaction:
        raise ValueError("Run creation requires an owned transaction")
    tx = JoinedTransaction(conn, "workspace_creation")
    try:
        authorize()
        fresh = get_proposal(
            proposal_id=proposal["proposal_id"],
            session_id=proposal["session_id"],
            tenant_id=proposal["tenant_id"],
            principal_id=proposal["principal_id"],
        )
        if fresh != proposal:
            raise ValueError("Creation proposal changed")
        row = conn.execute(
            "SELECT * FROM operator_run_creation_receipts WHERE proposal_id=?",
            (proposal["proposal_id"],),
        ).fetchone()
        if row:
            result = {**_verified(row, digest_field="receipt_digest"), "replayed": True}
            tx.commit()
            return result
        workspace = get_workspace(
            session_id=proposal["session_id"],
            tenant_id=proposal["tenant_id"],
            principal_id=proposal["principal_id"],
        )
        if not workspace or workspace["run_id"]:
            raise ValueError("Conversation already bound or unavailable")
        if datetime.fromisoformat(proposal["expires_at"]) <= datetime.now(timezone.utc):
            raise ValueError("Creation proposal expired")
        if current_preflight() != proposal["preflight"]:
            raise ValueError("Creation scope or policy changed; refresh the proposal")
        run = create_run()
        if (
            not run
            or run["status"] != "planned"
            or run.get("completion_authority_required") is not True
        ):
            raise ValueError("Run creation did not establish governed planning")
        # Every nested adapter must have joined, never committed, this transaction.
        if not conn.in_transaction:
            raise ValueError("Creation writer committed outside the owning transaction")
        conn.execute(
            "UPDATE operator_workspaces SET run_id=? WHERE session_id=? AND run_id IS NULL",
            (run["id"], proposal["session_id"]),
        )
        conn.execute(
            "UPDATE sessions SET state_json=? WHERE id=?",
            (
                json.dumps(
                    {
                        "conversation_kind": "operator_run",
                        "workspace": True,
                        "run_id": run["id"],
                    }
                ),
                proposal["session_id"],
            ),
        )
        event = audit(run)
        receipt = {
            "contract": "workflow.operator-run-creation-receipt.v1",
            "receipt_id": str(uuid.uuid4()),
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "session_id": proposal["session_id"],
            "tenant_id": proposal["tenant_id"],
            "principal_id": proposal["principal_id"],
            "run_id": run["id"],
            "event_id": event["id"],
            "acknowledgement": "governed_run_created",
            "run_status": "planned",
            "objective_completed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        digest = canonical_digest(receipt)
        conn.execute(
            "INSERT INTO operator_run_creation_receipts VALUES(?,?,?,?,?,?,?)",
            (
                receipt["receipt_id"],
                proposal["proposal_id"],
                proposal["session_id"],
                run["id"],
                digest,
                json.dumps(receipt),
                receipt["created_at"],
            ),
        )
        tx.commit()
        return {**receipt, "receipt_digest": digest, "replayed": False}
    except Exception:
        tx.rollback()
        raise


def list_workspaces(*, tenant_id: str, principal_id: str) -> dict:
    rows = (
        get_connection()
        .execute(
            "SELECT w.*, (SELECT content FROM turns WHERE session_id=w.session_id ORDER BY id LIMIT 1) AS preview FROM operator_workspaces w WHERE tenant_id=? AND principal_id=? ORDER BY created_at DESC, session_id LIMIT 101",
            (tenant_id, principal_id),
        )
        .fetchall()
    )
    return {"conversations": [dict(r) for r in rows[:100]], "has_more": len(rows) > 100}
