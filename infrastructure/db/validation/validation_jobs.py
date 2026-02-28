from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


def create_job(
    *,
    client_id: str,
    brand_id: Optional[str],
    product_id: Optional[str],
    entity_type: str,
    entity_id: str,
    provider: str,
    mode: str,
    model: Optional[str],
    prompt_version: Optional[str],
    status: str,
    integration_type: Optional[str] = None,
    provider_run_id: Optional[str] = None,
    callback_verified: Optional[bool] = None,
    input_payload: Dict[str, Any],
    requested_by: Optional[str],
) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO validation_jobs (
            id,
            client_id,
            brand_id,
            product_id,
            entity_type,
            entity_id,
            provider,
            mode,
            model,
            prompt_version,
            status,
            integration_type,
            provider_run_id,
            callback_verified,
            input_payload_json,
            requested_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?), ?)
        """,
        (
            job_id,
            client_id,
            brand_id,
            product_id,
            entity_type,
            entity_id,
            provider,
            mode,
            model,
            prompt_version,
            status,
            integration_type,
            provider_run_id,
            None if callback_verified is None else (1 if callback_verified else 0),
            to_json(input_payload) or to_json({}),
            requested_by,
        ),
    )
    conn.commit()
    return get_job(job_id) or {}


def update_job_status(
    *,
    job_id: str,
    status: str,
    client_id: Optional[str] = None,
    model: Optional[str] = None,
    provider_run_id: Optional[str] = None,
    callback_verified: Optional[bool] = None,
) -> Dict[str, Any] | None:
    conn = get_connection()
    updates: list[str] = ["status = ?"]
    params: list[Any] = [status]
    if model is not None:
        updates.append("model = ?")
        params.append(model)
    if provider_run_id is not None:
        updates.append("provider_run_id = ?")
        params.append(provider_run_id)
    if callback_verified is not None:
        updates.append("callback_verified = ?")
        params.append(1 if callback_verified else 0)
    updates.append("updated_at = datetime('now')")
    params.append(job_id)
    where_clause = "WHERE id = ?"
    if client_id:
        where_clause += " AND client_id = ?"
        params.append(client_id)
    conn.execute(
        f"""
        UPDATE validation_jobs
        SET {", ".join(updates)}
        {where_clause}
        """,
        params,
    )
    conn.commit()
    return get_job(job_id, client_id=client_id)


def get_job(job_id: str, *, client_id: Optional[str] = None) -> Dict[str, Any] | None:
    conn = get_connection()
    if client_id:
        row = conn.execute(
            "SELECT * FROM validation_jobs WHERE id = ? AND client_id = ?",
            (job_id, client_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM validation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return _row(row) if row else None


def list_jobs(
    *,
    client_id: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    conn = get_connection()
    filters: list[str] = ["client_id = ?"]
    params: list[Any] = [client_id]
    if entity_type:
        filters.append("entity_type = ?")
        params.append(entity_type)
    if entity_id:
        filters.append("entity_id = ?")
        params.append(entity_id)
    where_clause = f"WHERE {' AND '.join(filters)}"
    rows = conn.execute(
        f"""
        SELECT * FROM validation_jobs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_row(row) for row in rows]


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "provider": row["provider"],
        "mode": row["mode"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "status": row["status"],
        "integration_type": row["integration_type"],
        "provider_run_id": row["provider_run_id"],
        "callback_verified": bool(row["callback_verified"]) if row["callback_verified"] is not None else None,
        "input_payload": from_json(row["input_payload_json"], default={}),
        "requested_by": row["requested_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_job",
    "update_job_status",
    "get_job",
    "list_jobs",
]
