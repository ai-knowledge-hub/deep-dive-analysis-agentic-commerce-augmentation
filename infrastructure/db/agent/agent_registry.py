from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def ensure_agent_registry_version(
    *,
    registry_version: str,
    registry_fingerprint: str,
    payload: Dict[str, Any],
    hash_algorithm: str = "sha256",
    source: str = "static_code",
    status: str = "active",
) -> Dict[str, Any]:
    conn = get_connection()
    release_status = status or "active"
    active_before = get_active_agent_registry_version()
    conn.execute(
        """
        INSERT OR IGNORE INTO agent_registry_versions (
            id,
            registry_version,
            registry_fingerprint,
            hash_algorithm,
            source,
            payload_json,
            status
        )
        VALUES (?, ?, ?, ?, ?, json(?), ?)
        """,
        (
            registry_fingerprint,
            registry_version,
            registry_fingerprint,
            hash_algorithm,
            source,
            to_json(payload) or to_json({}),
            release_status,
        ),
    )
    conn.execute(
        """
        UPDATE agent_registry_versions
        SET
            registry_version = ?,
            hash_algorithm = ?,
            source = ?,
            payload_json = json(?),
            status = ?
        WHERE registry_fingerprint = ?
        """,
        (
            registry_version,
            hash_algorithm,
            source,
            to_json(payload) or to_json({}),
            release_status,
            registry_fingerprint,
        ),
    )
    if (
        release_status == "active"
        and active_before
        and active_before["registry_fingerprint"] != registry_fingerprint
    ):
        conn.execute(
            """
            UPDATE agent_registry_versions
            SET status = 'retired'
            WHERE status = 'active' AND registry_fingerprint != ?
            """,
            (registry_fingerprint,),
        )
        _create_registry_transition_event(
            previous=active_before,
            registry_version=registry_version,
            registry_fingerprint=registry_fingerprint,
            payload=payload,
            source=source,
        )
    conn.commit()
    return get_agent_registry_version(registry_fingerprint=registry_fingerprint) or {}


def get_agent_registry_version(
    *, registry_fingerprint: str
) -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_registry_versions
            WHERE registry_fingerprint = ?
            """,
            (registry_fingerprint,),
        )
        .fetchone()
    )
    return _row(row) if row else None


def get_latest_agent_registry_version() -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_registry_versions
            ORDER BY created_at DESC, registry_fingerprint ASC
            LIMIT 1
            """
        )
        .fetchone()
    )
    return _row(row) if row else None


def get_active_agent_registry_version() -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_registry_versions
            WHERE status = 'active'
            ORDER BY created_at DESC, registry_fingerprint ASC
            LIMIT 1
            """
        )
        .fetchone()
    )
    return _row(row) if row else None


def list_agent_registry_versions(
    *, status: Optional[str] = None, limit: int = 20
) -> list[Dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if status:
        filters.append("status = ?")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT *
            FROM agent_registry_versions
            {where_clause}
            ORDER BY
                CASE status WHEN 'active' THEN 0 ELSE 1 END,
                created_at DESC,
                registry_fingerprint ASC
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        .fetchall()
    )
    return [_release_row(row) for row in rows]


def list_agent_registry_audit_events(
    *, registry_fingerprint: Optional[str] = None, limit: int = 50
) -> list[Dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if registry_fingerprint:
        filters.append("registry_fingerprint = ?")
        params.append(registry_fingerprint)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT *
            FROM agent_registry_audit_events
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        .fetchall()
    )
    return [_audit_row(row) for row in rows]


def create_agent_registry_audit_event(
    *,
    event_type: str,
    registry_fingerprint: str,
    registry_version: str,
    diff: Dict[str, Any],
    previous_registry_fingerprint: Optional[str] = None,
    source: str = "system",
) -> Dict[str, Any]:
    event_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO agent_registry_audit_events (
            id,
            event_type,
            previous_registry_fingerprint,
            registry_fingerprint,
            registry_version,
            source,
            diff_json
        )
        VALUES (?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            event_id,
            event_type,
            previous_registry_fingerprint,
            registry_fingerprint,
            registry_version,
            source,
            to_json(diff) or to_json({}),
        ),
    )
    conn.commit()
    row = (
        conn.execute(
            "SELECT * FROM agent_registry_audit_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    )
    return _audit_row(row) if row else {}


def _create_registry_transition_event(
    *,
    previous: Dict[str, Any],
    registry_version: str,
    registry_fingerprint: str,
    payload: Dict[str, Any],
    source: str,
) -> None:
    get_connection().execute(
        """
        INSERT OR IGNORE INTO agent_registry_audit_events (
            id,
            event_type,
            previous_registry_fingerprint,
            registry_fingerprint,
            registry_version,
            source,
            diff_json
        )
        VALUES (?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            str(uuid.uuid4()),
            "registry_changed",
            previous["registry_fingerprint"],
            registry_fingerprint,
            registry_version,
            source,
            to_json(_diff_registry_payload(previous.get("payload") or {}, payload))
            or to_json({}),
        ),
    )


def _diff_registry_payload(
    previous: Dict[str, Any], current: Dict[str, Any]
) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    for key in ("skills", "tools", "capabilities", "policy_profiles"):
        previous_items = _items_by_identity(previous.get(key))
        current_items = _items_by_identity(current.get(key))
        previous_ids = set(previous_items)
        current_ids = set(current_items)
        changed = sorted(
            item_id
            for item_id in previous_ids & current_ids
            if _canonical(previous_items[item_id]) != _canonical(current_items[item_id])
        )
        diff[key] = {
            "added": sorted(current_ids - previous_ids),
            "removed": sorted(previous_ids - current_ids),
            "changed": changed,
        }
    diff["skill_ids_by_tool_changed"] = _canonical(
        previous.get("skill_ids_by_tool") or {}
    ) != _canonical(current.get("skill_ids_by_tool") or {})
    return diff


def _items_by_identity(value: Any) -> Dict[str, Any]:
    if not isinstance(value, list):
        return {}
    items: Dict[str, Any] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        identity = item.get("id") or item.get("name")
        if identity:
            items[str(identity)] = item
    return items


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "registry_version": row["registry_version"],
        "registry_fingerprint": row["registry_fingerprint"],
        "hash_algorithm": row["hash_algorithm"],
        "source": row["source"],
        "payload": from_json(row["payload_json"], {}),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _audit_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "event_type": row["event_type"],
        "previous_registry_fingerprint": row["previous_registry_fingerprint"],
        "registry_fingerprint": row["registry_fingerprint"],
        "registry_version": row["registry_version"],
        "source": row["source"],
        "diff": from_json(row["diff_json"], {}),
        "created_at": row["created_at"],
    }


def _release_row(row) -> Dict[str, Any]:
    payload = from_json(row["payload_json"], {})
    return {
        "id": row["id"],
        "registry_version": row["registry_version"],
        "registry_fingerprint": row["registry_fingerprint"],
        "hash_algorithm": row["hash_algorithm"],
        "source": row["source"],
        "status": row["status"],
        "created_at": row["created_at"],
        "counts": {
            "skills": len(payload.get("skills") or []),
            "tools": len(payload.get("tools") or []),
            "capabilities": len(payload.get("capabilities") or []),
            "policy_profiles": len(payload.get("policy_profiles") or []),
        },
    }


__all__ = [
    "create_agent_registry_audit_event",
    "ensure_agent_registry_version",
    "get_active_agent_registry_version",
    "get_agent_registry_version",
    "get_latest_agent_registry_version",
    "list_agent_registry_audit_events",
    "list_agent_registry_versions",
]
