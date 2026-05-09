from __future__ import annotations

import sqlite3
import uuid
from typing import Any, Dict, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


def create_external_agent_job(
    *,
    client_id: str,
    principal_id: str,
    agent_profile_id: Optional[str],
    idempotency_key: str,
    request_hash: str,
    run_id: str,
    requested_skill_id: Optional[str],
    requested_tool_id: Optional[str],
    status: str,
    trace_id: Optional[str],
    request: Dict[str, Any],
    response: Dict[str, Any],
) -> Dict[str, Any]:
    ensure_client(client_id)
    job_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO external_agent_jobs (
                id,
                client_id,
                principal_id,
                agent_profile_id,
                idempotency_key,
                request_hash,
                run_id,
                requested_skill_id,
                requested_tool_id,
                status,
                trace_id,
                request_json,
                response_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?), json(?))
            """,
            (
                job_id,
                client_id,
                principal_id,
                agent_profile_id,
                idempotency_key,
                request_hash,
                run_id,
                requested_skill_id,
                requested_tool_id,
                status,
                trace_id,
                to_json(request) or to_json({}),
                to_json(response) or to_json({}),
            ),
        )
        conn.commit()
        return get_external_agent_job(job_id=job_id, client_id=client_id) or {}
    except sqlite3.IntegrityError:
        conn.rollback()
        existing = get_external_agent_job_by_idempotency_key(
            client_id=client_id,
            principal_id=principal_id,
            idempotency_key=idempotency_key,
        )
        if existing:
            return existing
        raise


def get_external_agent_job(
    *, job_id: str, client_id: Optional[str] = None, principal_id: Optional[str] = None
) -> Dict[str, Any] | None:
    filters = ["id = ?"]
    params: list[Any] = [job_id]
    if client_id:
        filters.append("client_id = ?")
        params.append(client_id)
    if principal_id:
        filters.append("principal_id = ?")
        params.append(principal_id)
    row = get_connection().execute(
        f"SELECT * FROM external_agent_jobs WHERE {' AND '.join(filters)}", params
    ).fetchone()
    return _row(row) if row else None


def get_external_agent_job_by_idempotency_key(
    *, client_id: str, principal_id: str, idempotency_key: str
) -> Dict[str, Any] | None:
    row = get_connection().execute(
        """
        SELECT *
        FROM external_agent_jobs
        WHERE client_id = ? AND principal_id = ? AND idempotency_key = ?
        """,
        (client_id, principal_id, idempotency_key),
    ).fetchone()
    return _row(row) if row else None


def update_external_agent_job_status(
    *, job_id: str, status: str, response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any] | None:
    conn = get_connection()
    if response is None:
        conn.execute(
            """
            UPDATE external_agent_jobs
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, job_id),
        )
    else:
        conn.execute(
            """
            UPDATE external_agent_jobs
            SET status = ?, response_json = json(?), updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, to_json(response) or to_json({}), job_id),
        )
    conn.commit()
    return get_external_agent_job(job_id=job_id)


def update_external_agent_job_receipt(
    *,
    job_id: str,
    receipt_id: str,
    receipt_type: str,
    receipt_signature: str,
    receipt_signature_algorithm: str,
    receipt_payload: Dict[str, Any],
) -> Dict[str, Any] | None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE external_agent_jobs
        SET
            receipt_id = ?,
            receipt_type = ?,
            receipt_signature = ?,
            receipt_signature_algorithm = ?,
            receipt_payload_json = json(?),
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            receipt_id,
            receipt_type,
            receipt_signature,
            receipt_signature_algorithm,
            to_json(receipt_payload) or to_json({}),
            job_id,
        ),
    )
    conn.commit()
    return get_external_agent_job(job_id=job_id)


def create_external_agent_job_receipt(
    *,
    receipt_id: str,
    job_id: str,
    client_id: str,
    principal_id: str,
    run_id: str,
    receipt_type: str,
    status: str,
    receipt_context_hash: str,
    signature: str,
    signature_algorithm: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO external_agent_job_receipts (
                id,
                job_id,
                client_id,
                principal_id,
                run_id,
                receipt_type,
                status,
                receipt_context_hash,
                signature,
                signature_algorithm,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?))
            """,
            (
                receipt_id,
                job_id,
                client_id,
                principal_id,
                run_id,
                receipt_type,
                status,
                receipt_context_hash,
                signature,
                signature_algorithm,
                to_json(payload) or to_json({}),
            ),
        )
        conn.commit()
        return get_external_agent_job_receipt(
            receipt_id=receipt_id, client_id=client_id, principal_id=principal_id
        ) or {}
    except sqlite3.IntegrityError:
        conn.rollback()
        existing = get_external_agent_job_receipt_for_context_hash(
            job_id=job_id,
            client_id=client_id,
            principal_id=principal_id,
            status=status,
            receipt_context_hash=receipt_context_hash,
        )
        if existing:
            return existing
        raise


def list_external_agent_job_receipts(
    *,
    job_id: str,
    client_id: str,
    principal_id: str,
    limit: int = 50,
) -> list[Dict[str, Any]]:
    rows = get_connection().execute(
        """
        SELECT *
        FROM external_agent_job_receipts
        WHERE job_id = ? AND client_id = ? AND principal_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (job_id, client_id, principal_id, max(1, min(int(limit), 200))),
    ).fetchall()
    return [_receipt_row(row) for row in rows]


def get_external_agent_job_receipt(
    *,
    receipt_id: str,
    client_id: Optional[str] = None,
    principal_id: Optional[str] = None,
) -> Dict[str, Any] | None:
    filters = ["id = ?"]
    params: list[Any] = [receipt_id]
    if client_id:
        filters.append("client_id = ?")
        params.append(client_id)
    if principal_id:
        filters.append("principal_id = ?")
        params.append(principal_id)
    row = get_connection().execute(
        f"""
        SELECT *
        FROM external_agent_job_receipts
        WHERE {' AND '.join(filters)}
        """,
        params,
    ).fetchone()
    return _receipt_row(row) if row else None


def get_external_agent_job_receipt_for_status(
    *, job_id: str, client_id: str, principal_id: str, status: str
) -> Dict[str, Any] | None:
    row = get_connection().execute(
        """
        SELECT *
        FROM external_agent_job_receipts
        WHERE job_id = ? AND client_id = ? AND principal_id = ? AND status = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (job_id, client_id, principal_id, status),
    ).fetchone()
    return _receipt_row(row) if row else None


def get_external_agent_job_receipt_for_context_hash(
    *,
    job_id: str,
    client_id: str,
    principal_id: str,
    status: str,
    receipt_context_hash: str,
) -> Dict[str, Any] | None:
    row = get_connection().execute(
        """
        SELECT *
        FROM external_agent_job_receipts
        WHERE job_id = ?
          AND client_id = ?
          AND principal_id = ?
          AND status = ?
          AND receipt_context_hash = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (job_id, client_id, principal_id, status, receipt_context_hash),
    ).fetchone()
    return _receipt_row(row) if row else None


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "principal_id": row["principal_id"],
        "agent_profile_id": row["agent_profile_id"],
        "idempotency_key": row["idempotency_key"],
        "request_hash": row["request_hash"],
        "run_id": row["run_id"],
        "requested_skill_id": row["requested_skill_id"],
        "requested_tool_id": row["requested_tool_id"],
        "status": row["status"],
        "trace_id": row["trace_id"],
        "receipt_id": row["receipt_id"] if "receipt_id" in row.keys() else None,
        "receipt_type": row["receipt_type"] if "receipt_type" in row.keys() else None,
        "receipt_signature": row["receipt_signature"]
        if "receipt_signature" in row.keys()
        else None,
        "receipt_signature_algorithm": row["receipt_signature_algorithm"]
        if "receipt_signature_algorithm" in row.keys()
        else None,
        "receipt_payload": from_json(
            row["receipt_payload_json"]
            if "receipt_payload_json" in row.keys()
            else None,
            default={},
        ),
        "request": from_json(row["request_json"], default={}),
        "response": from_json(row["response_json"], default={}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _receipt_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "client_id": row["client_id"],
        "principal_id": row["principal_id"],
        "run_id": row["run_id"],
        "receipt_type": row["receipt_type"],
        "status": row["status"],
        "receipt_context_hash": row["receipt_context_hash"]
        if "receipt_context_hash" in row.keys()
        else None,
        "signature": row["signature"],
        "signature_algorithm": row["signature_algorithm"],
        "payload": from_json(row["payload_json"], default={}),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_external_agent_job_receipt",
    "create_external_agent_job",
    "get_external_agent_job",
    "get_external_agent_job_by_idempotency_key",
    "get_external_agent_job_receipt",
    "get_external_agent_job_receipt_for_context_hash",
    "get_external_agent_job_receipt_for_status",
    "list_external_agent_job_receipts",
    "update_external_agent_job_receipt",
    "update_external_agent_job_status",
]
