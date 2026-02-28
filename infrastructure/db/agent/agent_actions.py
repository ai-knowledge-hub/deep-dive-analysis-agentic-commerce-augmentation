from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def create_agent_action(
    *,
    agent_run_id: str,
    sequence: int,
    status: str,
    capability_name: str,
    capability_version: Optional[str],
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    inputs_hash: Optional[str],
    outputs_hash: Optional[str],
    rationale: Optional[str],
    confidence: Optional[float],
    snapshot_version: Optional[int],
    hypothesis_id: Optional[str],
    variant_id: Optional[str],
    validation_job_id: Optional[str],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    action_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO agent_actions (
            id,
            agent_run_id,
            sequence,
            status,
            capability_name,
            capability_version,
            inputs_json,
            outputs_json,
            inputs_hash,
            outputs_hash,
            rationale_text,
            confidence,
            snapshot_version,
            hypothesis_id,
            variant_id,
            validation_job_id,
            error_text
        )
        VALUES (?, ?, ?, ?, ?, ?, json(?), json(?), ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            agent_run_id,
            int(sequence),
            status,
            capability_name,
            capability_version,
            to_json(inputs) or to_json({}),
            to_json(outputs) or to_json({}),
            inputs_hash,
            outputs_hash,
            rationale,
            confidence,
            snapshot_version,
            hypothesis_id,
            variant_id,
            validation_job_id,
            error,
        ),
    )
    conn.commit()
    return get_agent_action(action_id) or {}


def update_agent_action_status(
    *,
    action_id: str,
    status: str,
    outputs: Optional[Dict[str, Any]] = None,
    outputs_hash: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any] | None:
    conn = get_connection()
    updates: list[str] = ["status = ?"]
    params: list[Any] = [status]
    if outputs is not None:
        updates.append("outputs_json = json(?)")
        params.append(to_json(outputs) or to_json({}))
    if outputs_hash is not None:
        updates.append("outputs_hash = ?")
        params.append(outputs_hash)
    if error is not None:
        updates.append("error_text = ?")
        params.append(error)
    updates.append("updated_at = datetime('now')")
    params.append(action_id)
    conn.execute(
        f"""
        UPDATE agent_actions
        SET {", ".join(updates)}
        WHERE id = ?
        """,
        params,
    )
    conn.commit()
    return get_agent_action(action_id)


def transition_agent_action_status(
    *,
    action_id: str,
    from_status: str,
    to_status: str,
) -> Dict[str, Any] | None:
    conn = get_connection()
    cursor = conn.execute(
        """
        UPDATE agent_actions
        SET status = ?, updated_at = datetime('now')
        WHERE id = ? AND status = ?
        """,
        (to_status, action_id, from_status),
    )
    conn.commit()
    if not cursor.rowcount:
        return None
    return get_agent_action(action_id)


def get_agent_action(
    action_id: str, *, client_id: Optional[str] = None
) -> Dict[str, Any] | None:
    conn = get_connection()
    if client_id:
        row = conn.execute(
            """
            SELECT a.*
            FROM agent_actions a
            JOIN agent_runs r ON r.id = a.agent_run_id
            WHERE a.id = ? AND r.client_id = ?
            """,
            (action_id, client_id),
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM agent_actions WHERE id = ?", (action_id,)).fetchone()
    return _row(row) if row else None


def list_agent_actions(
    *,
    agent_run_id: str,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    filters: list[str] = ["agent_run_id = ?"]
    params: list[Any] = [agent_run_id]
    if status:
        filters.append("status = ?")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(filters)}"
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT * FROM agent_actions
            {where_clause}
            ORDER BY sequence ASC
            LIMIT ?
            """,
            (*params, limit),
        )
        .fetchall()
    )
    return [_row(r) for r in rows]


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "agent_run_id": row["agent_run_id"],
        "sequence": int(row["sequence"]),
        "status": row["status"],
        "capability_name": row["capability_name"],
        "capability_version": row["capability_version"],
        "inputs": from_json(row["inputs_json"], default={}),
        "outputs": from_json(row["outputs_json"], default={}),
        "inputs_hash": row["inputs_hash"],
        "outputs_hash": row["outputs_hash"],
        "rationale": row["rationale_text"],
        "confidence": row["confidence"],
        "snapshot_version": int(row["snapshot_version"])
        if row["snapshot_version"] is not None
        else None,
        "hypothesis_id": row["hypothesis_id"],
        "variant_id": row["variant_id"],
        "validation_job_id": row["validation_job_id"],
        "error": row["error_text"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_agent_action",
    "update_agent_action_status",
    "transition_agent_action_status",
    "get_agent_action",
    "list_agent_actions",
]
