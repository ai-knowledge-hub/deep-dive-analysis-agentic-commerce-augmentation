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
    principal_type: Optional[str] = None,
    principal_id: Optional[str] = None,
    tool_id: Optional[str] = None,
    skill_id: Optional[str] = None,
    effect_class: Optional[str] = None,
    trace_id: Optional[str] = None,
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
            principal_type,
            principal_id,
            tool_id,
            skill_id,
            effect_class,
            trace_id,
            note_text,
            is_policy_event,
            anchors_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?))
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
            principal_type,
            principal_id,
            tool_id,
            skill_id,
            effect_class,
            trace_id,
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
    status: Optional[str] = None,
    capability_name: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 500,
    before: Optional[Dict[str, str]] = None,
    after: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    filters = ["agent_run_id = ?"]
    params: list[Any] = [agent_run_id]
    if event_type and event_type not in {"all", ""}:
        if event_type == "policy":
            filters.append("is_policy_event = 1")
        elif event_type in {"failed", "executed"}:
            filters.append("status = ?")
            params.append(event_type)
    if status and status not in {"all", ""}:
        filters.append("status = ?")
        params.append(status)
    if capability_name and capability_name not in {"all", ""}:
        filters.append("capability_name = ?")
        params.append(capability_name)
    if since:
        filters.append("datetime(created_at) >= datetime(?)")
        params.append(since)
    if until:
        filters.append("datetime(created_at) <= datetime(?)")
        params.append(until)
    if before and before.get("created_at") and before.get("id"):
        filters.append("(created_at < ? OR (created_at = ? AND id < ?))")
        params.extend([before["created_at"], before["created_at"], before["id"]])
        order_clause = "ORDER BY created_at DESC, id DESC"
        should_reverse = True
    elif after and after.get("created_at") and after.get("id"):
        filters.append("(created_at > ? OR (created_at = ? AND id > ?))")
        params.extend([after["created_at"], after["created_at"], after["id"]])
        order_clause = "ORDER BY created_at ASC, id ASC"
        should_reverse = False
    else:
        # Default: latest slice for timeline bootstrap.
        order_clause = "ORDER BY created_at DESC, id DESC"
        should_reverse = True

    where_clause = " AND ".join(filters)
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT * FROM agent_events
            WHERE {where_clause}
            {order_clause}
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        .fetchall()
    )
    mapped = [_row(row) for row in rows]
    return list(reversed(mapped)) if should_reverse else mapped


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
        "principal_type": row["principal_type"]
        if "principal_type" in row.keys()
        else None,
        "principal_id": row["principal_id"] if "principal_id" in row.keys() else None,
        "tool_id": row["tool_id"] if "tool_id" in row.keys() else None,
        "skill_id": row["skill_id"] if "skill_id" in row.keys() else None,
        "effect_class": row["effect_class"] if "effect_class" in row.keys() else None,
        "trace_id": row["trace_id"] if "trace_id" in row.keys() else None,
        "note": row["note_text"],
        "is_policy_event": bool(row["is_policy_event"]),
        "anchors": from_json(row["anchors_json"], default={}),
        "timestamp": row["created_at"],
    }


__all__ = ["create_agent_event", "get_agent_event", "list_agent_events"]
