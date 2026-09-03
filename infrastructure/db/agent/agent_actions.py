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
    tool_id: Optional[str] = None,
    skill_id: Optional[str] = None,
    registry_version: Optional[str] = None,
    registry_fingerprint: Optional[str] = None,
    tool_version: Optional[str] = None,
    skill_version: Optional[str] = None,
    effect_class: Optional[str] = None,
    side_effects: Optional[List[str]] = None,
    rollback_guidance: Optional[str] = None,
    compensating_actions: Optional[List[Dict[str, Any]]] = None,
    receipt_id: Optional[str] = None,
    retry_count: int = 0,
    dedupe_key: Optional[str] = None,
    error: Optional[str] = None,
    client_id: Optional[str] = None,
    admissible_run_statuses: tuple[str, ...] | None = None,
) -> Dict[str, Any]:
    action_id = str(uuid.uuid4())
    conn = get_connection()
    guarded = admissible_run_statuses is not None
    try:
        if guarded:
            if not client_id:
                raise ValueError("client_id is required for guarded action creation")
            conn.execute("BEGIN IMMEDIATE")
            run_row = conn.execute(
                "SELECT status FROM agent_runs WHERE id = ? AND client_id = ?",
                (agent_run_id, client_id),
            ).fetchone()
            allowed = {item.strip().lower() for item in admissible_run_statuses}
            current_status = (
                str(run_row["status"] or "").strip().lower() if run_row else ""
            )
            if current_status not in allowed:
                conn.rollback()
                return {}
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
                tool_id,
                skill_id,
                registry_version,
                registry_fingerprint,
                tool_version,
                skill_version,
                effect_class,
                side_effects_json,
                rollback_guidance,
                compensating_actions_json,
                receipt_id,
                retry_count,
                dedupe_key,
                error_text
            )
            VALUES (?, ?, ?, ?, ?, ?, json(?), json(?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?), ?, json(?), ?, ?, ?, ?)
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
                tool_id,
                skill_id,
                registry_version,
                registry_fingerprint,
                tool_version,
                skill_version,
                effect_class,
                to_json(side_effects or []) or to_json([]),
                rollback_guidance,
                to_json(compensating_actions or []) or to_json([]),
                receipt_id,
                int(retry_count),
                dedupe_key,
                error,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
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
        row = conn.execute(
            "SELECT * FROM agent_actions WHERE id = ?", (action_id,)
        ).fetchone()
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


def list_agent_actions_missing_registry_pins(
    *, client_id: str, limit: int = 200
) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT a.*
            FROM agent_actions a
            JOIN agent_runs r ON r.id = a.agent_run_id
            WHERE r.client_id = ?
              AND (
                  a.registry_version IS NULL
                  OR a.registry_fingerprint IS NULL
                  OR a.tool_version IS NULL
                  OR a.skill_version IS NULL
                  OR a.tool_id IS NULL
                  OR a.skill_id IS NULL
              )
            ORDER BY r.created_at ASC, a.sequence ASC
            LIMIT ?
            """,
            (client_id, int(limit)),
        )
        .fetchall()
    )
    return [_row(r) for r in rows]


def update_agent_action_registry_pins(
    *,
    action_id: str,
    tool_id: Optional[str],
    skill_id: Optional[str],
    registry_version: str,
    registry_fingerprint: str,
    tool_version: Optional[str],
    skill_version: Optional[str],
) -> Dict[str, Any] | None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_actions
        SET
            tool_id = ?,
            skill_id = ?,
            registry_version = ?,
            registry_fingerprint = ?,
            tool_version = ?,
            skill_version = ?,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            tool_id,
            skill_id,
            registry_version,
            registry_fingerprint,
            tool_version,
            skill_version,
            action_id,
        ),
    )
    conn.commit()
    return get_agent_action(action_id)


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
        "tool_id": row["tool_id"] if "tool_id" in row.keys() else None,
        "skill_id": row["skill_id"] if "skill_id" in row.keys() else None,
        "registry_version": row["registry_version"]
        if "registry_version" in row.keys()
        else None,
        "registry_fingerprint": row["registry_fingerprint"]
        if "registry_fingerprint" in row.keys()
        else None,
        "tool_version": row["tool_version"] if "tool_version" in row.keys() else None,
        "skill_version": row["skill_version"]
        if "skill_version" in row.keys()
        else None,
        "effect_class": row["effect_class"] if "effect_class" in row.keys() else None,
        "side_effects": from_json(row["side_effects_json"], default=[])
        if "side_effects_json" in row.keys()
        else [],
        "rollback_guidance": row["rollback_guidance"]
        if "rollback_guidance" in row.keys()
        else None,
        "compensating_actions": from_json(row["compensating_actions_json"], default=[])
        if "compensating_actions_json" in row.keys()
        else [],
        "receipt_id": row["receipt_id"] if "receipt_id" in row.keys() else None,
        "retry_count": int(row["retry_count"] or 0)
        if "retry_count" in row.keys()
        else 0,
        "dedupe_key": row["dedupe_key"] if "dedupe_key" in row.keys() else None,
        "approval_id": row["approval_id"] if "approval_id" in row.keys() else None,
        "approval_envelope_digest": row["approval_envelope_digest"]
        if "approval_envelope_digest" in row.keys()
        else None,
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
    "list_agent_actions_missing_registry_pins",
    "update_agent_action_registry_pins",
]
