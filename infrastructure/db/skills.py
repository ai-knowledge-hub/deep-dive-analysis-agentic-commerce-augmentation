from __future__ import annotations

from typing import Any, Dict, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json


def get_skill(*, name: str, include_disabled: bool = False) -> Dict[str, Any] | None:
    if include_disabled:
        row = (
            get_connection()
            .execute("SELECT * FROM skills WHERE name = ?", (name,))
            .fetchone()
        )
    else:
        row = (
            get_connection()
            .execute("SELECT * FROM skills WHERE name = ? AND enabled = 1", (name,))
            .fetchone()
        )
    return _row(row) if row else None


def upsert_skill(
    *,
    skill_id: str,
    name: str,
    description: str,
    version: str,
    content: str,
    enabled: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO skills (id, name, description, version, content, enabled, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            version = excluded.version,
            content = excluded.content,
            enabled = excluded.enabled,
            metadata_json = excluded.metadata_json,
            updated_at = datetime('now')
        """,
        (
            skill_id,
            name,
            description,
            version,
            content,
            1 if enabled else 0,
            to_json(metadata or {}) or to_json({}),
        ),
    )
    conn.commit()
    stored = get_skill(name=name, include_disabled=True) or {}
    if stored:
        _insert_history(conn, stored)
    return stored


def list_skill_history(*, name: str, limit: int = 25) -> list[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT h.* FROM skills_history h
            JOIN skills s ON s.id = h.skill_id
            WHERE s.name = ?
            ORDER BY h.id DESC
            LIMIT ?
            """,
            (name, limit),
        )
        .fetchall()
    )
    return [_history_row(row) for row in rows]


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "version": row["version"],
        "content": row["content"],
        "enabled": bool(row["enabled"]),
        "metadata": from_json(row["metadata_json"], default={}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _history_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "skill_id": row["skill_id"],
        "name": row["name"],
        "description": row["description"],
        "version": row["version"],
        "content": row["content"],
        "enabled": bool(row["enabled"]),
        "metadata": from_json(row["metadata_json"], default={}),
        "changed_at": row["changed_at"],
    }


def _insert_history(conn, stored: Dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO skills_history (
            skill_id, name, description, version, content, enabled, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            stored["id"],
            stored["name"],
            stored.get("description"),
            stored.get("version"),
            stored.get("content"),
            1 if stored.get("enabled") else 0,
            to_json(stored.get("metadata") or {}) or to_json({}),
        ),
    )
    conn.commit()


__all__ = ["get_skill", "upsert_skill", "list_skill_history"]
