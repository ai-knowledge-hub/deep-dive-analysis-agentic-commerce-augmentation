from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def create_agent_event(
    *,
    agent_run_id: str,
    action_id: Optional[str],
    sequence: int,
    event_type: str,
    status: str,
    capability_name: Optional[str] = None,
    capability_version: Optional[str] = None,
    note: Optional[str] = None,
    is_policy_event: bool = False,
    anchors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO agent_events (
            id,
            agent_run_id,
            action_id,
            sequence,
            event_type,
            status,
            capability_name,
            capability_version,
            note_text,
            is_policy_event,
            anchors_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            event_id,
            agent_run_id,
            action_id,
            int(sequence),
            event_type,
            status,
            capability_name,
            capability_version,
            note,
            1 if is_policy_event else 0,
            to_json(anchors or {}) or to_json({}),
        ),
    )
    conn.commit()
    return get_agent_event(event_id) or {}


def get_agent_event(event_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM agent_events WHERE id = ?", (event_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_agent_events(
    *,
    agent_run_id: str,
    event_type: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    filters = ["agent_run_id = ?"]
    params: list[Any] = [agent_run_id]
    if event_type and event_type not in {"all", ""}:
        if event_type == "policy":
            filters.append("is_policy_event = 1")
        elif event_type in {"failed", "executed"}:
            filters.append("status = ?")
            params.append(event_type)
    where_clause = " AND ".join(filters)
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT * FROM agent_events
            WHERE {where_clause}
            ORDER BY created_at ASC, sequence ASC
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        .fetchall()
    )
    return [_row(row) for row in rows]


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["agent_run_id"],
        "action_id": row["action_id"],
        "sequence": int(row["sequence"]),
        "event_type": row["event_type"],
        "status": row["status"],
        "capability_name": row["capability_name"],
        "capability_version": row["capability_version"],
        "note": row["note_text"],
        "is_policy_event": bool(row["is_policy_event"]),
        "anchors": from_json(row["anchors_json"], default={}),
        "timestamp": row["created_at"],
    }


__all__ = ["create_agent_event", "get_agent_event", "list_agent_events"]
